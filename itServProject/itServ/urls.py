from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("homeback/", views.homeback, name="homeback"),
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('employe/', views.employee, name='employee'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # Update this to use responsable_rh_dashboard
    path('responsablerh/dashboard/', views.responsable_rh_dashboard, name='responsablerh_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('changer-password/', views.ChangePasswordView.as_view(), name='changer_password'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password_reset'),
    path('reset-password/<uidb64>/<token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('leave-request/', views.leave_request, name='leave_request'),
    path('leave-list/', views.leave_list, name='leave_list'),
    path('list/', views.list_profil, name='list'),
    path('responsable_rh/', views.responsable_rh_dashboard, name='responsable_rh_dashboard'),
    # Consolidate duplicate update_leave_status paths
    path('responsable_rh/leave/<int:leave_id>/status/<str:status>/', views.update_leave_status, name='update_leave_status'),
    # path('update_leave_status/<int:leave_id>/<str:status>/', views.update_leave_status, name='update_leave_status'),  # Remove duplicate
    path('mark-notification-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('get-unread-count/', views.get_unread_count, name='get_unread_count'),
    #path('absence/request/', views.absence_request, name='absence_request'),
   # path('absence/list/', views.absence_list, name='absence_list'),
    #path('absence/update/<int:absence_id>/<str:status>/', views.update_absence_status, name='update_absence_status'),
    path('employe/', views.employee, name='employee'),
    path('export-pointages/', views.export_pointages_to_excel, name='export_pointages'),
    path('update_leave_status/<int:leave_id>/<str:status>/', views.update_leave_status, name='update_leave_status'),
    path('update_absence_status/<int:absence_id>/<str:status>/', views.update_absence_status, name='update_absence_status'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('autorisation/submit/', views.submit_autorisation, name='submit_autorisation'),
    path('autorisation/edit/<int:id>/', views.edit_autorisation, name='edit_autorisation'),
    path('autorisation/delete/<int:id>/', views.delete_autorisation, name='delete_autorisation'),
    path('autorisation/accept/<int:id>/', views.accept_autorisation, name='accept_autorisation'),
    path('autorisation/reject/<int:id>/', views.reject_autorisation, name='reject_autorisation'),
    path('responsablerh/leave-analysis/', views.leave_analysis_view, name='leave_analysis'),
    path('responsablerh/leave-planning/', views.leave_planning_view, name='leave_planning'),
    path('leave-events/', views.leave_events, name='leave_events'),
    path('submit-leave-from-planning/', views.submit_leave_from_planning,name='submit_leave_from_planning'),
    path('leave_recommendations/', views.leave_recommendations,name='leave_recommendations'),
    path('pointage_anomalies/', views.pointage_anomalies, name='pointage_anomalies'),
    path('leave_sentiments/', views.leave_sentiment_analysis, name='leave_sentiments'),
    path('export_pointages/', views.export_pointages, name='export_pointages'),
    path('leave_message/<int:leave_id>/', views.generate_leave_message, name='generate_leave_message'),

              ]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)