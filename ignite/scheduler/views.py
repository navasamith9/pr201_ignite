from django.contrib.auth import get_user_model
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Event,
    EventRegistration,
    BookingHistory,
    Room,
    RoomBookingPermission,
    TimetableEntry,
)

from .serializers import (
    BookingHistorySerializer,
    EventSerializer,
    RoomSerializer,
    TimetableEntrySerializer,
)

from .services import (
    get_suitable_rooms,
    recommend_room,
    student_recipients_for,
    user_matches_event_audience,
)

from .email_services import (
    send_event_cancellation,
    send_event_invitation,
    send_room_change_notification,
)
from .permissions import can_book_rooms, is_faculty, is_scheduler_admin

# ============================================================
# HELPER: CHECK EVENT MANAGEMENT PERMISSION
# ============================================================

def can_manage_event(user, event):
    """
    Returns True when the user is either:
    - the event creator, or
    - one of the coordinators/co-coordinators.
    """

    if not user or not user.is_authenticated:
        return False

    if is_scheduler_admin(user):
        return True

    if not can_book_rooms(user):
        return False

    if event.created_by_id == user.id:
        return True

    return event.coordinators.filter(id=user.id).exists()


def staff_only(request):
    """Return a response for a non-administrator request, otherwise None."""
    if is_scheduler_admin(request.user):
        return None
    return Response(
        {"error": "Only scheduler administrators can manage rooms and timetable entries."},
        status=status.HTTP_403_FORBIDDEN,
    )


def recommendation_data(event):
    return [
        {
            "room": RoomSerializer(item["room"]).data,
            "unused_seats": item["unused_seats"],
        }
        for item in get_suitable_rooms(event)
    ]


def wants_student_view(request):
    """Let approved student coordinators deliberately use their student workspace."""
    return (
        request.query_params.get("view") == "student"
        and request.user.role == request.user.Role.STUDENT
    )


# ============================================================
# ROOM AND TIMETABLE MANAGEMENT
# ============================================================

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def rooms(request):
    if request.method == "GET":
        return Response(RoomSerializer(Room.objects.all().order_by("name"), many=True).data)

    denied = staff_only(request)
    if denied:
        return denied

    serializer = RoomSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def room_detail(request, room_id):
    try:
        room = Room.objects.get(pk=room_id)
    except Room.DoesNotExist:
        return Response({"error": "Room not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(RoomSerializer(room).data)

    denied = staff_only(request)
    if denied:
        return denied
    if request.method == "DELETE":
        if room.booked_events.filter(status="BOOKED").exists():
            return Response(
                {"error": "A room with active bookings cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        room.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = RoomSerializer(room, data=request.data, partial=request.method == "PATCH")
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def timetable(request):
    if request.method == "GET":
        entries = TimetableEntry.objects.select_related("room").order_by(
            "day_of_week", "start_time", "room__name"
        )
        return Response(TimetableEntrySerializer(entries, many=True).data)

    denied = staff_only(request)
    if denied:
        return denied
    serializer = TimetableEntrySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def timetable_detail(request, entry_id):
    try:
        entry = TimetableEntry.objects.select_related("room").get(pk=entry_id)
    except TimetableEntry.DoesNotExist:
        return Response({"error": "Timetable entry not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(TimetableEntrySerializer(entry).data)

    denied = staff_only(request)
    if denied:
        return denied
    if request.method == "DELETE":
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = TimetableEntrySerializer(entry, data=request.data, partial=request.method == "PATCH")
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# 1. CREATE EVENT
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_events(request):
    """Return the current user's bookings, or their event registrations."""
    if wants_student_view(request):
        events = Event.objects.filter(registrations__user=request.user)
    elif is_scheduler_admin(request.user):
        events = Event.objects.all()
    elif can_book_rooms(request.user):
        events = Event.objects.filter(
            Q(created_by=request.user) | Q(coordinators=request.user)
        )
    else:
        events = Event.objects.filter(registrations__user=request.user)

    events = (
        events.select_related("booked_room", "created_by")
        .prefetch_related("coordinators", "registrations")
        .distinct()
        .order_by("event_date", "start_time")
    )

    return Response(EventSerializer(events, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def campus_events(request):
    """Return upcoming booked events for the faculty/admin campus timetable."""
    events = (
        Event.objects.filter(
            status="BOOKED",
            event_date__gte=timezone.localdate(),
        )
        .select_related("booked_room", "created_by")
        .prefetch_related("registrations")
        .order_by("event_date", "start_time")
    )
    now = timezone.localtime()
    # Do not show events that have already finished today as new events.
    events = [
        event for event in events
        if event.event_date > now.date() or event.end_time > now.time()
    ]
    if wants_student_view(request) or not can_book_rooms(request.user):
        events = [event for event in events if user_matches_event_audience(request.user, event)]
    registered_ids = set(
        EventRegistration.objects.filter(user=request.user, event__in=events)
        .values_list("event_id", flat=True)
    )
    registration_open_ids = {
        event.id
        for event in events
        if (
            not event.registration_closed
            and event.registration_deadline > timezone.now()
            and (event.event_date > now.date() or event.start_time > now.time())
        )
    }
    data = EventSerializer(events, many=True).data
    for item in data:
        item["is_registered"] = item["id"] in registered_ids
        item["registration_open"] = item["id"] in registration_open_ids
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def open_events(request):
    """Return booked events that are open for the current user to register."""
    now = timezone.localtime()
    events = (
        Event.objects.filter(
            status="BOOKED",
            registration_closed=False,
            registration_deadline__gt=timezone.now(),
            event_date__gte=timezone.localdate(),
        )
        .select_related("booked_room", "created_by")
        .prefetch_related("registrations")
        .order_by("event_date", "start_time")
    )
    events = [
        event for event in events
        if event.event_date > now.date() or event.start_time > now.time()
    ]
    events = [event for event in events if user_matches_event_audience(request.user, event)]
    registered_event_ids = set(
        EventRegistration.objects.filter(user=request.user, event__in=events)
        .values_list("event_id", flat=True)
    )
    data = EventSerializer(events, many=True).data
    for item in data:
        item["is_registered"] = item["id"] in registered_event_ids
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def scheduler_access(request):
    """Small role payload used by the role-aware scheduler workspace."""
    if is_scheduler_admin(request.user):
        role = "admin"
    elif is_faculty(request.user):
        role = "faculty"
    elif can_book_rooms(request.user):
        role = "coordinator"
    else:
        role = "student"

    return Response({
        "role": role,
        "can_book_rooms": can_book_rooms(request.user),
        "can_manage_rooms": is_scheduler_admin(request.user),
        "branch": request.user.branch,
        "academic_year": request.user.academic_year,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_notifications(request):
    """Return booking changes relevant to a participant or event manager."""
    attendee_view = wants_student_view(request) or not can_book_rooms(request.user)
    audience_events = []
    if attendee_view:
        audience_events = [
            event for event in Event.objects.all()
            if user_matches_event_audience(request.user, event)
        ]
        public_event_ids = [event.id for event in audience_events]
        event_filter = (
            Q(event__registrations__user=request.user)
            | Q(
                event_id__in=public_event_ids,
                action__in=["CREATED", "REGISTRATION_REMINDER_SENT", "CANCELLED"],
            )
        )
    elif is_scheduler_admin(request.user):
        event_filter = Q()
    elif can_book_rooms(request.user):
        event_filter = Q(event__created_by=request.user) | Q(event__coordinators=request.user)

    history = (
        BookingHistory.objects.filter(event_filter)
        .select_related("event", "old_room", "new_room")
        .distinct()
        .order_by("-created_at")[:12]
    )
    updates = [
        {
            "id": record.id,
            "event_id": record.event_id,
            "event_title": record.event.title,
            "action": record.action,
            "old_room_name": record.old_room.name if record.old_room else None,
            "new_room_name": record.new_room.name if record.new_room else None,
            "created_at": record.created_at,
        }
        for record in history
    ]

    # An ended event is still a useful update for an attendee, including when
    # a scheduled reminder job did not run at the expected time.  This is
    # calculated on read so opening the page never creates duplicate history.
    if attendee_view:
        now = timezone.localtime()
        for event in audience_events:
            if event.status != "BOOKED":
                continue
            ended_at = timezone.make_aware(
                datetime.combine(event.event_date, event.end_time),
                timezone.get_current_timezone(),
            )
            if ended_at <= now:
                updates.append({
                    "id": f"ended-{event.id}",
                    "event_id": event.id,
                    "event_title": event.title,
                    "action": "EVENT_ENDED",
                    "old_room_name": None,
                    "new_room_name": None,
                    "created_at": ended_at,
                })

    updates.sort(key=lambda item: item["created_at"], reverse=True)
    return Response(updates[:12])


def booking_permission_data(permission):
    return {
        "id": permission.id,
        "email": permission.user.email,
        "name": permission.user.get_full_name() or permission.user.username,
        "is_active": permission.is_active,
        "updated_at": permission.updated_at,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def coordinator_permissions(request):
    """Administrators grant or update room-booking access for students."""
    denied = staff_only(request)
    if denied:
        return denied

    if request.method == "GET":
        permissions = RoomBookingPermission.objects.select_related("user").order_by(
            "user__email"
        )
        return Response([booking_permission_data(permission) for permission in permissions])

    email = str(request.data.get("email", "")).strip().lower()
    if not email:
        return Response({"error": "Enter a student email address."}, status=status.HTTP_400_BAD_REQUEST)
    user = get_user_model().objects.filter(email__iexact=email).first()
    if user is None:
        return Response(
            {"error": "This student must sign in once before access can be granted."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if user.role != user.Role.STUDENT:
        return Response(
            {"error": "Room-booking coordinator access is only for student accounts."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    permission, _ = RoomBookingPermission.objects.update_or_create(
        user=user,
        defaults={"granted_by": request.user, "is_active": True},
    )
    return Response(booking_permission_data(permission), status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def coordinator_permission_detail(request, permission_id):
    """Revoke a student coordinator's booking access without deleting history."""
    denied = staff_only(request)
    if denied:
        return denied
    try:
        permission = RoomBookingPermission.objects.select_related("user").get(pk=permission_id)
    except RoomBookingPermission.DoesNotExist:
        return Response({"error": "Coordinator permission not found."}, status=status.HTTP_404_NOT_FOUND)

    permission.is_active = False
    permission.granted_by = request.user
    permission.save(update_fields=["is_active", "granted_by", "updated_at"])
    return Response(booking_permission_data(permission))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def event_detail(request, event_id):
    """Return an event if it is public for registration or user-managed."""
    try:
        event = (
            Event.objects.select_related("booked_room", "created_by")
            .prefetch_related("coordinators", "registrations")
            .get(pk=event_id)
        )
    except Event.DoesNotExist:
        return Response({"error": "Event not found."}, status=status.HTTP_404_NOT_FOUND)

    if event.status != "BOOKED" and not can_manage_event(request.user, event):
        return Response({"error": "You cannot view this event."}, status=status.HTTP_403_FORBIDDEN)
    if (
        event.status == "BOOKED"
        and not can_book_rooms(request.user)
        and not user_matches_event_audience(request.user, event)
    ):
        return Response({"error": "This event is not open to your branch or academic year."}, status=status.HTTP_403_FORBIDDEN)
    return Response(EventSerializer(event).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_history(request, event_id):
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        return Response({"error": "Event not found."}, status=status.HTTP_404_NOT_FOUND)

    if not can_manage_event(request.user, event):
        return Response(
            {"error": "Only an event coordinator can view booking history."},
            status=status.HTTP_403_FORBIDDEN,
        )

    history = event.booking_history.select_related(
        "old_room", "new_room", "changed_by"
    ).order_by("-created_at")
    return Response(BookingHistorySerializer(history, many=True).data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def availability(request):
    """Check room availability without creating an event or sending alerts."""
    if not can_book_rooms(request.user):
        return Response(
            {"error": "Only faculty and approved club coordinators can search and book rooms."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = EventSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    preview = Event(**serializer.validated_data)
    return Response({"recommended_rooms": recommendation_data(preview)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_event(request):
    """Create an event only after an authorised user chooses an available room."""
    if not can_book_rooms(request.user):
        return Response(
            {"error": "Only faculty and approved club coordinators can book rooms."},
            status=status.HTTP_403_FORBIDDEN,
        )

    requested_room_id = request.data.get("room_id")
    if not requested_room_id:
        return Response(
            {"error": "Choose an available room before confirming the booking."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw_coordinator_emails = request.data.get("coordinator_emails", [])
    if isinstance(raw_coordinator_emails, str):
        raw_coordinator_emails = [
            email.strip().lower()
            for email in raw_coordinator_emails.split(",")
            if email.strip()
        ]
    if not isinstance(raw_coordinator_emails, list) or not all(
        isinstance(email, str) for email in raw_coordinator_emails
    ):
        return Response(
            {"error": "Co-coordinator emails must be a comma-separated list."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    coordinator_emails = {email.strip().lower() for email in raw_coordinator_emails if email.strip()}
    coordinator_users = list(
        get_user_model().objects.filter(email__in=coordinator_emails)
    )
    found_emails = {user.email.lower() for user in coordinator_users}
    missing_emails = coordinator_emails - found_emails
    if missing_emails:
        return Response(
            {"error": f"No account found for: {', '.join(sorted(missing_emails))}."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if any(not can_book_rooms(user) for user in coordinator_users):
        return Response(
            {"error": "A co-coordinator must be faculty or have administrator-granted coordinator access."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = EventSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    event = serializer.save(created_by=request.user)
    event.coordinators.add(request.user)
    event.coordinators.add(*coordinator_users)

    room = next(
        (
            item["room"]
            for item in get_suitable_rooms(event)
            if str(item["room"].pk) == str(requested_room_id)
        ),
        None,
    )
    if room is None:
        transaction.set_rollback(True)
        return Response(
            {"error": "That room is no longer available. Search again to see current options."},
            status=status.HTTP_409_CONFLICT,
        )

    event.booked_room = room
    event.status = "BOOKED"
    event.save(update_fields=["booked_room", "status", "updated_at"])
    BookingHistory.objects.create(
        event=event,
        action="CREATED",
        new_room=room,
        changed_by=request.user,
    )

    recipients = student_recipients_for(event)
    transaction.on_commit(
        lambda: send_event_invitation(event=event, recipients=recipients)
    )
    return Response(
        {"message": "Room booked and event published.", "event": EventSerializer(event).data},
        status=status.HTTP_201_CREATED,
    )


# ============================================================
# 2. GET ROOM RECOMMENDATIONS
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recommend_rooms(request, event_id):
    """
    Returns all currently suitable rooms for an event.
    """

    try:
        event = Event.objects.get(
            pk=event_id
        )

    except Event.DoesNotExist:
        return Response(
            {
                "error": "Event not found."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if not can_manage_event(request.user, event):
        return Response(
            {"error": "Only an event coordinator can view room recommendations."},
            status=status.HTTP_403_FORBIDDEN,
        )

    suitable_rooms = get_suitable_rooms(event)

    result = []

    for item in suitable_rooms:

        result.append({
            "room": RoomSerializer(
                item["room"]
            ).data,

            "unused_seats":
                item["unused_seats"]
        })

    return Response({
        "event": EventSerializer(event).data,
        "recommended_rooms": result,
    })


# ============================================================
# 3. CONFIRM BOOKING
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def confirm_booking(request, event_id):
    """
    Books the best currently available room.

    Only the event creator/coordinator can perform this action.
    """

    try:
        event = Event.objects.select_for_update().get(
            pk=event_id
        )

    except Event.DoesNotExist:
        return Response(
            {
                "error": "Event not found."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if not can_manage_event(
        request.user,
        event
    ):
        return Response(
            {
                "error":
                    "Only the coordinator or "
                    "co-coordinator can book this event."
            },
            status=status.HTTP_403_FORBIDDEN
        )

    if event.status == "CANCELLED":
        return Response(
            {
                "error":
                    "A cancelled event cannot be booked."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    requested_room_id = request.data.get("room_id")
    if requested_room_id is None:
        room = recommend_room(event)
    else:
        room = next(
            (
                item["room"]
                for item in get_suitable_rooms(event)
                if str(item["room"].pk) == str(requested_room_id)
            ),
            None,
        )

    if room is None:
        return Response(
            {
                "error":
                    "No suitable room is currently available."
            },
            status=status.HTTP_409_CONFLICT
        )

    old_room = event.booked_room

    event.booked_room = room
    event.status = "BOOKED"

    event.save(
        update_fields=[
            "booked_room",
            "status",
            "updated_at",
        ]
    )

    BookingHistory.objects.create(
        event=event,
        action=(
            "ROOM_CHANGED"
            if old_room
            else "CREATED"
        ),
        old_room=old_room,
        new_room=room,
        changed_by=request.user,
    )

    # A new booking opens registration for all student accounts.  Email is
    # queued until the database transaction commits successfully.
    if old_room is None:
        recipients = student_recipients_for(event)
        transaction.on_commit(
            lambda: send_event_invitation(event=event, recipients=recipients)
        )

    return Response({
        "message": "Room booked successfully.",
        "event": EventSerializer(event).data,
    })


# ============================================================
# 4. REGISTER FOR EVENT
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_event(request, event_id):
    """
    Allows a logged-in user to register for a booked event.
    """

    try:
        event = Event.objects.get(
            pk=event_id
        )

    except Event.DoesNotExist:
        return Response(
            {
                "error": "Event not found."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if request.user.role != request.user.Role.STUDENT:
        return Response(
            {"error": "Only student accounts can register for events."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not user_matches_event_audience(request.user, event):
        return Response(
            {"error": "This event is not open to your branch or academic year."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if event.status != "BOOKED":
        return Response(
            {
                "error":
                    "Registration is available only "
                    "for booked events."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if event.registration_closed:
        return Response(
            {
                "error":
                    "Registration for this event is closed."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    now = timezone.localtime()
    if event.event_date < now.date() or (
        event.event_date == now.date() and event.start_time <= now.time()
    ):
        return Response(
            {"error": "This event has already started."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if timezone.now() > event.registration_deadline:
        return Response(
            {
                "error":
                    "The registration deadline has passed."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    registration, created = (
        EventRegistration.objects.get_or_create(
            event=event,
            user=request.user
        )
    )

    if not created:
        return Response(
            {
                "message":
                    "You are already registered "
                    "for this event."
            },
            status=status.HTTP_200_OK
        )

    return Response(
        {
            "message":
                "Event registration successful.",

            "registered_strength":
                event.registrations.count()
        },
        status=status.HTTP_201_CREATED
    )


# ============================================================
# 5. CANCEL EVENT REGISTRATION
# ============================================================

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def unregister_event(request, event_id):
    """
    Allows a student to cancel their own registration
    before registration closes.
    """

    try:
        event = Event.objects.get(
            pk=event_id
        )

    except Event.DoesNotExist:
        return Response(
            {
                "error": "Event not found."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if request.user.role != request.user.Role.STUDENT:
        return Response(
            {"error": "Only student accounts can update registrations."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if event.registration_closed:
        return Response(
            {
                "error":
                    "Registration is already closed."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    registration = EventRegistration.objects.filter(
        event=event,
        user=request.user
    ).first()

    if registration is None:
        return Response(
            {
                "error":
                    "You are not registered for this event."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    registration.delete()

    return Response({
        "message": "Event registration cancelled."
    })


# ============================================================
# 6. CANCEL THE ENTIRE BOOKING
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cancel_booking(request, event_id):
    """
    Cancels an event booking.

    Only coordinator/co-coordinator can do this.
    """

    try:
        event = Event.objects.select_for_update().get(
            pk=event_id
        )

    except Event.DoesNotExist:
        return Response(
            {
                "error": "Event not found."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if not can_manage_event(
        request.user,
        event
    ):
        return Response(
            {
                "error":
                    "Only the coordinator or "
                    "co-coordinator can cancel this booking."
            },
            status=status.HTTP_403_FORBIDDEN
        )

    if event.status == "CANCELLED":
        return Response(
            {
                "message":
                    "This event is already cancelled."
            },
            status=status.HTTP_200_OK
        )

    old_room = event.booked_room

    event.status = "CANCELLED"
    event.booked_room = None

    event.save(
        update_fields=[
            "status",
            "booked_room",
            "updated_at",
        ]
    )

    BookingHistory.objects.create(
        event=event,
        action="CANCELLED",
        old_room=old_room,
        changed_by=request.user,
    )

    # Get all registered participants
    registered_users = [
        registration.user
        for registration in event.registrations.select_related("user")
    ]

    transaction.on_commit(
        lambda: send_event_cancellation(
            event=event,
            recipients=registered_users,
        )
    )

    return Response({
        "message": "Booking cancelled successfully."
    })


# ============================================================
# 7. RESCHEDULE EVENT
# ============================================================

@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def reschedule_event(request, event_id):
    """
    Changes event information such as:

    - date
    - start time
    - end time
    - expected strength
    - requirements

    The room recommendation is recalculated automatically.
    """

    try:
        event = Event.objects.select_for_update().get(
            pk=event_id
        )

    except Event.DoesNotExist:
        return Response(
            {
                "error": "Event not found."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if not can_manage_event(
        request.user,
        event
    ):
        return Response(
            {
                "error":
                    "Only the coordinator or "
                    "co-coordinator can modify this event."
            },
            status=status.HTTP_403_FORBIDDEN
        )

    if event.status == "CANCELLED":
        return Response(
            {
                "error":
                    "A cancelled event cannot be rescheduled."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    old_room = event.booked_room

    serializer = EventSerializer(
        event,
        data=request.data,
        partial=True
    )

    serializer.is_valid(
        raise_exception=True
    )

    # Save the changed event temporarily.
    event = serializer.save()

    # Find the best room for the new event details.
    new_room = recommend_room(event)

    if new_room is None:
        # Roll back all changes made inside this transaction.
        transaction.set_rollback(True)

        return Response(
            {
                "error":
                    "No suitable room is available "
                    "for the new event details."
            },
            status=status.HTTP_409_CONFLICT
        )

    event.booked_room = new_room

    # If this was already booked, keep it booked.
    # A draft event remains draft.
    if event.status == "BOOKED":
        event.status = "BOOKED"

    event.save(
        update_fields=[
            "booked_room",
            "status",
            "updated_at",
        ]
    )

    BookingHistory.objects.create(
        event=event,
        action="RESCHEDULED",
        old_room=old_room,
        new_room=new_room,
        changed_by=request.user,
    )

    if old_room != new_room:
        registered_users = [
            registration.user
            for registration in event.registrations.select_related("user")
        ]
        transaction.on_commit(
            lambda: send_room_change_notification(
                event=event,
                recipients=registered_users,
                old_room=old_room,
                new_room=new_room,
            )
        )

    return Response({
        "message":
            "Event updated and room recalculated successfully.",

        "room_changed":
            old_room != new_room,

        "event":
            EventSerializer(event).data,
    })
