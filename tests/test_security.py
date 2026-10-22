from unittest.mock import patch
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.accounts.models import AuditLog
from apps.events.models import Event, FilterRule
from apps.notifications.models import NotificationPreference
from apps.notifications.backends.discord import DiscordWebhookBackend

User = get_user_model()


class SignupApprovalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="Adm1n-Password!")

    def test_signup_creates_inactive_account_and_notifies_admins(self):
        response = Client().post('/accounts/signup/', {
            'email': 'nouveau@etu.univ-cotedazur.fr',
            'password1': 'Un-Mot-De-Passe-Solide-42',
            'password2': 'Un-Mot-De-Passe-Solide-42',
        })
        user = User.objects.get(email='nouveau@etu.univ-cotedazur.fr')
        self.assertFalse(user.is_active)
        self.assertRedirects(response, '/accounts/inactive/', fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(user=user, action='SIGNUP').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('admin@example.com', mail.outbox[0].to)
        self.assertIn('nouveau@etu.univ-cotedazur.fr', mail.outbox[0].subject)

    def test_pending_account_cannot_log_in(self):
        User.objects.create_user(email="attente@example.com", password="Un-Mot-De-Passe-Solide-42", is_active=False)
        client = Client()
        client.post('/accounts/login/', {'login': 'attente@example.com', 'password': 'Un-Mot-De-Passe-Solide-42'})
        self.assertEqual(client.get('/rules/').status_code, 302)

    def test_admin_action_approves_accounts(self):
        pending = User.objects.create_user(email="attente@example.com", password="x", is_active=False)
        client = Client()
        client.force_login(self.admin)
        client.post('/admin/accounts/customuser/', {'action': 'approve_accounts', '_selected_action': [pending.pk]})
        pending.refresh_from_db()
        self.assertTrue(pending.is_active)
        self.assertTrue(AuditLog.objects.filter(action='ACCOUNT_APPROVAL').exists())


class AdminLoginTests(TestCase):
    def test_admin_login_goes_through_allauth(self):
        response = Client().get('/admin/login/?next=/admin/')
        self.assertRedirects(response, '/accounts/login/?next=%2Fadmin%2F', fetch_redirect_response=False)

    def test_admin_login_ignores_external_next(self):
        response = Client().get('/admin/login/?next=https://evil.example/')
        self.assertRedirects(response, '/accounts/login/?next=%2Fadmin%2F', fetch_redirect_response=False)

    def test_admin_login_forbidden_for_non_staff(self):
        client = Client()
        client.force_login(User.objects.create_user(email="u@example.com", password="x"))
        self.assertEqual(client.get('/admin/login/').status_code, 403)


class NotificationInputTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="athlete@example.com", password="x")
        self.client = Client()
        self.client.force_login(self.user)

    def test_non_discord_webhook_is_rejected(self):
        self.client.post('/notifications/', {
            'discord_active': '1',
            'discord_webhook_url': 'http://unicasport_redis:6379/',
        })
        self.assertFalse(NotificationPreference.objects.filter(user=self.user, channel='discord_webhook').exists())

    def test_backend_refuses_stored_non_discord_url(self):
        NotificationPreference.objects.create(user=self.user, channel='discord_webhook', config={'webhook_url': 'http://db:5432/'})
        event = Event.objects.create(source_id="1", title="T", url="https://sport.univ-cotedazur.fr/", content_hash="h")
        with patch('requests.post') as mocked:
            self.assertFalse(DiscordWebhookBackend().send(self.user, event, "msg"))
            mocked.assert_not_called()

    def test_test_notification_is_rate_limited_and_cleans_up(self):
        for _ in range(5):
            self.client.post('/notifications/test/', {'title': '<b>phishing</b>'})
        self.assertEqual(len(mail.outbox), 5)
        self.assertNotIn('phishing', mail.outbox[0].subject)
        self.assertFalse(Event.objects.filter(is_simulated=True).exists())
        self.client.post('/notifications/test/')
        self.assertEqual(len(mail.outbox), 5)

    def test_test_notification_ignores_next(self):
        response = self.client.post('/notifications/test/', {'next': 'https://evil.example/'})
        self.assertRedirects(response, '/notifications/', fetch_redirect_response=False)


class RuleDeletionTests(TestCase):
    def test_delete_rule_requires_post(self):
        user = User.objects.create_user(email="a@example.com", password="x")
        rule = FilterRule.objects.create(user=user, keyword="Kayak")
        client = Client()
        client.force_login(user)
        self.assertEqual(client.get(f'/rules/{rule.id}/delete/').status_code, 405)
        self.assertTrue(FilterRule.objects.filter(id=rule.id).exists())


class SecurityHeaderTests(TestCase):
    def test_csp_header_present(self):
        response = Client().get('/')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
