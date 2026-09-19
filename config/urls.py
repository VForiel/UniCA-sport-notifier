from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('', include('apps.core.urls')),
    path('', include('apps.events.urls')),
    path('notifications/', include('apps.notifications.urls')),
]

admin.site.site_header = "UniCA Sport Notifier — Administration"
admin.site.site_title = "UniCA Sport Notifier"
admin.site.index_title = "Tableau de bord d'administration"
