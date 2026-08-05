from django.urls import path

from . import views


urlpatterns = [
    # Room and timetable administration (staff only for write operations)
    path("rooms/", views.rooms, name="rooms"),
    path("rooms/<int:room_id>/", views.room_detail, name="room-detail"),
    path("timetable/", views.timetable, name="timetable"),
    path("timetable/<int:entry_id>/", views.timetable_detail, name="timetable-detail"),

    # Events the current user owns or coordinates
    path(
        "events/",
        views.list_events,
        name="list-events",
    ),
    path("events/campus/", views.campus_events, name="campus-events"),
    path("events/availability/", views.availability, name="availability"),

    # Events students can currently register for
    path("events/open/", views.open_events, name="open-events"),
    path("access/", views.scheduler_access, name="scheduler-access"),
    path("notifications/", views.my_notifications, name="scheduler-notifications"),
    path("coordinator-permissions/", views.coordinator_permissions, name="coordinator-permissions"),
    path(
        "coordinator-permissions/<int:permission_id>/",
        views.coordinator_permission_detail,
        name="coordinator-permission-detail",
    ),

    # One event and its booking history
    path("events/<int:event_id>/", views.event_detail, name="event-detail"),
    path("events/<int:event_id>/history/", views.booking_history, name="booking-history"),

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
