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
    must_change_password = models.BooleanField(default=True)
    first_login = models.DateTimeField(null=True, blank=True)  # Champ existant pour la première connexion
    last_authentication = models.DateTimeField(null=True, blank=True)  # Nouveau champ pour la dernière authentification

    def __str__(self):
        return f"{self.user.username} - {self.poste}"

class UserLoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    login_time = models.DateTimeField(auto_now_add=True)  # Date et heure de la connexion
    poste = models.CharField(max_length=20)  # Stocke le poste au moment de la connexion

    def __str__(self):
        return f"{self.user.username} - {self.login_time}"