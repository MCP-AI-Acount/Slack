import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from common.n8n_schedule_sync import (
    KST,
    MISSING_CONTENT_DEFAULT,
    afternoon_recovery_schedules,
    build_run_schedule_payload,
    filter_schedules_for_weekday,
    missing_content_schedules,
    parse_schedules,
    webhook_response_likely_noop,
)
from scripts.standalone_startup_catchup import build_run_schedule_payload as standalone_run_payload


class N8nScheduleSyncTests(unittest.TestCase):
    def test_missing_content_default_excludes_weather(self) -> None:
        self.assertNotIn("weather", MISSING_CONTENT_DEFAULT)
        self.assertIn("news", MISSING_CONTENT_DEFAULT)
        self.assertIn("regular", MISSING_CONTENT_DEFAULT)

    def test_run_schedule_payload(self) -> None:
        payload = build_run_schedule_payload("news", channel_id="C1", trigger="test")
        self.assertEqual(payload["action"], "run_schedule")
        self.assertEqual(payload["schedule"], "news")

    def test_standalone_run_schedule(self) -> None:
        payload = standalone_run_payload("regular")
        self.assertEqual(payload["action"], "run_schedule")
        self.assertEqual(payload["schedule"], "regular")

    def test_webhook_url_candidates_include_localhost(self) -> None:
        from common.n8n_schedule_sync import local_n8n_webhook_url, webhook_url_candidates

        urls = webhook_url_candidates()
        self.assertTrue(any("127.0.0.1" in u or "localhost" in u for u in urls))
        self.assertIn("/webhook/", local_n8n_webhook_url())

    def test_is_dns_resolution_error(self) -> None:
        import urllib.error

        from common.n8n_schedule_sync import is_dns_resolution_error

        exc = urllib.error.URLError(OSError(-3, "Temporary failure in name resolution"))
        self.assertTrue(is_dns_resolution_error(exc))

    def test_missing_content_excludes_monday_weekly_on_friday(self) -> None:
        friday_afternoon = datetime(2026, 6, 12, 15, 0, tzinfo=KST)
        schedules = missing_content_schedules(now=friday_afternoon)
        self.assertNotIn("monday_weekly", schedules)
        self.assertIn("regular", schedules)

    def test_filter_schedules_for_weekday_keeps_monday_weekly_on_monday(self) -> None:
        monday = datetime(2026, 6, 8, 10, 0, tzinfo=KST)
        schedules = filter_schedules_for_weekday(MISSING_CONTENT_DEFAULT, now=monday)
        self.assertIn("monday_weekly", schedules)

    def test_afternoon_recovery_friday(self) -> None:
        friday_afternoon = datetime(2026, 6, 12, 15, 0, tzinfo=KST)
        schedules = afternoon_recovery_schedules(now=friday_afternoon)
        self.assertEqual(schedules[0], "news")
        self.assertIn("regular", schedules)
        self.assertNotIn("monday_weekly", schedules)

    def test_afternoon_recovery_before_slot_raises(self) -> None:
        early = datetime(2026, 6, 12, 10, 0, tzinfo=KST)
        with self.assertRaises(SystemExit):
            afternoon_recovery_schedules(now=early)

    def test_webhook_response_likely_noop(self) -> None:
        self.assertTrue(webhook_response_likely_noop(200, ""))
        self.assertTrue(
            webhook_response_likely_noop(200, '{"headers":{},"params":{},"query":{},"body":{}}')
        )
        self.assertFalse(webhook_response_likely_noop(200, '{"ok": true, "schedule": "regular"}'))
        self.assertFalse(
            webhook_response_likely_noop(200, '{"message":"Workflow was started"}')
        )


if __name__ == "__main__":
    unittest.main()
