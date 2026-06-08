import unittest

from scripts.standalone_startup_catchup import MISSING_CONTENT_DEFAULT, build_run_schedule_payload


class StandaloneStartupCatchupTests(unittest.TestCase):
    def test_run_schedule_news(self) -> None:
        payload = build_run_schedule_payload("news")
        self.assertEqual(payload["action"], "run_schedule")
        self.assertEqual(payload["schedule"], "news")

    def test_missing_default_has_news_not_weather(self) -> None:
        self.assertIn("news", MISSING_CONTENT_DEFAULT)
        self.assertNotIn("weather", MISSING_CONTENT_DEFAULT)


if __name__ == "__main__":
    unittest.main()
