# Generated by Django 4.2.9 on 2025-03-20 03:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('itServ', '0011_notification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conge',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('veapprod', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20),
        ),
        migrations.CreateModel(
            name='Absence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('approved', 'Approuvé'), ('rejected', 'Refusé')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='absence_requests', to=settings.AUTH_USER_MODEL)),
                ('type_conge', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='absence_requests', to='itServ.typeconge')),
            ],
        ),
    ]
