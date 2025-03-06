from django.urls import path
from . import views

urlpatterns=[
    path("",views.home,name="home"),
    path("login/",views.LoginView.as_view(),name="login"),
    path("homeback/",views.homeback,name="homeback"),
        path('signup/',views.SignupView.as_view(), name='signup'),
    path('employe/', views.employee, name='employee'),
path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('responsablerh/dashboard/', views.responsablerh_dashboard, name='responsablerh_dashboard'),

]
