# itServ/forms.py
from django import forms
from .models import TypeConge
from django.utils import timezone

class LeaveRequestForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'readonly': 'readonly'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    type_conge = forms.ModelChoiceField(queryset=TypeConge.objects.filter(flag_active=True), empty_label=None)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError("La date de fin doit être postérieure à la date de début.")
            if start_date < timezone.now().date():
                raise forms.ValidationError("La date de début ne peut pas être dans le passé.")
        return cleaned_data