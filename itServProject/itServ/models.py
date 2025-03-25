from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

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
    # Ajout des champs de suivi
    date_creation = models.DateTimeField(default=now)  # Use default instead of auto_now_add
    date_maj = models.DateTimeField(auto_now=True)  # Date de la dernière modification
    def __str__(self):
        return f"{self.user.username} - {self.poste}"

class UserLoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    login_time = models.DateTimeField(auto_now_add=True)  # Date et heure de la connexion
    poste = models.CharField(max_length=20)  # Stocke le poste au moment de la connexion

    def __str__(self):
        return f"{self.user.username} - {self.login_time}"
class TypeConge(models.Model):
    id = models.AutoField(primary_key=True)
    type = models.CharField(max_length=100, unique=True)
    flag_active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(default=now)
    date_maj = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.type

class Conge(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    type_conge = models.ForeignKey(TypeConge, on_delete=models.SET_NULL, null=True, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('En attente', 'En attente'),
            ('Approuvé', 'Approuvé'),
            ('Refusé', 'Refusé'),
        ],
        default='En attente'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.username} - {self.start_date} to {self.end_date} ({self.status})"
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification pour {self.user.username} - {self.created_at}"

class TypeAbsence(models.Model):
    type = models.CharField(max_length=100, unique=True)
    flag_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.type


class Absence(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
    )

    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    type_absence = models.ForeignKey(TypeAbsence, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='absence_images/', null=True, blank=True)  # Nouveau champ pour l'image


    def __str__(self):
        return f"{self.employee.username} - {self.type_absence.type} - {self.start_date}"
class Pointage(models.Model):
    employe = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pointages', verbose_name="Employé")
    heure_entree = models.DateTimeField(null=True, blank=True, verbose_name="Heure d'entrée")
    heure_sortie = models.DateTimeField(null=True, blank=True, verbose_name="Heure de sortie")
    date = models.DateField(default=now, verbose_name="Date")
    cree_le = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    mis_a_jour_le = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    def __str__(self):
        return f"{self.employe.username} - {self.date} - Entrée: {self.heure_entree}, Sortie: {self.heure_sortie}"

    class Meta:
        verbose_name = "Pointage"
        verbose_name_plural = "Pointages"