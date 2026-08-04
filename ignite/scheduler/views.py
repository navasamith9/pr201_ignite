from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Event,
    EventRegistration,
    BookingHistory,
)

from .serializers import (
    EventSerializer,
    RoomSerializer,
)

from .services import (
    get_suitable_rooms,
    recommend_room,
)

from .email_services import (
    send_event_cancellation,
    send_room_change_notification,
)

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

    if event.created_by_id == user.id:
        return True

    return event.coordinators.filter(id=user.id).exists()


# ============================================================
# 1. CREATE EVENT
# ============================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_event(request):
    """
    Creates an event in DRAFT state.

    After creation, suitable rooms are returned to the frontend.
    """

    serializer = EventSerializer(
        data=request.data
    )

    serializer.is_valid(
        raise_exception=True
    )

    event = serializer.save(
        created_by=request.user
    )

    # Event creator is automatically one of the coordinators.
    event.coordinators.add(request.user)

    suitable_rooms = get_suitable_rooms(event)

    recommendations = []

    for item in suitable_rooms[:5]:

        recommendations.append({
            "room": RoomSerializer(
                item["room"]
            ).data,

            "unused_seats":
                item["unused_seats"]
        })

    return Response(
        {
            "message": "Event created successfully.",
            "event": EventSerializer(event).data,
            "recommended_rooms": recommendations,
        },
        status=status.HTTP_201_CREATED
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

    room = recommend_room(event)

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

    # Send cancellation email
    send_event_cancellation(
        event=event,
        recipients=registered_users,
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

    return Response({
        "message":
            "Event updated and room recalculated successfully.",

        "room_changed":
            old_room != new_room,

        "event":
            EventSerializer(event).data,
    })