import datetime
from django.db import models

class ServerSettings(models.Model):
    """
    Singleton pour les paramètres globaux du serveur et de l'ordonnanceur.
    Éditable depuis l'interface d'administration Django sans redéploiement.
    """
    # Ordonnanceur (Diurne / Nocturne et Jitter)
    day_interval_seconds = models.PositiveIntegerField(
        default=60,
        verbose_name="Intervalle de scan diurne (sec)",
        help_text="Fréquence de scan en journée (défaut: 60s)"
    )
    day_jitter_seconds = models.PositiveIntegerField(
        default=10,
        verbose_name="Jitter aléatoire diurne (sec)",
        help_text="Variation aléatoire ± appliquée à l'intervalle diurne (défaut: ±10s)"
    )
    night_interval_seconds = models.PositiveIntegerField(
        default=900,
        verbose_name="Intervalle de scan nocturne (sec)",
        help_text="Fréquence de scan la nuit (défaut: 900s = 15 min)"
    )
    night_jitter_seconds = models.PositiveIntegerField(
        default=30,
        verbose_name="Jitter aléatoire nocturne (sec)",
        help_text="Variation aléatoire ± appliquée à l'intervalle nocturne (défaut: ±30s)"
    )
    day_start_time = models.TimeField(
        default=datetime.time(6, 0),
        verbose_name="Heure de bascule jour (Europe/Paris)",
        help_text="Heure de début du mode diurne (ex: 06:00)"
    )
    night_start_time = models.TimeField(
        default=datetime.time(0, 0),
        verbose_name="Heure de bascule nuit (Europe/Paris)",
        help_text="Heure de début du mode nocturne (ex: 00:00 = minuit)"
    )

    # Configuration SMTP
    smtp_host = models.CharField(max_length=255, default='smtp.gmail.com', blank=True, verbose_name="Hôte SMTP")
    smtp_port = models.PositiveIntegerField(default=587, verbose_name="Port SMTP")
    smtp_user = models.CharField(max_length=255, blank=True, verbose_name="Utilisateur SMTP")
    smtp_password = models.CharField(max_length=255, blank=True, verbose_name="Mot de passe SMTP")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="Utiliser TLS")
    smtp_from_email = models.CharField(max_length=255, default='notifications@sport-notifier.fr', blank=True, verbose_name="Expéditeur par défaut")

    # API Externes
    google_oauth_client_id = models.CharField(max_length=255, blank=True, verbose_name="Client ID Google OAuth")
    google_oauth_client_secret = models.CharField(max_length=255, blank=True, verbose_name="Secret Google OAuth")
    telegram_bot_token = models.CharField(max_length=255, blank=True, verbose_name="Token Bot Telegram")
    whatsapp_api_token = models.CharField(max_length=255, blank=True, verbose_name="Token Meta WhatsApp")
    whatsapp_phone_number_id = models.CharField(max_length=100, blank=True, verbose_name="Phone Number ID WhatsApp")
    whatsapp_business_account_id = models.CharField(max_length=100, blank=True, verbose_name="Business Account ID WhatsApp")

    class Meta:
        verbose_name = "Paramètres du serveur"
        verbose_name_plural = "Paramètres du serveur"

    def __str__(self):
        return "Configuration du serveur (Singleton)"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1  # Force singleton ID
        super().save(*args, **kwargs)


class ScanLog(models.Model):
    STATUS_CHOICES = [
        ('succès', 'Succès'),
        ('échec', 'Échec'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Date et heure")
    execution_duration_seconds = models.FloatField(verbose_name="Durée (sec)")
    events_found_count = models.PositiveIntegerField(default=0, verbose_name="Événements trouvés")
    new_events_count = models.PositiveIntegerField(default=0, verbose_name="Nouveaux événements")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='succès', verbose_name="Statut")
    error_message = models.TextField(blank=True, verbose_name="Message d'erreur / Diagnostic")

    class Meta:
        verbose_name = "Journal de scan"
        verbose_name_plural = "Journaux de scan"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.status.upper()} - {self.events_found_count} trouvés ({self.new_events_count} nouv.)"
