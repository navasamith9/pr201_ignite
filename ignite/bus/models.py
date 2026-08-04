import uuid

from django.conf import settings
from django.db import models


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
    max_capacity = models.PositiveSmallIntegerField(default=40)
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
    quantity = models.PositiveSmallIntegerField(default=1)
    route = models.CharField(max_length=32, choices=BusSchedule.ROUTE_CHOICES)
    booked_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payment_reference = models.CharField(max_length=128, blank=True)
    razorpay_payment_id = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ['-travel_date', '-booked_at']

    def __str__(self):
        return f"{self.user} — {self.bus.name} on {self.travel_date} ({self.quantity} ticket{'s' if self.quantity != 1 else ''})"

    @property
    def qr_payload(self):
        return f"{self.ticket_id}|{self.user.username}|{self.bus.name}|{self.travel_date}|{self.quantity}|{self.payment_reference}"

    def get_ticket_label(self):
        return f"Ticket {self.ticket_id}"
