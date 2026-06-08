import unittest
from unittest.mock import patch

from common.n8n_schedule_sync import DEFAULT_CATCHUP_SCHEDULES, build_catchup_payload
from scripts.sync_n8n import build_backfill_payload, parse_catchup_schedules, wait_for_n8n_ready


class SyncN8nTests(unittest.TestCase):
    def test_backfill_payload_shape(self) -> None:
        payload = build_backfill_payload(1.0, channel_id="C_TEST")
        self.assertEqual(payload["action"], "card_news_backfill")
        self.assertEqual(payload["slack"]["channel_id"], "C_TEST")
        self.assertIn("since", payload["backfill"])
        self.assertEqual(payload["backfill"]["hours"], 1.0)

    def test_catchup_payload_defaults(self) -> None:
        payload = build_catchup_payload(
            24.0,
            channel_id="C_TEST",
            skip_already_posted=True,
            schedules=list(DEFAULT_CATCHUP_SCHEDULES),
            trigger="n8n_startup",
        )
        self.assertEqual(payload["action"], "card_news_catchup")
        self.assertEqual(payload["catchup"]["skip_already_posted"], True)
        self.assertEqual(payload["catchup"]["trigger"], "n8n_startup")
        self.assertTrue(payload["catchup"]["auto"])
        self.assertEqual(payload["slack"]["channel_id"], "C_TEST")

    def test_parse_catchup_schedules(self) -> None:
        self.assertEqual(parse_catchup_schedules(None), DEFAULT_CATCHUP_SCHEDULES)
        self.assertEqual(parse_catchup_schedules("economy,weather"), ["economy", "weather"])

    def test_parse_catchup_schedules_rejects_unknown(self) -> None:
        with self.assertRaises(SystemExit):
            parse_catchup_schedules("weekly")

    @patch("scripts.sync_n8n.urllib.request.urlopen")
    def test_wait_for_n8n_ready(self, urlopen_mock) -> None:
        response = urlopen_mock.return_value.__enter__.return_value
        response.status = 200
        self.assertTrue(wait_for_n8n_ready(max_seconds=1, interval_seconds=0.01))


if __name__ == "__main__":
    unittest.main()
