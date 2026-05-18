import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "MCP_Server" / "slack_thread_server.py"
SPEC = importlib.util.spec_from_file_location("slack_thread_server", MODULE_PATH)
slack_thread_server = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(slack_thread_server)


class SlackThreadServerTest(unittest.TestCase):
    def test_reply_uses_parent_ts_as_thread_ts_and_remembers_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = slack_thread_server.ThreadStore(Path(temp_dir) / "threads.json")
            posted_payloads = []

            def fake_post_message(payload):
                posted_payloads.append(payload)
                return {
                    "ok": True,
                    "channel": payload["channel"],
                    "ts": "1710000000.000002",
                    "message": {"thread_ts": payload["thread_ts"]},
                }

            result = slack_thread_server.reply_in_thread(
                {
                    "channel": "C123",
                    "text": "first reply",
                    "parent_ts": "1710000000.000001",
                    "thread_key": "issue-1",
                },
                store,
                fake_post_message,
            )

            self.assertEqual(posted_payloads[0]["thread_ts"], "1710000000.000001")
            self.assertEqual(result["thread_ts"], "1710000000.000001")
            self.assertEqual(store.get("issue-1"), "1710000000.000001")

    def test_reply_can_continue_from_stored_thread_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = slack_thread_server.ThreadStore(Path(temp_dir) / "threads.json")
            store.set("issue-1", "1710000000.000001")
            posted_payloads = []

            def fake_post_message(payload):
                posted_payloads.append(payload)
                return {
                    "ok": True,
                    "channel": payload["channel"],
                    "ts": "1710000000.000003",
                    "message": {"thread_ts": payload["thread_ts"]},
                }

            slack_thread_server.reply_in_thread(
                {"channel": "C123", "text": "follow-up", "thread_key": "issue-1"},
                store,
                fake_post_message,
            )

            self.assertEqual(posted_payloads[0]["thread_ts"], "1710000000.000001")

    def test_reply_requires_thread_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = slack_thread_server.ThreadStore(Path(temp_dir) / "threads.json")

            with self.assertRaisesRegex(slack_thread_server.McpError, "Provide 'thread_ts'"):
                slack_thread_server.build_post_message_payload(
                    {"channel": "C123", "text": "missing thread"},
                    store,
                )

    def test_handle_request_lists_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = slack_thread_server.ThreadStore(Path(temp_dir) / "threads.json")

            response = slack_thread_server.handle_request(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                store,
            )

            self.assertEqual(response["jsonrpc"], "2.0")
            self.assertEqual(response["id"], 1)
            tool_names = {tool["name"] for tool in response["result"]["tools"]}
            self.assertIn("reply_in_thread", tool_names)
            self.assertIn("remember_thread", tool_names)

    def test_handle_request_returns_tool_error_without_exception(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = slack_thread_server.ThreadStore(Path(temp_dir) / "threads.json")

            response = slack_thread_server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "reply_in_thread",
                        "arguments": {"channel": "C123", "text": "missing thread"},
                    },
                },
                store,
            )

            result = response["result"]
            self.assertTrue(result["isError"])
            body = json.loads(result["content"][0]["text"])
            self.assertFalse(body["ok"])


if __name__ == "__main__":
    unittest.main()
