from django.urls import path
from . import views

urlpatterns=[
    path("",views.home,name="home"),
    path("login/",views.login,name="login"),
    path("homeback/",views.homeback,name="homeback"),
    path('signup/',views.SignupView.as_view(), name='signup'),


]
