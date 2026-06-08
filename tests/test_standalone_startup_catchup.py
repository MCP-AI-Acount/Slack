import unittest

from scripts.standalone_startup_catchup import build_catchup_payload


class StandaloneStartupCatchupTests(unittest.TestCase):
    def test_build_catchup_payload(self) -> None:
        payload = build_catchup_payload(24.0)
        self.assertEqual(payload["action"], "card_news_catchup")
        self.assertEqual(payload["catchup"]["trigger"], "n8n_startup")
        self.assertTrue(payload["catchup"]["skip_already_posted"])
        self.assertIn("weather", payload["catchup"]["schedules"])
        self.assertIn("economy", payload["catchup"]["schedules"])


if __name__ == "__main__":
    unittest.main()
