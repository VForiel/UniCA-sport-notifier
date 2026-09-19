from django.db import models
from django.conf import settings
from django.utils import timezone

class Event(models.Model):
    source_id = models.CharField(max_length=100, unique=True, verbose_name="ID Source UniCA")
    title = models.CharField(max_length=255, verbose_name="Titre")
    event_type = models.CharField(max_length=100, blank=True, verbose_name="Type d'événement")
    description = models.TextField(blank=True, verbose_name="Description")
    date_event = models.CharField(max_length=150, blank=True, verbose_name="Horaires / Date")
    location = models.CharField(max_length=255, blank=True, verbose_name="Lieu")
    supervisor = models.CharField(max_length=255, blank=True, verbose_name="Encadrant(s)")
    url = models.URLField(max_length=500, verbose_name="URL de l'événement")
    image_url = models.URLField(max_length=500, blank=True, verbose_name="URL de l'image")
    is_simulated = models.BooleanField(default=False, db_index=True, verbose_name="Événement de test / simulation")
    first_detected_at = models.DateTimeField(default=timezone.now, verbose_name="Première détection")
    content_hash = models.CharField(max_length=64, verbose_name="Hash de contenu SHA-256")

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Événements"
        ordering = ['-first_detected_at']

    def __str__(self):
        return f"{self.title} ({self.date_event or 'Date inconnue'})"


class FilterRule(models.Model):
    RULE_TYPES = [
        ('blacklist', 'Liste noire (ne pas notifier)'),
        ('favorite', 'Favori (notifier & tenter inscription auto)'),
    ]

    MATCH_MODES = [
        ('contains', 'Contient'),
        ('starts_with', 'Commence par'),
        ('ends_with', 'Se termine par'),
        ('equals', 'Égal à'),
    ]

    TARGET_FIELDS = [
        ('title', 'Titre uniquement'),
        ('title_and_description', 'Titre et description'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='filter_rules', verbose_name="Utilisateur")
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, default='favorite', verbose_name="Type de règle")
    match_mode = models.CharField(max_length=20, choices=MATCH_MODES, default='contains', verbose_name="Mode de correspondance")
    keyword = models.CharField(max_length=150, verbose_name="Mot-clé")
    target_field = models.CharField(max_length=30, choices=TARGET_FIELDS, default='title_and_description', verbose_name="Champ ciblé")
    case_sensitive = models.BooleanField(default=False, verbose_name="Sensible à la casse")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        verbose_name = "Règle de filtrage"
        verbose_name_plural = "Règles de filtrage"
        ordering = ['-created_at']

    def __str__(self):
        mode_label = dict(self.MATCH_MODES).get(self.match_mode, self.match_mode)
        type_label = dict(self.RULE_TYPES).get(self.rule_type, self.rule_type)
        return f"[{type_label}] {mode_label} '{self.keyword}' ({self.user.email})"


class UniCACredentials(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='unica_credentials', verbose_name="Utilisateur")
    unica_identifier = models.CharField(max_length=150, blank=True, verbose_name="Identifiant UniCA")
    encrypted_password = models.TextField(blank=True, verbose_name="Mot de passe chiffré (Fernet)")
    auto_registration_consent = models.BooleanField(
        default=False,
        verbose_name="Consentement explicite pour réservation automatique temporaire (30 min)"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Identifiants UniCA"
        verbose_name_plural = "Identifiants UniCA"

    def __str__(self):
        status = "configuré" if self.unica_identifier else "non configuré"
        return f"Identifiants de {self.user.email} ({status})"


class RegistrationAttempt(models.Model):
    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('réussi', 'Réussi (place réservée 30 min)'),
        ('échoué', 'Échoué'),
        ('expiré', 'Expiré'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registration_attempts', verbose_name="Événement")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='registration_attempts', verbose_name="Utilisateur")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_attente', verbose_name="Statut")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Date de tentative")
    hold_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expiration du blocage (30 min)")
    error_message = models.TextField(blank=True, verbose_name="Message / Diagnostic")

    class Meta:
        verbose_name = "Tentative d'inscription"
        verbose_name_plural = "Tentatives d'inscription"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.user.email} - {self.event.title}"
