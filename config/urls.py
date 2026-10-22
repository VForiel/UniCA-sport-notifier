from django.contrib import admin
from django.urls import path, include
from apps.core.views import admin_login_view

urlpatterns = [
    # Connexion à l'admin via allauth, qui limite le nombre de tentatives
    path('admin/login/', admin_login_view),
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
