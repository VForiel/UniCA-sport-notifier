from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superutilisateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superutilisateur doit avoir is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name="Adresse email")
    is_staff = models.BooleanField(default=False, verbose_name="Accès administration")
    is_active = models.BooleanField(default=True, verbose_name="Compte actif")
    date_joined = models.DateTimeField(default=timezone.now, verbose_name="Date d'inscription")

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_joined']

    def __str__(self):
        return self.email


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'Connexion'),
        ('SIGNUP', "Demande d'accès"),
        ('ACCOUNT_APPROVAL', 'Validation de compte'),
        ('ROLE_CHANGE', 'Modification de rôle'),
        ('ACCOUNT_DELETION', 'Suppression de compte'),
        ('CREDENTIALS_UPDATE', 'Mise à jour des identifiants'),
        ('SETTINGS_UPDATE', 'Mise à jour des paramètres'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs', verbose_name="Utilisateur")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name="Action")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Date et heure")
    details = models.TextField(blank=True, verbose_name="Détails")

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.get_action_display()} - {self.user or 'Système'}"
