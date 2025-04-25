from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Autorisation,Societe
from sklearn.cluster import KMeans
import json
from math import radians, sin, cos, sqrt, atan2

from django.views.decorators.cache import never_cache
from transformers import pipeline
from django.contrib.auth.decorators import login_required
import redis
from django.urls import reverse
from celery.exceptions import OperationalError
from django.contrib import messages
from django.views import View
from .forms import LeaveRequestForm  # Add this import
from .tasks import optimize_leaves
from ortools.constraint_solver import pywrapcp as cp_model
from django.utils.decorators import method_decorator
from django.http import HttpResponse
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib
from datetime import datetime, timedelta
from calendar import monthrange
from django.utils import timezone
from calendar import monthrange
from .tasks import generate_leave_planning  # Add this line

from celery import shared_task
from django.utils import timezone
from itServ.models import Notification, Profil

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from itServ.models import Profil, Conge, Absence ,Societe
from django.utils import timezone
import logging
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

#from .tasks import generate_leave_planning  # Importer depuis tasks.py

import string
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Conge,TypeConge,Absence,TypeAbsence,Pointage
from django.utils import timezone
from django.core.exceptions import ValidationError
# itServ/views.py
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from ortools.sat.python import cp_model
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib



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

    # Get year and month, handling empty strings
    year_str = request.GET.get('year', str(timezone.now().year))
    month_str = request.GET.get('month', str(timezone.now().month))

    # Convert to integers, defaulting to current year/month if invalid or empty
    try:
        year = int(year_str) if year_str.strip() else timezone.now().year
    except ValueError:
        year = timezone.now().year
        logger.warning(f"Invalid year value: {year_str}, defaulting to {year}")

    try:
        month = int(month_str) if month_str.strip() else timezone.now().month
    except ValueError:
        month = timezone.now().month
        logger.warning(f"Invalid month value: {month_str}, defaulting to {month}")

    # Normaliser le mois et l'année
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    # Logique du calendrier
    first_day = datetime(year, month, 1)
    num_days = monthrange(year, month)[1]
    last_day = first_day + timedelta(days=num_days - 1)
    first_weekday = first_day.weekday()

    pointages_calendar = Pointage.objects.filter(
        employe=request.user,
        date__range=[first_day, last_day]
    ).values('date', 'heure_entree')

    conges = Conge.objects.filter(
        employee=request.user,
        start_date__lte=last_day,
        end_date__gte=first_day
    ).values('start_date', 'end_date')

    absences = Absence.objects.filter(
        employee=request.user,
        start_date__lte=last_day,
        end_date__gte=first_day
    ).values('start_date', 'end_date')

    days = []
    for day in range(1, num_days + 1):
        current_date = datetime(year, month, day).date()
        days.append({
            'day': day,
            'date': current_date,
            'worked': False,
            'absent': False
        })

    for pointage in pointages_calendar:
        for entry in days:
            if entry['date'] == pointage['date'] and pointage['heure_entree']:
                entry['worked'] = True

    for conge in conges:
        start = max(conge['start_date'], first_day.date())
        end = min(conge['end_date'], last_day.date())
        while start <= end:
            for entry in days:
                if entry['date'] == start:
                    entry['absent'] = True
                    entry['worked'] = False
            start += timedelta(days=1)

    for absence in absences:
        start = max(absence['start_date'], first_day.date())
        end = min(absence['end_date'], last_day.date())
        while start <= end:
            for entry in days:
                if entry['date'] == start:
                    entry['absent'] = True
                    entry['worked'] = False
            start += timedelta(days=1)

    calendar_grid = []
    current_day = 1
    for week in range(6):
        week_row = []
        for day in range(7):
            if (week == 0 and day < first_weekday) or current_day > num_days:
                week_row.append(None)
            else:
                for entry in days:
                    if entry['day'] == current_day:
                        week_row.append(entry)
                        current_day += 1
                        break
        calendar_grid.append(week_row)

    # Gestion du filtre
    start_date_from = request.GET.get('start_date_from')
    start_date_to = request.GET.get('start_date_to')

    autorisations = Autorisation.objects.filter(employee=request.user)

    if start_date_from:
        autorisations = autorisations.filter(start_datetime__date__gte=start_date_from)
    if start_date_to:
        autorisations = autorisations.filter(start_datetime__date__lte=start_date_to)

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

    # Pagination
    items_per_page = 5  # Nombre d'éléments par page

    # Pagination pour les congés (leave_requests)
    leave_paginator = Paginator(leave_requests, items_per_page)
    leave_page_number = request.GET.get('leave_page')
    try:
        leave_requests_page = leave_paginator.page(leave_page_number)
    except PageNotAnInteger:
        leave_requests_page = leave_paginator.page(1)
    except EmptyPage:
        leave_requests_page = leave_paginator.page(leave_paginator.num_pages)

    # Pagination pour les absences (absence_requests)
    absence_paginator = Paginator(absence_requests, items_per_page)
    absence_page_number = request.GET.get('absence_page')
    try:
        absence_requests_page = absence_paginator.page(absence_page_number)
    except PageNotAnInteger:
        absence_requests_page = absence_paginator.page(1)
    except EmptyPage:
        absence_requests_page = absence_paginator.page(absence_paginator.num_pages)

    # Pagination pour les pointages (pointages)
    pointage_paginator = Paginator(pointages, items_per_page)
    pointage_page_number = request.GET.get('pointage_page')
    try:
        pointages_page = pointage_paginator.page(pointage_page_number)
    except PageNotAnInteger:
        pointages_page = pointage_paginator.page(1)
    except EmptyPage:
        pointages_page = pointage_paginator.page(pointage_paginator.num_pages)

    # Pagination pour les autorisations (autorisations)
    autorisation_paginator = Paginator(autorisations, items_per_page)
    autorisation_page_number = request.GET.get('autorisation_page')
    try:
        autorisations_page = autorisation_paginator.page(autorisation_page_number)
    except PageNotAnInteger:
        autorisations_page = autorisation_paginator.page(1)
    except EmptyPage:
        autorisations_page = autorisation_paginator.page(autorisation_paginator.num_pages)

    # Pagination pour l'historique de connexion (login_histories)
    login_histories = UserLoginHistory.objects.filter(user=request.user).order_by('-login_time')
    login_paginator = Paginator(login_histories, items_per_page)
    login_page_number = request.GET.get('login_page')
    try:
        login_histories_page = login_paginator.page(login_page_number)
    except PageNotAnInteger:
        login_histories_page = login_paginator.page(1)
    except EmptyPage:
        login_histories_page = login_paginator.page(login_paginator.num_pages)

    try:
        societe = Societe.objects.first()  # À adapter si plusieurs sociétés
        if not societe.location_societe:
            messages.error(request, "La localisation de la société n'est pas configurée.")
            logger.error("Localisation de la société non configurée.")
            return redirect('employee')
        societe_lat, societe_lon = map(float, societe.location_societe.split(','))
    except Societe.DoesNotExist:
        messages.error(request, "Aucune société configurée dans la base de données.")
        logger.error("Aucune société trouvée dans la base de données.")
        return redirect('employee')

        # Gestion du pointage (entrée)
    if request.method == 'POST' and 'check_in' in request.POST:
        try:
            # Récupérer la localisation envoyée par le client
            employee_lat = request.POST.get('latitude')
            employee_lon = request.POST.get('longitude')

            if not employee_lat or not employee_lon:
                messages.error(request, "Impossible de récupérer votre localisation.")
                logger.warning(f"Localisation non fournie pour {request.user.username}")
                return redirect('employee')

            # Calculer la distance
            distance = haversine_distance(employee_lat, employee_lon, societe_lat, societe_lon)
            if distance > societe.rayon_acceptable:
                messages.error(
                    request,
                    f"Pointage refusé : vous êtes trop loin du lieu de travail ({int(distance)}m, maximum {societe.rayon_acceptable}m)."
                )
                logger.warning(
                    f"Pointage refusé pour {request.user.username} : distance {distance}m > {societe.rayon_acceptable}m"
                )
                return redirect('employee')

            # Si la localisation est valide, procéder au pointage
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

        # Gestion du pointage (sortie)
    if request.method == 'POST' and 'check_out' in request.POST:
        try:
            # Récupérer la localisation envoyée par le client
            employee_lat = request.POST.get('latitude')
            employee_lon = request.POST.get('longitude')

            if not employee_lat or not employee_lon:
                messages.error(request, "Impossible de récupérer votre localisation.")
                logger.warning(f"Localisation non fournie pour {request.user.username}")
                return redirect('employee')

            # Calculer la distance
            distance = haversine_distance(employee_lat, employee_lon, societe_lat, societe_lon)
            if distance > societe.rayon_acceptable:
                messages.error(
                    request,
                    f"Pointage refusé : vous êtes trop loin du lieu de travail ({int(distance)}m, maximum {societe.rayon_acceptable}m)."
                )
                logger.warning(
                    f"Pointage refusé pour {request.user.username} : distance {distance}m > {societe.rayon_acceptable}m"
                )
                return redirect('employee')

            # Si la localisation est valide, procéder au pointage
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
        return redirect(f"{reverse('employee')}?tab=pointage")

    # Soumission d'une nouvelle demande d'absence
    if request.method == 'POST' and 'type_absence' in request.POST and 'start_date' in request.POST:
        type_absence_id = request.POST.get('type_absence')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        image = request.FILES.get('image')
        logger.info(
            f"Requête POST reçue : type_absence={type_absence_id}, start_date={start_date}, end_date={end_date}, reason={reason}, image={image}")
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
                return redirect(f"{reverse('employee')}?tab=absences")
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

                # Vérifier les chevauchements avec les congés existants (approuvés ou planifiés) d'autres employés
                overlapping_leaves = Conge.objects.filter(
                    status__in=['approved', 'planned'],  # Vérifier les congés approuvés ou planifiés
                    employee__profil__poste='EMPLOYE',  # Seulement les employés
                    start_date__lte=end_date,  # Le congé existant commence avant la fin de la demande
                    end_date__gte=start_date  # Le congé existant se termine après le début de la demande
                ).exclude(employee=request.user)  # Exclure l'utilisateur actuel

                if overlapping_leaves.exists():
                    # Si un chevauchement est trouvé, afficher un message d'erreur
                    overlapping_leave = overlapping_leaves.first()
                    messages.error(
                        request,
                        f"Les dates demandées ({start_date} au {end_date}) chevauchent un congé existant de "
                        f"{overlapping_leave.employee.username} (du {overlapping_leave.start_date} au "
                        f"{overlapping_leave.end_date}). Veuillez choisir d'autres dates."
                    )
                    logger.warning(
                        f"Chevauchement détecté pour {request.user.username} : demande ({start_date} au {end_date}) "
                        f"chevauche le congé de {overlapping_leave.employee.username} "
                        f"({overlapping_leave.start_date} au {overlapping_leave.end_date})"
                    )
                else:
                    # Si aucun chevauchement, créer la demande de congé
                    leave = Conge(
                        employee=request.user,
                        type_conge_id=type_conge_id,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason,
                    )
                    leave.save()

                    # Notification pour l'utilisateur
                    Notification.objects.create(
                        user=request.user,
                        message=f"Nouvelle demande de congé soumise du {start_date} au {end_date}."
                    )

                    # Notification pour les Responsables RH
                    responsables_rh = Profil.objects.filter(poste='ResponsableRH')
                    for profil in responsables_rh:
                        Notification.objects.create(
                            user=profil.user,
                            message=f"Nouvelle demande de congé de {request.user.username} du {start_date} au {end_date}."
                        )

                    messages.success(request, "Demande de congé soumise avec succès !")
                    logger.info(f"Demande de congé créée avec succès : ID={leave.id}")
                    return redirect(f"{reverse('employee')}?tab=conge")

            except ValueError:
                messages.error(request, "Format de date invalide. Utilisez AAAA-MM-JJ.")
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Erreur lors de la soumission de la demande : {str(e)}")
                logger.error(f"Erreur lors de la soumission de la demande de congé : {str(e)}")

    # Logique pour ajouter un nouveau type de congé
    if request.method == 'POST' and 'new_type_conge' in request.POST:
        new_type = request.POST.get('new_type_conge')
        if new_type:
            try:
                TypeConge.objects.create(type=new_type)
                messages.success(request, "Nouveau type de congé ajouté avec succès !")
            except Exception as e:
                messages.error(request, f"Erreur lors de l'ajout : {str(e)}")
        return redirect(f"{reverse('employee')}?tab=conge")


    # Logique pour ajouter un nouveau type d'absence
    if request.method == 'POST' and 'new_type_absence' in request.POST:
        if request.user.profil.poste == 'EMPLOYE' or request.user.is_superuser:
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
        return redirect(f"{reverse('employee')}?tab=absences")

    # Récupérer les notifications
    notifications = request.user.notifications.all().order_by('-created_at')
    unread_notifications_count = request.user.notifications.filter(is_read=False).count()

    # Contexte
    types_conge = TypeConge.objects.filter(flag_active=True)
    types_absence = TypeAbsence.objects.filter(flag_active=True)

    context = {
        'poste': poste,
        'is_home': False,
        'leave_requests': leave_requests_page,  # Utiliser l'objet paginé
        'absence_requests': absence_requests_page,  # Utiliser l'objet paginé
        'pointages': pointages_page,  # Utiliser l'objet paginé
        'types_conge': types_conge,
        'types_absence': types_absence,
        'status_choices': Conge._meta.get_field('status').choices,
        'login_histories': login_histories_page,  # Utiliser l'objet paginé
        'unread_notifications_count': unread_notifications_count,
        'notifications': notifications,
        'type_conge_choices': TypeConge.objects.filter(flag_active=True).values_list('id', 'type'),
        'type_absence_choices': TypeAbsence.objects.filter(flag_active=True).values_list('id', 'type'),
        'autorisations': autorisations_page,  # Utiliser l'objet paginé
        'start_date_from': start_date_from,
        'start_date_to': start_date_to,
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

    # Gestion du formulaire pour ajouter/modifier une entreprise
    if request.method == 'POST' and 'update_societe' in request.POST:
        societe_id = request.POST.get('societe_id')
        nom = request.POST.get('nom')
        adresse = request.POST.get('adresse')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        try:
            if societe_id:
                societe = Societe.objects.get(id=societe_id)
                societe.nom = nom
                societe.adresse = adresse
                societe.latitude = float(latitude) if latitude else None
                societe.longitude = float(longitude) if longitude else None
                societe.modified_by = request.user
                societe.save()
                messages.success(request, f"Entreprise {nom} mise à jour avec succès.")
            else:
                societe = Societe.objects.create(
                    nom=nom,
                    adresse=adresse,
                    latitude=float(latitude) if latitude else None,
                    longitude=float(longitude) if longitude else None,
                    modified_by=request.user
                )
                messages.success(request, f"Entreprise {nom} ajoutée avec succès.")
        except ValueError:
            messages.error(request, "Format de localisation invalide. Veuillez entrer des valeurs numériques pour la latitude et la longitude.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la gestion de l'entreprise : {str(e)}")
        return redirect(f"{reverse('responsable_rh_dashboard')}#pointage")

    # Gestion du formulaire pour ajouter/modifier un employé
    if request.method == 'POST' and 'update_employee' in request.POST:
        employee_id = request.POST.get('employee_id')
        username = request.POST.get('username')
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        telephone = request.POST.get('telephone')
        adresse = request.POST.get('adresse')
        societe_id = request.POST.get('societe')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        try:
            if employee_id:
                user = User.objects.get(id=employee_id)
                profil = Profil.objects.get(user=user)
                user.username = username
                profil.nom = nom
                profil.prenom = prenom
                profil.telephone = telephone
                profil.adresse = adresse
                profil.societe = Societe.objects.get(id=societe_id) if societe_id else None
                profil.latitude = float(latitude) if latitude else None
                profil.longitude = float(longitude) if longitude else None
                profil.modified_by = request.user
                user.save()
                profil.save()
                messages.success(request, f"Employé {username} mis à jour avec succès.")
            else:
                user = User.objects.create_user(
                    username=username,
                    password='defaultpassword123',  # À modifier par l'employé
                    is_active=True
                )
                profil = Profil.objects.create(
                    user=user,
                    nom=nom,
                    prenom=prenom,
                    telephone=telephone,
                    adresse=adresse,
                    poste='EMPLOYE',
                    societe=Societe.objects.get(id=societe_id) if societe_id else None,
                    latitude=float(latitude) if latitude else None,
                    longitude=float(longitude) if longitude else None,
                    modified_by=request.user
                )
                messages.success(request, f"Employé {username} ajouté avec succès.")
        except User.DoesNotExist:
            messages.error(request, "Employé non trouvé.")
        except Societe.DoesNotExist:
            messages.error(request, "Entreprise non trouvée.")
        except ValueError:
            messages.error(request, "Format de localisation invalide ou données incorrectes.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la gestion de l'employé : {str(e)}")
        return redirect(f"{reverse('responsable_rh_dashboard')}#pointage")

    # Récupérer les données pour les formulaires
    societes = Societe.objects.all()
    employees = User.objects.filter(profil__poste='EMPLOYE')
    pointages = Pointage.objects.all().order_by('-date')

    # Gestion des autres onglets (congés, absences, etc.) - inchangé
    autorisations = Autorisation.objects.all().order_by('-created_at')
    status = request.GET.get('status', '')
    start_date_from = request.GET.get('start_date_from', '')
    start_date_to = request.GET.get('start_date_to', '')

    if status:
        autorisations = autorisations.filter(status=status)
    if start_date_from:
        autorisations = autorisations.filter(start_datetime__date__gte=start_date_from)
    if start_date_to:
        autorisations = autorisations.filter(start_datetime__date__lte=start_date_to)

    autorisation_paginator = Paginator(autorisations, 10)
    autorisation_page = request.GET.get('autorisation_page', 1)
    try:
        autorisations = autorisation_paginator.page(autorisation_page)
    except PageNotAnInteger:
        autorisations = autorisation_paginator.page(1)
    except EmptyPage:
        autorisations = autorisation_paginator.page(autorisation_paginator.num_pages)

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

    leave_paginator = Paginator(leave_requests, 10)
    leave_page = request.GET.get('leave_page', 1)
    try:
        leave_requests = leave_paginator.page(leave_page)
    except PageNotAnInteger:
        leave_requests = leave_paginator.page(1)
    except EmptyPage:
        leave_requests = leave_paginator.page(leave_paginator.num_pages)

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

    absence_paginator = Paginator(absence_requests, 10)
    absence_page = request.GET.get('absence_page', 1)
    try:
        absence_requests = absence_paginator.page(absence_page)
    except PageNotAnInteger:
        absence_requests = absence_paginator.page(1)
    except EmptyPage:
        absence_requests = absence_paginator.page(absence_paginator.num_pages)

    login_histories = UserLoginHistory.objects.all().order_by('user', '-login_time')
    user_filter = request.GET.get('user_filter', '')
    if user_filter:
        login_histories = login_histories.filter(user__username__icontains=user_filter)

    history_paginator = Paginator(login_histories, 10)
    history_page = request.GET.get('history_page', 1)
    try:
        login_histories = history_paginator.page(history_page)
    except PageNotAnInteger:
        login_histories = history_paginator.page(1)
    except EmptyPage:
        login_histories = history_paginator.page(history_paginator.num_pages)

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
        'autorisations': autorisations,
        'societes': societes,
        'employees': employees,
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
        notifications = Notification.objects.filter(user=request.user, is_read=False)
        count_before = notifications.count()
        notifications.update(is_read=True)
        return JsonResponse({
            'success': True,
            'unread_count': 0,
            'message': f'{count_before} notifications marked as read.'
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
def load_leave_and_absence_data():
    # Charger les données des congés
    conges = Conge.objects.all().values(
        'employee__username',
        'type_conge__type',
        'start_date',
        'end_date',
        'status',
        'created_at'
    )
    conges_df = pd.DataFrame(list(conges))

    # Charger les données des absences
    absences = Absence.objects.all().values(
        'employee__username',
        'type_absence__type',
        'start_date',
        'end_date',
        'status',
        'created_at'
    )
    absences_df = pd.DataFrame(list(absences))

    # Combiner les données
    if not conges_df.empty and not absences_df.empty:
        data = pd.concat([conges_df, absences_df], ignore_index=True)
    elif not conges_df.empty:
        data = conges_df
    elif not absences_df.empty:
        data = absences_df
    else:
        return pd.DataFrame()  # Retourner un DataFrame vide si aucune donnée

    # Renommer les colonnes pour uniformiser
    data = data.rename(columns={
        'employee__username': 'employee',
        'type_conge__type': 'type_conge',
        'type_absence__type': 'type_absence'
    })

    # Remplir les colonnes manquantes
    if 'type_conge' not in data:
        data['type_conge'] = None
    if 'type_absence' not in data:
        data['type_absence'] = None

    return data
def train_leave_prediction_model():
    # Charger les données directement depuis la base
    data = load_leave_and_absence_data()

    if data.empty:
        logger.warning("Aucune donnée de congé ou d'absence disponible pour l'entraînement.")
        return False

    # Préparer les features
    data['start_date'] = pd.to_datetime(data['start_date'])
    data['month'] = data['start_date'].dt.month
    data['day_of_week'] = data['start_date'].dt.dayofweek
    data['is_weekend'] = data['day_of_week'].isin([5, 6]).astype(int)

    # Feature : type de congé/absence
    data['type'] = data['type_conge'].fillna(data['type_absence'])

    # Feature : employé (encodage)
    data['employee_code'] = data['employee'].astype('category').cat.codes

    # Target : 1 si absence/congé, 0 sinon
    data['is_absent'] = 1  # Puisque les données sont des congés/absences

    # Sélectionner les features et la cible
    features = ['employee_code', 'month', 'day_of_week', 'is_weekend']
    X = data[features]
    y = data['is_absent']

    # Diviser les données en entraînement et test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Entraîner un modèle RandomForest
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Évaluer le modèle
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logger.info(f"Précision du modèle : {accuracy}")

    # Sauvegarder le modèle
    joblib.dump(model, 'absence_prediction_model.pkl')
    logger.info("Modèle entraîné et sauvegardé avec succès.")
    return True



@login_required
def calendar_view(request):
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    # Normaliser le mois et l'année
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    first_day = datetime(year, month, 1)
    num_days = monthrange(year, month)[1]
    last_day = first_day + timedelta(days=num_days - 1)
    first_weekday = first_day.weekday()  # 0 = Lundi, 6 = Dimanche

    # Récupérer les pointages, congés et absences
    pointages = Pointage.objects.filter(
        employe=request.user,
        date__range=[first_day, last_day]
    ).values('date', 'heure_entree')

    conges = Conge.objects.filter(
        employee=request.user,
        start_date__lte=last_day,
        end_date__gte=first_day
    ).values('start_date', 'end_date')

    absences = Absence.objects.filter(
        employee=request.user,
        start_date__lte=last_day,
        end_date__gte=first_day
    ).values('start_date', 'end_date')

    # Créer une liste de jours avec leur statut
    days = []
    for day in range(1, num_days + 1):
        current_date = datetime(year, month, day).date()
        days.append({
            'day': day,
            'date': current_date,
            'worked': False,
            'absent': False
        })

    for pointage in pointages:
        for entry in days:
            if entry['date'] == pointage['date'] and pointage['heure_entree']:
                entry['worked'] = True

    for conge in conges:
        start = max(conge['start_date'], first_day.date())
        end = min(conge['end_date'], last_day.date())
        while start <= end:
            for entry in days:
                if entry['date'] == start:
                    entry['absent'] = True
                    entry['worked'] = False
            start += timedelta(days=1)

    for absence in absences:
        start = max(absence['start_date'], first_day.date())
        end = min(absence['end_date'], last_day.date())
        while start <= end:
            for entry in days:
                if entry['date'] == start:
                    entry['absent'] = True
                    entry['worked'] = False
            start += timedelta(days=1)

    # Créer une grille pour le calendrier (6 semaines x 7 jours)
    calendar_grid = []
    current_day = 1
    for week in range(6):
        week_row = []
        for day in range(7):
            if (week == 0 and day < first_weekday) or current_day > num_days:
                week_row.append(None)
            else:
                for entry in days:
                    if entry['day'] == current_day:
                        week_row.append(entry)
                        current_day += 1
                        break
        calendar_grid.append(week_row)

    context = {
        'year': year,
        'month': month,
        'calendar_grid': calendar_grid,
        'month_name': first_day.strftime('%B'),
        'weekdays': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
    }
    return render(request, 'ITservBack/calendar.html', context)
@login_required
def submit_autorisation(request):
    if request.method == 'POST':
        start_datetime = request.POST.get('start_datetime')
        end_datetime = request.POST.get('end_datetime')
        description = request.POST.get('description')

        try:
            start_datetime = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
            end_datetime = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
        except ValueError:
            messages.error(request, "Format de date/heure invalide.")
            logger.error(f"Format de date/heure invalide : start_datetime={start_datetime}, end_datetime={end_datetime}")
            return redirect('employee')

        if end_datetime <= start_datetime:
            messages.error(request, "La date de fin doit être postérieure à la date de début.")
            logger.warning(f"Date de fin ({end_datetime}) antérieure ou égale à la date de début ({start_datetime})")
            return redirect('employee')

        # Vérifier les chevauchements avec les congés approuvés ou planifiés de tous les employés
        overlapping_leaves = Conge.objects.filter(
            status__in=['approved', 'planned'],
            start_date__lte=end_datetime.date(),
            end_date__gte=start_datetime.date()
        )

        if overlapping_leaves.exists():
            overlapping_leave = overlapping_leaves.first()
            error_message = (
                f"Un employé ({overlapping_leave.employee.username}) est en congé du "
                f"{overlapping_leave.start_date} au {overlapping_leave.end_date}. "
                f"Les autorisations ne sont pas autorisées pendant cette période."
            )
            messages.error(request, error_message)
            logger.warning(
                f"Demande d'autorisation refusée pour {request.user.username} : chevauchement avec congé "
                f"de {overlapping_leave.employee.username} "
                f"({overlapping_leave.start_date} au {overlapping_leave.end_date})"
            )
            return redirect('employee')

        duration = end_datetime - start_datetime
        duration_hours = duration.total_seconds() / 3600

        try:
            autorisation = Autorisation.objects.create(
                employee=request.user,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                description=description,
                duration=f"{duration_hours:.2f} heure(s)",
                status='en cours',
                created_at=timezone.now()
            )
            messages.success(request, "Demande d'autorisation enregistrée avec succès.")
            logger.info(f"Autorisation créée avec succès : ID={autorisation.id}, pour {request.user.username}")

            # Notification pour l'utilisateur
            Notification.objects.create(
                user=request.user,
                message=f"Nouvelle demande d'autorisation soumise pour le {start_datetime.strftime('%Y-%m-%d %H:%M')}."
            )

            # Notification pour les Responsables RH
            responsables_rh = Profil.objects.filter(poste='ResponsableRH')
            for profil in responsables_rh:
                Notification.objects.create(
                    user=profil.user,
                    message=f"Nouvelle demande d'autorisation de {request.user.username} pour le "
                            f"{start_datetime.strftime('%Y-%m-%d %H:%M')}."
                )

        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement de l'autorisation : {str(e)}")
            logger.error(f"Erreur lors de la création de l'autorisation : {str(e)}")

        return redirect('employee')

    return redirect('employee')



@login_required
def edit_autorisation(request, id):
    autorisation = get_object_or_404(Autorisation, id=id, employee=request.user)
    if request.method == 'POST':
        start_datetime = request.POST.get('start_datetime')
        end_datetime = request.POST.get('end_datetime')
        description = request.POST.get('description')

        try:
            start_datetime = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M')
            end_datetime = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M')
        except ValueError:
            messages.error(request, "Format de date/heure invalide.")
            return redirect('employee')

        if end_datetime <= start_datetime:
            messages.error(request, "La date de fin doit être postérieure à la date de début.")
            return redirect('employee')

        duration = end_datetime - start_datetime
        duration_hours = duration.total_seconds() / 3600

        autorisation.start_datetime = start_datetime
        autorisation.end_datetime = end_datetime
        autorisation.description = description
        autorisation.duration = f"{duration_hours:.2f} heure(s)"
        autorisation.save()
        messages.success(request, "Demande d'autorisation modifiée avec succès.")
        return redirect('employee')

    # Pour une requête GET, nous n'affichons pas une page séparée
    # Les données sont gérées directement dans le template via JavaScript
    return redirect('employee')

@login_required
def delete_autorisation(request, id):
    autorisation = get_object_or_404(Autorisation, id=id, employee=request.user)
    autorisation.delete()
    messages.success(request, "Demande d'autorisation supprimée avec succès.")
    return redirect('employee')
@login_required
def accept_autorisation(request, id):
    try:
        profil = Profil.objects.get(user=request.user)
        if profil.poste != 'ResponsableRH':
            messages.error(request, "Vous n'avez pas les autorisations nécessaires pour effectuer cette action.")
            return redirect('employee')
    except Profil.DoesNotExist:
        messages.error(request, "Profil non trouvé.")
        return redirect('employee')

    autorisation = get_object_or_404(Autorisation, id=id)
    autorisation.status = 'Approved'
    autorisation.save()
    messages.success(request, f"La demande d'autorisation de {autorisation.employee.username} a été acceptée.")
    return redirect('responsable_rh_dashboard')

@login_required
def reject_autorisation(request, id):
    try:
        profil = Profil.objects.get(user=request.user)
        if profil.poste != 'ResponsableRH':
            messages.error(request, "Vous n'avez pas les autorisations nécessaires pour effectuer cette action.")
            return redirect('employee')
    except Profil.DoesNotExist:
        messages.error(request, "Profil non trouvé.")
        return redirect('employee')

    autorisation = get_object_or_404(Autorisation, id=id)
    autorisation.status = 'Rejected'
    autorisation.save()
    messages.success(request, f"La demande d'autorisation de {autorisation.employee.username} a été refusée.")
    return redirect('responsable_rh_dashboard')

@login_required
def leave_analysis_view(request):
    try:
        profil = Profil.objects.get(user=request.user)
    except Profil.DoesNotExist:
        messages.error(request, "Profil non trouvé.")
        return redirect('employee')

    # Collecter les données
    try:
        conges = Conge.objects.filter(status__iexact='approved').values('employee__username', 'start_date', 'end_date', 'type_conge__type')
        autorisations = Autorisation.objects.filter(status__iexact='approved').values('employee__username', 'start_datetime', 'end_datetime', 'duration')
        logger.info(f"Congés récupérés : {len(list(conges))}, Autorisations : {len(list(autorisations))}")
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des données : {str(e)}")
        messages.error(request, "Erreur lors de la récupération des données.")
        return render(request, 'ITservBack/leave_analysis.html', {'total_leaves': 0})

    # Convertir en DataFrames
    conges_df = pd.DataFrame(list(conges))
    autorisations_df = pd.DataFrame(list(autorisations))

    if not conges_df.empty:
        conges= conges_df['type'] = 'Conge'
        conges_df = conges_df.rename(columns={'start_date': 'start', 'end_date': 'end', 'type_conge__type': 'reason'})
    else:
        conges_df = pd.DataFrame(columns=['employee__username', 'start', 'end', 'reason', 'type'])

    if not autorisations_df.empty:
        autorisations_df['type'] = 'Autorisation'
        autorisations_df = autorisations_df.rename(columns={'start_datetime': 'start', 'end_datetime': 'end', 'duration': 'reason'})
    else:
        autorisations_df = pd.DataFrame(columns=['employee__username', 'start', 'end', 'reason', 'type'])

    combined_df = pd.concat([conges_df, autorisations_df], ignore_index=True)
    logger.info(f"Combined_df initial : {len(combined_df)} rows")
    logger.info(f"Échantillon de combined_df : \n{combined_df.head().to_string()}")

    # Analyser les tendances
    analysis_results = analyze_leave_trends(combined_df)

    # Graphiques
    monthly_trends = analysis_results['monthly_trends']
    employee_clusters = analysis_results['employee_clusters']

    if monthly_trends:
        months = list(monthly_trends.keys())
        counts = list(monthly_trends.values())
        monthly_fig = px.bar(
            x=months,
            y=counts,
            labels={'x': 'Mois', 'y': 'Nombre de congés/autorisations'},
            title="Tendances Mensuelles",
            color=counts,
            color_continuous_scale='Viridis'
        )
        monthly_fig.update_layout(xaxis={'tickmode': 'array', 'tickvals': list(range(1, 13)), 'ticktext': ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']})
        monthly_chart = monthly_fig.to_html(full_html=False)
    else:
        monthly_chart = "<p>Aucune donnée disponible pour les tendances mensuelles.</p>"

    if employee_clusters and len(employee_clusters) > 1:
        employee_months = combined_df.pivot_table(
            index='employee__username',
            columns='month',
            values='type',
            aggfunc='count',
            fill_value=0
        )
        employee_months['cluster'] = employee_months.index.map(employee_clusters)
        employee_months['total_leaves'] = employee_months.drop('cluster', axis=1).sum(axis=1)

        cluster_fig = px.scatter(
            employee_months,
            x=employee_months.index,
            y='total_leaves',
            color='cluster',
            labels={'x': 'Employé', 'y': 'Nombre total', 'color': 'Cluster'},
            title="Clusters d'Employés",
            hover_data={'cluster': True}
        )
        cluster_fig.update_layout(xaxis={'tickangle': 45})
        cluster_chart = cluster_fig.to_html(full_html=False)
    else:
        cluster_chart = "<p>Pas assez de données pour générer des clusters.</p>"

    context = {
        'total_leaves': len(combined_df),
        'monthly_trends': monthly_trends,
        'employee_clusters': employee_clusters,
        'monthly_chart': monthly_chart,
        'cluster_chart': cluster_chart,
    }
    return render(request, 'ITservBack/leave_analysis.html', context)

def analyze_leave_trends(combined_df):
    if combined_df.empty:
        logger.warning("Aucun congé ou autorisation trouvé pour l'analyse.")
        return {'monthly_trends': {}, 'employee_clusters': {}}

    # Convertir les dates
    combined_df['start'] = pd.to_datetime(combined_df['start'], utc=True, errors='coerce')
    combined_df['end'] = pd.to_datetime(combined_df['end'], utc=True, errors='coerce')
    logger.info(f"Après conversion, combined_df : \n{combined_df.head().to_string()}")

    # Filtrer les lignes invalides
    combined_df = combined_df.dropna(subset=['start'])
    logger.info(f"Après dropna, combined_df : {len(combined_df)} rows")

    if combined_df.empty or combined_df['start'].isna().all():
        logger.warning("Aucune donnée valide pour l'analyse après conversion et filtrage.")
        return {'monthly_trends': {}, 'employee_clusters': {}}

    # Extraire le mois
    combined_df['month'] = combined_df['start'].dt.month
    logger.info(f"Après ajout de 'month', colonnes : {combined_df.columns.tolist()}")
    logger.info(f"Échantillon avec 'month' : \n{combined_df.head().to_string()}")

    # Tendances mensuelles
    monthly_counts = combined_df.groupby('month').size().to_dict()

    # Clustering
    unique_employees = combined_df['employee__username'].nunique()
    employee_clusters = {}
    if unique_employees > 1:
        employee_months = combined_df.pivot_table(
            index='employee__username',
            columns='month',
            values='type',
            aggfunc='count',
            fill_value=0
        )
        kmeans = KMeans(n_clusters=min(3, len(employee_months)), random_state=42)
        clusters = kmeans.fit_predict(employee_months)
        employee_clusters = dict(zip(employee_months.index, clusters))

    return {
        'monthly_trends': monthly_counts,
        'employee_clusters': employee_clusters
    }

@login_required
@never_cache
def leave_planning_view(request):

    logger.info("Entrée dans leave_planning_view")

    # Vérifier si l'utilisateur est authentifié
    if not request.user.is_authenticated:
        logger.error("Utilisateur non authentifié, redirection vers login")
        return redirect('login')

    # Vérifier le rôle de l'utilisateur
    try:
        profil = Profil.objects.get(user=request.user)
        logger.info(f"Profil trouvé : {profil.poste}")
        if profil.poste == 'ResponsableRH':
            logger.warning("Utilisateur non autorisé, redirection vers 'employee'")
            messages.error(request, "Vous n'êtes pas autorisé à générer un planning.")
            return redirect('employee')
    except Profil.DoesNotExist:
        logger.error("Profil non trouvé, redirection vers 'employee'")
        messages.error(request, "Profil non trouvé.")
        return redirect('employee')

    # Définir les dates par défaut (période de 60 jours à partir d'aujourd'hui)
    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=60)

    # Si des dates sont passées via GET, les utiliser
    if 'start_date' in request.GET and 'end_date' in request.GET:
        try:
            start_date = timezone.datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
            if start_date > end_date:
                messages.error(request, "La date de fin doit être postérieure à la date de début.")
                return redirect('leave_planning')
        except ValueError:
            messages.error(request, "Format de date invalide. Utilisez AAAA-MM-JJ.")
            return redirect('leave_planning')

    logger.info(f"Période sélectionnée : {start_date} à {end_date}")

    # Liste des jours pour la période
    planning_days = [(start_date + timedelta(days=i)) for i in range((end_date - start_date).days + 1)]
    first_day = datetime(start_date.year, start_date.month, 1)
    num_days = monthrange(start_date.year, start_date.month)[1]
    last_day = first_day + timedelta(days=num_days - 1)

    # Récupérer toutes les demandes de congé en attente
    pending_leaves = Conge.objects.filter(status='En attente').select_related('employee', 'type_conge')
    logger.info(f"Nombre de demandes de congé en attente : {pending_leaves.count()}")
    # Déclencher la tâche Celery pour optimiser les congés en attente
    if pending_leaves.exists():
        task = optimize_leaves.delay()
        logger.info(f"Tâche Celery déclenchée pour l'optimisation des congés : Task ID {task.id}")
        messages.info(request,
                      "L'optimisation des congés est en cours. Veuillez rafraîchir la page dans quelques instants.")

    # Optimisation avec OR-Tools
    if pending_leaves.exists():
        # Créer le modèle de programmation par contraintes
        model = cp_model.CpModel()

        # Variables : une variable binaire par demande de congé (1 si acceptée, 0 sinon)
        leave_vars = {}
        for leave in pending_leaves:
            leave_vars[leave.id] = model.NewBoolVar(f'leave_{leave.id}')

        # Déterminer la période totale couverte par toutes les demandes
        all_dates = set()
        for leave in pending_leaves:
            current_date = leave.start_date
            while current_date <= leave.end_date:
                all_dates.add(current_date)
                current_date += timedelta(days=1)
        all_dates = sorted(list(all_dates))

        # Contrainte : un seul employé en congé par jour
        for date in all_dates:
            # Liste des demandes qui incluent cette date
            leaves_on_date = []
            for leave in pending_leaves:
                if leave.start_date <= date <= leave.end_date:
                    leaves_on_date.append(leave_vars[leave.id])
            # Contrainte : somme des variables <= 1
            model.Add(sum(leaves_on_date) <= 1)

        # Objectif : maximiser le nombre de demandes acceptées
        model.Maximize(sum(leave_vars.values()))

        # Résoudre le modèle
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info("Solution optimale trouvée par OR-Tools")
            # Mettre à jour les statuts des demandes
            for leave in pending_leaves:
                if solver.Value(leave_vars[leave.id]) == 1:
                    leave.status = 'approved'
                    logger.info(f"Demande {leave.id} approuvée : {leave.employee.username}, {leave.start_date} - {leave.end_date}")
                else:
                    leave.status = 'Rejeté'
                    logger.info(f"Demande {leave.id} rejetée : {leave.employee.username}, {leave.start_date} - {leave.end_date}")
                leave.save()
        else:
            logger.warning("Aucune solution optimale trouvée par OR-Tools")
            messages.error(request, "Impossible d'optimiser les congés. Veuillez contacter un administrateur.")

    # Récupérer les congés approuvés ou en attente dans la période affichée
    conges = Conge.objects.filter(
        status__in=['approved',],
        start_date__lte=end_date,
        end_date__gte=start_date
    ).select_related('employee', 'type_conge')
    logger.info(f"Nombre de congés trouvés pour la période : {conges.count()}")
    for conge in conges:
        logger.info(f"Congé : {conge.employee.username}, {conge.start_date} - {conge.end_date}, Statut: {conge.status}")

    # Préparer les congés avec les couleurs des employés
    employees = User.objects.filter(profil__poste='EMPLOYE').order_by('username')
    employee_colors = {}
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD', '#D4A5A5', '#9B59B6', '#3498DB', '#E74C3C', '#2ECC71']
    for idx, emp in enumerate(employees):
        employee_colors[emp.id] = colors[idx % len(colors)]

    leaves = []
    for conge in conges:
        if not conge.employee or not conge.type_conge:
            logger.warning(f"Congé invalide : ID {conge.id}, Employee: {conge.employee}, Type: {conge.type_conge}")
            continue
        leaves.append({
            'employee': conge.employee,
            'employee_color': employee_colors.get(conge.employee.id, '#000000'),
            'start_date': conge.start_date,
            'end_date': conge.end_date,
            'type_conge': conge.type_conge,
        })
        logger.info(f"Congé ajouté à leaves : {conge.employee.username}, {conge.start_date} - {conge.end_date}, Statut: {conge.status}")

    # Calculer les dates occupées
    occupied_dates = set()
    for leave in leaves:
        if not leave['start_date'] or not leave['end_date']:
            logger.warning(f"Congé avec dates invalides : {leave}")
            continue
        if leave['end_date'] < leave['start_date']:
            logger.warning(f"Congé avec end_date avant start_date : {leave}")
            continue
        current_date = leave['start_date']
        while current_date <= leave['end_date']:
            occupied_dates.add(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
    logger.info(f"Dates occupées : {occupied_dates}")

    # Convertir occupied_dates en liste pour JavaScript
    occupied_dates_list = list(occupied_dates)

    # Préparer les employés avec leurs couleurs pour la légende
    employees_with_colors = []
    for emp in employees:
        employees_with_colors.append({
            'username': emp.username,
            'color': employee_colors[emp.id]
        })

    # Calculer les dates pour la navigation entre les mois
    prev_month = first_day - timedelta(days=1)  # Aller au dernier jour du mois précédent
    prev_month_start = prev_month.replace(day=1)
    prev_month_end = prev_month.replace(day=monthrange(prev_month.year, prev_month.month)[1])

    next_month = (first_day + timedelta(days=32)).replace(day=1)  # Aller au premier jour du mois suivant
    next_month_start = next_month
    next_month_end = next_month.replace(day=monthrange(next_month.year, next_month.month)[1])

    logger.info(f"Navigation - Précédent : {prev_month_start} à {prev_month_end}")
    logger.info(f"Navigation - Suivant : {next_month_start} à {next_month_end}")

    # Récupérer les types de congé pour le formulaire
    types_conge = TypeConge.objects.filter(flag_active=True)

    # Préparer le contexte pour le template
    context = {
        'planning_days': planning_days,
        'leaves': leaves,
        'occupied_dates': occupied_dates_list,
        'month_name': first_day.strftime('%B %Y'),
        'employees_with_colors': employees_with_colors,
        'types_conge': types_conge,
        'prev_month_start': prev_month_start,
        'prev_month_end': prev_month_end,
        'next_month_start': next_month_start,
        'next_month_end': next_month_end,
    }

    logger.info("Rendu du template leave_planning.html")
    return render(request, 'ITservBack/leave_planning.html', context)
@login_required
def submit_leave_from_planning(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            try:
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']
                type_conge = form.cleaned_data['type_conge']
                reason = form.cleaned_data['reason']

                # Vérifier les chevauchements avec les congés existants
                overlapping_leaves = Conge.objects.filter(
                    status__in=['Approuvé', 'En attente'],
                    employee__profil__poste='EMPLOYE',
                    start_date__lte=end_date,
                    end_date__gte=start_date
                ).exclude(employee=request.user)

                if overlapping_leaves.exists():
                    overlapping_leave = overlapping_leaves.first()
                    error_message = (
                        f"Les dates demandées ({start_date} au {end_date}) chevauchent un congé existant de "
                        f"{overlapping_leave.employee.username} (du {overlapping_leave.start_date} au "
                        f"{overlapping_leave.end_date}). Veuillez choisir d'autres dates."
                    )
                    # Check if the request is AJAX by inspecting the X-Requested-With header
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'errors': error_message})
                    messages.error(request, error_message)
                    return redirect('leave_planning')

                # Créer la demande de congé
                leave = Conge(
                    employee=request.user,
                    type_conge=type_conge,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                    status='En attente'
                )
                leave.save()

                # Notification pour l'utilisateur
                Notification.objects.create(
                    user=request.user,
                    message=f"Nouvelle demande de congé soumise du {start_date} au {end_date}."
                )

                # Notification pour les Responsables RH
                responsables_rh = Profil.objects.filter(poste='ResponsableRH')
                for profil in responsables_rh:
                    Notification.objects.create(
                        user=profil.user,
                        message=f"Nouvelle demande de congé de {request.user.username} du {start_date} au {end_date}."
                    )

                # Check if the request is AJAX by inspecting the X-Requested-With header
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': "Demande de congé soumise avec succès !"})
                messages.success(request, "Demande de congé soumise avec succès !")
                return redirect('leave_planning')

            except Exception as e:
                logger.error(f"Erreur lors de la soumission de la demande de congé : {str(e)}")
                # Check if the request is AJAX by inspecting the X-Requested-With header
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': f"Erreur : {str(e)}"})
                messages.error(request, f"Erreur lors de la soumission de la demande : {str(e)}")
        else:
            logger.warning(f"Erreur de validation du formulaire : {form.errors}")
            # Check if the request is AJAX by inspecting the X-Requested-With header
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': str(form.errors)})
            messages.error(request, "Erreur dans le formulaire. Veuillez vérifier les champs.")
    return redirect('leave_planning')
def leave_events(request):
    start_date = request.GET.get('start_date', timezone.now().date())
    end_date = request.GET.get('end_date', (timezone.now().date() + timedelta(days=29)))
    try:
        start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    conges = Conge.objects.filter(
        status='approved',
        start_date__lte=end_date,
        end_date__gte=start_date
    ).select_related('employee')

    employees = User.objects.filter(profil__poste='EMPLOYE')
    employee_colors = {}
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD', '#D4A5A5', '#9B59B6', '#3498DB', '#E74C3C', '#2ECC71']
    for idx, emp in enumerate(employees):
        employee_colors[emp.id] = colors[idx % len(colors)]

    events = []
    for conge in conges:
        events.append({
            'title': conge.employee.username,
            'start': conge.start_date.strftime('%Y-%m-%d'),
            'end': (conge.end_date + timedelta(days=1)).strftime('%Y-%m-%d'),  # FullCalendar exclut le dernier jour
            'backgroundColor': employee_colors[conge.employee.id],
            'borderColor': employee_colors[conge.employee.id],
        })
    return JsonResponse(events, safe=False)
redis_client = redis.Redis(host='localhost', port=6379, db=0)
@login_required
def leave_recommendations(request):
         recommendations = redis_client.get(f"leave_recommendation:{request.user.id}")
         dates = json.loads(recommendations) if recommendations else []
         return render(request, 'ITservBack/leave_recommendations.html', {'dates': dates})

redis_client = redis.Redis(host='localhost', port=6379, db=0)
@login_required
def pointage_anomalies(request):
         if request.user.profil.poste != 'EMPLOYE':
             messages.error(request, "Accès non autorisé.")
             return redirect('employee')

         anomalies = [redis_client.lindex('pointage_anomalies', i).decode('utf-8')
                      for i in range(redis_client.llen('pointage_anomalies'))]
         return render(request, 'ITservBack/pointage_anomalies.html', {'anomalies': anomalies})


redis_client = redis.Redis(host='localhost', port=6379, db=0)

@login_required
def leave_sentiment_analysis(request):
         if request.user.profil.poste != 'EMPLOYE':
             messages.error(request, "Accès non autorisé.")
             return redirect('employee')

         sentiments = []
         for conge in Conge.objects.all():
             sentiment = redis_client.hget('leave_sentiments', conge.id)
             if sentiment:
                 sentiments.append({'reason': conge.reason, 'sentiment': sentiment.decode('utf-8')})
         for absence in Absence.objects.all():
             sentiment = redis_client.hget('leave_sentiments', absence.id)
             if sentiment:
                 sentiments.append({'reason': absence.reason, 'sentiment': sentiment.decode('utf-8')})

         return render(request, 'ITservBack/leave_sentiments.html', {'sentiments': sentiments})
@login_required
def export_pointages(request):
    pointages = Pointage.objects.filter(employe=request.user)
    wb = Workbook()
    ws = wb.active
    ws.title = "Pointages"
    ws.append(["Date", "Heure d'entrée", "Heure de sortie", "Localisation", "Valide"])
    for p in pointages:
        ws.append([
            p.date,
            p.heure_entree or "-",
            p.heure_sortie or "-",
            f"{p.latitude}, {p.longitude}" if p.latitude and p.longitude else "-",
            "Oui" if p.est_valide else "Non"
        ])
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=pointages.xlsx"
    return response





@login_required
def generate_leave_message(request, leave_id):
    logger.info(f"Entrée dans generate_leave_message pour congé ID {leave_id}")

    # Vérifier si l'utilisateur est authentifié et a un rôle d'employé
    if not request.user.is_authenticated or request.user.profil.poste != 'EMPLOYE':
        logger.error("Utilisateur non autorisé ou non authentifié, redirection vers login")
        messages.error(request, "Accès non autorisé.")
        return redirect('login')

    # Récupérer la demande de congé
    try:
        leave = Conge.objects.get(id=leave_id, employee=request.user)
    except Conge.DoesNotExist:
        logger.error(f"Demande de congé ID {leave_id} non trouvée")
        messages.error(request, "Demande de congé non trouvée.")
        return redirect('employee')

    # Charger le modèle d'IA générative (distilgpt2)
    try:
        generator = pipeline('text-generation', model='distilgpt2')
    except Exception as e:
        logger.error(f"Erreur lors du chargement du modèle d'IA générative : {str(e)}")
        messages.error(request, "Erreur lors de la génération du message.")
        return redirect('employee')

    # Générer un message en fonction du statut de la demande
    if leave.status == 'approved':
        prompt = f"Écrire un message à {request.user.username} pour confirmer que son congé du {leave.start_date} au {leave.end_date} a été approuvé."
    else:
        # Si la demande est rejetée, suggérer une période alternative
        alternative_dates = suggest_alternative_dates(leave)  # Fonction définie ci-dessous
        if alternative_dates:
            alt_start, alt_end = alternative_dates[0]
            prompt = f"Écrire un message à {request.user.username} pour expliquer que son congé du {leave.start_date} au {leave.end_date} a été rejeté et suggérer une nouvelle période du {alt_start} au {alt_end}."
        else:
            prompt = f"Écrire un message à {request.user.username} pour expliquer que son congé du {leave.start_date} au {leave.end_date} a été rejeté et qu'aucune période alternative n'est disponible."

    # Générer le message
    try:
        message = generator(prompt, max_length=50, num_return_sequences=1)[0]['generated_text']
        logger.info(f"Message généré : {message}")
    except Exception as e:
        logger.error(f"Erreur lors de la génération du message : {str(e)}")
        message = "Erreur lors de la génération du message. Veuillez contacter un administrateur."
        messages.error(request, message)

    # Sauvegarder le message dans les notifications
    Notification.objects.create(
        user=request.user,
        message=message
    )

    context = {
        'leave': leave,
        'message': message,
    }
    return render(request, 'ITservBack/leave_message.html', context)


def suggest_alternative_dates(leave):
    start_date = leave.start_date
    end_date = leave.end_date
    duration = (end_date - start_date).days + 1
    alternative_dates = []

    # Chercher une période de même durée sans chevauchement
    current_start = start_date + timedelta(days=1)
    max_attempts = 30  # Chercher sur 30 jours
    for _ in range(max_attempts):
        current_end = current_start + timedelta(days=duration - 1)
        overlapping_leaves = Conge.objects.filter(
            status='approved',
            start_date__lte=current_end,
            end_date__gte=current_start
        ).exclude(employee=leave.employee)
        if not overlapping_leaves.exists():
            alternative_dates.append((current_start, current_end))
            break
        current_start += timedelta(days=1)

    return alternative_dates
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calcule la distance en mètres entre deux points (latitude, longitude)."""
    R = 6371000  # Rayon de la Terre en mètres
    lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance
