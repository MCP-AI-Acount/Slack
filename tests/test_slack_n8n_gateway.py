import hashlib
import hmac
import time
import unittest
import urllib.parse

from common.slack_n8n_gateway import (
    output_slack_response_url,
    parse_slack_form,
    slack_form_to_payload,
    verify_slack_signature,
)


class SlackN8nGatewayTests(unittest.TestCase):
    def test_verify_slack_signature_accepts_valid_signature(self):
        secret = "secret"
        timestamp = str(int(time.time()))
        body = b"command=%2Fcursor&text=make+canva"
        base = b"v0:" + timestamp.encode("utf-8") + b":" + body
        signature = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

        self.assertTrue(
            verify_slack_signature(
                secret,
                timestamp,
                signature,
                body,
                now=int(timestamp),
            )
        )

    def test_verify_slack_signature_rejects_stale_timestamp(self):
        secret = "secret"
        timestamp = "100"
        body = b"command=%2Fcursor"
        base = b"v0:" + timestamp.encode("utf-8") + b":" + body
        signature = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

        self.assertFalse(
            verify_slack_signature(secret, timestamp, signature, body, now=1000)
        )

    def test_parse_slack_form_decodes_urlencoded_fields(self):
        body = urllib.parse.urlencode(
            {
                "command": "/cursor",
                "text": "make canva",
                "user_id": "U123",
            }
        ).encode("utf-8")

        self.assertEqual(
            parse_slack_form(body),
            {
                "command": "/cursor",
                "text": "make canva",
                "user_id": "U123",
            },
        )

    def test_slack_form_to_payload_does_not_forward_legacy_token(self):
        payload = slack_form_to_payload(
            {
                "token": "do-not-forward",
                "team_id": "T123",
                "channel_id": "C123",
                "user_id": "U123",
                "command": "/cursor",
                "text": "make canva",
                "response_url": "https://hooks.slack.com/commands/123",
            }
        )

        self.assertEqual(payload["source"], "slack")
        self.assertEqual(payload["slack"]["command"], "/cursor")
        self.assertEqual(payload["slack"]["text"], "make canva")
        self.assertNotIn("token", payload["slack"]["raw"])

    def test_output_slack_response_url_accepts_payload_or_metadata(self):
        self.assertEqual(
            output_slack_response_url(
                {"slack_response_url": "https://hooks.slack.com/commands/T/B/X"},
                {},
            ),
            "https://hooks.slack.com/commands/T/B/X",
        )
        self.assertEqual(
            output_slack_response_url(
                {},
                {"response_url": "https://hooks.slack.com/commands/T/B/Y"},
            ),
            "https://hooks.slack.com/commands/T/B/Y",
        )


if __name__ == "__main__":
    unittest.main()
