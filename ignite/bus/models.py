import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse


class BusSchedule(models.Model):
    ROUTE_COLLEGE_CITY = 'college_city'
    ROUTE_CITY_COLLEGE = 'city_college'

    ROUTE_CHOICES = [
        (ROUTE_COLLEGE_CITY, 'College to City'),
        (ROUTE_CITY_COLLEGE, 'City to College'),
    ]

    DAY_CHOICES = [
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ]

    name = models.CharField(max_length=128)
    route = models.CharField(max_length=32, choices=ROUTE_CHOICES)
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    departure_time = models.TimeField()
    price = models.PositiveIntegerField(default=100)
    max_capacity = models.PositiveSmallIntegerField(default=40, validators=[MinValueValidator(1), MaxValueValidator(40)])
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['day', 'departure_time']
        unique_together = ['name', 'day', 'departure_time']

    def __str__(self):
        return f"{self.name} — {self.get_route_display()} on {self.get_day_display()} at {self.departure_time.strftime('%H:%M')}"

    def available_seats(self, travel_date):
        booked = self.bookings.filter(travel_date=travel_date, status='paid').aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        return max(self.max_capacity - booked, 0)


class TicketBooking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bus_bookings')
    bus = models.ForeignKey(BusSchedule, on_delete=models.PROTECT, related_name='bookings')
    travel_date = models.DateField()
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(2)])
    route = models.CharField(max_length=32, choices=BusSchedule.ROUTE_CHOICES)
    booked_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payment_reference = models.CharField(max_length=128, blank=True)
    razorpay_payment_id = models.CharField(max_length=128, blank=True)
    checked_in_at = models.DateTimeField(blank=True, null=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='verified_bus_tickets',
    )

    class Meta:
        ordering = ['-travel_date', '-booked_at']

    def __str__(self):
        return f"{self.user} — {self.bus.name} on {self.travel_date} ({self.quantity} ticket{'s' if self.quantity != 1 else ''})"

    @property
    def qr_payload(self):
        """A signed, opaque payload so a scanner can reject altered QR data."""
        from django.core import signing

        return signing.dumps({'ticket_id': str(self.ticket_id)}, salt='ignite.bus.ticket')

    def get_ticket_label(self):
        return f"Ticket {self.ticket_id}"

    @property
    def can_be_verified(self):
        from django.utils import timezone

        return self.status == self.STATUS_PAID and self.travel_date >= timezone.localdate()

    def payment_success_url(self):
        return reverse('bus:ticket_detail', kwargs={'ticket_id': self.ticket_id})

    def complete_payment(self, *, payment_reference, payment_id):
        """Atomically turn a pending booking into a paid ticket.

        The checks are repeated after Razorpay confirms the payment so two
        simultaneous checkouts cannot exceed the 40-seat or two-ticket limits.
        """
        from django.core.exceptions import ValidationError
        from django.db import transaction

        with transaction.atomic():
            # Lock the account and schedule in a consistent order.
            type(self.user).objects.select_for_update().get(pk=self.user_id)
            booking = type(self).objects.select_for_update().select_related('bus').get(pk=self.pk)
            bus = BusSchedule.objects.select_for_update().get(pk=booking.bus_id)

            if booking.status == self.STATUS_PAID:
                return booking
            if booking.status != self.STATUS_PENDING:
                raise ValidationError('This booking is no longer available for payment.')

            occupied = type(self).objects.filter(
                bus_id=bus.pk,
                travel_date=booking.travel_date,
                status=self.STATUS_PAID,
            ).exclude(pk=booking.pk).aggregate(total=models.Sum('quantity'))['total'] or 0
            if occupied + booking.quantity > bus.max_capacity:
                raise ValidationError('This bus became full before the payment could be confirmed.')

            account_total = type(self).objects.filter(
                user_id=booking.user_id,
                travel_date=booking.travel_date,
                status=self.STATUS_PAID,
            ).exclude(pk=booking.pk).aggregate(total=models.Sum('quantity'))['total'] or 0
            if account_total + booking.quantity > 2:
                raise ValidationError('Your account already has the maximum two tickets for this date.')

            booking.status = self.STATUS_PAID
            booking.payment_reference = payment_reference
            booking.razorpay_payment_id = payment_id
            booking.save(update_fields=['status', 'payment_reference', 'razorpay_payment_id'])
            return booking
