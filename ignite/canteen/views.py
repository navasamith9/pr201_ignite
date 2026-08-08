from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import MenuItemForm
from .models import CanteenOrder, CanteenOrderItem, MenuItem
from payments.models import Payment


def is_canteen_admin(user):
    """Allow global administrators and the service-specific canteen role."""
    return bool(user.is_authenticated and (
        user.is_superuser or user.is_staff or getattr(user, 'role', None) == 'admin'
        or getattr(user, 'is_canteen_admin', False)
    ))


def _cart(request):
    return request.session.get('canteen_cart', {})


def _save_cart(request, cart):
    request.session['canteen_cart'] = cart
    request.session.modified = True


def _clear_pending_checkout(request):
    if request.session.pop('canteen_pending_order', None) is not None:
        request.session.modified = True


def _cart_lines(request):
    cart = _cart(request)
    quantities = {}
    for item_id, quantity in cart.items():
        try:
            item_id, quantity = int(item_id), int(quantity)
        except (TypeError, ValueError):
            continue
        if quantity > 0:
            quantities[item_id] = min(quantity, 20)

    items = MenuItem.objects.filter(pk__in=quantities).order_by('category', 'name')
    lines, total = [], Decimal('0.00')
    for item in items:
        subtotal = item.price * quantities[item.pk]
        total += subtotal
        lines.append({'item': item, 'quantity': quantities[item.pk], 'subtotal': subtotal})
    return lines, total


@login_required
def menu(request):
    items = MenuItem.objects.all()
    return render(request, 'canteen/menu.html', {
        'items': items,
        'cart_count': sum(line['quantity'] for line in _cart_lines(request)[0]),
        'is_canteen_admin': is_canteen_admin(request.user),
    })


@login_required
@require_POST
def add_to_cart(request, item_id):
    item = get_object_or_404(MenuItem, pk=item_id)
    if not item.is_available:
        messages.error(request, f'{item.name} is currently unavailable.')
        return redirect('canteen:menu')
    cart = _cart(request)
    key = str(item.pk)
    cart[key] = min(int(cart.get(key, 0)) + 1, 20)
    _save_cart(request, cart)
    _clear_pending_checkout(request)
    messages.success(request, f'{item.name} was added to your cart.')
    return redirect('canteen:menu')


@login_required
def cart(request):
    lines, total = _cart_lines(request)
    return render(request, 'canteen/cart.html', {
        'lines': lines,
        'total': total,
        'can_checkout': bool(lines) and all(line['item'].is_available for line in lines),
    })


@login_required
@require_POST
def update_cart(request):
    cart = _cart(request)
    for key in list(cart):
        try:
            quantity = int(request.POST.get(f'quantity_{key}', 0))
        except (TypeError, ValueError):
            quantity = 0
        if quantity > 0:
            cart[key] = min(quantity, 20)
        else:
            cart.pop(key, None)
    _save_cart(request, cart)
    _clear_pending_checkout(request)
    messages.success(request, 'Your cart was updated.')
    return redirect('canteen:cart')


@login_required
@require_POST
def remove_from_cart(request, item_id):
    cart = _cart(request)
    if cart.pop(str(item_id), None) is not None:
        _save_cart(request, cart)
        _clear_pending_checkout(request)
        messages.success(request, 'Item removed from your cart.')
    return redirect('canteen:cart')


def _payment_for_order(order, user):
    return Payment.objects.filter(
        user=user,
        content_type=ContentType.objects.get_for_model(CanteenOrder),
        object_id=order.pk,
        status=Payment.Status.PENDING,
    ).first()


@login_required
@require_POST
def place_order(request):
    pending_order_id = request.session.get('canteen_pending_order')
    if pending_order_id:
        pending_order = CanteenOrder.objects.filter(
            pk=pending_order_id, student=request.user, is_paid=False
        ).first()
        if pending_order and _payment_for_order(pending_order, request.user):
            return redirect('canteen:checkout_order', order_id=pending_order.pk)
        request.session.pop('canteen_pending_order', None)

    lines, _ = _cart_lines(request)
    if not lines:
        messages.warning(request, 'Your cart is empty.')
        return redirect('canteen:menu')

    quantities = {line['item'].pk: line['quantity'] for line in lines}
    with transaction.atomic():
        # Re-read and lock menu records: staff may sell out an item mid-checkout.
        menu_items = {item.pk: item for item in MenuItem.objects.select_for_update().filter(pk__in=quantities)}
        if len(menu_items) != len(quantities) or any(not item.is_available for item in menu_items.values()):
            messages.error(request, 'One or more cart items are no longer available. Please update your cart.')
            return redirect('canteen:cart')

        total = sum((menu_items[item_id].price * quantity for item_id, quantity in quantities.items()), Decimal('0.00'))
        token_number = (CanteenOrder.objects.select_for_update().aggregate(last=Max('token_number'))['last'] or 0) + 1
        order = CanteenOrder.objects.create(student=request.user, token_number=token_number, total_amount=total)
        CanteenOrderItem.objects.bulk_create([
            CanteenOrderItem(order=order, menu_item=item, item_name=item.name, unit_price=item.price, quantity=quantities[item.pk])
            for item in menu_items.values()
        ])
        Payment.objects.create(
            user=request.user,
            content_object=order,
            amount_paise=int(total * 100),
        )

    request.session['canteen_pending_order'] = order.pk
    request.session.modified = True
    return redirect('canteen:checkout_order', order_id=order.pk)


@login_required
def checkout_order(request, order_id):
    order = get_object_or_404(CanteenOrder, pk=order_id, student=request.user, is_paid=False)
    payment = _payment_for_order(order, request.user)
    if not payment:
        messages.error(request, 'This payment is no longer available.')
        return redirect('canteen:cart')
    return render(request, 'canteen/checkout.html', {
        'order': order,
        'payment': payment,
        'razorpay_key': settings.RAZORPAY_KEY_ID,
    })


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(CanteenOrder, pk=order_id, student=request.user, is_paid=True)
    _save_cart(request, {})
    request.session.pop('canteen_pending_order', None)
    request.session.modified = True
    messages.success(request, f'Payment confirmed. Your token number is {order.token_label}.')
    return redirect('canteen:order_detail', order_id=order.pk)


def _order_for_request(request, order_id):
    order = get_object_or_404(CanteenOrder.objects.prefetch_related('items'), pk=order_id)
    if order.student_id != request.user.id and not is_canteen_admin(request.user):
        raise Http404()
    return order


@login_required
def my_orders(request):
    return render(request, 'canteen/my_orders.html', {
        'orders': CanteenOrder.objects.filter(student=request.user, is_paid=True).prefetch_related('items'),
    })


@login_required
def order_detail(request, order_id):
    return render(request, 'canteen/order_detail.html', {
        'order': _order_for_request(request, order_id),
        'status_choices': CanteenOrder.Status.choices,
    })


@user_passes_test(is_canteen_admin)
def staff_menu(request):
    return render(request, 'canteen/staff_menu.html', {'items': MenuItem.objects.all()})


@user_passes_test(is_canteen_admin)
def staff_menu_edit(request, item_id=None):
    item = get_object_or_404(MenuItem, pk=item_id) if item_id else None
    form = MenuItemForm(request.POST or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        saved_item = form.save()
        messages.success(request, f'{saved_item.name} was saved.')
        return redirect('canteen:staff_menu')
    return render(request, 'canteen/staff_menu_form.html', {'form': form, 'item': item})


@user_passes_test(is_canteen_admin)
@require_POST
def toggle_item_availability(request, item_id):
    item = get_object_or_404(MenuItem, pk=item_id)
    item.is_available = not item.is_available
    item.save(update_fields=['is_available', 'updated_at'])
    messages.success(request, f'{item.name} is now {"available" if item.is_available else "unavailable"}.')
    return redirect('canteen:staff_menu')


@user_passes_test(is_canteen_admin)
@require_POST
def delete_menu_item(request, item_id):
    item = get_object_or_404(MenuItem, pk=item_id)
    if item.order_items.exists():
        messages.warning(request, f'{item.name} is part of an existing order and cannot be removed. Mark it unavailable instead.')
    else:
        item_name = item.name
        item.delete()
        messages.success(request, f'{item_name} was removed from the menu.')
    return redirect('canteen:staff_menu')


@user_passes_test(is_canteen_admin)
def staff_orders(request):
    return render(request, 'canteen/staff_orders.html', {
        'orders': CanteenOrder.objects.filter(is_paid=True).select_related('student').prefetch_related('items'),
        'status_choices': CanteenOrder.Status.choices,
    })


@user_passes_test(is_canteen_admin)
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(CanteenOrder, pk=order_id)
    status = request.POST.get('status')
    statuses = [choice for choice, _ in CanteenOrder.Status.choices]
    if status not in statuses:
        raise Http404()
    if statuses.index(status) < statuses.index(order.status):
        messages.error(request, 'Order status can only move forward.')
    elif status != order.status:
        order.status = status
        order.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'{order.token_label} is now {order.get_status_display()}.')
    return redirect('canteen:staff_orders')
