import unittest

from scripts.sync_n8n import build_backfill_payload


class SyncN8nTests(unittest.TestCase):
    def test_backfill_payload_shape(self) -> None:
        payload = build_backfill_payload(1.0, channel_id="C_TEST")
        self.assertEqual(payload["action"], "card_news_backfill")
        self.assertEqual(payload["slack"]["channel_id"], "C_TEST")
        self.assertIn("since", payload["backfill"])
        self.assertEqual(payload["backfill"]["hours"], 1.0)


if __name__ == "__main__":
    unittest.main()
