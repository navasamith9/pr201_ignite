from django import forms
from django.contrib.auth import get_user_model

from .models import DoctorProfile, DoctorSchedule, PHCAnnouncement, PHCSettings


class DoctorProfileForm(forms.ModelForm):
    """Admin-facing doctor form; the account association is deliberately optional."""
    class Meta:
        model = DoctorProfile
        fields = ('name', 'email', 'specialization', 'room')
        widgets = {
            'expected_availability': forms.TextInput(attrs={'placeholder': 'e.g. Available after 3:00 PM'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['email'].help_text = 'The doctor must sign in using this same institute email address.'

    def save(self, commit=True):
        """An edited email must never keep the old doctor's account link."""
        doctor = super().save(commit=False)
        if doctor.user_id and (doctor.user.email or '').casefold() != doctor.email.casefold():
            doctor.user = None
        if commit:
            doctor.save()
            self.save_m2m()
        return doctor


class DoctorScheduleForm(forms.ModelForm):
    class Meta:
        model = DoctorSchedule
        fields = ('doctor', 'day', 'start_time', 'end_time')
        widgets = {'start_time': forms.TimeInput(attrs={'type': 'time'}), 'end_time': forms.TimeInput(attrs={'type': 'time'})}


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = PHCAnnouncement
        fields = ('title', 'message', 'expires_at', 'active')
        widgets = {'expires_at': forms.DateTimeInput(attrs={'type': 'datetime-local'})}


class PHCSettingsForm(forms.ModelForm):
    class Meta:
        model = PHCSettings
        fields = ('opening_hours', 'phc_phone', 'ambulance_phone', 'security_phone', 'emergency_hospital')
