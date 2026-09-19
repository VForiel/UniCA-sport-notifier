from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.events.models import Event

User = get_user_model()

class EventViewFilterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="member@univ-cotedazur.fr", password="Password123!")
        self.client.force_login(self.user)

        # Real event
        self.real_event = Event.objects.create(
            source_id="real_980",
            title="KAYAK Réel",
            event_type="Sortie",
            date_event="20/09/2026 10:00",
            location="Mer",
            url="https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement#event-real_980",
            image_url="https://sport.univ-cotedazur.fr/media/cache/thumb_large_big/upload/public/image/6a17e6307f445452066731.png",
            is_simulated=False,
            content_hash="hash_real"
        )

        # Simulated event
        self.sim_event = Event.objects.create(
            source_id="sim_12345",
            title="KAYAK de Test [SIMULATION]",
            event_type="Sortie",
            date_event="Demain 10:00",
            location="Valrose",
            url="https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement#event-sim_12345",
            image_url="https://sport.univ-cotedazur.fr/media/cache/thumb_large_big/upload/public/image/dummy.png",
            is_simulated=True,
            content_hash="hash_sim"
        )

    def test_dashboard_shows_only_real_events(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Doit contenir l'événement réel
        self.assertIn("KAYAK Réel", content)
        self.assertIn(self.real_event.image_url, content)
        # Ne doit PAS contenir l'événement simulé
        self.assertNotIn("KAYAK de Test [SIMULATION]", content)

    def test_recent_events_page_shows_only_real_events(self):
        response = self.client.get('/events/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Doit contenir l'événement réel et son image
        self.assertIn("KAYAK Réel", content)
        self.assertIn(self.real_event.image_url, content)
        # Ne doit PAS contenir l'événement simulé
        self.assertNotIn("KAYAK de Test [SIMULATION]", content)
