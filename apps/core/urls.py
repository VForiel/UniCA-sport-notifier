from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('service-worker.js', views.service_worker_view, name='service_worker'),
    path('manifest.json', views.manifest_view, name='pwa_manifest'),
]
