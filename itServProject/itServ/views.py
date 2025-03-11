from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from .models import Profil, UserLoginHistory  # Ajout de UserLoginHistory
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
import secrets
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
import string
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Conge,TypeConge
from django.utils import timezone
from django.core.exceptions import ValidationError




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

    # Logique pour la liste des demandes de congé
    if request.user.is_superuser:
        leave_requests = Conge.objects.all().order_by('-created_at')
    else:
        leave_requests = Conge.objects.filter(employee=request.user).order_by('-created_at')

    # Appliquer les filtres si une requête GET avec paramètres est envoyée
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

    # Récupérer les historiques de connexion
    if request.user.is_superuser:
        login_histories = UserLoginHistory.objects.all().order_by('user', '-login_time')
    else:
        login_histories = UserLoginHistory.objects.filter(user=request.user).order_by('-login_time')

    types_conge = TypeConge.objects.filter(flag_active=True)

    context = {
        'poste': poste,
        'is_home': False,
        'leave_requests': leave_requests,
        'types_conge': types_conge,
        'status_choices': Conge._meta.get_field('status').choices,
        'login_histories': login_histories,
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
    leave_paginator = Paginator(leave_requests, 10)  # 10 par page
    leave_page = request.GET.get('leave_page', 1)  # Utiliser 'leave_page' pour éviter les conflits
    try:
        leave_requests = leave_paginator.page(leave_page)
    except PageNotAnInteger:
        leave_requests = leave_paginator.page(1)
    except EmptyPage:
        leave_requests = leave_paginator.page(leave_paginator.num_pages)

    # Récupérer et filtrer l'historique de connexion
    login_histories = UserLoginHistory.objects.all().order_by('user', '-login_time')
    user_filter = request.GET.get('user_filter', '')
    if user_filter:
        login_histories = login_histories.filter(user__username__icontains=user_filter)

    # Pagination pour l'historique de connexion
    history_paginator = Paginator(login_histories, 10)  # 10 par page
    history_page = request.GET.get('history_page', 1)  # Utiliser 'history_page'
    try:
        login_histories = history_paginator.page(history_page)
    except PageNotAnInteger:
        login_histories = history_paginator.page(1)
    except EmptyPage:
        login_histories = history_paginator.page(history_paginator.num_pages)

    context = {
        'leave_requests': leave_requests,
        'types_conge': TypeConge.objects.filter(flag_active=True),
        'status_choices': Conge._meta.get_field('status').choices,
        'type_conge': type_conge,
        'status': status,
        'start_date_from': start_date_from,
        'start_date_to': start_date_to,
        'end_date_from': end_date_from,
        'end_date_to': end_date_to,
        'login_histories': login_histories,
        'user_filter': user_filter,
    }
    return render(request, "ITservBack/dashboard_ResponsableRH.html ", context)


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