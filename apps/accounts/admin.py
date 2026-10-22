from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import PasswordResetForm
from django.utils.html import format_html
from django.urls import reverse
from .models import CustomUser, AuditLog
from .forms import CustomUserCreationForm, CustomUserChangeForm

@admin.action(description="Envoyer un email de réinitialisation de mot de passe")
def send_password_reset_email(modeladmin, request, queryset):
    count = 0
    for user in queryset:
        form = PasswordResetForm({'email': user.email})
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name='registration/password_reset_email.html',
                subject_template_name='registration/password_reset_subject.txt',
            )
            count += 1
            AuditLog.objects.create(
                user=request.user,
                action='SETTINGS_UPDATE',
                ip_address=request.META.get('REMOTE_ADDR'),
                details=f"Email de réinitialisation envoyé à {user.email}"
            )
    modeladmin.message_user(request, f"{count} email(s) de réinitialisation envoyés avec succès.", messages.SUCCESS)

@admin.action(description="Valider les comptes sélectionnés")
def approve_accounts(modeladmin, request, queryset):
    pending = list(queryset.filter(is_active=False))
    for user in pending:
        user.is_active = True
        user.save(update_fields=['is_active'])
        AuditLog.objects.create(
            user=request.user,
            action='ACCOUNT_APPROVAL',
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f"Compte de {user.email} validé"
        )
    modeladmin.message_user(request, f"{len(pending)} compte(s) validé(s).", messages.SUCCESS)

@admin.action(description="Basculer le rôle Administrateur (is_staff)")
def toggle_staff_status(modeladmin, request, queryset):
    for user in queryset:
        user.is_staff = not user.is_staff
        user.save(update_fields=['is_staff'])
        AuditLog.objects.create(
            user=request.user,
            action='ROLE_CHANGE',
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f"Rôle administrateur de {user.email} basculé vers {user.is_staff}"
        )
    modeladmin.message_user(request, f"Statut administrateur mis à jour pour {queryset.count()} utilisateur(s).", messages.SUCCESS)

@admin.action(description="Supprimer les comptes sélectionnés (avec cascade)")
def delete_accounts_cascade(modeladmin, request, queryset):
    count = queryset.count()
    for user in queryset:
        email = user.email
        user.delete()
        AuditLog.objects.create(
            user=request.user,
            action='ACCOUNT_DELETION',
            ip_address=request.META.get('REMOTE_ADDR'),
            details=f"Suppression complète du compte et des données associées pour {email}"
        )
    modeladmin.message_user(request, f"{count} compte(s) supprimé(s) définitivement.", messages.SUCCESS)


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ('email', 'is_active', 'is_staff', 'rules_count', 'notification_channels', 'has_unica_credentials', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'date_joined')
    search_fields = ('email',)
    ordering = ('-date_joined',)
    actions = [approve_accounts, send_password_reset_email, toggle_staff_status, delete_accounts_cascade]

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )

    def rules_count(self, obj):
        count = obj.filter_rules.count() if hasattr(obj, 'filter_rules') else 0
        return f"{count} règle(s)"
    rules_count.short_description = "Règles actives"

    def notification_channels(self, obj):
        if not hasattr(obj, 'notification_preferences'):
            return "Aucun"
        channels = [p.get_channel_display() for p in obj.notification_preferences.filter(is_active=True)]
        return ", ".join(channels) if channels else "Aucun canal actif"
    notification_channels.short_description = "Canaux notifs"

    def has_unica_credentials(self, obj):
        if hasattr(obj, 'unica_credentials') and obj.unica_credentials.unica_identifier:
            consent = " (Auto-inscr. activée)" if obj.unica_credentials.auto_registration_consent else ""
            return format_html("<span style='color:green;'>Configuré{}</span>", consent)
        return format_html("<span style='color:gray;'>Non configuré</span>")
    has_unica_credentials.short_description = "Identifiants UniCA"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'user', 'ip_address', 'details')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__email', 'details', 'ip_address')
    readonly_fields = ('timestamp', 'action', 'user', 'ip_address', 'details')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
