from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from django.views.decorators.csrf import csrf_protect
from .models import Profil, UserLoginHistory,TypeAbsence,Absence # Ajout de UserLoginHistory
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
import secrets
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Notification  #
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
import string
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Conge,TypeConge,Absence,TypeAbsence,Pointage
from django.utils import timezone
from django.core.exceptions import ValidationError
# itServ/views.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync




logger = logging.getLogger(__name__)

def home(request):
    context = {'is_home': True}  # Indicateur pour la page d'accueil
    return render(request, "home.html", context)


@login_required
def employee(request):
    try:
        profil = Profil.objects.get(user=request.user)
        poste = profil.poste
    except Profil.DoesNotExist:
        poste = 'EMPLOYE'
        logger.warning(f"Profil non trouvé pour l'utilisateur {request.user.username}, poste par défaut : EMPLOYE")

    # Gestion des congés, absences et pointages
    if request.user.is_superuser:
        leave_requests = Conge.objects.all().order_by('-created_at')
        absence_requests = Absence.objects.all().order_by('-created_at')
        pointages = Pointage.objects.all().order_by('-date')
    else:
        leave_requests = Conge.objects.filter(employee=request.user).order_by('-created_at')
        absence_requests = Absence.objects.filter(employee=request.user).order_by('-created_at')
        pointages = Pointage.objects.filter(employe=request.user).order_by('-date')

    # Filtres pour les congés
    type_conge = request.GET.get('type_conge', '')
    status = request.GET.get('status', '')
    start_date_from = request.GET.get('start_date_from', '')
    start_date_to = request.GET.get('start_date_to', '')
    end_date_from = request.GET.get('end_date_from', '')
    end_date_to = request.GET.get('end_date_to', '')

    if type_conge:
        leave_requests = leave_requests.filter(type_conge__id=type_conge)
    if status:
        leave_requests = leave_requests.filter(status=status)
    if start_date_from:
        leave_requests = leave_requests.filter(start_date__gte=start_date_from)
    if start_date_to:
        leave_requests = leave_requests.filter(start_date__lte=start_date_to)
    if end_date_from:
        leave_requests = leave_requests.filter(end_date__gte=end_date_from)
    if end_date_to:
        leave_requests = leave_requests.filter(end_date__lte=end_date_to)

    # Filtres pour les absences
    type_absence = request.GET.get('type_absence', '')
    if type_absence:
        absence_requests = absence_requests.filter(type_absence__id=type_absence)
    if status:
        absence_requests = absence_requests.filter(status=status)
    if start_date_from:
        absence_requests = absence_requests.filter(start_date__gte=start_date_from)
    if start_date_to:
        absence_requests = absence_requests.filter(start_date__lte=start_date_to)
    if end_date_from:
        absence_requests = absence_requests.filter(end_date__gte=end_date_from)
    if end_date_to:
        absence_requests = absence_requests.filter(end_date__lte=end_date_to)

    # Gestion du pointage (entrée et sortie)
    if request.method == 'POST' and 'check_in' in request.POST:
        try:
            today = timezone.now().date()
            pointage, created = Pointage.objects.get_or_create(
                employe=request.user,
                date=today,
                defaults={'heure_entree': timezone.now()}
            )
            if not created and pointage.heure_entree:
                messages.warning(request, "Vous avez déjà pointé votre entrée aujourd'hui.")
                logger.warning(f"Entrée déjà pointée pour {request.user.username} le {today}")
            else:
                Notification.objects.create(
                    user=request.user,
                    message=f"Vous avez pointé votre entrée le {today} à {pointage.heure_entree.strftime('%H:%M:%S')}"
                )
                messages.success(request, "Entrée pointée avec succès !")
                logger.info(f"Entrée pointée pour {request.user.username} le {today}")
        except Exception as e:
            messages.error(request, f"Erreur lors du pointage d'entrée : {str(e)}")
            logger.error(f"Erreur lors du pointage d'entrée pour {request.user.username} : {str(e)}")
        return redirect('employee')

    if request.method == 'POST' and 'check_out' in request.POST:
        try:
            today = timezone.now().date()
            pointage = Pointage.objects.filter(employe=request.user, date=today).first()
            if pointage:
                if pointage.heure_sortie:
                    messages.warning(request, "Vous avez déjà pointé votre sortie aujourd'hui.")
                    logger.warning(f"Sortie déjà pointée pour {request.user.username} le {today}")
                else:
                    pointage.heure_sortie = timezone.now()
                    pointage.save()
                    Notification.objects.create(
                        user=request.user,
                        message=f"Vous avez pointé votre sortie le {today} à {pointage.heure_sortie.strftime('%H:%M:%S')}"
                    )
                    messages.success(request, "Sortie pointée avec succès !")
                    logger.info(f"Sortie pointée pour {request.user.username} le {today}")
            else:
                messages.error(request, "Vous devez d'abord pointer une entrée avant de pointer une sortie.")
                logger.warning(f"Pas d'entrée trouvée pour {request.user.username} le {today}")
        except Exception as e:
            messages.error(request, f"Erreur lors du pointage de sortie : {str(e)}")
            logger.error(f"Erreur lors du pointage de sortie pour {request.user.username} : {str(e)}")
        return redirect('employee')

    # Soumission d'une nouvelle demande d'absence
    if request.method == 'POST' and 'type_absence' in request.POST and 'start_date' in request.POST:
        type_absence_id = request.POST.get('type_absence')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        image = request.FILES.get('image')
        logger.info(f"Requête POST reçue : type_absence={type_absence_id}, start_date={start_date}, end_date={end_date}, reason={reason}, image={image}")
        if not start_date or not end_date or not reason:
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
            logger.warning("Champs manquants pour la demande d'absence.")
        else:
            try:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
                if start_date > end_date:
                    raise ValidationError("La date de fin doit être postérieure à la date de début.")
                if start_date < timezone.now().date():
                    raise ValidationError("La date de début ne peut pas être dans le passé.")

                type_absence = TypeAbsence.objects.get(id=type_absence_id)
                absence = Absence(
                    employee=request.user,
                    type_absence=type_absence,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                    image=image
                )
                absence.save()

                # Notification pour l'utilisateur
                Notification.objects.create(
                    user=request.user,
                    message=f"Nouvelle demande d'absence soumise du {start_date} au {end_date}."
                )

                # Notification pour les Responsables RH
                responsables_rh = Profil.objects.filter(poste='ResponsableRH')
                for profil in responsables_rh:
                    Notification.objects.create(
                        user=profil.user,
                        message=f"Nouvelle demande d'absence de {request.user.username} du {start_date} au {end_date}."
                    )

                messages.success(request, "Demande d'absence soumise avec succès !")
                logger.info(f"Demande d'absence créée avec succès : ID={absence.id}")
                return redirect('employee')
            except ValueError as e:
                messages.error(request, "Format de date invalide. Utilisez AAAA-MM-JJ.")
                logger.error(f"Erreur de format de date : {str(e)}")
            except ValidationError as e:
                messages.error(request, str(e))
                logger.error(f"Erreur de validation : {str(e)}")
            except TypeAbsence.DoesNotExist:
                messages.error(request, "Type d'absence invalide.")
                logger.error("Type d'absence invalide.")
            except Exception as e:
                messages.error(request, f"Erreur lors de la soumission de la demande : {str(e)}")
                logger.error(f"Erreur lors de la soumission de la demande d'absence : {str(e)}")

        # Logique pour soumettre une nouvelle demande de congé
    if request.method == 'POST' and 'type_conge' in request.POST and 'start_date' in request.POST:
        type_conge_id = request.POST.get('type_conge')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')

        if not start_date or not end_date or not reason:
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
        else:
            try:
                start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
                if start_date > end_date:
                    raise ValidationError("La date de fin doit être postérieure à la date de début.")
                if start_date < timezone.now().date():
                    raise ValidationError("La date de début ne peut pas être dans le passé.")

                leave = Conge(
                    employee=request.user,
                    type_conge_id=type_conge_id,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                )
                leave.save()
                messages.success(request, "Demande de congé soumise avec succès !")
                return redirect('employee')
            except ValueError:
                messages.error(request, "Format de date invalide. Utilisez AAAA-MM-JJ.")
            except ValidationError as e:
                messages.error(request, str(e))

        # Logique pour ajouter un nouveau type de congé
    if request.method == 'POST' and 'new_type_conge' in request.POST:
        new_type = request.POST.get('new_type_conge')
        if new_type:
            try:
                TypeConge.objects.create(type=new_type)
                messages.success(request, "Nouveau type de congé ajouté avec succès !")
            except Exception as e:
                messages.error(request, f"Erreur lors de l'ajout : {str(e)}")
        return redirect('employee')
    # Logique pour ajouter un nouveau type d'absence
    if request.method == 'POST' and 'new_type_absence' in request.POST:
        if request.user.profil.poste == 'ResponsableRH' or request.user.is_superuser:
            new_type = request.POST.get('new_type_absence')
            if new_type:
                try:
                    TypeAbsence.objects.create(type=new_type, flag_active=True)
                    Notification.objects.create(
                        user=request.user,
                        message=f"Nouveau type d'absence '{new_type}' ajouté avec succès."
                    )
                    messages.success(request, "Nouveau type d'absence ajouté avec succès !")
                    logger.info(f"Nouveau type d'absence ajouté : {new_type}")
                except Exception as e:
                    messages.error(request, f"Erreur lors de l'ajout : {str(e)}")
                    logger.error(f"Erreur lors de l'ajout du type d'absence : {str(e)}")
            else:
                messages.error(request, "Veuillez entrer un nom pour le type d'absence.")
                logger.warning("Nom du type d'absence manquant.")
        else:
            messages.error(request, "Vous n'êtes pas autorisé à ajouter un type d'absence.")
            logger.warning(f"Utilisateur non autorisé à ajouter un type d'absence : {request.user.username}")
        return redirect('employee')

    # Récupérer les notifications
    notifications = request.user.notifications.all().order_by('-created_at')
    unread_notifications_count = request.user.notifications.filter(is_read=False).count()

    # Contexte
    types_conge = TypeConge.objects.filter(flag_active=True)
    types_absence = TypeAbsence.objects.filter(flag_active=True)

    context = {
        'poste': poste,
        'is_home': False,
        'leave_requests': leave_requests,
        'absence_requests': absence_requests,
        'pointages': pointages,
        'types_conge': types_conge,
        'types_absence': types_absence,
        'status_choices': Conge._meta.get_field('status').choices,
        'login_histories': UserLoginHistory.objects.filter(user=request.user).order_by('-login_time'),
        'unread_notifications_count': unread_notifications_count,
        'notifications': notifications,
        'type_conge_choices': TypeConge.objects.filter(flag_active=True).values_list('id', 'type'),
        'type_absence_choices': TypeAbsence.objects.filter(flag_active=True).values_list('id', 'type'),
    }
    return render(request, "ITservBack/employe_dashboard.html", context)
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
    unread_notifications_count = request.user.notifications.filter(is_read=False).count()
    context = {
        'poste': profil.poste,
        'is_home': False,
        'segment': 'dashboard',
        'unread_notifications_count': unread_notifications_count,
    }
    return render(request, 'ITservBack/layouts/base.html', context)



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
        username = request.POST.get('username')
       # alphabet = string.ascii_lowercase + string.digits

       # while User.objects.filter(username=username).exists():
      #      username = ''.join(secrets.choice(alphabet) for _ in range(8))

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
        context = {'is_home': True}
        return render(request, self.template_name, context)

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
                return render(request, self.template_name, {'is_home': True})
            else:
                logger.info(f"Mot de passe correct pour {username} dans auth_user.")

            try:
                profil = Profil.objects.get(user=authenticated_user)
                poste = profil.poste
                logger.info(f"Poste '{poste}' trouvé pour {username} dans itServ_profil.")

                if (role == 'EMPLOYE' and poste != 'EMPLOYE') or (role == 'ResponsableRH' and poste != 'ResponsableRH'):
                    logger.warning(f"Rôle '{role}' ne correspond pas au poste '{poste}' pour {username}.")
                    if role == 'EMPLOYE':
                        messages.error(request, "Vous êtes un Responsable RH. Veuillez utiliser le formulaire Entreprise.")
                    else:
                        messages.error(request, "Vous êtes un Employé. Veuillez utiliser le formulaire Employé.")
                    return render(request, self.template_name, {'is_home': True})

                # Enregistrer la première connexion si elle n'existe pas encore
                if profil.first_login is None:
                    profil.first_login = timezone.now()
                    logger.info(f"Première connexion enregistrée pour {username} à {profil.first_login}.")

                # Mettre à jour la dernière authentification
                profil.last_authentication = timezone.now()
                profil.save()
                logger.info(f"Dernière authentification enregistrée pour {username} à {profil.last_authentication}.")

                # Enregistrer l'historique de connexion
                UserLoginHistory.objects.create(
                    user=authenticated_user,
                    login_time=timezone.now(),
                    poste=poste
                )
                logger.info(f"Connexion enregistrée dans l'historique pour {username} à {timezone.now()}.")

                auth_login(request, authenticated_user)
                logger.info(f"Connexion réussie pour {username}")

                # Vérifier si le mot de passe doit être changé
                if profil.must_change_password:
                    logger.info(f"Première connexion détectée pour {username}, redirection vers change_password.")
                    return redirect('change_password')

                # Passer poste dans le contexte pour toutes les redirections
                context = {
                    'is_home': False,
                    'poste': poste
                }

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
                    return render(request, self.template_name, {'is_home': True})

            except Profil.DoesNotExist:
                logger.warning(f"Aucun profil trouvé pour {username} dans itServ_profil.")
                messages.error(request, "Profil non configuré. Contactez l'administrateur.")
                return render(request, self.template_name, {'is_home': True})

        except User.DoesNotExist:
            logger.warning(f"Utilisateur '{username}' non trouvé dans auth_user.")
            messages.error(request, "Nom d'utilisateur incorrect.")
            return render(request, self.template_name, {'is_home': True})


class ChangePasswordView(View):
    template_name = 'ITservBack/login/changer_password.html'
    context = {'is_home': True}  # Class-level attribute

    @method_decorator(csrf_protect)
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        return render(request, self.template_name, self.context)  # Use self.context

    @method_decorator(csrf_protect)
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('login')

        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, self.template_name, self.context)  # Use self.context

        if len(new_password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
            return render(request, self.template_name, self.context)  # Use self.context

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


@login_required
def leave_request(request):
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')

        # Validation des dates
        if not start_date or not end_date:
            messages.error(request, "Please provide both start and end dates.")
            return render(request, 'leave_request.html', {'error': 'Dates are required.'})

        try:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
            if start_date > end_date:
                raise ValidationError("End date must be after start date.")
            if start_date < timezone.now().date():
                raise ValidationError("Start date cannot be in the past.")
        except ValueError:
            messages.error(request, "Invalid date format. Use YYYY-MM-DD.")
            return render(request, 'leave_request.html', {'error': 'Invalid date format.'})

        # Créer la demande de congé
        leave = Conge(
            employee=request.user,
            start_date=start_date,
            end_date=end_date,
            reason=reason
        )
        leave.save()
        messages.success(request, "Leave request submitted successfully!")
        return redirect('leave_request')

    return render(request, 'leave_request.html')
@login_required
def leave_list(request):
    if request.user.is_superuser:  # Si l'utilisateur est un admin
        leave_requests = Conge.objects.all().order_by('-created_at')
    else:  # Si c'est un employé normal
        leave_requests = Conge.objects.filter(employee=request.user).order_by('-created_at')

    return render(request, 'leave_list.html', {'leave_requests': leave_requests})
@login_required
def list_profil(request):
        profiles = Profil.objects.all().order_by('user__username')
        paginator = Paginator(profiles, 10)  # 10 profils par page
        page = request.GET.get('page')
        try:
            profiles_page = paginator.page(page)
        except PageNotAnInteger:
            profiles_page = paginator.page(1)
        except EmptyPage:
            profiles_page = paginator.page(paginator.num_pages)
        context = {
            'profiles': profiles_page,
        }
        return render(request, "ITservBack/profil_list.html", context)


@login_required
def responsable_rh_dashboard(request):
    try:
        profil = Profil.objects.get(user=request.user)
        if profil.poste != 'ResponsableRH':
            messages.error(request, "Vous n'êtes pas autorisé à accéder à ce tableau de bord.")
            return redirect('employee')
    except Profil.DoesNotExist:
        messages.error(request, "Profil non trouvé.")
        return redirect('employee')

    # Gestion des pointages (entrée/sortie)
    if request.method == 'POST' and 'check_in' in request.POST:
        try:
            today = timezone.now().date()
            pointage, created = Pointage.objects.get_or_create(
                employe=request.user,
                date=today,
                defaults={'heure_entree': timezone.now().time()}
            )
            if not created and pointage.heure_entree:
                messages.warning(request, "Vous avez déjà pointé votre entrée aujourd'hui.")
            else:
                messages.success(request, "Entrée pointée avec succès !")
        except Exception as e:
            logger.error(f"Erreur lors du pointage d'entrée : {str(e)}")
            messages.error(request, f"Erreur lors du pointage d'entrée : {str(e)}")
        return redirect('responsable_rh_dashboard')

    if request.method == 'POST' and 'check_out' in request.POST:
        try:
            today = timezone.now().date()
            pointage = Pointage.objects.filter(employe=request.user, date=today).first()
            if pointage:
                if pointage.heure_sortie:
                    messages.warning(request, "Vous avez déjà pointé votre sortie aujourd'hui.")
                else:
                    pointage.heure_sortie = timezone.now().time()
                    pointage.save()
                    messages.success(request, "Sortie pointée avec succès !")
            else:
                messages.error(request, "Vous devez d'abord pointer une entrée avant de pointer une sortie.")
        except Exception as e:
            logger.error(f"Erreur lors du pointage de sortie : {str(e)}")
            messages.error(request, f"Erreur lors du pointage de sortie : {str(e)}")
        return redirect('responsable_rh_dashboard')

    # Gestion de l'importation des pointages via Excel
    if request.method == 'POST' and 'upload_pointage_excel' in request.POST:
        try:
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                messages.error(request, "Aucun fichier sélectionné.")
                return redirect('responsable_rh_dashboard')

            # Vérifier l'extension du fichier
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, "Le fichier doit être au format Excel (.xlsx ou .xls).")
                return redirect('responsable_rh_dashboard')

            # Lire le fichier Excel avec pandas
            df = pd.read_excel(excel_file)
            logger.info(f"Colonnes du fichier Excel : {df.columns.tolist()}")

            # Vérifier les colonnes attendues
            required_columns = ['username', 'date', 'heure_entree', 'heure_sortie']
            if not all(col in df.columns for col in required_columns):
                messages.error(request, "Le fichier Excel doit contenir les colonnes suivantes : username, date, heure_entree, heure_sortie.")
                return redirect('responsable_rh_dashboard')

            # Traiter chaque ligne du fichier Excel
            for index, row in df.iterrows():
                try:
                    username = row['username']
                    date_str = row['date']
                    heure_entree = row['heure_entree']
                    heure_sortie = row['heure_sortie']

                    # Récupérer l'utilisateur
                    user = User.objects.filter(username=username).first()
                    if not user:
                        logger.warning(f"Utilisateur {username} non trouvé à la ligne {index + 2}.")
                        continue

                    # Convertir la date
                    if isinstance(date_str, str):
                        date = pd.to_datetime(date_str).date()
                    elif pd.isna(date_str):
                        logger.warning(f"Date manquante à la ligne {index + 2}.")
                        continue
                    else:
                        date = date_str

                    # Convertir les heures
                    if pd.isna(heure_entree):
                        heure_entree = None
                    elif isinstance(heure_entree, str):
                        try:
                            # Supposons que l'heure est au format HH:MM:SS ou HH:MM
                            heure_entree = pd.to_datetime(heure_entree, format='%H:%M:%S' if ':' in heure_entree else '%H:%M').time()
                        except ValueError:
                            logger.warning(f"Format d'heure d'entrée invalide à la ligne {index + 2}: {heure_entree}")
                            continue

                    if pd.isna(heure_sortie):
                        heure_sortie = None
                    elif isinstance(heure_sortie, str):
                        try:
                            heure_sortie = pd.to_datetime(heure_sortie, format='%H:%M:%S' if ':' in heure_sortie else '%H:%M').time()
                        except ValueError:
                            logger.warning(f"Format d'heure de sortie invalide à la ligne {index + 2}: {heure_sortie}")
                            continue

                    # Créer ou mettre à jour le pointage
                    pointage, created = Pointage.objects.get_or_create(
                        employe=user,
                        date=date,
                        defaults={
                            'heure_entree': heure_entree,
                            'heure_sortie': heure_sortie
                        }
                    )
                    if not created:
                        pointage.heure_entree = heure_entree
                        pointage.heure_sortie = heure_sortie
                        pointage.save()
                except Exception as e:
                    logger.error(f"Erreur lors du traitement de la ligne {index + 2} : {str(e)}")
                    messages.warning(request, f"Erreur à la ligne {index + 2} : {str(e)}")
                    continue

            messages.success(request, "Pointages importés avec succès !")
        except Exception as e:
            logger.error(f"Erreur lors de l'importation du fichier Excel : {str(e)}")
            messages.error(request, f"Erreur lors de l'importation du fichier : {str(e)}")
        return redirect('responsable_rh_dashboard')

    # Récupérer les pointages (tous les employés pour le Responsable RH)
    pointages = Pointage.objects.all().order_by('-date')

    # Récupérer et filtrer les demandes de congé
    leave_requests = Conge.objects.all().order_by('-created_at')
    type_conge = request.GET.get('type_conge', '')
    status = request.GET.get('status', '')
    start_date_from = request.GET.get('start_date_from', '')
    start_date_to = request.GET.get('start_date_to', '')
    end_date_from = request.GET.get('end_date_from', '')
    end_date_to = request.GET.get('end_date_to', '')

    if type_conge:
        leave_requests = leave_requests.filter(type_conge__type=type_conge)
    if status:
        leave_requests = leave_requests.filter(status=status)
    if start_date_from:
        leave_requests = leave_requests.filter(start_date__gte=start_date_from)
    if start_date_to:
        leave_requests = leave_requests.filter(start_date__lte=start_date_to)
    if end_date_from:
        leave_requests = leave_requests.filter(end_date__gte=end_date_from)
    if end_date_to:
        leave_requests = leave_requests.filter(end_date__lte=end_date_to)

    # Pagination pour les demandes de congé
    leave_paginator = Paginator(leave_requests, 10)
    leave_page = request.GET.get('leave_page', 1)
    try:
        leave_requests = leave_paginator.page(leave_page)
    except PageNotAnInteger:
        leave_requests = leave_paginator.page(1)
    except EmptyPage:
        leave_requests = leave_paginator.page(leave_paginator.num_pages)

    # Récupérer et filtrer les demandes d'absence
    absence_requests = Absence.objects.all().order_by('-created_at')
    type_absence = request.GET.get('type_absence', '')
    if type_absence:
        absence_requests = absence_requests.filter(type_absence__id=type_absence)
    if status:
        absence_requests = absence_requests.filter(status=status)
    if start_date_from:
        absence_requests = absence_requests.filter(start_date__gte=start_date_from)
    if start_date_to:
        absence_requests = absence_requests.filter(start_date__lte=start_date_to)
    if end_date_from:
        absence_requests = absence_requests.filter(end_date__gte=end_date_from)
    if end_date_to:
        absence_requests = absence_requests.filter(end_date__lte=end_date_to)

    # Pagination pour les demandes d'absence
    absence_paginator = Paginator(absence_requests, 10)
    absence_page = request.GET.get('absence_page', 1)
    try:
        absence_requests = absence_paginator.page(absence_page)
    except PageNotAnInteger:
        absence_requests = absence_paginator.page(1)
    except EmptyPage:
        absence_requests = absence_paginator.page(absence_paginator.num_pages)

    # Récupérer et filtrer l'historique de connexion
    login_histories = UserLoginHistory.objects.all().order_by('user', '-login_time')
    user_filter = request.GET.get('user_filter', '')
    if user_filter:
        login_histories = login_histories.filter(user__username__icontains=user_filter)

    # Pagination pour l'historique de connexion
    history_paginator = Paginator(login_histories, 10)
    history_page = request.GET.get('history_page', 1)
    try:
        login_histories = history_paginator.page(history_page)
    except PageNotAnInteger:
        login_histories = history_paginator.page(1)
    except EmptyPage:
        login_histories = history_paginator.page(history_paginator.num_pages)

    # Calculer le nombre de notifications non lues
    unread_notifications_count = request.user.notifications.filter(is_read=False).count()

    context = {
        'leave_requests': leave_requests,
        'absence_requests': absence_requests,
        'pointages': pointages,
        'types_conge': TypeConge.objects.filter(flag_active=True),
        'types_absence': TypeAbsence.objects.filter(flag_active=True),
        'status_choices': Conge._meta.get_field('status').choices,
        'type_conge': type_conge,
        'type_absence': type_absence,
        'status': status,
        'start_date_from': start_date_from,
        'start_date_to': start_date_to,
        'end_date_from': end_date_from,
        'end_date_to': end_date_to,
        'login_histories': login_histories,
        'user_filter': user_filter,
        'unread_notifications_count': unread_notifications_count,
    }
    return render(request, "ITservBack/dashboard_ResponsableRH.html", context)

def responsablerh_dashboard(request):

    return render(request, 'ITservBack/dashboard_ResponsableRH.html', context)
@login_required
def update_leave_status(request, leave_id, status):
    if request.user.profil.poste != 'ResponsableRH':
        messages.error(request, "Vous n'êtes pas autorisé à effectuer cette action.")
        return redirect('responsable_rh_dashboard')

    try:
        leave = Conge.objects.get(id=leave_id)
        if status in ['approved', 'rejected']:
            leave.status = status
            leave.save()
            messages.success(request, f"La demande de congé a été {status} avec succès.")
        else:
            messages.error(request, "Statut invalide.")
    except Conge.DoesNotExist:
        messages.error(request, "Demande de congé introuvable.")
    return redirect('responsable_rh_dashboard')

def send_notification_to_user(user_id, message, notification_id):
    channel_layer = get_channel_layer()
    group_name = f'user_{user_id}'
    logger.info(f"Sending notification to group {group_name}: {message} (ID: {notification_id})")
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'send_notification',
                'message': message,
                'notification_id': notification_id
            }
        )
        logger.info(f"Successfully sent notification to group {group_name}")
    except Exception as e:
        logger.error(f"Failed to send notification to group {group_name}: {str(e)}")

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        unread_count = request.user.notifications.filter(is_read=False).count()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Notification marked as read.',
                'unread_count': unread_count
            })
        messages.success(request, "Notification marked as read.")
    except Notification.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'message': 'Notification not found or you do not have permission to access it.'},
                status=404)
        messages.error(request, "Notification not found or you do not have permission to access it.")
    return redirect(request.META.get('HTTP_REFERER', 'employee'))
@login_required
def get_unread_count(request):
    unread_count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'unread_count': unread_count})
@login_required
def export_pointages_to_excel(request):
    if request.user.profil.poste == 'ResponsableRH' or request.user.is_superuser:
        # Récupérer les pointages
        pointages = Pointage.objects.all()

        # Créer une liste de dictionnaires pour les données
        data = []
        for pointage in pointages:
            data.append({
                'Nom d\'utilisateur': pointage.employe.username,
                'Date': pointage.date,
                'Heure d\'entrée': pointage.heure_entree,
                'Heure de sortie': pointage.heure_sortie,
            })

        # Créer un DataFrame pandas
        df = pd.DataFrame(data)

        # Créer un fichier Excel en mémoire
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Pointages')

        # Préparer la réponse HTTP pour le téléchargement
        buffer.seek(0)
        response = HttpResponse(
            buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="pointages.xlsx"'
        return response
    else:
        messages.error(request, "Vous n'êtes pas autorisé à exporter les pointages.")
        return redirect('employee')
@login_required
def update_absence_status(request, absence_id, status):
    if request.user.profil.poste != 'ResponsableRH':
        messages.error(request, "Vous n'êtes pas autorisé à effectuer cette action.")
        return redirect('responsable_rh_dashboard')

    try:
        absence = Absence.objects.get(id=absence_id)
        if status in ['approved', 'rejected']:
            absence.status = status
            absence.save()
            messages.success(request, f"La demande d'absence a été {status} avec succès.")
        else:
            messages.error(request, "Statut invalide.")
    except Absence.DoesNotExist:
        messages.error(request, "Demande d'absence introuvable.")
    return redirect('responsable_rh_dashboard')

