#!/usr/bin/env python3
"""Thread-aware Slack MCP server.

The server exposes tools that keep Slack replies inside an existing thread by
always passing ``thread_ts`` to ``chat.postMessage``.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional


SERVER_NAME = "slack-thread-server"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_STORE_PATH = Path("temp/slack_threads.json")


class McpError(Exception):
    """Error returned to the MCP client as a tool failure."""


class ThreadStore:
    """Small JSON-backed mapping from local keys to Slack thread timestamps."""

    def __init__(self, path: Path = DEFAULT_STORE_PATH) -> None:
        self.path = path

    def load(self) -> Dict[str, str]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as store_file:
            raw = json.load(store_file)
        if not isinstance(raw, dict):
            raise McpError(f"Thread store must contain a JSON object: {self.path}")
        return {str(key): str(value) for key, value in raw.items()}

    def save(self, values: Dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as store_file:
            json.dump(values, store_file, ensure_ascii=True, indent=2, sort_keys=True)
            store_file.write("\n")
        temp_path.replace(self.path)

    def get(self, key: str) -> Optional[str]:
        return self.load().get(key)

    def set(self, key: str, thread_ts: str) -> None:
        values = self.load()
        values[key] = thread_ts
        self.save(values)


def _required_text(arguments: Dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise McpError(f"'{key}' is required")
    return value


def _optional_text(arguments: Dict[str, Any], key: str) -> Optional[str]:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise McpError(f"'{key}' must be a non-empty string when provided")
    return value


def resolve_thread_ts(arguments: Dict[str, Any], store: ThreadStore) -> str:
    """Resolve the Slack thread timestamp used for a reply."""

    thread_ts = _optional_text(arguments, "thread_ts")
    parent_ts = _optional_text(arguments, "parent_ts")
    thread_key = _optional_text(arguments, "thread_key")

    if thread_ts:
        return thread_ts
    if parent_ts:
        return parent_ts
    if thread_key:
        stored_thread_ts = store.get(thread_key)
        if stored_thread_ts:
            return stored_thread_ts
        raise McpError(f"No Slack thread is stored for thread_key '{thread_key}'")

    raise McpError("Provide 'thread_ts', 'parent_ts', or a stored 'thread_key'")


def build_post_message_payload(arguments: Dict[str, Any], store: ThreadStore) -> Dict[str, Any]:
    """Build a Slack chat.postMessage payload that stays inside a thread."""

    payload: Dict[str, Any] = {
        "channel": _required_text(arguments, "channel"),
        "text": _required_text(arguments, "text"),
        "thread_ts": resolve_thread_ts(arguments, store),
    }

    if arguments.get("reply_broadcast") is True:
        payload["reply_broadcast"] = True
    if arguments.get("unfurl_links") is False:
        payload["unfurl_links"] = False
    if arguments.get("unfurl_media") is False:
        payload["unfurl_media"] = False

    return payload


def slack_post_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise McpError("SLACK_BOT_TOKEN is not set")

    request = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise McpError(f"Slack HTTP error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise McpError(f"Slack request failed: {exc.reason}") from exc

    if not isinstance(result, dict):
        raise McpError("Slack returned a non-object response")
    if not result.get("ok"):
        raise McpError(f"Slack API error: {result.get('error', 'unknown_error')}")

    return result


def _response_thread_ts(result: Dict[str, Any], fallback: str) -> str:
    message = result.get("message")
    if isinstance(message, dict) and isinstance(message.get("thread_ts"), str):
        return message["thread_ts"]
    if isinstance(result.get("thread_ts"), str):
        return result["thread_ts"]
    return fallback


def reply_in_thread(
    arguments: Dict[str, Any],
    store: ThreadStore,
    post_message: Callable[[Dict[str, Any]], Dict[str, Any]] = slack_post_message,
) -> Dict[str, Any]:
    payload = build_post_message_payload(arguments, store)
    result = post_message(payload)

    thread_key = _optional_text(arguments, "thread_key")
    if thread_key:
        store.set(thread_key, _response_thread_ts(result, payload["thread_ts"]))

    return {
        "ok": True,
        "channel": result.get("channel", payload["channel"]),
        "ts": result.get("ts"),
        "thread_ts": _response_thread_ts(result, payload["thread_ts"]),
    }


def remember_thread(arguments: Dict[str, Any], store: ThreadStore) -> Dict[str, Any]:
    thread_key = _required_text(arguments, "thread_key")
    thread_ts = _required_text(arguments, "thread_ts")
    store.set(thread_key, thread_ts)
    return {"ok": True, "thread_key": thread_key, "thread_ts": thread_ts}


TOOLS = [
    {
        "name": "reply_in_thread",
        "description": "Post a Slack message as a reply in an existing thread and optionally remember the thread for follow-up replies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Slack channel ID, for example C0123ABCDEF.",
                },
                "text": {
                    "type": "string",
                    "description": "Message text to send.",
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Existing Slack thread timestamp. Preferred when already known.",
                },
                "parent_ts": {
                    "type": "string",
                    "description": "Timestamp of a root message to reply to when thread_ts is not available.",
                },
                "thread_key": {
                    "type": "string",
                    "description": "Local key used to remember or continue a Slack thread across calls.",
                },
                "reply_broadcast": {
                    "type": "boolean",
                    "description": "Whether Slack should broadcast the thread reply to the channel.",
                },
                "unfurl_links": {
                    "type": "boolean",
                    "description": "Set false to disable link unfurling.",
                },
                "unfurl_media": {
                    "type": "boolean",
                    "description": "Set false to disable media unfurling.",
                },
            },
            "required": ["channel", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "remember_thread",
        "description": "Remember a Slack thread timestamp under a local key for later reply_in_thread calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "thread_key": {
                    "type": "string",
                    "description": "Local key for the Slack thread.",
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Slack thread timestamp to remember.",
                },
            },
            "required": ["thread_key", "thread_ts"],
            "additionalProperties": False,
        },
    },
]


def _tool_result(value: Dict[str, Any], is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=True)}],
        "isError": is_error,
    }


def handle_request(request: Dict[str, Any], store: ThreadStore) -> Optional[Dict[str, Any]]:
    method = request.get("method")
    request_id = request.get("id")

    if request_id is None:
        return None

    try:
        if method == "initialize":
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            protocol_version = params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION)
            result = {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = request.get("params")
            if not isinstance(params, dict):
                raise McpError("'params' must be an object")
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(arguments, dict):
                raise McpError("'arguments' must be an object")

            if name == "reply_in_thread":
                result = _tool_result(reply_in_thread(arguments, store))
            elif name == "remember_thread":
                result = _tool_result(remember_thread(arguments, store))
            else:
                raise McpError(f"Unknown tool '{name}'")
        elif method == "ping":
            result = {}
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except McpError as exc:
        if method == "tools/call":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": _tool_result({"ok": False, "error": str(exc)}, is_error=True),
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": str(exc)},
        }


def read_mcp_messages(stream: Any) -> Iterable[Dict[str, Any]]:
    while True:
        headers: Dict[str, str] = {}
        while True:
            line = stream.readline()
            if line == b"":
                return
            if line in (b"\r\n", b"\n"):
                break
            key, _, value = line.decode("ascii").partition(":")
            headers[key.strip().lower()] = value.strip()

        content_length = headers.get("content-length")
        if content_length is None:
            raise McpError("Missing Content-Length header")
        body = stream.read(int(content_length))
        message = json.loads(body.decode("utf-8"))
        if isinstance(message, dict):
            yield message
        else:
            raise McpError("MCP message must be a JSON object")


def write_mcp_message(stream: Any, message: Dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stream.write(body)
    stream.flush()


def main() -> int:
    store_path = Path(os.environ.get("SLACK_THREAD_STORE", str(DEFAULT_STORE_PATH)))
    store = ThreadStore(store_path)

    try:
        for request in read_mcp_messages(sys.stdin.buffer):
            response = handle_request(request, store)
            if response is not None:
                write_mcp_message(sys.stdout.buffer, response)
    except Exception as exc:  # MCP servers should fail visibly but never leak tokens.
        sys.stderr.write(f"{SERVER_NAME}: {exc}\n")
        sys.stderr.flush()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
