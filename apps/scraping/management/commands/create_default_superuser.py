import secrets
import string
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings

class Command(BaseCommand):
    help = "Crée le compte superadministrateur initial s'il n'existe pas déjà."

    def handle(self, *args, **options):
        User = get_user_model()
        email = getattr(settings, 'DEFAULT_SUPERUSER_EMAIL', 'vincent.foriel@gmail.com')

        from allauth.account.models import EmailAddress

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            EmailAddress.objects.get_or_create(
                user=user,
                email=email,
                defaults={'primary': True, 'verified': True}
            )
            self.stdout.write(self.style.SUCCESS(f"Le superadmin '{email}' existe déjà. EmailAddress synchronisé."))
            return

        # Génération d'un mot de passe fort et aléatoire de 16 caractères
        alphabet = string.ascii_letters + string.digits + "!@#$%&*-_"
        password = ''.join(secrets.choice(alphabet) for _ in range(16))

        user = User.objects.create_superuser(
            email=email,
            password=password
        )

        EmailAddress.objects.create(
            user=user,
            email=email,
            primary=True,
            verified=True
        )

        # Affichage sécurisé unique dans les logs
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("COMPTE SUPERADMIN INITIAL CRÉÉ AVEC SUCCÈS"))
        self.stdout.write(f"Email        : {email}")
        self.stdout.write(self.style.WARNING(f"Mot de passe : {password}"))
        self.stdout.write(self.style.NOTICE("Note : Ce mot de passe est affiché une seule fois au démarrage."))
        self.stdout.write(self.style.NOTICE("Veuillez le conserver précieusement ou le modifier immédiatement."))
        self.stdout.write("=" * 70)
