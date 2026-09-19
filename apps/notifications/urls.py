from django.urls import path
from . import views

urlpatterns = [
    path('', views.preferences_view, name='notification_preferences'),
    path('push/vapid-key/', views.push_vapid_key_view, name='push_vapid_key'),
    path('push/subscribe/', views.push_subscribe_view, name='push_subscribe'),
    path('test/', views.simulate_test_notification_view, name='simulate_notification_test'),
]
