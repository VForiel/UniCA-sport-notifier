from django.contrib import admin
from django.utils.html import format_html
from .models import Event, FilterRule, UniCACredentials, RegistrationAttempt

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'date_event', 'location', 'first_detected_at', 'view_link')
    list_filter = ('event_type', 'first_detected_at')
    search_fields = ('title', 'description', 'location', 'source_id')
    readonly_fields = ('source_id', 'content_hash', 'first_detected_at')

    def view_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">Voir sur UniCA</a>', obj.url)
    view_link.short_description = "Lien UniCA"


@admin.register(FilterRule)
class FilterRuleAdmin(admin.ModelAdmin):
    list_display = ('user', 'rule_type', 'match_mode', 'keyword', 'target_field', 'case_sensitive', 'created_at')
    list_filter = ('rule_type', 'match_mode', 'target_field', 'case_sensitive')
    search_fields = ('user__email', 'keyword')


@admin.register(UniCACredentials)
class UniCACredentialsAdmin(admin.ModelAdmin):
    list_display = ('user', 'unica_identifier', 'auto_registration_consent', 'is_configured', 'updated_at')
    list_filter = ('auto_registration_consent',)
    search_fields = ('user__email', 'unica_identifier')
    readonly_fields = ('encrypted_password_preview', 'updated_at')

    def is_configured(self, obj):
        return bool(obj.unica_identifier and obj.encrypted_password)
    is_configured.boolean = True
    is_configured.short_description = "Chiffré & Configuré"

    def encrypted_password_preview(self, obj):
        if obj.encrypted_password:
            return format_html("<code>[Chiffré via Fernet - {} octets]</code>", len(obj.encrypted_password))
        return "Non configuré"
    encrypted_password_preview.short_description = "Mot de passe chiffré"


@admin.register(RegistrationAttempt)
class RegistrationAttemptAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'status_badge', 'timestamp', 'hold_expires_at')
    list_filter = ('status', 'timestamp')
    search_fields = ('user__email', 'event__title', 'error_message')
    readonly_fields = ('event', 'user', 'status', 'timestamp', 'hold_expires_at', 'error_message')

    def status_badge(self, obj):
        colors = {
            'réussi': 'green',
            'échoué': 'crimson',
            'en_attente': 'goldenrod',
            'expiré': 'gray'
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Statut"
