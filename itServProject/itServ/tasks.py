# itServ/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Conge

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def generate_leave_planning(self, start_date=None, end_date=None):
    logger.info("Début de la génération du planning des congés.")
    try:
        # Définir la période de planification
        if start_date is None or end_date is None:
            start_date = timezone.now().date()
            end_date = start_date + timedelta(days=60)
        else:
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

        logger.info(f"Période de planification demandée : {start_date} à {end_date}")

        # Supprimer les anciens congés planifiés pour éviter les doublons
        conges_to_delete = Conge.objects.filter(
            status='planned',
            start_date__gte=start_date,
            end_date__lte=end_date
        )
        logger.info(f"Congés à supprimer (statut 'planned') : {[(c.employee.username, c.start_date, c.end_date) for c in conges_to_delete]}")
        conges_to_delete.delete()
        logger.info("Anciens congés planifiés supprimés.")

        # Retourner un message indiquant que la génération automatique est désactivée
        logger.info("Génération automatique des congés désactivée. Les employés doivent soumettre leurs demandes manuellement.")
        return {
            "status": "success",
            "message": "Génération automatique désactivée. Les employés doivent soumettre leurs demandes manuellement."
        }

    except Exception as e:
        logger.error(f"Erreur dans generate_leave_planning : {str(e)}", exc_info=True)
        raise