import razorpay
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bus.models import TicketBooking


@csrf_exempt
def razorpay_checkout(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=400)

    amount = int(request.POST.get('amount', 0))
    booking_id = request.POST.get('booking_id')

    if amount <= 0 or not booking_id:
        return JsonResponse({'error': 'Amount and booking ID are required.'}, status=400)

    try:
        booking = TicketBooking.objects.get(pk=booking_id, status=TicketBooking.STATUS_PENDING)
    except TicketBooking.DoesNotExist:
        return JsonResponse({'error': 'Booking not found.'}, status=404)

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order_data = {
        'amount': amount * 100,
        'currency': 'INR',
        'payment_capture': 1,
        'notes': {
            'booking_id': str(booking.pk),
            'ticket_id': str(booking.ticket_id),
        },
    }
    order = client.order.create(data=order_data)
    return JsonResponse({'order': order})


@csrf_exempt
def razorpay_confirm(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=400)

    payment_id = request.POST.get('razorpay_payment_id')
    order_id = request.POST.get('razorpay_order_id')
    signature = request.POST.get('razorpay_signature')
    booking_id = request.POST.get('booking_id')

    if not all([payment_id, order_id, signature, booking_id]):
        return JsonResponse({'error': 'Missing payment parameters.'}, status=400)

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        params = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        }
        client.utility.verify_payment_signature(params)
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({'error': 'Signature verification failed.'}, status=400)

    try:
        booking = TicketBooking.objects.get(pk=booking_id, status=TicketBooking.STATUS_PENDING)
    except TicketBooking.DoesNotExist:
        return JsonResponse({'error': 'Booking not found.'}, status=404)

    booking.status = TicketBooking.STATUS_PAID
    booking.payment_reference = order_id
    booking.razorpay_payment_id = payment_id
    booking.save()

    return JsonResponse({'success': True, 'ticket_id': str(booking.ticket_id)})
