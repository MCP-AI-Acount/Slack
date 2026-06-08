import unittest

from scripts.sync_n8n import build_backfill_payload, build_catchup_payload, parse_catchup_schedules


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
            schedules=["regular", "monday_weekly"],
        )
        self.assertEqual(payload["action"], "card_news_catchup")
        self.assertEqual(payload["catchup"]["skip_already_posted"], True)
        self.assertEqual(payload["catchup"]["schedules"], ["regular", "monday_weekly"])
        self.assertEqual(payload["slack"]["channel_id"], "C_TEST")

    def test_parse_catchup_schedules(self) -> None:
        self.assertEqual(parse_catchup_schedules(None), ["regular", "monday_weekly"])
        self.assertEqual(parse_catchup_schedules("daily,regular"), ["daily", "regular"])

    def test_parse_catchup_schedules_rejects_unknown(self) -> None:
        with self.assertRaises(SystemExit):
            parse_catchup_schedules("weekly")


if __name__ == "__main__":
    unittest.main()
