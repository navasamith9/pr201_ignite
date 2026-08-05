from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models



# ============================================================
# 1. LECTURE HALL / ROOM
# ============================================================

class Room(models.Model):
    """
    Stores information about every lecture hall / room
    that can be booked.
    """

    name = models.CharField(
        max_length=100,
        unique=True
    )

    building = models.CharField(
        max_length=100,
        blank=True
    )

    floor = models.CharField(
        max_length=30,
        blank=True
    )

    capacity = models.PositiveIntegerField()

    # Room facilities
    has_projector = models.BooleanField(default=False)
    has_ac = models.BooleanField(default=False)
    has_wifi = models.BooleanField(default=False)
    has_audio_system = models.BooleanField(default=False)
    has_smart_board = models.BooleanField(default=False)

    # Allows administrators to temporarily disable a room
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - Capacity {self.capacity}"


# ============================================================
# 2. NORMAL COLLEGE TIMETABLE
# ============================================================

class TimetableEntry(models.Model):
    """
    Stores regular classes/exams already scheduled in rooms.

    The booking system will check this table before recommending
    a lecture hall.
    """

    DAYS = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="timetable_entries"
    )

    day_of_week = models.PositiveSmallIntegerField(
        choices=DAYS
    )

    start_time = models.TimeField()

    end_time = models.TimeField()

    branch = models.CharField(
        max_length=50
    )

    year = models.PositiveSmallIntegerField()

    subject = models.CharField(
        max_length=150,
        blank=True
    )

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError(
                "End time must be after start time."
            )

    def __str__(self):
        return (
            f"{self.room.name} - "
            f"{self.get_day_of_week_display()} "
            f"{self.start_time}-{self.end_time}"
        )


# ============================================================
# 3. EVENT / LECTURE HALL BOOKING
# ============================================================

class Event(models.Model):
    """
    Stores events for which lecture halls are requested/booked.
    """

    EVENT_TYPES = [
        ("CLUB", "Club Event"),
        ("EXTRA_CLASS", "Extra Class"),
        ("EXAM", "Exam"),
        ("MEETING", "Meeting"),
        ("WORKSHOP", "Workshop"),
        ("SEMINAR", "Seminar"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("BOOKED", "Booked"),
        ("CANCELLED", "Cancelled"),
        ("COMPLETED", "Completed"),
    ]

    title = models.CharField(
        max_length=200
    )

    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPES
    )

    purpose = models.TextField()

    # Rough strength initially provided by coordinator
    expected_strength = models.PositiveIntegerField()

    # Examples:
    # ["CSE", "ECE"]
    branches = models.JSONField(
        default=list
    )

    # Example:
    # [1, 2, 3]
    years = models.JSONField(
        default=list
    )

    event_date = models.DateField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    # Students can register until this time
    registration_deadline = models.DateTimeField()

    # --------------------------------------------------------
    # Facilities required for this event
    # --------------------------------------------------------

    require_projector = models.BooleanField(
        default=False
    )

    require_ac = models.BooleanField(
        default=False
    )

    require_wifi = models.BooleanField(
        default=False
    )

    require_audio_system = models.BooleanField(
        default=False
    )

    require_smart_board = models.BooleanField(
        default=False
    )

    # --------------------------------------------------------
    # Room finally assigned
    # --------------------------------------------------------

    booked_room = models.ForeignKey(
        Room,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="booked_events"
    )

    # --------------------------------------------------------
    # User who originally created the booking
    # --------------------------------------------------------

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_scheduler_events"
    )

    # --------------------------------------------------------
    # Coordinator / co-coordinators allowed to manage event
    # --------------------------------------------------------

    coordinators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="coordinated_scheduler_events",
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT"
    )

    registration_closed = models.BooleanField(
        default=False
    )

    registration_reminder_sent = models.BooleanField(
       default=False
    )

    event_reminder_sent = models.BooleanField(
        default=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def clean(self):

        if self.start_time >= self.end_time:
            raise ValidationError(
                "Event end time must be after start time."
            )

        if self.expected_strength <= 0:
            raise ValidationError(
                "Expected strength must be greater than zero."
            )

    def __str__(self):
        return self.title


# ============================================================
# 4. EVENT REGISTRATION
# ============================================================

class EventRegistration(models.Model):
    """
    Stores students who register for an event.

    Final registration count will later be used to determine
    whether the room should be changed automatically.
    """

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="registrations"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scheduler_registrations"
    )

    registered_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"],
                name="unique_scheduler_event_registration"
            )
        ]

    def __str__(self):
        return f"{self.user} -> {self.event}"


# ============================================================
# 5. STUDENT COORDINATOR ACCESS
# ============================================================

class RoomBookingPermission(models.Model):
    """An administrator-managed grant that lets a student book rooms."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_booking_permission",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scheduler_permission_grants",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {'active' if self.is_active else 'inactive'}"


# ============================================================
# 6. BOOKING HISTORY
# ============================================================

class BookingHistory(models.Model):
    """
    Keeps track of every important booking change.

    Examples:
        Room changed
        Event rescheduled
        Booking cancelled
        Room automatically changed after registration
    """

    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("ROOM_CHANGED", "Room Changed"),
        ("RESCHEDULED", "Rescheduled"),
        ("CANCELLED", "Cancelled"),
        ("AUTO_ROOM_CHANGED", "Automatic Room Change"),
        ("REGISTRATION_REMINDER_SENT", "Registration Reminder Sent"),
        ("EVENT_REMINDER_SENT", "Event Reminder Sent"),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="booking_history"
    )

    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES
    )

    old_room = models.ForeignKey(
        Room,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )

    new_room = models.ForeignKey(
        Room,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scheduler_booking_changes"
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.event.title} - {self.get_action_display()}"
