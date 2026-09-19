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
