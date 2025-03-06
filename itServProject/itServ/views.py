from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from .models import Profil
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
import secrets
import string
import logging


logger = logging.getLogger(__name__)

def home(request):
    context = {'is_home': True}  # Indicateur pour la page d'accueil
    return render(request, "home.html", context)
def employee(request):
    return render(request, "ITservBack/employe_dashboard.html")
def logout_view(request):  # Nouvelle vue pour la déconnexion
    auth_logout(request)  # Déconnecte l'utilisateur
    logger.info("Utilisateur déconnecté avec succès.")
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('home')
def login(request):  # Renommé pour éviter le conflit avec la fonction login importée
    context = {'is_home': True}  # Indicateur pour la page d'accueil
    return render(request, "login.html",context)

def homeback(request):
    return render(request, "ITservBack/layouts/base.html")
# Ajout des vues manquantes
def admin_dashboard(request):
    profil = Profil.objects.get(user=request.user)
    context = {'poste': profil.poste, 'is_home': False, 'segment': 'dashboard'}
    return render(request, 'ITservBack/layouts/base.html', context)

def responsablerh_dashboard(request):
    profil = Profil.objects.get(user=request.user)
    context = {'poste': profil.poste, 'is_home': False, 'segment': 'dashboard'}
    return render(request, 'ITservBack/dashboard_ResponsableRH.html', context)
class SignupView(View):
    template_name = 'ITservBack/login/signup.html'

    @method_decorator(csrf_protect)
    def get(self, request):
        return render(request, self.template_name)

    @method_decorator(csrf_protect)
    def post(self, request):
        email = request.POST.get('email')
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        tel = request.POST.get('tel')
        adresse = request.POST.get('adresse')
        poste = request.POST.get('poste')

        alphabet = string.ascii_lowercase + string.digits
        username = ''.join(secrets.choice(alphabet) for _ in range(8))
        while User.objects.filter(username=username).exists():
            username = ''.join(secrets.choice(alphabet) for _ in range(8))

        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for _ in range(12))

        logger.info(f"Tentative de création de compte pour {username} ({email})")

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            Profil.objects.create(
                user=user,
                nom=nom,
                prenom=prenom,
                telephone=tel,
                adresse=adresse,
                poste=poste,
                must_change_password=True  # Déjà True par défaut, mais explicite pour clarté
            )

            subject = "Bienvenue - Vos identifiants de connexion"
            message = (
                f"Bonjour {prenom} {nom},\n\n"
                f"Votre compte a été créé avec succès. Voici vos identifiants :\n"
                f"Nom d'utilisateur : {username}\n"
                f"Mot de passe : {password}\n\n"
                f"Veuillez vous connecter à : http://127.0.0.1:8000/login/\n"
                f"Vous devrez changer votre mot de passe lors de votre première connexion.\n\n"
                f"Cordialement,\nL'équipe ITserv"
            )
            from_email = 'oussama21072000@gmail.com'
            recipient_list = [email]

            try:
                send_mail(subject, message, from_email, recipient_list, fail_silently=False)
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

            try:
                profil = Profil.objects.get(user=authenticated_user)
                poste = profil.poste
                logger.info(f"Poste '{poste}' trouvé pour {username} dans itServ_profil.")


                if (role == 'EMPLOYE' and poste != 'EMPLOYE') or (role == 'ResponsableRH' and poste != 'ResponsableRH'):
                    logger.warning(f"Rôle '{role}' ne correspond pas au poste '{poste}' pour {username}.")
                    if role == 'EMPLOYE':
                        messages.error(request,
                                       "Vous êtes un Responsable RH. Veuillez utiliser le formulaire Entreprise.")
                    else:
                        messages.error(request, "Vous êtes un Employé. Veuillez utiliser le formulaire Employé.")
                    return render(request, self.template_name)

                auth_login(request, authenticated_user)
                logger.info(f"Connexion réussie pour {username}")

                # Vérifier si c'est la première connexion
                if profil.must_change_password:
                    logger.info(f"Première connexion détectée pour {username}, redirection vers changer_password.")
                    return redirect('changer_password')

                # Redirection selon le poste
                if poste == 'admin':
                    logger.info(f"Redirection vers admin_dashboard pour {username}.")
                    return redirect('admin_dashboard')
                elif poste == 'EMPLOYE':
                    logger.info(f"Redirection vers employee pour {username}.")
                    return redirect('employee')
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

class ChangePasswordView(View):
    template_name = 'ITservBack/login/changer_password.html'

    @method_decorator(csrf_protect)
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        return render(request, self.template_name)

    @method_decorator(csrf_protect)
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('login')

        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, self.template_name)

        if len(new_password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
            return render(request, self.template_name)

        # Mettre à jour le mot de passe
        user = request.user
        user.set_password(new_password)
        user.save()

        # Mettre à jour must_change_password à False
        profil = Profil.objects.get(user=user)
        profil.must_change_password = False
        profil.save()

        logger.info(f"Mot de passe changé avec succès pour {user.username}.")
        messages.success(request, "Votre mot de passe a été changé avec succès. Veuillez vous reconnecter.")
        auth_logout(request)  # Déconnecter après changement
        return redirect('login')
class PasswordResetView(View):
    template_name = 'ITservBack/login/password_reset.html'

    @method_decorator(csrf_protect)
    def get(self, request):
        return render(request, self.template_name)

    @method_decorator(csrf_protect)
    def post(self, request):
        username = request.POST.get('username')

        try:
            user = User.objects.get(username=username)
            logger.info(f"Demande de réinitialisation de mot de passe pour {username}.")

            # Générer un token et un UID pour le lien
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Créer le lien de réinitialisation
            reset_link = f"http://127.0.0.1:8000/reset-password/{uid}/{token}/"

            # Envoyer l'email
            subject = "Réinitialisation de votre mot de passe"
            message = (
                f"Bonjour {user.username},\n\n"
                f"Vous avez demandé à réinitialiser votre mot de passe. Cliquez sur le lien ci-dessous pour procéder :\n"
                f"{reset_link}\n\n"
                f"Si vous n'avez pas fait cette demande, ignorez cet email.\n\n"
                f"Cordialement,\nL'équipe ITserv"
            )
            from_email = 'oussama21072000@gmail.com'
            recipient_list = [user.email]

            try:
                send_mail(subject, message, from_email, recipient_list, fail_silently=False)
                logger.info(f"Email de réinitialisation envoyé avec succès à {user.email}")
                messages.success(request, "Un lien de réinitialisation a été envoyé à votre email.")
            except Exception as e:
                logger.error(f"Échec de l'envoi de l'email à {user.email} : {str(e)}")
                messages.error(request, f"Erreur lors de l'envoi de l'email : {str(e)}")
            return redirect('login')

        except User.DoesNotExist:
            logger.warning(f"Utilisateur '{username}' non trouvé pour réinitialisation.")
            messages.error(request, "Nom d'utilisateur incorrect.")
            return render(request, self.template_name)

class PasswordResetConfirmView(View):
    template_name = 'ITservBack/login/password_reset_confirm.html'

    @method_decorator(csrf_protect)
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if default_token_generator.check_token(user, token):
                return render(request, self.template_name, {'uidb64': uidb64, 'token': token})
            else:
                messages.error(request, "Le lien de réinitialisation est invalide ou a expiré.")
                return redirect('login')
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            messages.error(request, "Le lien de réinitialisation est invalide.")
            return redirect('login')

    @method_decorator(csrf_protect)
    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if not default_token_generator.check_token(user, token):
                messages.error(request, "Le lien de réinitialisation est invalide ou a expiré.")
                return redirect('login')

            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if new_password != confirm_password:
                messages.error(request, "Les mots de passe ne correspondent pas.")
                return render(request, self.template_name, {'uidb64': uidb64, 'token': token})

            if len(new_password) < 8:
                messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
                return render(request, self.template_name, {'uidb64': uidb64, 'token': token})

            user.set_password(new_password)
            user.save()
            logger.info(f"Mot de passe réinitialisé avec succès pour {user.username}.")
            messages.success(request, "Votre mot de passe a été réinitialisé avec succès. Veuillez vous connecter.")
            return redirect('login')

        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            messages.error(request, "Le lien de réinitialisation est invalide.")
            return redirect('login')