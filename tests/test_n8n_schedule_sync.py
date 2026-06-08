import unittest
from unittest.mock import patch

from common.n8n_schedule_sync import (
    MISSING_CONTENT_DEFAULT,
    build_run_schedule_payload,
    parse_schedules,
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

    def test_parse_schedules(self) -> None:
        self.assertEqual(parse_schedules("news,economy", default=MISSING_CONTENT_DEFAULT), ["news", "economy"])


if __name__ == "__main__":
    unittest.main()
