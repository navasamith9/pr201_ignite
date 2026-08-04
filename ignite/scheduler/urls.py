from django.urls import path

from . import views


urlpatterns = [
    # Create a new event
    path(
        "events/create/",
        views.create_event,
        name="create-event",
    ),

    # Get recommended rooms
    path(
        "events/<int:event_id>/recommend/",
        views.recommend_rooms,
        name="recommend-rooms",
    ),

    # Confirm/book the recommended room
    path(
        "events/<int:event_id>/book/",
        views.confirm_booking,
        name="confirm-booking",
    ),

    # Student registers for event
    path(
        "events/<int:event_id>/register/",
        views.register_event,
        name="register-event",
    ),

    # Student cancels their registration
    path(
        "events/<int:event_id>/unregister/",
        views.unregister_event,
        name="unregister-event",
    ),

    # Coordinator cancels entire booking
    path(
        "events/<int:event_id>/cancel/",
        views.cancel_booking,
        name="cancel-booking",
    ),

    # Coordinator changes date/time/strength/etc.
    path(
        "events/<int:event_id>/reschedule/",
        views.reschedule_event,
        name="reschedule-event",
    ),
]