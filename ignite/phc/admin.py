from django.contrib import admin
from .models import AuditLog, ConsultationQueue, DoctorNotificationSubscription, DoctorProfile, DoctorSchedule, PHCAnnouncement, PHCNotification, PHCSettings

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'user', 'specialization', 'room', 'status', 'accepting_patients')
    list_filter = ('status', 'accepting_patients')
    search_fields = ('name', 'email', 'user__username', 'user__first_name', 'user__last_name', 'specialization')
    fieldsets = (
        ('Doctor details', {'fields': ('name', 'email', 'specialization', 'room')}),
        ('Availability', {'fields': ('status', 'expected_availability', 'accepting_patients')}),
        ('Portal access', {'fields': ('user',), 'description': 'Linked automatically when a doctor logs in with the email above.'}),
    )

admin.site.register([DoctorSchedule, ConsultationQueue, DoctorNotificationSubscription, PHCAnnouncement, PHCNotification, AuditLog])

@admin.register(PHCSettings)
class PHCSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return not PHCSettings.objects.exists()
    def has_delete_permission(self, request, obj=None): return False
