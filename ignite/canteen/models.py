from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class MenuItem(models.Model):
    """A food item offered by the single campus canteen."""

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('category', 'name')

    def __str__(self):
        return f'{self.name} ({self.category})'


class CanteenOrder(models.Model):
    class Status(models.TextChoices):
        PLACED = 'placed', 'Placed'
        PREPARING = 'preparing', 'Preparing'
        READY = 'ready', 'Ready'
        COMPLETED = 'completed', 'Completed'

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='canteen_orders')
    token_number = models.PositiveIntegerField(unique=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLACED)
    is_paid = models.BooleanField(default=False)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Canteen token {self.token_number} - {self.student}'

    @property
    def token_label(self):
        return f'CN-{self.token_number:04d}'

    def payment_success_url(self):
        return reverse('canteen:payment_success', kwargs={'order_id': self.pk})

    def complete_payment(self, *, payment_reference, payment_id):
        """Confirm payment only while every ordered item is still available."""
        from django.core.exceptions import ValidationError
        from django.db import transaction

        with transaction.atomic():
            order = type(self).objects.select_for_update().prefetch_related('items').get(pk=self.pk)
            if order.is_paid:
                return order
            menu_items = MenuItem.objects.select_for_update().filter(
                pk__in=order.items.values_list('menu_item_id', flat=True)
            )
            if menu_items.count() != order.items.count() or any(not item.is_available for item in menu_items):
                raise ValidationError('One or more items became unavailable before payment was confirmed.')
            order.is_paid = True
            order.save(update_fields=['is_paid', 'updated_at'])
            return order


class CanteenOrderItem(models.Model):
    """A price/name snapshot so completed orders remain accurate after menu edits."""

    order = models.ForeignKey(CanteenOrder, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name='order_items')
    item_name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ('id',)

    def __str__(self):
        return f'{self.quantity} x {self.item_name}'

    @property
    def subtotal(self):
        return self.unit_price * self.quantity
