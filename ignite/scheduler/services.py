from .models import Room, Event


# ============================================================
# 1. CHECK WHETHER TWO TIME PERIODS OVERLAP
# ============================================================

def time_overlaps(start1, end1, start2, end2):
    """
    Returns True when two time periods overlap.

    Example:
        09:00 - 10:00
        09:30 - 10:30
        => True

        09:00 - 10:00
        10:30 - 11:30
        => False
    """

    return start1 < end2 and start2 < end1


# ============================================================
# 2. CHECK NORMAL COLLEGE TIMETABLE
# ============================================================

def has_timetable_conflict(room, event_date, start_time, end_time):
    """
    Checks whether a regular class already occupies the room
    during the requested event time.
    """

    day_of_week = event_date.weekday()

    timetable_entries = room.timetable_entries.filter(
        day_of_week=day_of_week
    )

    for entry in timetable_entries:

        if time_overlaps(
            start_time,
            end_time,
            entry.start_time,
            entry.end_time
        ):
            return True

    return False


# ============================================================
# 3. CHECK OTHER EVENT BOOKINGS
# ============================================================

def has_booking_conflict(
    room,
    event_date,
    start_time,
    end_time,
    exclude_event=None
):
    """
    Checks whether another event has already booked this room.
    """

    events = Event.objects.filter(
        booked_room=room,
        event_date=event_date,
        status="BOOKED"
    )

    # Useful when an existing event is being rescheduled.
    if exclude_event is not None:
        events = events.exclude(pk=exclude_event.pk)

    for existing_event in events:

        if time_overlaps(
            start_time,
            end_time,
            existing_event.start_time,
            existing_event.end_time
        ):
            return True

    return False


# ============================================================
# 4. CHECK REQUIRED FACILITIES
# ============================================================

def room_meets_requirements(room, event):
    """
    Checks whether a room contains all facilities requested
    for an event.
    """

    if event.require_projector and not room.has_projector:
        return False

    if event.require_ac and not room.has_ac:
        return False

    if event.require_wifi and not room.has_wifi:
        return False

    if event.require_audio_system and not room.has_audio_system:
        return False

    if event.require_smart_board and not room.has_smart_board:
        return False

    return True


# ============================================================
# 5. FIND ALL SUITABLE ROOMS
# ============================================================

def get_suitable_rooms(event, strength=None):
    """
    Finds rooms that:

    1. Have enough capacity
    2. Have the required facilities
    3. Do not clash with the college timetable
    4. Do not clash with another booking

    Rooms are ordered from best capacity fit to worst fit.
    """

    if strength is None:
        strength = event.expected_strength

    # Start with active rooms that have enough seats.
    rooms = Room.objects.filter(
        is_active=True,
        capacity__gte=strength
    )

    suitable_rooms = []

    for room in rooms:

        # ---------------------------------------------
        # Required facilities
        # ---------------------------------------------

        if not room_meets_requirements(room, event):
            continue

        # ---------------------------------------------
        # College timetable conflict
        # ---------------------------------------------

        if has_timetable_conflict(
            room,
            event.event_date,
            event.start_time,
            event.end_time
        ):
            continue

        # ---------------------------------------------
        # Existing event booking conflict
        # ---------------------------------------------

        if has_booking_conflict(
            room,
            event.event_date,
            event.start_time,
            event.end_time,
            exclude_event=event
        ):
            continue

        # ---------------------------------------------
        # Capacity score
        # ---------------------------------------------

        unused_seats = room.capacity - strength

        suitable_rooms.append(
            {
                "room": room,
                "unused_seats": unused_seats
            }
        )

    # Smaller number of unused seats = better fit.
    suitable_rooms.sort(
        key=lambda item: item["unused_seats"]
    )

    return suitable_rooms


# ============================================================
# 6. RECOMMEND THE BEST ROOM
# ============================================================

def recommend_room(event, strength=None):
    """
    Returns the best suitable Room object.

    Returns None if no suitable room exists.
    """

    suitable_rooms = get_suitable_rooms(
        event,
        strength=strength
    )

    if not suitable_rooms:
        return None

    return suitable_rooms[0]["room"]