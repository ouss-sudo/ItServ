# itServ/forms.py
from django import forms
from .models import TypeConge
from django.utils import timezone
from itServ.models import Profil, Societe
from django.contrib.auth.models import User


class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, label="Nom d'utilisateur", widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true'}))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={'class': 'form-control', 'required': 'true'}))
    nom = forms.CharField(max_length=100, label="Nom", widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true'}))
    prenom = forms.CharField(max_length=100, label="Prénom", widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true'}))
    telephone = forms.CharField(max_length=10, label="Téléphone", widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true'}))
    adresse = forms.CharField(label="Adresse", widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': 'true'}))
    company_name = forms.CharField(max_length=255, label="Nom de l'entreprise", widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'true'}))
    company_adresse = forms.CharField(label="Adresse de l'entreprise", required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    company_location = forms.CharField(label="Localisation (latitude,longitude)", required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: 48.8566,2.3522'}))
    employee_limit = forms.IntegerField(label="Limite d'employés", min_value=1, initial=10, widget=forms.NumberInput(attrs={'class': 'form-control', 'required': 'true'}))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ce nom d'utilisateur est déjà pris.")
        return username
class SocieteForm(forms.ModelForm):
    class Meta:
        model = Societe
        fields = ['nom', 'adresse', 'location_societe', 'rayon_acceptable']
        labels = {
            'nom': 'Nom de l\'entreprise',
            'adresse': 'Adresse',
            'location_societe': 'Localisation (latitude,longitude)',
            'rayon_acceptable': 'Rayon acceptable (mètres)',
        }
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'adresse': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'location_societe': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'rayon_acceptable': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg', 'min': 0}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            profil = user.profil
            if profil.societe:
                self.fields['nom'].initial = profil.societe.nom
        except AttributeError:
            pass
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