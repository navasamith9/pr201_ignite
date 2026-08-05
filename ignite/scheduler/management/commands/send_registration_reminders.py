from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from scheduler.models import BookingHistory, Event
from scheduler.email_services import send_registration_reminder
from scheduler.services import student_recipients_for


class Command(BaseCommand):
    help = "Sends reminders for event registrations closing soon."

    def handle(self, *args, **options):

        now = timezone.now()

        # For now, send reminders when the deadline
        # is within the next 24 hours.
        reminder_limit = now + timedelta(hours=24)

        events = Event.objects.filter(
            status="BOOKED",
            registration_closed=False,
            registration_reminder_sent=False,
            registration_deadline__gt=now,
            registration_deadline__lte=reminder_limit,
        )

        if not events.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    "No registration reminders need to be sent."
                )
            )
            return

        for event in events:

            recipients = student_recipients_for(event)

            sent_count = send_registration_reminder(
                event=event,
                recipients=recipients,
            )

            event.registration_reminder_sent = True

            event.save(
                update_fields=[
                    "registration_reminder_sent",
                    "updated_at",
                ]   
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{event.title}: "
                    f"registration reminder processed "
                    f"for {sent_count} email(s)."
                )
            )
            BookingHistory.objects.create(
                event=event,
                action="REGISTRATION_REMINDER_SENT",
                notes="Registration closes within 24 hours.",
            )
