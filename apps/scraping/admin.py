from django.contrib import admin
from django.utils.html import format_html
from .models import ServerSettings, ScanLog

@admin.register(ServerSettings)
class ServerSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Fréquences et Rythme de Scan", {
            'fields': (
                ('day_interval_seconds', 'day_jitter_seconds'),
                ('night_interval_seconds', 'night_jitter_seconds'),
                ('day_start_time', 'night_start_time'),
            ),
            'description': "Configurez les délais et le jitter aléatoire pour le mode diurne et nocturne (fuseau Europe/Paris)."
        }),
        ("Configuration Email / SMTP", {
            'classes': ('collapse',),
            'fields': (
                ('smtp_host', 'smtp_port'),
                ('smtp_user', 'smtp_password'),
                ('smtp_use_tls', 'smtp_from_email'),
            )
        }),
        ("Clés Google OAuth2", {
            'classes': ('collapse',),
            'fields': ('google_oauth_client_id', 'google_oauth_client_secret')
        }),
        ("Bots et Messageries Instantanées", {
            'classes': ('collapse',),
            'fields': (
                'telegram_bot_token',
                'whatsapp_api_token',
                'whatsapp_phone_number_id',
                'whatsapp_business_account_id',
            )
        }),
    )

    def has_add_permission(self, request):
        # Empêche la création de multiples instances (Singleton)
        return not ServerSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'status_badge', 'execution_duration_seconds', 'events_found_count', 'new_events_count')
    list_filter = ('status', 'timestamp')
    search_fields = ('error_message',)
    readonly_fields = ('timestamp', 'execution_duration_seconds', 'events_found_count', 'new_events_count', 'status', 'error_message')

    def status_badge(self, obj):
        color = "green" if obj.status == 'succès' else "crimson"
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.status.upper())
    status_badge.short_description = "Statut"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
