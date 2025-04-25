# itServ/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Conge
import redis
from itServ.models import Conge, User
import json
from sklearn.cluster import KMeans
from ortools.constraint_solver import pywrapcp as cp_model

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
            status='approved',
            start_date__gte=start_date,
            end_date__lte=end_date
        )
        logger.info(f"Congés à supprimer (statut 'approved') : {[(c.employee.username, c.start_date, c.end_date) for c in conges_to_delete]}")
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
@shared_task
def optimize_leaves():
    """
    Tâche Celery pour optimiser les demandes de congé en attente avec OR-Tools.
    """
    logger.info("Début de l'optimisation des congés avec OR-Tools via Celery")

    # Récupérer toutes les demandes de congé en attente
    pending_leaves = Conge.objects.filter(status='En attente').select_related('employee', 'type_conge')
    logger.info(f"Nombre de demandes de congé en attente : {pending_leaves.count()}")

    if not pending_leaves.exists():
        logger.info("Aucune demande de congé en attente à optimiser.")
        return "Aucune demande à optimiser."

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
        leaves_on_date = []
        for leave in pending_leaves:
            if leave.start_date <= date <= leave.end_date:
                leaves_on_date.append(leave_vars[leave.id])
        model.Add(sum(leaves_on_date) <= 1)

    # Objectif : maximiser le nombre de demandes acceptées
    model.Maximize(sum(leave_vars.values()))

    # Résoudre le modèle
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        logger.info("Solution optimale trouvée par OR-Tools")
        for leave in pending_leaves:
            if solver.Value(leave_vars[leave.id]) == 1:
                leave.status = 'Approved'  # Uniformiser avec 'Approved'
                logger.info(f"Demande {leave.id} approuvée : {leave.employee.username}, {leave.start_date} - {leave.end_date}")
            else:
                leave.status = 'Rejeté'
                logger.info(f"Demande {leave.id} rejetée : {leave.employee.username}, {leave.start_date} - {leave.end_date}")
            leave.save()
        return "Optimisation terminée avec succès."
    else:
        logger.warning("Aucune solution optimale trouvée par OR-Tools")
        return "Échec de l'optimisation."

logger = logging.getLogger(__name__)
redis_client = redis.Redis(host='localhost', port=6379, db=0)

@shared_task
def recommend_leave_dates():
         logger.info("Calcul des recommandations de congés")
         conges = Conge.objects.filter(status='approved').values(
             'employee__id', 'start_date', 'end_date'
         )
         df = pd.DataFrame(conges)

         if df.empty:
             logger.warning("Aucun congé pour générer des recommandations")
             return

         # Créer une liste de dates futures
         start_date = datetime.now().date()
         end_date = start_date + timedelta(days=365)
         dates = pd.date_range(start_date, end_date)
         date_df = pd.DataFrame({'date': dates})
         date_df['month'] = date_df['date'].dt.month
         date_df['day_of_week'] = date_df['date'].dt.dayofweek
         date_df['leave_count'] = 0

         # Compter les congés par date
         for _, row in df.iterrows():
             current = row['start_date']
             while current <= row['end_date']:
                 date_df.loc[date_df['date'] == current, 'leave_count'] += 1
                 current += timedelta(days=1)

         # Clustering pour identifier les périodes optimales
         X = date_df[['month', 'day_of_week', 'leave_count']]
         kmeans = KMeans(n_clusters=5, random_state=42)
         date_df['cluster'] = kmeans.fit_predict(X)

         # Sélectionner les clusters avec peu de congés
         optimal_dates = date_df[date_df['cluster'] == date_df.groupby('cluster')['leave_count'].mean().idxmin()]
         optimal_dates = optimal_dates['date'].dt.strftime('%Y-%m-%d').tolist()

         # Stocker pour chaque employé
         for user in User.objects.filter(profil__poste='EMPLOYE'):
             redis_client.set(f"leave_recommendation:{user.id}", json.dumps(optimal_dates[:5]))
         logger.info("Recommandations stockées dans Redis")


logger = logging.getLogger(__name__)
redis_client = redis.Redis(host='localhost', port=6379, db=0)
@shared_task
def detect_pointage_anomalies():
    logger.info("Analyse des anomalies de pointage")
    pointages = Pointage.objects.filter(date=timezone.now().date(), est_valide=False)
    anomalies = []
    for pointage in pointages:
        anomaly = f"Anomalie pour {pointage.employe.username} le {pointage.date} : localisation hors rayon"
        redis_client.rpush('pointage_anomalies', anomaly)
        Notification.objects.create(
            user=pointage.employe,
            message=anomaly
        )
        anomalies.append(anomaly)
        logger.info(anomaly)
    logger.info(f"{len(anomalies)} anomalies détectées")
    return anomalies
redis_client = redis.Redis(host='localhost', port=6379, db=0)
@shared_task
def analyze_leave_reasons():
    logger.info("Analyse des sentiments des raisons")
    conges = Conge.objects.all().values('id', 'reason')
    absences = Absence.objects.all().values('id', 'reason')
    df = pd.concat([
        pd.DataFrame(conges).assign(type='conge'),
        pd.DataFrame(absences).assign(type='absence')
    ])

    if df['reason'].isna().all():
        logger.warning("Aucune raison valide à analyser")
        return

    # Supposons un étiquetage initial (simulé ici, à remplacer par IA générative)
    sample_data = {
        'reason': ['repos familial', 'maladie', 'vacances', 'urgence personnelle'],
        'sentiment': ['positif', 'négatif', 'positif', 'négatif']
    }
    sample_df = pd.DataFrame(sample_data)

    # Entraîner un modèle
    pipeline = make_pipeline(TfidfVectorizer(), LogisticRegression())
    pipeline.fit(sample_df['reason'], sample_df['sentiment'])

    # Prédire les sentiments
    df['sentiment'] = pipeline.predict(df['reason'].fillna(''))

    # Stocker dans Redis
    for idx, row in df.iterrows():
        redis_client.hset('leave_sentiments', row['id'], row['sentiment'])
    logger.info("Sentiments stockés dans Redis")
