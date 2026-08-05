from django.contrib import admin
from .models import AuditLog, ConsultationQueue, DoctorNotificationSubscription, DoctorProfile, DoctorSchedule, PHCAnnouncement, PHCNotification, PHCSettings

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'specialization', 'room', 'status', 'accepting_patients', 'active')
    list_filter = ('status', 'active', 'accepting_patients')
    search_fields = ('name', 'user__username', 'user__first_name', 'user__last_name', 'specialization')
    fieldsets = (
        ('Doctor details', {'fields': ('name', 'specialization', 'room')}),
        ('Availability', {'fields': ('status', 'expected_availability', 'accepting_patients', 'active')}),
        ('Portal access (optional)', {'fields': ('user',), 'description': 'Only select an existing account when this doctor needs access to the private doctor portal.'}),
    )

admin.site.register([DoctorSchedule, ConsultationQueue, DoctorNotificationSubscription, PHCAnnouncement, PHCNotification, AuditLog])

@admin.register(PHCSettings)
class PHCSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return not PHCSettings.objects.exists()
    def has_delete_permission(self, request, obj=None): return False
