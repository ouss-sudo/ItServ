# Generated by Django 4.2.9 on 2025-03-10 01:51

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('itServ', '0007_leaverequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='profil',
            name='date_creation',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='profil',
            name='date_maj',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
