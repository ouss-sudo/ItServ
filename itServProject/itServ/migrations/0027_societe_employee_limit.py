# Generated by Django 4.2.9 on 2025-04-25 01:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('itServ', '0026_profil_societe'),
    ]

    operations = [
        migrations.AddField(
            model_name='societe',
            name='employee_limit',
            field=models.PositiveIntegerField(default=10, verbose_name="Limite d'employés"),
        ),
    ]
