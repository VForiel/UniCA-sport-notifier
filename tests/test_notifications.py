from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.events.models import Event
from apps.notifications.models import NotificationPreference
from apps.notifications.backends.email import EmailBackend
from apps.notifications.backends.discord import DiscordWebhookBackend
from apps.notifications.backends.telegram import TelegramBackend
from apps.notifications.backends.whatsapp import WhatsAppBackend

User = get_user_model()

class NotificationBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="athlete@univ-cotedazur.fr", password="password123")
        self.event = Event.objects.create(
            source_id="555",
            title="Escalade Initiation",
            event_type="Stage",
            date_event="25/09/2026 14:00",
            location="Saint-Jeannet",
            url="https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement#event-555",
            content_hash="dummyhash"
        )

    def test_discord_backend_handles_missing_webhook(self):
        backend = DiscordWebhookBackend()
        # Pas de préférence -> Doit retourner False proprement sans lever d'exception
        result = backend.send(self.user, self.event, "Test")
        self.assertFalse(result)

    def test_telegram_backend_handles_missing_chat_id(self):
        backend = TelegramBackend()
        result = backend.send(self.user, self.event, "Test")
        self.assertFalse(result)

    def test_whatsapp_backend_handles_missing_phone(self):
        backend = WhatsAppBackend()
        result = backend.send(self.user, self.event, "Test")
        self.assertFalse(result)

    def test_email_backend_success(self):
        backend = EmailBackend()
        # En mode test Django, l'envoi d'email utilise la boîte aux lettres mémoire
        result = backend.send(self.user, self.event, "Nouveau créneau")
        self.assertTrue(result)

    def test_discord_backend_payload_with_image_and_ping(self):
        from unittest.mock import patch
        self.event.image_url = "https://example.com/sport.jpg"
        self.event.save()

        NotificationPreference.objects.create(
            user=self.user,
            channel='discord_webhook',
            is_active=True,
            config={
                'webhook_url': 'https://discord.com/api/webhooks/1234567890/dummy-token',
                'discord_user_id': '282912345678901234',
                'discord_ping_mode': 'all',
            }
        )

        backend = DiscordWebhookBackend()
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 204
            success = backend.send(self.user, self.event, "Test ping all")
            self.assertTrue(success)
            self.assertTrue(mock_post.called)
            payload = mock_post.call_args[1]['json']
            self.assertIn("<@282912345678901234>", payload['content'])
            self.assertEqual(payload['embeds'][0]['image']['url'], "https://example.com/sport.jpg")

    def test_discord_backend_ping_favorite_only(self):
        from unittest.mock import patch
        pref = NotificationPreference.objects.create(
            user=self.user,
            channel='discord_webhook',
            is_active=True,
            config={
                'webhook_url': 'https://discord.com/api/webhooks/1234567890/dummy-token',
                'discord_user_id': '282912345678901234',
                'discord_ping_mode': 'favorite_only',
            }
        )

        backend = DiscordWebhookBackend()
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 204
            # Événement normal non favori : pas de mention
            backend.send(self.user, self.event, "Événement normal")
            payload_normal = mock_post.call_args[1]['json']
            self.assertNotIn("<@282912345678901234>", payload_normal['content'])

            # Événement favori : mention présente
            backend.send(self.user, self.event, "⭐ Événement FAVORIS !")
            payload_fav = mock_post.call_args[1]['json']
            self.assertIn("<@282912345678901234>", payload_fav['content'])

    def test_preferences_view_saves_discord_config(self):
        self.client.force_login(self.user)
        response = self.client.post('/notifications/', {
            'discord_active': '1',
            'discord_webhook_url': 'https://discord.com/api/webhooks/123/abc',
            'discord_user_id': '555444333222111000',
            'discord_ping_mode': 'favorite_only',
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        pref = NotificationPreference.objects.get(user=self.user, channel='discord_webhook')
        self.assertTrue(pref.is_active)
        self.assertEqual(pref.config.get('webhook_url'), 'https://discord.com/api/webhooks/123/abc')
        self.assertEqual(pref.config.get('discord_user_id'), '555444333222111000')
        self.assertEqual(pref.config.get('discord_ping_mode'), 'favorite_only')
