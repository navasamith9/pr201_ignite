from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from scheduler.email_services import send_event_reminder
from scheduler.models import BookingHistory, Event


class Command(BaseCommand):
    help = "Sends one final reminder to registered attendees before an event."

    def handle(self, *args, **options):
        now = timezone.now()
        reminder_limit = now + timedelta(days=1)
        candidates = Event.objects.filter(
            status="BOOKED",
            registration_closed=True,
            event_reminder_sent=False,
            event_date__gte=now.date(),
            event_date__lte=reminder_limit.date(),
        ).select_related("booked_room").prefetch_related("registrations__user")

        sent_events = 0
        for event in candidates:
            event_start = timezone.make_aware(
                datetime.combine(event.event_date, event.start_time),
                timezone.get_current_timezone(),
            )
            if not now < event_start <= reminder_limit:
                continue

            recipients = [registration.user for registration in event.registrations.all()]
            sent_count = send_event_reminder(event, recipients)
            event.event_reminder_sent = True
            event.save(update_fields=["event_reminder_sent", "updated_at"])
            BookingHistory.objects.create(
                event=event,
                action="EVENT_REMINDER_SENT",
                notes="Final reminder sent to registered attendees.",
            )
            sent_events += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"{event.title}: final reminder processed for {sent_count} email(s)."
                )
            )

        if not sent_events:
            self.stdout.write(self.style.SUCCESS("No event reminders need to be sent."))
