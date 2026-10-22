from zoneinfo import ZoneInfo
from datetime import datetime, time
from django.test import TestCase
from apps.scraping.models import ServerSettings
from apps.scraping.tasks import calculate_next_scan_delay

class SchedulerTests(TestCase):
    def setUp(self):
        self.settings = ServerSettings.get_solo()
        self.settings.day_interval_seconds = 60
        self.settings.day_jitter_seconds = 10
        self.settings.night_interval_seconds = 900
        self.settings.night_jitter_seconds = 30
        self.settings.day_start_time = time(6, 0)
        self.settings.night_start_time = time(0, 0)
        self.settings.save()

    def test_day_scan_delay_with_jitter(self):
        # 14h30 heure de Paris -> Plein jour
        dt_day = datetime(2026, 9, 19, 14, 30, tzinfo=ZoneInfo("Europe/Paris"))
        for _ in range(50):
            delay = calculate_next_scan_delay(dt_day, self.settings)
            # 60s ± 10s => [50s, 70s]
            self.assertGreaterEqual(delay, 50)
            self.assertLessEqual(delay, 70)

    def test_night_scan_delay_with_jitter(self):
        # 02h45 heure de Paris -> Pleine nuit
        dt_night = datetime(2026, 9, 19, 2, 45, tzinfo=ZoneInfo("Europe/Paris"))
        for _ in range(50):
            delay = calculate_next_scan_delay(dt_night, self.settings)
            # 900s ± 30s => [870s, 930s]
            self.assertGreaterEqual(delay, 870)
            self.assertLessEqual(delay, 930)

    def test_day_boundary_at_06_00(self):
        # Exactement 06:00 -> Mode diurne
        dt_start = datetime(2026, 9, 19, 6, 0, tzinfo=ZoneInfo("Europe/Paris"))
        delay = calculate_next_scan_delay(dt_start, self.settings)
        self.assertGreaterEqual(delay, 50)
        self.assertLessEqual(delay, 70)

    def test_night_boundary_at_00_00(self):
        # Exactement minuit 00:00 -> Mode nocturne
        dt_midnight = datetime(2026, 9, 19, 0, 0, tzinfo=ZoneInfo("Europe/Paris"))
        delay = calculate_next_scan_delay(dt_midnight, self.settings)
        self.assertGreaterEqual(delay, 870)
        self.assertLessEqual(delay, 930)

    def test_minimum_safety_delay(self):
        self.settings.day_interval_seconds = 2
        self.settings.day_jitter_seconds = 0
        dt = datetime(2026, 9, 19, 12, 0, tzinfo=ZoneInfo("Europe/Paris"))
        delay = calculate_next_scan_delay(dt, self.settings)
        # La fonction impose un plancher de 5 secondes pour éviter le flood
        self.assertEqual(delay, 5)


class ScanWatchdogTests(TestCase):
    def test_restarts_chain_without_recent_scan(self):
        from unittest.mock import patch
        from apps.scraping.tasks import ensure_scan_running_task
        with patch('apps.scraping.tasks.scan_events_task.apply_async') as mocked:
            self.assertTrue(ensure_scan_running_task())
            mocked.assert_called_once()

    def test_leaves_running_chain_alone(self):
        from unittest.mock import patch
        from apps.scraping.models import ScanLog
        from apps.scraping.tasks import ensure_scan_running_task
        ScanLog.objects.create(execution_duration_seconds=1.0)
        with patch('apps.scraping.tasks.scan_events_task.apply_async') as mocked:
            self.assertFalse(ensure_scan_running_task())
            mocked.assert_not_called()
