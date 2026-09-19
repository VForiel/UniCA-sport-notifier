from django.db import models
from django.conf import settings

class NotificationPreference(models.Model):
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('discord_webhook', 'Webhook Discord'),
        ('telegram', 'Telegram Bot'),
        ('whatsapp', 'WhatsApp (Meta Cloud API)'),
        ('push', 'Web Push (Navigateur)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences', verbose_name="Utilisateur")
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, verbose_name="Canal")
    config = models.JSONField(default=dict, blank=True, verbose_name="Configuration spécifique")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Préférence de notification"
        verbose_name_plural = "Préférences de notification"
        unique_together = ('user', 'channel')

    def __str__(self):
        status = "actif" if self.is_active else "inactif"
        return f"{self.user.email} - {self.get_channel_display()} ({status})"


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_subscriptions', verbose_name="Utilisateur")
    endpoint = models.TextField(unique=True, verbose_name="Endpoint Push")
    p256dh = models.TextField(verbose_name="Clé p256dh")
    auth = models.TextField(verbose_name="Clé Auth")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Abonnement WebPush"
        verbose_name_plural = "Abonnements WebPush"

    def __str__(self):
        return f"Abonnement Push de {self.user.email} ({self.endpoint[:30]}...)"
