from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        FACULTY = 'faculty', 'Faculty'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(max_length=10, choices=Role.choices, blank=True)
    branch = models.CharField(max_length=50, blank=True)
    academic_year = models.PositiveSmallIntegerField(null=True, blank=True)
    # Service-level roles can be combined without granting site-wide admin
    # access.  The global ``role=ADMIN`` remains the full Ignite admin role.
    is_lhtc_admin = models.BooleanField(default=False)
    is_phc_admin = models.BooleanField(default=False)
    is_bus_admin = models.BooleanField(default=False)
    is_canteen_admin = models.BooleanField(default=False)
    # Preserve the original account state when global admin access is granted
    # through Ignite, so revoking it restores the user's normal role.
    is_global_admin_grant = models.BooleanField(default=False)
    global_admin_previous_role = models.CharField(max_length=10, blank=True)
    global_admin_previous_staff = models.BooleanField(default=False)

    def __str__(self):
        return self.email or self.username
