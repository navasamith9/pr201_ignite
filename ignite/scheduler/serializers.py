from datetime import datetime

from rest_framework import serializers
from django.utils import timezone

from .models import (
    Room,
    TimetableEntry,
    Event,
    EventRegistration,
    BookingHistory,
)


# ============================================================
# 1. ROOM SERIALIZER
# ============================================================

class RoomSerializer(serializers.ModelSerializer):

    class Meta:
        model = Room
        fields = [
            "id",
            "name",
            "building",
            "floor",
            "capacity",
            "has_projector",
            "has_ac",
            "has_wifi",
            "has_audio_system",
            "has_smart_board",
            "is_active",
        ]

        read_only_fields = ["id"]


# ============================================================
# 2. TIMETABLE SERIALIZER
# ============================================================

class TimetableEntrySerializer(serializers.ModelSerializer):

    room_name = serializers.CharField(
        source="room.name",
        read_only=True
    )

    class Meta:
        model = TimetableEntry

        fields = [
            "id",
            "room",
            "room_name",
            "day_of_week",
            "start_time",
            "end_time",
            "branch",
            "year",
            "subject",
        ]

        read_only_fields = ["id"]

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({
                "end_time": "End time must be after start time."
            })
        return attrs


# ============================================================
# 3. EVENT SERIALIZER
# ============================================================

class EventSerializer(serializers.ModelSerializer):

    booked_room_details = RoomSerializer(
        source="booked_room",
        read_only=True
    )

    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True
    )

    registered_strength = serializers.SerializerMethodField()

    class Meta:
        model = Event

        fields = [
            "id",
            "title",
            "event_type",
            "purpose",
            "expected_strength",
            "registered_strength",
            "branches",
            "years",
            "event_date",
            "start_time",
            "end_time",
            "registration_deadline",

            "require_projector",
            "require_ac",
            "require_wifi",
            "require_audio_system",
            "require_smart_board",

            "booked_room",
            "booked_room_details",

            "created_by",
            "created_by_username",

            "coordinators",

            "status",
            "registration_closed",

            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_by",
            "coordinators",
            "booked_room",
            "status",
            "registration_closed",
            "created_at",
            "updated_at",
        ]

    def get_registered_strength(self, obj):
        return obj.registrations.count()

    def validate(self, attrs):
        """
        Basic event validation.
        """

        start_time = attrs.get(
            "start_time",
            getattr(self.instance, "start_time", None)
        )

        end_time = attrs.get(
            "end_time",
            getattr(self.instance, "end_time", None)
        )

        expected_strength = attrs.get(
            "expected_strength",
            getattr(self.instance, "expected_strength", None)
        )

        if (
            start_time is not None
            and end_time is not None
            and start_time >= end_time
        ):
            raise serializers.ValidationError({
                "end_time":
                    "End time must be after start time."
            })

        if (
            expected_strength is not None
            and expected_strength <= 0
        ):
            raise serializers.ValidationError({
                "expected_strength":
                "Expected strength must be greater than zero."
            })

        registration_deadline = attrs.get(
            "registration_deadline",
            getattr(self.instance, "registration_deadline", None),
        )
        event_date = attrs.get("event_date", getattr(self.instance, "event_date", None))

        if (
            "registration_deadline" in attrs
            and registration_deadline
            and registration_deadline <= timezone.now()
        ):
            raise serializers.ValidationError({
                "registration_deadline":
                "Registration deadline must be in the future."
            })

        if registration_deadline and event_date and start_time:
            event_start = timezone.make_aware(
                datetime.combine(event_date, start_time),
                timezone.get_current_timezone(),
            )
            if event_start <= timezone.now():
                raise serializers.ValidationError({
                    "event_date": "Bookings can only be created or changed before the event starts."
                })
            if (
                registration_deadline >= event_start
                and not getattr(self.instance, "registration_closed", False)
            ):
                raise serializers.ValidationError({
                    "registration_deadline":
                    "Registration must close before the event starts."
                })

        branches = attrs.get("branches", getattr(self.instance, "branches", []))
        if not isinstance(branches, list) or not all(isinstance(branch, str) for branch in branches):
            raise serializers.ValidationError({"branches": "Use a list of branch names."})

        years = attrs.get("years", getattr(self.instance, "years", []))
        if (
            not isinstance(years, list)
            or not all(isinstance(year, int) and 1 <= year <= 5 for year in years)
        ):
            raise serializers.ValidationError({"years": "Use academic years from 1 to 5."})

        return attrs


# ============================================================
# 4. EVENT REGISTRATION SERIALIZER
# ============================================================

class EventRegistrationSerializer(
    serializers.ModelSerializer
):

    event_title = serializers.CharField(
        source="event.title",
        read_only=True
    )

    user_username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    class Meta:
        model = EventRegistration

        fields = [
            "id",
            "event",
            "event_title",
            "user",
            "user_username",
            "registered_at",
        ]

        read_only_fields = [
            "id",
            "user",
            "registered_at",
        ]


# ============================================================
# 5. BOOKING HISTORY SERIALIZER
# ============================================================

class BookingHistorySerializer(
    serializers.ModelSerializer
):

    old_room_name = serializers.CharField(
        source="old_room.name",
        read_only=True
    )

    new_room_name = serializers.CharField(
        source="new_room.name",
        read_only=True
    )

    changed_by_username = serializers.CharField(
        source="changed_by.username",
        read_only=True
    )

    class Meta:
        model = BookingHistory

        fields = [
            "id",
            "event",
            "action",

            "old_room",
            "old_room_name",

            "new_room",
            "new_room_name",

            "changed_by",
            "changed_by_username",

            "notes",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]


# ============================================================
# 6. ROOM RECOMMENDATION SERIALIZER
# ============================================================

class RoomRecommendationSerializer(serializers.Serializer):
    """
    Used when returning room recommendations.
    """

    room = RoomSerializer(
        read_only=True
    )

    unused_seats = serializers.IntegerField(
        read_only=True
    )
