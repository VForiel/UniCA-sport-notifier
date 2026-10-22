import logging
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import AuditLog

logger = logging.getLogger(__name__)


def hold_for_approval(request, user):
    """Désactive un compte fraîchement créé et prévient les administrateurs."""
    user.is_active = False
    user.save(update_fields=['is_active'])
    AuditLog.objects.create(
        user=user,
        action='SIGNUP',
        ip_address=request.META.get('REMOTE_ADDR') if request else None,
        details=f"Demande d'accès de {user.email}, en attente de validation",
    )

    admins = list(get_user_model().objects.filter(is_staff=True, is_active=True).values_list('email', flat=True))
    if not admins:
        return
    from apps.notifications.backends.email import get_mail_settings
    from_email, connection = get_mail_settings()
    admin_url = reverse('admin:accounts_customuser_changelist') + '?is_active__exact=0'
    if request:
        admin_url = request.build_absolute_uri(admin_url)
    try:
        send_mail(
            subject=f"[UniCA Sport] Demande d'accès : {user.email}",
            message=f"{user.email} vient de créer un compte.\n\nPour le valider : {admin_url}\n",
            from_email=from_email,
            recipient_list=admins,
            connection=connection,
        )
    except Exception as e:
        logger.error(f"Notification de nouvelle inscription non envoyée : {e}")


class ApprovalAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit)
        if commit:
            hold_for_approval(request, user)
        return user


class ApprovalSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        hold_for_approval(request, user)
        return user
