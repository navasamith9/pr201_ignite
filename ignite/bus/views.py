import base64
import io
import uuid
from datetime import datetime

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core import signing
from django.db import transaction
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from payments.models import Payment

from .forms import BusScheduleForm
from .models import BusSchedule, TicketBooking


def _parse_travel_date(value):
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= timezone.localdate() else None


def _account_ticket_total(user, travel_date):
    return TicketBooking.objects.filter(
        user=user,
        travel_date=travel_date,
        status=TicketBooking.STATUS_PAID,
    ).aggregate(total=Sum('quantity'))['total'] or 0


def is_bus_admin(user):
    """Allow global administrators and Bus-only administrators."""
    return bool(
        user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
            or getattr(user, 'role', None) == 'admin'
            or user.is_bus_admin
        )
    )


@login_required
def dashboard(request):
    return render(request, 'bus/dashboard.html', {'is_bus_admin': is_bus_admin(request.user)})


@user_passes_test(is_bus_admin)
def add_bus(request):
    if request.method == 'POST':
        form = BusScheduleForm(request.POST)
        if form.is_valid():
            bus = form.save()
            messages.success(request, f'{bus.name} was added to the bus schedule.')
            return redirect('bus:dashboard')
    else:
        form = BusScheduleForm()

    return render(request, 'bus/add_bus.html', {'form': form})


@login_required
def book_ticket(request):
    selected_date = request.POST.get('travel_date') or request.GET.get('travel_date')
    selected_route = request.POST.get('route') or request.GET.get('route')
    available_buses = []
    error = None
    travel_date = None

    if selected_date or selected_route:
        travel_date = _parse_travel_date(selected_date)
        if not travel_date:
            error = 'Choose today or a future date.'
        elif selected_route not in dict(BusSchedule.ROUTE_CHOICES):
            error = 'Choose a valid route.'
        else:
            weekday = travel_date.strftime('%a').lower()[:3]
            buses = BusSchedule.objects.filter(day=weekday, route=selected_route, active=True)
            available_buses = [(bus, bus.available_seats(travel_date)) for bus in buses]
            available_buses = [(bus, seats) for bus, seats in available_buses if seats > 0]
            if not available_buses:
                error = 'No seats are available for that route and date.'

    return render(request, 'bus/book_ticket.html', {
        'selected_date': selected_date,
        'selected_route': selected_route,
        'available_buses': available_buses,
        'route_choices': BusSchedule.ROUTE_CHOICES,
        'error': error,
        'travel_date': travel_date,
        'today': timezone.localdate().isoformat(),
    })


@login_required
def checkout(request):
    if request.method == 'POST':
        travel_date = _parse_travel_date(request.POST.get('travel_date'))
        try:
            bus_id = int(request.POST.get('bus_id', ''))
            quantity = int(request.POST.get('quantity', ''))
        except (TypeError, ValueError):
            messages.error(request, 'Select a valid bus and ticket quantity.')
            return redirect('bus:book_ticket')

        if not travel_date:
            messages.error(request, 'Travel date must be today or later.')
            return redirect('bus:book_ticket')

        with transaction.atomic():
            # Locking prevents two checkout requests from creating invalid orders.
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            bus = get_object_or_404(BusSchedule.objects.select_for_update(), pk=bus_id, active=True)
            if bus.day != travel_date.strftime('%a').lower()[:3]:
                messages.error(request, 'This bus does not operate on the selected date.')
                return redirect('bus:book_ticket')

            seats_left = bus.available_seats(travel_date)
            user_remaining = max(0, 2 - _account_ticket_total(request.user, travel_date))
            allowed_quantity = min(2, seats_left, user_remaining)
            if quantity < 1 or quantity > allowed_quantity:
                messages.error(request, 'Only available seats may be booked, up to two tickets per account for a travel date.')
                return redirect('bus:book_ticket')

            booking = TicketBooking.objects.create(
                user=request.user,
                bus=bus,
                travel_date=travel_date,
                quantity=quantity,
                route=bus.route,
            )
            payment = Payment.objects.create(
                user=request.user,
                content_object=booking,
                amount_paise=bus.price * quantity * 100,
            )

        return render(request, 'bus/checkout.html', {
            'booking': booking,
            'payment': payment,
            'bus': bus,
            'razorpay_key': settings.RAZORPAY_KEY_ID,
        })

    travel_date = _parse_travel_date(request.GET.get('travel_date'))
    try:
        bus_id = int(request.GET.get('bus_id', ''))
    except (TypeError, ValueError):
        bus_id = None
    if not travel_date or not bus_id:
        messages.warning(request, 'Choose a bus and travel date before checking out.')
        return redirect('bus:book_ticket')

    bus = get_object_or_404(BusSchedule, pk=bus_id, active=True)
    if bus.day != travel_date.strftime('%a').lower()[:3]:
        messages.error(request, 'This bus does not operate on the selected date.')
        return redirect('bus:book_ticket')

    allowed_quantity = min(2, bus.available_seats(travel_date), max(0, 2 - _account_ticket_total(request.user, travel_date)))
    if allowed_quantity <= 0:
        messages.error(request, 'No seats remain, or you have already booked two tickets for that date.')
        return redirect('bus:previous_bookings')

    return render(request, 'bus/checkout.html', {
        'bus': bus,
        'travel_date': travel_date,
        'max_quantity': allowed_quantity,
        'quantity_choices': range(1, allowed_quantity + 1),
    })


@login_required
def previous_bookings(request):
    bookings = TicketBooking.objects.filter(user=request.user).select_related('bus').order_by('-travel_date', '-booked_at')
    return render(request, 'bus/previous_bookings.html', {'bookings': bookings})


def _get_ticket_for_view(request, ticket_id):
    booking = get_object_or_404(TicketBooking.objects.select_related('bus', 'user'), ticket_id=ticket_id)
    if booking.user_id != request.user.id and not is_bus_admin(request.user):
        raise Http404()
    return booking


@login_required
def ticket_detail(request, ticket_id):
    booking = _get_ticket_for_view(request, ticket_id)
    if booking.status != TicketBooking.STATUS_PAID:
        messages.warning(request, 'This booking has not been paid for yet.')
        return redirect('bus:previous_bookings')

    image = qrcode.make(booking.qr_payload)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return render(request, 'bus/ticket_detail.html', {'booking': booking, 'qr_base64': qr_base64})


@login_required
def download_ticket(request, ticket_id):
    booking = _get_ticket_for_view(request, ticket_id)
    if booking.status != TicketBooking.STATUS_PAID:
        raise Http404()

    qr_image = qrcode.make(booking.qr_payload).convert('RGB').resize((360, 360))
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new('RGB', (1000, 700), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    details = [
        'IGNITE BUS TICKET',
        f'Ticket ID: {booking.ticket_id}',
        f'Passenger: {booking.user.get_full_name() or booking.user.username}',
        f'Bus: {booking.bus.name}',
        f'Route: {booking.bus.get_route_display()}',
        f'Date: {booking.travel_date:%d %b %Y}',
        f'Departure: {booking.bus.departure_time:%I:%M %p}',
        f'Tickets: {booking.quantity}',
        f'Payment ref: {booking.payment_reference}',
    ]
    top = 50
    for line in details:
        draw.text((45, top), line, fill='#17203a', font=font)
        top += 42
    image.paste(qr_image, (590, 65))

    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="ignite-bus-ticket-{booking.ticket_id}.png"'
    return response


@user_passes_test(is_bus_admin)
def verify_ticket(request):
    result = None
    verification_error = None
    verification_state = None

    if request.method == 'POST':
        ticket_input = request.POST.get('ticket_payload', '').strip()
        ticket_id = None
        try:
            payload = signing.loads(ticket_input, salt='ignite.bus.ticket')
            ticket_id = uuid.UUID(payload['ticket_id'])
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            # Support the printed ticket ID as a manual fall-back for scanner issues.
            try:
                ticket_id = uuid.UUID(ticket_input)
            except (TypeError, ValueError):
                verification_error = 'The scanned QR code is not a valid Ignite ticket.'

        if ticket_id and not verification_error:
            try:
                with transaction.atomic():
                    result = TicketBooking.objects.select_for_update().select_related('bus', 'user').get(ticket_id=ticket_id)
                    if result.status != TicketBooking.STATUS_PAID:
                        verification_error = 'Payment has not been completed for this ticket.'
                    elif result.travel_date < timezone.localdate():
                        verification_error = 'This ticket is for a past travel date.'
                    elif result.checked_in_at:
                        verification_error = f'This ticket was already verified at {timezone.localtime(result.checked_in_at):%I:%M %p}.'
                    else:
                        result.checked_in_at = timezone.now()
                        result.checked_in_by = request.user
                        result.save(update_fields=['checked_in_at', 'checked_in_by'])
                        verification_state = 'accepted'
            except TicketBooking.DoesNotExist:
                verification_error = 'No booking matches this ticket.'

    return render(request, 'bus/verify_ticket.html', {
        'result': result,
        'verification_error': verification_error,
        'verification_state': verification_state,
    })
