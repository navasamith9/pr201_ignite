import razorpay
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Payment


def _get_user_payment(request):
    try:
        payment_id = int(request.POST.get('payment_id', ''))
    except (TypeError, ValueError):
        return None
    try:
        return Payment.objects.get(pk=payment_id, user=request.user, status=Payment.Status.PENDING)
    except Payment.DoesNotExist:
        return None


def _razorpay_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@login_required
@require_POST
def razorpay_checkout(request):
    payment = _get_user_payment(request)
    if not payment:
        return JsonResponse({'error': 'This payment is unavailable.'}, status=404)
    client = _razorpay_client()
    if not client:
        return JsonResponse({'error': 'Razorpay test keys have not been configured.'}, status=503)

    try:
        if payment.provider_order_id:
            order = client.order.fetch(payment.provider_order_id)
        else:
            order = client.order.create(data={
                'amount': payment.amount_paise,
                'currency': payment.currency,
                'payment_capture': 1,
                'notes': {'payment_id': str(payment.pk), 'service': payment.content_type.model},
            })
            payment.provider_order_id = order['id']
            payment.save(update_fields=['provider_order_id'])
    except razorpay.errors.BadRequestError:
        return JsonResponse({'error': 'Razorpay could not create the order. Please try again.'}, status=502)

    return JsonResponse({'order': order, 'key': settings.RAZORPAY_KEY_ID})


@login_required
@require_POST
def razorpay_confirm(request):
    payment = _get_user_payment(request)
    order_id = request.POST.get('razorpay_order_id', '')
    payment_id = request.POST.get('razorpay_payment_id', '')
    signature = request.POST.get('razorpay_signature', '')
    if not payment or not all([order_id, payment_id, signature]):
        return JsonResponse({'error': 'The payment details are incomplete.'}, status=400)
    if order_id != payment.provider_order_id:
        return JsonResponse({'error': 'The payment order does not match this checkout.'}, status=400)

    client = _razorpay_client()
    if not client:
        return JsonResponse({'error': 'Razorpay test keys have not been configured.'}, status=503)
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        })
    except razorpay.errors.SignatureVerificationError:
        return JsonResponse({'error': 'Razorpay could not verify this payment.'}, status=400)

    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk, user=request.user)
            if payment.status != Payment.Status.PAID:
                payable = payment.content_object
                if not payable or not hasattr(payable, 'complete_payment'):
                    return JsonResponse({'error': 'This service does not support payment confirmation.'}, status=400)
                payable = payable.complete_payment(payment_reference=order_id, payment_id=payment_id)
                payment.status = Payment.Status.PAID
                payment.provider_payment_id = payment_id
                payment.provider_signature = signature
                payment.paid_at = timezone.now()
                payment.save(update_fields=['status', 'provider_payment_id', 'provider_signature', 'paid_at'])
            else:
                payable = payment.content_object
    except ValidationError as error:
        return JsonResponse({'error': error.messages[0]}, status=409)

    if not payable or not hasattr(payable, 'payment_success_url'):
        return JsonResponse({'error': 'Payment completed, but the receipt cannot be opened.'}, status=500)
    return JsonResponse({'success': True, 'redirect_url': payable.payment_success_url()})
