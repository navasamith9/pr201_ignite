from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Runs all scheduler deadline, reassignment, and reminder tasks."

    def handle(self, *args, **options):
        call_command("send_registration_reminders")
        call_command("close_registrations")
        call_command("send_event_reminders")
        self.stdout.write(self.style.SUCCESS("Scheduler notification cycle completed."))
