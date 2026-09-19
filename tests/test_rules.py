from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.events.models import Event, FilterRule
from apps.events.services import matches_rule, evaluate_event_for_user

User = get_user_model()

class RuleMatchingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="testuser@univ-cotedazur.fr", password="secretpassword123")

    def test_match_mode_contains(self):
        rule = FilterRule(
            user=self.user,
            rule_type='favorite',
            match_mode='contains',
            keyword='Kayak',
            target_field='title',
            case_sensitive=False
        )
        self.assertTrue(matches_rule(rule, "Sortie KAYAK en mer", "Description"))
        self.assertTrue(matches_rule(rule, "kayak polo", "Description"))
        self.assertFalse(matches_rule(rule, "Paddle à Valrose", "Description"))

    def test_match_mode_starts_with(self):
        rule = FilterRule(
            user=self.user,
            rule_type='favorite',
            match_mode='starts_with',
            keyword='Tennis',
            target_field='title',
            case_sensitive=False
        )
        self.assertTrue(matches_rule(rule, "Tennis de table", ""))
        self.assertFalse(matches_rule(rule, "Tournoi de Tennis", ""))

    def test_match_mode_ends_with(self):
        rule = FilterRule(
            user=self.user,
            rule_type='favorite',
            match_mode='ends_with',
            keyword='Valrose',
            target_field='title',
            case_sensitive=False
        )
        self.assertTrue(matches_rule(rule, "Entraînement Valrose", ""))
        self.assertFalse(matches_rule(rule, "Valrose Stadium Tournoi", ""))

    def test_match_mode_equals(self):
        rule = FilterRule(
            user=self.user,
            rule_type='favorite',
            match_mode='equals',
            keyword='Escalade',
            target_field='title',
            case_sensitive=False
        )
        self.assertTrue(matches_rule(rule, "Escalade", ""))
        self.assertTrue(matches_rule(rule, " escalade ", ""))
        self.assertFalse(matches_rule(rule, "Escalade en falaise", ""))

    def test_case_sensitivity(self):
        rule_sensitive = FilterRule(
            user=self.user,
            rule_type='favorite',
            match_mode='contains',
            keyword='KAYAK',
            target_field='title',
            case_sensitive=True
        )
        self.assertTrue(matches_rule(rule_sensitive, "Sortie KAYAK", ""))
        self.assertFalse(matches_rule(rule_sensitive, "Sortie kayak", ""))

    def test_target_field_title_vs_description(self):
        rule_desc = FilterRule(
            user=self.user,
            rule_type='favorite',
            match_mode='contains',
            keyword='combinaison',
            target_field='title_and_description',
            case_sensitive=False
        )
        # Mot-clé présent uniquement dans la description
        self.assertTrue(matches_rule(rule_desc, "Plongée sous-marine", "Prévoir une combinaison isotherme"))

        rule_title_only = FilterRule(
            user=self.user,
            rule_type='favorite',
            match_mode='contains',
            keyword='combinaison',
            target_field='title',
            case_sensitive=False
        )
        self.assertFalse(matches_rule(rule_title_only, "Plongée sous-marine", "Prévoir une combinaison isotherme"))

    def test_evaluate_event_blacklist_priority(self):
        FilterRule.objects.create(
            user=self.user,
            rule_type='blacklist',
            match_mode='contains',
            keyword='annulé',
            target_field='title_and_description'
        )
        FilterRule.objects.create(
            user=self.user,
            rule_type='favorite',
            match_mode='contains',
            keyword='Kayak',
            target_field='title'
        )

        event_both = Event(
            source_id="101",
            title="Sortie Kayak",
            description="Événement annulé pour cause météo",
            url="https://example.com"
        )
        res = evaluate_event_for_user(self.user, event_both)
        self.assertTrue(res['is_blacklisted'])
        self.assertTrue(res['is_favorite'])


class AutoRegisterHoldLimitTests(TestCase):
    def setUp(self):
        import asyncio
        from datetime import timedelta
        from django.utils import timezone
        from apps.events.models import RegistrationAttempt, UniCACredentials

        self.user = User.objects.create_user(email="user@univ-cotedazur.fr", password="password123")
        self.admin = User.objects.create_user(email="admin@univ-cotedazur.fr", password="password123", is_staff=True)

        self.event = Event.objects.create(
            source_id="3001",
            title="Voile",
            date_event="25/09/2026",
            location="Mer",
            content_hash="hash3001"
        )

        # Configurer les identifiants pour les deux utilisateurs
        UniCACredentials.objects.create(
            user=self.user,
            unica_identifier="user_test",
            encrypted_password="dummy_encrypted",
            auto_registration_consent=True
        )
        UniCACredentials.objects.create(
            user=self.admin,
            unica_identifier="admin_test",
            encrypted_password="dummy_encrypted",
            auto_registration_consent=True
        )

        # Créer 2 tentatives actives (holds) pour chaque utilisateur
        future = timezone.now() + timedelta(minutes=20)
        RegistrationAttempt.objects.create(user=self.user, event=self.event, status='réussi', hold_expires_at=future)
        RegistrationAttempt.objects.create(user=self.user, event=self.event, status='réussi', hold_expires_at=future)

        RegistrationAttempt.objects.create(user=self.admin, event=self.event, status='réussi', hold_expires_at=future)
        RegistrationAttempt.objects.create(user=self.admin, event=self.event, status='réussi', hold_expires_at=future)

    def test_standard_user_blocked_by_max_holds(self):
        from apps.events.models import RegistrationAttempt
        from apps.scraping.auto_register import perform_auto_registration_playwright

        attempt = RegistrationAttempt.objects.create(user=self.user, event=self.event, status='en_attente')
        success, message = perform_auto_registration_playwright(self.user, self.event, attempt.id)
        self.assertFalse(success)
        self.assertIn("Limite éthique atteinte", message)

    def test_admin_bypasses_max_holds(self):
        from unittest.mock import patch
        from apps.events.models import RegistrationAttempt
        from apps.scraping.auto_register import perform_auto_registration_playwright

        attempt = RegistrationAttempt.objects.create(user=self.admin, event=self.event, status='en_attente')
        # On mock decrypt_password pour vérifier que la validation franchit le check des holds
        with patch('apps.scraping.auto_register.decrypt_password', side_effect=Exception("DecryptionReached")):
            success, message = perform_auto_registration_playwright(self.admin, self.event, attempt.id)
            self.assertFalse(success)
            # Ne doit PAS être bloqué par la limite éthique, mais atteindre l'étape suivante (déchiffrement)
            self.assertNotIn("Limite éthique atteinte", message)
            self.assertIn("DecryptionReached", message)
