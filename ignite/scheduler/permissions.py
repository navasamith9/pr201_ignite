from rest_framework.permissions import BasePermission


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

        # Event creator/coordinator
        if obj.created_by_id == user.id:
            return True

        # Check coordinator/co-coordinator list
        if obj.coordinators.filter(id=user.id).exists():
            return True

        return False