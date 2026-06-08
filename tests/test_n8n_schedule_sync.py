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


if __name__ == "__main__":
    unittest.main()
