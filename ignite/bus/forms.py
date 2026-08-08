from django import forms

from .models import BusSchedule


class BusScheduleForm(forms.ModelForm):
    """Schedule form used by transport administrators."""

    class Meta:
        model = BusSchedule
        fields = ('name', 'route', 'day', 'departure_time', 'price', 'max_capacity', 'active')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Campus Express'}),
            'route': forms.Select(attrs={'class': 'form-select'}),
            'day': forms.Select(attrs={'class': 'form-select'}),
            'departure_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'max_capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 40}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
