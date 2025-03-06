from django.db import models
from django.contrib.auth.models import User

class Profil(models.Model):
    POSTE_CHOICES = [
        ('EMPLOYE', 'Employé'),
        ('ResponsableRH', 'Responsable RH'),
        ('admin', 'Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=10)
    adresse = models.TextField()
    poste = models.CharField(max_length=20, choices=POSTE_CHOICES)
    must_change_password = models.BooleanField(default=True)  # Nouveau champ, True par défaut pour les nouveaux utilisateurs

    def __str__(self):
        return f"{self.user.username} - {self.poste}"