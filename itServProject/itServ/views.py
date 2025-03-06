from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from .models import Profil
from django.core.mail import send_mail
import secrets
import string
import logging

logger = logging.getLogger(__name__)

def home(request):
    return render(request, "home.html")

def login(request):  # Renommé pour éviter le conflit avec la fonction login importée
    return render(request, "login.html")

def homeback(request):
    return render(request, "ITservBack/layouts/base.html")

class SignupView(View):
    template_name = 'ITservBack/login/signup.html'

    @method_decorator(csrf_protect)
    def get(self, request):
        return render(request, self.template_name)

    @method_decorator(csrf_protect)
    def post(self, request):
        # Récupérer les données du formulaire (sans username)
        email = request.POST.get('email')
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        tel = request.POST.get('tel')
        adresse = request.POST.get('adresse')
        poste = request.POST.get('poste')

        # Génération automatique du username
        alphabet = string.ascii_lowercase + string.digits
        username = ''.join(secrets.choice(alphabet) for _ in range(8))
        while User.objects.filter(username=username).exists():
            username = ''.join(secrets.choice(alphabet) for _ in range(8))

        # Génération automatique du password
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for _ in range(12))

        logger.info(f"Tentative de création de compte pour {username} ({email})")

        try:
            # Création de l'utilisateur dans auth_user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # Création du profil associé
            profil = Profil.objects.create(
                user=user,
                nom=nom,
                prenom=prenom,
                telephone=tel,
                adresse=adresse,
                poste=poste
            )

            # Envoi de l'email avec les identifiants
            subject = "Bienvenue - Vos identifiants de connexion"
            message = (
                f"Bonjour {prenom} {nom},\n\n"
                f"Votre compte a été créé avec succès. Voici vos identifiants :\n"
                f"Nom d'utilisateur : {username}\n"
                f"Mot de passe : {password}\n\n"
                f"Veuillez vous connecter à l'adresse suivante : http://127.0.0.1:8000/login/\n"
                f"Nous vous recommandons de changer votre mot de passe après votre première connexion.\n\n"
                f"Cordialement,\nL'équipe ITserv"
            )
            from_email = 'oussama21072000@gmail.com'
            recipient_list = [email]

            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=from_email,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Email envoyé avec succès à {email}")
            except Exception as e:
                logger.error(f"Échec de l'envoi de l'email à {email} : {str(e)}")
                messages.error(request, f"Erreur lors de l'envoi de l'email : {str(e)}")
                return render(request, self.template_name)

            messages.success(request, "Inscription réussie ! Un email avec les identifiants a été envoyé.")
            return redirect('home')

        except Exception as e:
            logger.error(f"Erreur lors de la création du compte : {str(e)}")
            messages.error(request, f"Une erreur s'est produite : {str(e)}")
            return render(request, self.template_name)

class LoginView(View):
    template_name = 'ITservBack/login/login.html'  # Votre template

    @method_decorator(csrf_protect)
    def get(self, request):
        return render(request, self.template_name)

    @method_decorator(csrf_protect)
    def post(self, request):
        username = request.POST.get('username')
        role = request.POST.get('role')  # Récupérer le rôle depuis le formulaire

        logger.info(f"Tentative de connexion pour {username} avec rôle {role}")

        try:
            # Vérifier si l'utilisateur existe
            user = User.objects.get(username=username)
            # Récupérer le mot de passe stocké dans auth_user (il a été généré automatiquement)
            password = user.password  # Note : C'est haché, on ne peut pas l'utiliser directement

            # Authentifier avec le username et le mot de passe stocké (Django gère le hachage)
            user = authenticate(request, username=username, password=None)  # On ne passe pas de mot de passe ici
            if user is None:
                # Si l'authentification échoue, on tente avec le mot de passe généré (mais il faut le récupérer autrement si modifié)
                logger.warning(f"Échec initial de l'authentification pour {username}")
                messages.error(request, "Erreur d'authentification. Utilisez le mot de passe envoyé par email.")
                return render(request, self.template_name)

            login(request, user)
            logger.info(f"Connexion réussie pour {username}")

            try:
                profil = Profil.objects.get(user=user)
                poste = profil.poste.lower()

                # Redirection basée sur le rôle et le poste
                if role == 'entreprise' and poste == 'responsablerh':
                    messages.success(request, "Bienvenue, Responsable RH !")
                    return redirect('client_dashboard')
                elif role == 'employe' and poste == 'employe':
                    messages.success(request, "Bienvenue, Employé !")
                    return redirect('technicien_dashboard')
                elif poste == 'admin':
                    messages.success(request, "Bienvenue, Administrateur !")
                    return redirect('admin_dashboard')
                else:
                    messages.error(request, "Rôle non autorisé pour ce formulaire.")
                    return render(request, self.template_name)

            except Profil.DoesNotExist:
                logger.warning(f"Aucun profil trouvé pour {username}")
                messages.error(request, "Profil non configuré. Contactez l'administrateur.")
                return render(request, self.template_name)

        except User.DoesNotExist:
            logger.warning(f"Utilisateur {username} non trouvé")
            messages.error(request, "Nom d'utilisateur incorrect.")
            return render(request, self.template_name)

def admin_dashboard(request):
    profil = Profil.objects.get(user=request.user)
    context = {'poste': profil.poste.lower(), 'segment': 'dashboard'}
    return render(request, 'ITservBack/layouts/base.html', context)

def EMPLOYE_dashboard(request):
    profil = Profil.objects.get(user=request.user)
    context = {'poste': profil.poste.lower(), 'segment': 'dashboard'}
    return render(request, 'ITservBack/layouts/base.html', context)

def ResponsableRH_dashboard(request):
    profil = Profil.objects.get(user=request.user)
    context = {'poste': profil.poste.lower(), 'segment': 'dashboard'}
    return render(request, 'ITservBack/layouts/base.html', context)