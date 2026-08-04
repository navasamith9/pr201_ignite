from django.contrib import admin

from .models import BusSchedule, TicketBooking


@admin.register(BusSchedule)
class BusScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'route', 'day', 'departure_time', 'price', 'active', 'max_capacity')
    list_filter = ('route', 'day', 'active')
    search_fields = ('name',)


@admin.register(TicketBooking)
class TicketBookingAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'user', 'bus', 'travel_date', 'quantity', 'status', 'payment_reference')
    list_filter = ('status', 'travel_date', 'bus')
    search_fields = ('user__username', 'ticket_id', 'payment_reference')
    readonly_fields = ('ticket_id', 'booked_at')
