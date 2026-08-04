from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from scheduler.models import Event, BookingHistory
from scheduler.services import recommend_room
from scheduler.email_services import send_room_change_notification

class Command(BaseCommand):
    help = (
        "Closes expired event registrations and "
        "recalculates the best room."
    )

    def handle(self, *args, **options):

        now = timezone.now()

        events = Event.objects.filter(
            status="BOOKED",
            registration_closed=False,
            registration_deadline__lte=now,
        )

        if not events.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    "No registrations need to be closed."
                )
            )
            return

        for event in events:

            with transaction.atomic():

                event = Event.objects.select_for_update().get(
                    pk=event.pk
                )

                # Check again after obtaining the database lock.
                if event.registration_closed:
                    continue

                registered_strength = (
                    event.registrations.count()
                )

                old_room = event.booked_room

                # Registration is now officially closed.
                event.registration_closed = True
                event.save(
                    update_fields=[
                        "registration_closed",
                        "updated_at",
                    ]
                )

                # If nobody registered, keep the existing room.
                if registered_strength == 0:

                    self.stdout.write(
                        self.style.WARNING(
                            f"{event.title}: registration closed "
                            f"with 0 registrations. "
                            f"Existing room kept."
                        )
                    )

                    continue

                # Temporarily use actual registered strength
                # when calculating the best room.
                original_strength = event.expected_strength

                event.expected_strength = registered_strength

                new_room = recommend_room(event)

                # Restore the originally estimated strength.
                event.expected_strength = original_strength

                if new_room is None:

                    self.stdout.write(
                        self.style.ERROR(
                            f"{event.title}: registration closed "
                            f"with {registered_strength} students, "
                            f"but no suitable room is available."
                        )
                    )

                    continue

                if old_room != new_room:

                    event.booked_room = new_room

                    event.save(
                        update_fields=[
                            "booked_room",
                            "updated_at",
                        ]
                    )

                    BookingHistory.objects.create(
                        event=event,
                        action="AUTO_ROOM_CHANGED",
                        old_room=old_room,
                        new_room=new_room,
                        changed_by=None,
                        notes=(
                            "Room automatically changed after "
                            "registration closed. Final registered "
                            f"strength: {registered_strength}."
                        ),
                    )

                    # Get all users who registered for this event
                    registered_users = [
                        registration.user
                        for registration in event.registrations.select_related("user")
                    ]

                    # Notify registered participants about the room change
                    send_room_change_notification(
                        event=event,
                        recipients=registered_users,
                        old_room=old_room,
                        new_room=new_room,
                    )
                    
                    old_name = (
                        old_room.name
                        if old_room
                        else "None"
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{event.title}: "
                            f"{old_name} -> {new_room.name} "
                            f"({registered_strength} registrations)"
                        )
                    )

                else:

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{event.title}: registration closed. "
                            f"{registered_strength} registrations. "
                            f"Room remains {old_room.name}."
                        )
                    )