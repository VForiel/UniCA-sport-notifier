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

    def test_redundant_buttons_removed_and_logout_moved(self):
        # 1. Page événements : pas de bouton "Gérer mes règles"
        r_events = self.client.get('/events/')
        self.assertNotIn("Gérer mes règles", r_events.content.decode('utf-8'))

        # 2. Page d'accueil : pas de boutons redondants
        r_home = self.client.get('/')
        home_html = r_home.content.decode('utf-8')
        self.assertNotIn("Simuler un test", home_html)
        self.assertNotIn("Nouvelle règle", home_html)
        self.assertNotIn("Voir les événements", home_html)
        self.assertNotIn("/accounts/logout/", home_html)

        # 3. Page profil : bouton de déconnexion présent
        r_prof = self.client.get('/accounts/profile/')
        prof_html = r_prof.content.decode('utf-8')
        self.assertIn("Se déconnecter", prof_html)
        self.assertIn("/accounts/logout/", prof_html)
