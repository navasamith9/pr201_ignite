from rest_framework.permissions import BasePermission


FACULTY_EMAILS = {
    "pkhanna@iiitdmj.ac.in",
    "sraban@iiitdmj.ac.in",
    "mkbajpai@iiitdmj.ac.in",
    "ayan@iiitdmj.ac.in",
    "ranjeet.kr@iiitdmj.ac.in",
    "neelam.dayal@iiitdmj.ac.in",
    "durgesh@iiitdmj.ac.in",
}


def is_scheduler_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.is_staff or user.role == user.Role.ADMIN)
    )


def is_faculty(user):
    return bool(
        user
        and user.is_authenticated
        and (user.role == user.Role.FACULTY or user.email.lower() in FACULTY_EMAILS)
    )


def can_book_rooms(user):
    """Faculty, scheduler administrators, and approved student coordinators."""
    if not user or not user.is_authenticated:
        return False
    if is_scheduler_admin(user) or is_faculty(user):
        return True
    return getattr(getattr(user, "room_booking_permission", None), "is_active", False)


class IsEventCoordinator(BasePermission):
    """
    Allows event modifications only when the logged-in user is:

    1. The user who created the event, OR
    2. One of the event's coordinators/co-coordinators.
    """

    message = (
        "Only the event coordinator or co-coordinator "
        "can modify this booking."
    )

    def has_object_permission(self, request, view, obj):

        user = request.user

        # User must be logged in
        if not user or not user.is_authenticated:
            return False

        if is_scheduler_admin(user):
            return True

        if not can_book_rooms(user):
            return False

        # Event creator/coordinator
        if obj.created_by_id == user.id:
            return True

        # Check coordinator/co-coordinator list
        if obj.coordinators.filter(id=user.id).exists():
            return True

        return False
