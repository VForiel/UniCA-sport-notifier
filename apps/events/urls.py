from django.urls import path
from . import views

urlpatterns = [
    path('rules/', views.rules_view, name='rules_list'),
    path('rules/<int:rule_id>/delete/', views.delete_rule_view, name='delete_rule'),
    path('credentials/', views.credentials_view, name='credentials_settings'),
    path('events/', views.recent_events_view, name='recent_events'),
]
