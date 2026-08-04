from django import forms

from .models import FoundItem, LostItem


class ReportFormMixin:
    """Shared Bootstrap presentation and basic image-size validation."""

    def _style_fields(self):
        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_class} form-control".strip()

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if photo.size > 8 * 1024 * 1024:
            raise forms.ValidationError("Please upload an image smaller than 8 MB.")
        return photo


class LostReportForm(ReportFormMixin, forms.ModelForm):
    class Meta:
        model = LostItem
        fields = (
            "reporter_name",
            "roll_number",
            "item_name",
            "photo",
            "contact_details",
            "lost_place",
        )
        labels = {
            "reporter_name": "Your name",
            "item_name": "Item lost",
            "photo": "Photo of the item",
            "contact_details": "Contact details",
            "lost_place": "Where was it lost?",
        }
        widgets = {
            "reporter_name": forms.TextInput(attrs={"placeholder": "Your full name"}),
            "roll_number": forms.TextInput(attrs={"placeholder": "e.g. 23CS001"}),
            "item_name": forms.TextInput(attrs={"placeholder": "e.g. Black water bottle"}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "contact_details": forms.TextInput(attrs={"placeholder": "Phone number or email"}),
            "lost_place": forms.TextInput(attrs={"placeholder": "e.g. Central library, second floor"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class FoundReportForm(ReportFormMixin, forms.ModelForm):
    class Meta:
        model = FoundItem
        fields = ("reporter_name", "roll_number", "contact_details", "photo")
        labels = {
            "reporter_name": "Your name",
            "contact_details": "Contact details",
            "photo": "Photo of the item you found",
        }
        widgets = {
            "reporter_name": forms.TextInput(attrs={"placeholder": "Your full name"}),
            "roll_number": forms.TextInput(attrs={"placeholder": "e.g. 23CS001"}),
            "contact_details": forms.TextInput(attrs={"placeholder": "Phone number or email"}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class FinderDetailsForm(forms.Form):
    finder_name = forms.CharField(
        max_length=120,
        label="Your name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Your full name"}),
    )
    finder_contact = forms.CharField(
        max_length=160,
        label="Your contact details",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone number or email"}),
    )
