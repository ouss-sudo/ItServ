from django.contrib import admin
from .models import Profil, UserLoginHistory

@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'poste', 'first_login', 'last_authentication')

@admin.register(UserLoginHistory)
class UserLoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'poste')
    list_filter = ('user', 'poste')
    ordering = ('-login_time',)