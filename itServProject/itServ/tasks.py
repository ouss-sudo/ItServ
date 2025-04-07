# itServ/tasks.py
import logging
from celery import shared_task
from ortools.sat.python import cp_model
from django.utils import timezone
from datetime import timedelta
from .models import Conge, Autorisation, LeavePreference, User
import pandas as pd

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_leave_planning(self, start_date=None, end_date=None):
    logger.info("Début de la génération du planning des congés.")
    try:
        # Définir la période de planification
        if start_date is None or end_date is None:
            start_date = timezone.now().date()
            end_date = start_date + timedelta(days=29)
        else:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
        planning_days = [(start_date + timedelta(days=i)) for i in range((end_date - start_date).days + 1)]
        logger.info(f"Période de planification : {start_date} à {end_date}")

        # Supprimer les anciens congés planifiés pour éviter les doublons
        Conge.objects.filter(
            status='planned',
            start_date__gte=start_date,
            end_date__lte=end_date
        ).delete()
        logger.info("Anciens congés planifiés supprimés.")

        # Collecter les employés (exclure les non-employés)
        employees = User.objects.filter(profil__poste='EMPLOYE')
        employee_ids = [e.id for e in employees]
        logger.info(f"Nombre d'employés trouvés : {len(employee_ids)}")
        if not employee_ids:
            logger.warning("Aucun employé trouvé.")
            return {"status": "failed", "message": "Aucun employé trouvé."}

        # Collecter les préférences
        preferences = LeavePreference.objects.filter(
            preferred_start_date__gte=start_date,
            preferred_end_date__lte=end_date
        ).values('employee__id', 'preferred_start_date', 'preferred_end_date', 'priority')
        preferences_df = pd.DataFrame(list(preferences))
        logger.info(f"Nombre de préférences trouvées : {len(preferences_df)}")

        # Collecter les congés/autorisations existants
        existing_leaves = Conge.objects.filter(
            status__iexact='approved',
            start_date__lte=end_date,
            end_date__gte=start_date
        ).values('employee__id', 'start_date', 'end_date')
        existing_autorisations = Autorisation.objects.filter(
            status__iexact='approved',
            start_datetime__date__lte=end_date,
            end_datetime__date__gte=start_date
        ).values('employee__id', 'start_datetime__date', 'end_datetime__date')
        existing_leaves_df = pd.DataFrame(list(existing_leaves)).rename(columns={'start_date': 'start', 'end_date': 'end'})
        existing_autorisations_df = pd.DataFrame(list(existing_autorisations)).rename(
            columns={'start_datetime__date': 'start', 'end_datetime__date': 'end'}
        )
        existing_df = pd.concat([existing_leaves_df, existing_autorisations_df], ignore_index=True)
        logger.info(f"Nombre de congés/autorisations existants : {len(existing_df)}")

        # Initialiser le modèle OR-Tools
        model = cp_model.CpModel()

        # Variables
        leave = {}
        for e in employee_ids:
            for d in planning_days:
                leave[(e, d)] = model.NewBoolVar(f'leave_e{e}_d{d}')

        # Contraintes
        max_employees_on_leave = 3
        for d in planning_days:
            model.Add(sum(leave[(e, d)] for e in employee_ids) <= max_employees_on_leave)

        for _, row in existing_df.iterrows():
            emp_id = row['employee__id']
            start = row['start']
            end = row['end']
            for d in planning_days:
                if start <= d <= end:
                    model.Add(leave[(emp_id, d)] == 0)

        leave_duration = 5
        for e in employee_ids:
            start_leave = {}
            for i, d in enumerate(planning_days[:-leave_duration + 1]):
                start_leave[(e, d)] = model.NewBoolVar(f'start_leave_e{e}_d{d}')
                for j in range(leave_duration):
                    if i + j < len(planning_days):
                        model.AddImplication(start_leave[(e, d)], leave[(e, planning_days[i + j])])
            model.Add(sum(start_leave[(e, d)] for d in planning_days[:-leave_duration + 1]) <= 1)

        preference_score = []
        for _, row in preferences_df.iterrows():
            emp_id = row['employee__id']
            pref_start = row['preferred_start_date']
            priority = row['priority']
            if pref_start in planning_days:
                score = model.NewBoolVar(f'pref_score_e{emp_id}_d{pref_start}')
                model.AddImplication(score, start_leave[(emp_id, pref_start)])
                preference_score.append(score * (6 - priority))
        model.Maximize(sum(preference_score))

        # Résoudre
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        logger.info(f"Statut du solveur : {status}")

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            planning = []
            for e in employee_ids:
                leave_days = []
                for d in planning_days:
                    if solver.Value(leave[(e, d)]):
                        leave_days.append(d)
                if leave_days:
                    start = min(leave_days)
                    end = max(leave_days)
                    employee = User.objects.get(id=e)
                    conge = Conge(
                        employee=employee,
                        start_date=start,
                        end_date=end,
                        status='planned',
                    )
                    conge.save()
                    planning.append({
                        'employee_id': e,
                        'start_date': start,
                        'end_date': end,
                        'type': 'planned_leave'
                    })
            logger.info(f"Planning généré avec succès : {len(planning)} congés attribués.")
            return {"status": "success", "planning": planning}
        else:
            logger.warning("Aucun planning réalisable trouvé.")
            return {"status": "failed", "message": "Aucun planning réalisable."}
    except Exception as e:
        logger.error(f"Erreur dans generate_leave_planning : {str(e)}", exc_info=True)
        raise