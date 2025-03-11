# Generated by Django 4.2.9 on 2025-03-10 02:07

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('itServ', '0008_profil_date_creation_profil_date_maj'),
    ]

    operations = [
        migrations.CreateModel(
            name='Conge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('date_mise_a_jour', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_requests', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TypeConge',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('type', models.CharField(max_length=100, unique=True)),
                ('flag_active', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(default=django.utils.timezone.now)),
                ('date_maj', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.DeleteModel(
            name='LeaveRequest',
        ),
    ]
