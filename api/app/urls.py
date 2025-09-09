# api/urls.py

from django.urls import path, include
from service.views import ping, LoginView


urlpatterns = [
    path("api/ping/", ping),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/", include("service.urls")),

]