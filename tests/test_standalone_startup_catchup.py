import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from scripts.standalone_startup_catchup import (
    KST,
    MISSING_CONTENT_DEFAULT,
    afternoon_recovery_schedules,
    build_run_schedule_payload,
    missing_content_schedules,
)


class StandaloneStartupCatchupTests(unittest.TestCase):
    def test_run_schedule_news(self) -> None:
        payload = build_run_schedule_payload("news")
        self.assertEqual(payload["action"], "run_schedule")
        self.assertEqual(payload["schedule"], "news")

    def test_missing_default_has_news_not_weather(self) -> None:
        self.assertIn("news", MISSING_CONTENT_DEFAULT)
        self.assertNotIn("weather", MISSING_CONTENT_DEFAULT)

    def test_missing_content_skips_monday_weekly_on_friday(self) -> None:
        with mock.patch(
            "scripts.standalone_startup_catchup.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 6, 12, 15, 0, tzinfo=KST)
            schedules = missing_content_schedules()
        self.assertNotIn("monday_weekly", schedules)

    def test_afternoon_recovery_includes_regular(self) -> None:
        with mock.patch(
            "scripts.standalone_startup_catchup.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 6, 12, 15, 0, tzinfo=KST)
            schedules = afternoon_recovery_schedules()
        self.assertIn("regular", schedules)

    def test_evening_payload_daily(self) -> None:
        payload = build_run_schedule_payload("daily")
        self.assertEqual(payload["action"], "run_schedule")
        self.assertEqual(payload["schedule"], "daily")


if __name__ == "__main__":
    unittest.main()
