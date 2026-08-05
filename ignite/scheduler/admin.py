from django.contrib import admin

from .models import (
    Room,
    TimetableEntry,
    Event,
    EventRegistration,
    BookingHistory,
    RoomBookingPermission,
)


# ============================================================
# ROOM ADMIN
# ============================================================

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "building",
        "floor",
        "capacity",
        "has_projector",
        "has_ac",
        "has_wifi",
        "is_active",
    )

    search_fields = (
        "name",
        "building",
    )

    list_filter = (
        "building",
        "has_projector",
        "has_ac",
        "has_wifi",
        "is_active",
    )


# ============================================================
# TIMETABLE ADMIN
# ============================================================

@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = (
        "room",
        "day_of_week",
        "start_time",
        "end_time",
        "branch",
        "year",
        "subject",
    )

    list_filter = (
        "day_of_week",
        "branch",
        "year",
        "room",
    )

    search_fields = (
        "room__name",
        "branch",
        "subject",
    )


# ============================================================
# EVENT ADMIN
# ============================================================

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "event_type",
        "event_date",
        "start_time",
        "end_time",
        "expected_strength",
        "booked_room",
        "status",
        "registration_closed",
        "event_reminder_sent",
    )

    list_filter = (
        "event_type",
        "status",
        "event_date",
        "registration_closed",
        "event_reminder_sent",
    )

    search_fields = (
        "title",
        "purpose",
        "created_by__username",
        "created_by__email",
    )

    filter_horizontal = (
        "coordinators",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


# ============================================================
# EVENT REGISTRATION ADMIN
# ============================================================

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "user",
        "registered_at",
    )

    list_filter = (
        "event",
        "registered_at",
    )

    search_fields = (
        "event__title",
        "user__username",
        "user__email",
    )

    readonly_fields = (
        "registered_at",
    )


@admin.register(RoomBookingPermission)
class RoomBookingPermissionAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "granted_by", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")


# ============================================================
# BOOKING HISTORY ADMIN
# ============================================================

@admin.register(BookingHistory)
class BookingHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "action",
        "old_room",
        "new_room",
        "changed_by",
        "created_at",
    )

    list_filter = (
        "action",
        "created_at",
    )

    search_fields = (
        "event__title",
        "changed_by__username",
        "changed_by__email",
    )

    readonly_fields = (
        "created_at",
    )
