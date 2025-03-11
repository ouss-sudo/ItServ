from django.urls import path
from . import views

urlpatterns=[
    path("",views.home,name="home"),
   path("login/",views.LoginView.as_view(),name="login"),
    path("homeback/",views.homeback,name="homeback"),
    path('signup/',views.SignupView.as_view(), name='signup'),
    #path('login/', views.logout_view(), name='login'),

    path('employe/', views.employee, name='employee'),
path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('responsablerh/dashboard/', views.responsablerh_dashboard, name='responsablerh_dashboard'),
    path('logout/', views.logout_view, name='logout'),  # Nouvelle route pour logout
    path('changer-password/', views.ChangePasswordView.as_view(), name='changer_password'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password_reset'),
    path('reset-password/<uidb64>/<token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('leave-request/', views.leave_request, name='leave_request'),
    path('leave-list/', views.leave_list, name='leave_list'),
    path('list/', views.list_profil, name='list'),  # Nouvelle URL pour le tableau de bord admin
    path('responsable_rh/', views.responsable_rh_dashboard, name='responsable_rh_dashboard'),
    path('responsable_rh/leave/<int:leave_id>/status/<str:status>/', views.update_leave_status, name='update_leave_status'),
    # Nouvelle route

]
