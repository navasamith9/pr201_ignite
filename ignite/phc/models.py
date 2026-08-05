from django.conf import settings
from django.db import models


class DoctorProfile(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        BUSY = 'busy', 'Busy / With Patient'
        BREAK = 'break', 'On Break'
        UNAVAILABLE = 'unavailable', 'Unavailable'

    # A profile may be published before a doctor is provisioned a login account.
    # The optional user link is used only for the private doctor portal.
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True, null=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='doctor_profile',
        blank=True,
        null=True,
    )
    specialization = models.CharField(max_length=120)
    room = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNAVAILABLE)
    status_updated_at = models.DateTimeField(auto_now=True)
    expected_availability = models.CharField(max_length=160, blank=True)
    accepting_patients = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_joinable(self):
        return self.status == self.Status.AVAILABLE and self.accepting_patients


class DoctorSchedule(models.Model):
    class Day(models.TextChoices):
        MONDAY = 'mon', 'Monday'; TUESDAY = 'tue', 'Tuesday'; WEDNESDAY = 'wed', 'Wednesday'
        THURSDAY = 'thu', 'Thursday'; FRIDAY = 'fri', 'Friday'; SATURDAY = 'sat', 'Saturday'; SUNDAY = 'sun', 'Sunday'
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='schedules')
    day = models.CharField(max_length=3, choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    class Meta:
        ordering = ['day', 'start_time']
        constraints = [models.UniqueConstraint(fields=['doctor', 'day', 'start_time'], name='unique_doctor_schedule_slot')]


class DoctorNotificationSubscription(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='phc_notification_subscriptions')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='notification_subscriptions')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(blank=True, null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['student', 'doctor'], name='unique_doctor_notification_subscription')]


class ConsultationQueue(models.Model):
    class Status(models.TextChoices):
        WAITING = 'waiting', 'Waiting'; CALLED = 'called', 'Called'; COMPLETED = 'completed', 'Completed'; SKIPPED = 'skipped', 'Skipped'; CANCELLED = 'cancelled', 'Cancelled'
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='phc_queue_entries')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='queue_entries')
    # Completed/cancelled entries release their token, while active entries
    # keep a compact, live queue number.
    token_number = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING)
    joined_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    class Meta:
        ordering = ['token_number']
        constraints = [models.UniqueConstraint(fields=['doctor', 'token_number'], name='unique_doctor_token'), models.UniqueConstraint(fields=['student', 'doctor'], condition=models.Q(status__in=['waiting', 'called']), name='unique_active_student_doctor_queue')]

    @property
    def students_ahead(self):
        return ConsultationQueue.objects.filter(doctor=self.doctor, status__in=[self.Status.WAITING, self.Status.CALLED], token_number__lt=self.token_number).count()


class PHCAnnouncement(models.Model):
    title = models.CharField(max_length=160)
    message = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='phc_announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)
    class Meta: ordering = ['-created_at']


class PHCSettings(models.Model):
    opening_hours = models.CharField(max_length=255, default='Monday-Saturday, 9:00 AM-5:00 PM')
    phc_phone = models.CharField(max_length=50, blank=True)
    ambulance_phone = models.CharField(max_length=50, blank=True)
    security_phone = models.CharField(max_length=50, blank=True)
    emergency_hospital = models.CharField(max_length=255, blank=True)
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
    @classmethod
    def get_solo(cls): return cls.objects.get_or_create(pk=1)[0]


class PHCNotification(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='phc_notifications')
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)
    class Meta: ordering = ['-created_at']


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='phc_audit_logs')
    action = models.CharField(max_length=160)
    relevant_object = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-timestamp']
