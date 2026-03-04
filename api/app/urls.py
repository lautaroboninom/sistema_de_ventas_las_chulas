# api/urls.py

from django.urls import include, path
from service.views import ping


urlpatterns = [
    path('api/ping/', ping),
    path('api/health/', ping),
    path('api/', include('service.urls')),
]
