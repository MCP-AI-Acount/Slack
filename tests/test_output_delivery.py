import base64
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest import mock

from common import output_delivery
from common.output_delivery import (
    OutputDeliveryConfig,
    UploadedOutput,
    build_image_object_name,
    decode_image_payload,
    is_slack_response_url,
    object_link,
    progress_payload,
    public_metadata,
    safe_filename,
    slack_completion_payload,
)


class OutputDeliveryTests(unittest.TestCase):
    def test_safe_filename_keeps_extension_and_removes_unsafe_chars(self):
        self.assertEqual(
            safe_filename("../my image!!.png", "image/png"),
            "my-image.png",
        )

    def test_safe_filename_adds_extension_from_content_type(self):
        self.assertEqual(safe_filename("card", "image/png"), "card.png")

    def test_build_image_object_name_uses_output_image_prefix(self):
        config = OutputDeliveryConfig(bucket="bucket")
        object_name = build_image_object_name(
            config,
            "card.png",
            "image/png",
            now=datetime(2026, 5, 19, 9, 30, 0, tzinfo=timezone.utc),
            task_id="task 1",
        )

        self.assertEqual(
            object_name,
            "Output/Image/20260519T093000Z-task-1-card.png",
        )

    def test_decode_image_payload_accepts_data_url(self):
        raw = b"image-bytes"
        payload = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

        self.assertEqual(decode_image_payload(payload), (raw, "image/png"))

    def test_object_link_uses_public_base_url_when_configured(self):
        config = OutputDeliveryConfig(
            bucket="bucket",
            public_base_url="https://cdn.example.com/assets/",
        )

        self.assertEqual(
            object_link(config, "Output/Image/a b.png"),
            "https://cdn.example.com/assets/Output/Image/a%20b.png",
        )

    def test_progress_payload_contains_completed_link(self):
        uploaded_output = UploadedOutput(
            bucket="bucket",
            object_name="Output/Image/card.png",
            link="https://example.com/card.png",
            content_type="image/png",
            size_bytes=10,
        )

        payload = progress_payload(
            uploaded_output,
            title="Canva card",
            task_id="task-1",
            metadata={"source": "slack"},
        )

        self.assertEqual(payload["event"], "task.completed")
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["links"][0]["url"], "https://example.com/card.png")
        self.assertEqual(payload["metadata"], {"source": "slack"})

    def test_public_metadata_filters_sensitive_delivery_fields(self):
        self.assertEqual(
            public_metadata(
                {
                    "command": "/auto",
                    "response_url": "https://hooks.slack.com/commands/T/B/X",
                    "token": "secret",
                }
            ),
            {"command": "/auto"},
        )

    def test_post_progress_completed_returns_failure_without_raising(self):
        uploaded_output = UploadedOutput(
            bucket="bucket",
            object_name="Output/Image/card.png",
            link="https://example.com/card.png",
            content_type="image/png",
            size_bytes=10,
        )
        config = OutputDeliveryConfig(
            bucket="bucket",
            progress_webhook_url="https://progress.example.com/hook",
        )

        with mock.patch(
            "common.output_delivery.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            status, body = output_delivery.post_progress_completed(
                uploaded_output,
                title="Canva card",
                config=config,
            )

        self.assertEqual(status, 0)
        self.assertIn("request_failed", body)

    def test_slack_response_url_is_limited_to_slack_command_hooks(self):
        self.assertTrue(is_slack_response_url("https://hooks.slack.com/commands/T/B/X"))
        self.assertFalse(is_slack_response_url("https://example.com/commands/T/B/X"))

    def test_slack_completion_payload_links_uploaded_output(self):
        uploaded_output = UploadedOutput(
            bucket="bucket",
            object_name="Output/Image/card.png",
            link="https://example.com/card.png",
            content_type="image/png",
            size_bytes=10,
        )

        payload = slack_completion_payload(uploaded_output, title="Canva card")

        self.assertEqual(payload["response_type"], "ephemeral")
        self.assertIn("https://example.com/card.png", payload["text"])

    def test_deliver_image_output_posts_slack_response_and_sanitizes_metadata(self):
        uploaded_output = UploadedOutput(
            bucket="bucket",
            object_name="Output/Image/card.png",
            link="https://example.com/card.png",
            content_type="image/png",
            size_bytes=10,
        )
        config = OutputDeliveryConfig(bucket="bucket")

        with (
            mock.patch("common.output_delivery.upload_image_bytes", return_value=uploaded_output) as upload,
            mock.patch("common.output_delivery.post_progress_completed", return_value=None) as progress,
            mock.patch("common.output_delivery.post_slack_response", return_value=(200, "ok")) as slack,
        ):
            result = output_delivery.deliver_image_output(
                base64.b64encode(b"image-bytes").decode("ascii"),
                filename="card.png",
                content_type="image/png",
                title="Canva card",
                metadata={
                    "command": "/auto",
                    "response_url": "https://hooks.slack.com/commands/T/B/X",
                },
                slack_response_url="https://hooks.slack.com/commands/T/B/X",
                config=config,
            )

        self.assertEqual(upload.call_args.kwargs["metadata"], {"command": "/auto"})
        self.assertEqual(progress.call_args.kwargs["metadata"], {"command": "/auto"})
        self.assertEqual(
            slack.call_args.args[0],
            "https://hooks.slack.com/commands/T/B/X",
        )
        self.assertTrue(result["slack_response"]["notified"])
        self.assertEqual(result["slack_response"]["status"], 200)


if __name__ == "__main__":
    unittest.main()
