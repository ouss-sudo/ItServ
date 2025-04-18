# Generated by Django 4.2.9 on 2025-03-22 03:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('itServ', '0014_remove_absence_image_alter_absence_type_absence_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Pointage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('heure_entree', models.DateTimeField(blank=True, null=True, verbose_name="Heure d'entrée")),
                ('heure_sortie', models.DateTimeField(blank=True, null=True, verbose_name='Heure de sortie')),
                ('date', models.DateField(default=django.utils.timezone.now, verbose_name='Date')),
                ('cree_le', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('mis_a_jour_le', models.DateTimeField(auto_now=True, verbose_name='Mis à jour le')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pointages', to=settings.AUTH_USER_MODEL, verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Pointage',
                'verbose_name_plural': 'Pointages',
            },
        ),
    ]
