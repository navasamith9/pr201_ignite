from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Payment(models.Model):
    """Reusable payment record for any campus service (bus, canteen, and more)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'

    class Provider(models.TextChoices):
        RAZORPAY = 'razorpay', 'Razorpay'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payments')
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    amount_paise = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default='INR')
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.RAZORPAY)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    provider_order_id = models.CharField(max_length=128, blank=True, null=True, unique=True)
    provider_payment_id = models.CharField(max_length=128, blank=True)
    provider_signature = models.CharField(max_length=256, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['content_type', 'object_id'])]

    def __str__(self):
        return f"Payment #{self.pk} · {self.amount_paise} {self.currency} · {self.status}"

    @property
    def amount_rupees(self):
        return self.amount_paise / 100
