from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login  # Import avec alias pour éviter conflit
from django.contrib.auth import authenticate
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
    context = {'is_home': True}  # Indicateur pour la page d'accueil
    return render(request, "home.html", context)
def employee(request):
    return render(request, "ITservBack/employe_dashboard.html")

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



logger = logging.getLogger(__name__)

class LoginView(View):
    template_name = 'login.html'

    @method_decorator(csrf_protect)
    def get(self, request):
        logger.info("Méthode GET appelée pour afficher la page de login.")
        return render(request, self.template_name)

    @method_decorator(csrf_protect)
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        logger.info(f"Tentative de connexion pour {username} avec rôle {role}")

        try:
            user = User.objects.get(username=username)
            logger.info(f"Username '{username}' trouvé dans auth_user.")

            authenticated_user = authenticate(request, username=username, password=password)
            if authenticated_user is None:
                logger.warning(f"Échec : Mot de passe incorrect pour {username} dans auth_user.")
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
                return render(request, self.template_name)
            else:
                logger.info(f"Mot de passe correct pour {username} dans auth_user.")

            auth_login(request, authenticated_user)
            logger.info(f"Connexion réussie pour {username}")

            try:
                profil = Profil.objects.get(user=authenticated_user)
                poste = profil.poste
                logger.info(f"Poste '{poste}' trouvé pour {username} dans itServ_profil.")
                # Vérifier si le rôle du formulaire correspond au poste de l'utilisateur
                if (role == 'EMPLOYE' and poste != 'EMPLOYE') or (role == 'ResponsableRH' and poste != 'ResponsableRH'):
                    logger.warning(f"Rôle '{role}' ne correspond pas au poste '{poste}' pour {username}.")
                    if role == 'EMPLOYE':
                        messages.error(request,
                                       "Vous êtes un Responsable RH. Veuillez utiliser le formulaire Entreprise.")
                    else:
                        messages.error(request, "Vous êtes un Employé. Veuillez utiliser le formulaire Employé.")
                    return render(request, self.template_name)
                    # Connexion réussie si le rôle correspond
                    auth_login(request, authenticated_user)
                    logger.info(f"Connexion réussie pour {username}")
                if poste == 'admin':
                    logger.info(f"Redirection vers admin_dashboard pour {username}.")
                    return redirect('admin_dashboard')
                elif poste == 'EMPLOYE':
                    logger.info(f"Redirection vers employee pour {username}.")
                    return redirect('employee')  # Notez le nom correct
                elif poste == 'ResponsableRH':
                    logger.info(f"Redirection vers responsablerh_dashboard pour {username}.")
                    return redirect('responsablerh_dashboard')
                else:
                    logger.warning(f"Poste '{poste}' non reconnu pour {username}.")
                    messages.error(request, "Poste non reconnu.")
                    return render(request, self.template_name)

            except Profil.DoesNotExist:
                logger.warning(f"Aucun profil trouvé pour {username} dans itServ_profil.")
                messages.error(request, "Profil non configuré. Contactez l'administrateur.")
                return render(request, self.template_name)

        except User.DoesNotExist:
            logger.warning(f"Utilisateur '{username}' non trouvé dans auth_user.")
            messages.error(request, "Nom d'utilisateur incorrect.")
            return render(request, self.template_name)

# Ajout des vues manquantes
def admin_dashboard(request):
    profil = Profil.objects.get(user=request.user)
    context = {'poste': profil.poste, 'is_home': False, 'segment': 'dashboard'}
    return render(request, 'ITservBack/layouts/base.html', context)

def responsablerh_dashboard(request):
    profil = Profil.objects.get(user=request.user)
    context = {'poste': profil.poste, 'is_home': False, 'segment': 'dashboard'}
    return render(request, 'ITservBack/dashboard_ResponsableRH.html', context)