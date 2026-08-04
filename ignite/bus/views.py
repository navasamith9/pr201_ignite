import base64
import io
from datetime import datetime, date

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from PIL import Image, ImageDraw, ImageFont

from .models import BusSchedule, TicketBooking


@login_required
def dashboard(request):
    return render(request, 'bus/dashboard.html')


@login_required
def book_ticket(request):
    selected_date = request.POST.get('travel_date') or request.GET.get('travel_date')
    selected_route = request.POST.get('route') or request.GET.get('route')
    available_buses = []
    error = None

    if request.method == 'POST' and selected_date and selected_route:
        try:
            travel_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            if travel_date < date.today():
                raise ValueError('Please select today or a future date.')
        except ValueError:
            error = 'Please select a valid date.'
            travel_date = None
        else:
            week_day = travel_date.strftime('%a').lower()[:3]
            buses = BusSchedule.objects.filter(day=week_day, route=selected_route, active=True)
            available_buses = [bus for bus in buses if bus.available_seats(travel_date) > 0]
            if not available_buses:
                error = 'No buses are available for the selected route and date.'
    else:
        travel_date = None

    return render(request, 'bus/book_ticket.html', {
        'selected_date': selected_date,
        'selected_route': selected_route,
        'available_buses': available_buses,
        'route_choices': BusSchedule.ROUTE_CHOICES,
        'error': error,
        'travel_date': travel_date,
    })


@login_required
def checkout(request):
    if request.method == 'POST':
        bus_id = request.POST.get('bus_id')
        travel_date = request.POST.get('travel_date')
        quantity = int(request.POST.get('quantity', 1))
        bus = get_object_or_404(BusSchedule, id=bus_id, active=True)

        try:
            travel_date_value = datetime.strptime(travel_date, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid travel date.')
            return redirect('bus:book_ticket')

        if travel_date_value < date.today():
            messages.error(request, 'Travel date must be today or later.')
            return redirect('bus:book_ticket')

        available = bus.available_seats(travel_date_value)
        user_booked = TicketBooking.objects.filter(
            user=request.user,
            travel_date=travel_date_value,
            status=TicketBooking.STATUS_PAID,
        ).aggregate(total=Sum('quantity'))['total'] or 0

        remaining_for_user = max(0, 2 - user_booked)
        max_quantity = min(available, remaining_for_user, 2)

        if quantity < 1 or quantity > max_quantity:
            messages.error(request, 'Please select a valid quantity within the allowed limit.')
            return redirect('bus:book_ticket')

        booking = TicketBooking.objects.create(
            user=request.user,
            bus=bus,
            travel_date=travel_date_value,
            quantity=quantity,
            route=bus.route,
            status=TicketBooking.STATUS_PENDING,
        )

        return render(request, 'bus/checkout.html', {
            'booking': booking,
            'amount': booking.quantity * bus.price,
            'razorpay_key': '',
        })

    bus_id = request.GET.get('bus_id')
    travel_date = request.GET.get('travel_date')
    if not bus_id or not travel_date:
        messages.warning(request, 'Please select a bus and travel date before proceeding to checkout.')
        return redirect('bus:book_ticket')

    bus = get_object_or_404(BusSchedule, id=bus_id, active=True)
    try:
        travel_date_value = datetime.strptime(travel_date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid travel date.')
        return redirect('bus:book_ticket')

    if travel_date_value < date.today():
        messages.error(request, 'Travel date must be today or later.')
        return redirect('bus:book_ticket')

    available = bus.available_seats(travel_date_value)
    user_booked = TicketBooking.objects.filter(
        user=request.user,
        travel_date=travel_date_value,
        status=TicketBooking.STATUS_PAID,
    ).aggregate(total=Sum('quantity'))['total'] or 0

    remaining_for_user = max(0, 2 - user_booked)
    max_quantity = min(available, remaining_for_user, 2)

    if max_quantity <= 0:
        messages.error(request, 'You have reached the 2-ticket limit for this date or no seats remain.')
        return redirect('bus:previous_bookings')

    return render(request, 'bus/checkout.html', {
        'bus': bus,
        'travel_date': travel_date_value,
        'max_quantity': max_quantity,
        'price_per_ticket': bus.price,
        'total_amount': bus.price,
    })


@login_required
def previous_bookings(request):
    bookings = TicketBooking.objects.filter(user=request.user).order_by('-travel_date', '-booked_at')
    return render(request, 'bus/previous_bookings.html', {'bookings': bookings})


@login_required
def ticket_detail(request, ticket_id):
    booking = get_object_or_404(TicketBooking, ticket_id=ticket_id)
    if booking.user != request.user and not request.user.is_staff:
        raise Http404()

    qr_payload = booking.qr_payload
    image = qrcode.make(qr_payload)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return render(request, 'bus/ticket_detail.html', {
        'booking': booking,
        'qr_base64': qr_base64,
    })


@login_required
def download_ticket(request, ticket_id):
    booking = get_object_or_404(TicketBooking, ticket_id=ticket_id)
    if booking.user != request.user and not request.user.is_staff:
        raise Http404()

    payload = booking.qr_payload
    qr_image = qrcode.make(payload).convert('RGB')
    width = 1000
    height = 700
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    details = [
        f'Ticket ID: {booking.ticket_id}',
        f'Name: {booking.user.get_full_name() or booking.user.username}',
        f'Route: {booking.bus.get_route_display()}',
        f'Date: {booking.travel_date}',
        f'Time: {booking.bus.departure_time.strftime("%H:%M")}',
        f'Bus: {booking.bus.name}',
        f'Quantity: {booking.quantity}',
        f'Payment: {booking.payment_reference or "N/A"}',
    ]

    left = 40
    top = 40
    for line in details:
        draw.text((left, top), line, fill='black', font=font)
        top += 38

    qr_image = qr_image.resize((360, 360))
    image.paste(qr_image, (width - qr_image.width - 40, 40))

    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename=ticket_{booking.ticket_id}.png'
    return response


@user_passes_test(lambda user: user.is_staff)
def verify_ticket(request):
    result = None
    verification_error = None

    if request.method == 'POST':
        ticket_input = request.POST.get('ticket_id', '').strip()
        booking = None

        if ticket_input:
            try:
                booking = TicketBooking.objects.get(ticket_id=ticket_input)
            except TicketBooking.DoesNotExist:
                if '|' in ticket_input:
                    ticket_uuid = ticket_input.split('|', 1)[0]
                    try:
                        booking = TicketBooking.objects.get(ticket_id=ticket_uuid)
                    except TicketBooking.DoesNotExist:
                        booking = None

        if booking:
            result = booking
        else:
            verification_error = 'Ticket could not be verified. Confirm the QR data or Ticket ID.'

    return render(request, 'bus/verify_ticket.html', {
        'result': result,
        'verification_error': verification_error,
    })
