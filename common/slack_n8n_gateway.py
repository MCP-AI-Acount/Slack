#!/usr/bin/env python3
"""Small Slack slash-command gateway that forwards verified commands to n8n."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from common.output_delivery import DeliveryError, deliver_image_output


LOGGER = logging.getLogger("slack_n8n_gateway")
SIGNATURE_TOLERANCE_SECONDS = 60 * 5
MAX_BODY_BYTES = 1024 * 1024
SENSITIVE_FORM_KEYS = {"token"}


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing."""


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def verify_slack_signature(
    signing_secret: str,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    *,
    now: float | None = None,
) -> bool:
    """Validate Slack's v0 request signature."""
    if not signing_secret or not timestamp or not signature:
        return False

    try:
        request_time = int(timestamp)
    except ValueError:
        return False

    current_time = int(now if now is not None else time.time())
    if abs(current_time - request_time) > SIGNATURE_TOLERANCE_SECONDS:
        return False

    basestring = b"v0:" + timestamp.encode("utf-8") + b":" + body
    expected = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        basestring,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_slack_form(body: bytes) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[0] if values else "" for key, values in parsed.items()}


def slack_form_to_payload(form: dict[str, str]) -> dict[str, Any]:
    raw = {
        key: value
        for key, value in form.items()
        if key.lower() not in SENSITIVE_FORM_KEYS
    }
    return {
        "source": "slack",
        "gateway": "slack-n8n-gateway",
        "received_at": int(time.time()),
        "slack": {
            "team_id": form.get("team_id", ""),
            "team_domain": form.get("team_domain", ""),
            "enterprise_id": form.get("enterprise_id", ""),
            "enterprise_name": form.get("enterprise_name", ""),
            "channel_id": form.get("channel_id", ""),
            "channel_name": form.get("channel_name", ""),
            "user_id": form.get("user_id", ""),
            "user_name": form.get("user_name", ""),
            "command": form.get("command", ""),
            "text": form.get("text", ""),
            "api_app_id": form.get("api_app_id", ""),
            "trigger_id": form.get("trigger_id", ""),
            "response_url": form.get("response_url", ""),
            "raw": raw,
        },
    }


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    shared_secret: str | None = None,
    authorization: str | None = None,
    timeout_seconds: float = 2.0,
) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "slack-n8n-gateway/1.0",
    }
    if shared_secret:
        headers["X-Slack-Gateway-Secret"] = shared_secret
    if authorization:
        headers["Authorization"] = authorization

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.status, response_body
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        return exc.code, response_body


def slack_response(text: str, *, status: int = HTTPStatus.OK) -> tuple[int, bytes]:
    payload = {
        "response_type": "ephemeral",
        "text": text,
    }
    return status, json.dumps(payload).encode("utf-8")


class SlackN8nGatewayHandler(BaseHTTPRequestHandler):
    server_version = "SlackN8nGateway/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:
        if self.path != "/health":
            self.write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return
        self.write_json(HTTPStatus.OK, {"ok": True})

    def do_POST(self) -> None:
        if self.path == "/outputs/image":
            try:
                status, payload = self.handle_output_image()
            except ConfigError as exc:
                LOGGER.error("configuration error: %s", exc)
                status = HTTPStatus.INTERNAL_SERVER_ERROR
                payload = {"ok": False, "error": "configuration_error"}
            except DeliveryError as exc:
                LOGGER.warning("output delivery error: %s", exc)
                status = HTTPStatus.BAD_REQUEST
                payload = {"ok": False, "error": str(exc)}
            except Exception:
                LOGGER.exception("unexpected output handling error")
                status = HTTPStatus.INTERNAL_SERVER_ERROR
                payload = {"ok": False, "error": "output_gateway_error"}
            self.write_json(status, payload)
            return

        if self.path != "/slack/command":
            self.write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
            return

        try:
            status, body = self.handle_slack_command()
        except ConfigError as exc:
            LOGGER.error("configuration error: %s", exc)
            status, body = slack_response("Gateway configuration error.", status=HTTPStatus.INTERNAL_SERVER_ERROR)
        except Exception:
            LOGGER.exception("unexpected request handling error")
            status, body = slack_response("Gateway error while handling the command.", status=HTTPStatus.INTERNAL_SERVER_ERROR)

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_slack_command(self) -> tuple[int, bytes]:
        body = self.read_body()
        signing_secret = os.getenv("SLACK_SIGNING_SECRET", "")
        allow_unsigned = env_bool("ALLOW_UNSIGNED_SLACK_REQUESTS", False)

        if not allow_unsigned:
            verified = verify_slack_signature(
                signing_secret,
                self.headers.get("X-Slack-Request-Timestamp"),
                self.headers.get("X-Slack-Signature"),
                body,
            )
            if not verified:
                return slack_response("Slack request verification failed.", status=HTTPStatus.UNAUTHORIZED)

        webhook_url = get_required_env("N8N_WEBHOOK_URL")
        timeout_seconds = env_float("N8N_FORWARD_TIMEOUT_SECONDS", 2.0)
        payload = slack_form_to_payload(parse_slack_form(body))
        status, response_body = post_json(
            webhook_url,
            payload,
            shared_secret=os.getenv("N8N_SHARED_SECRET"),
            authorization=os.getenv("N8N_AUTHORIZATION"),
            timeout_seconds=timeout_seconds,
        )
        if not HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
            LOGGER.warning("n8n webhook returned %s: %s", status, response_body[:500])
            return slack_response("n8n webhook returned an error.", status=HTTPStatus.BAD_GATEWAY)

        ack_text = os.getenv("SLACK_ACK_TEXT", "Command received. n8n will continue processing it.")
        return slack_response(ack_text)

    def handle_output_image(self) -> tuple[int, dict[str, Any]]:
        if not self.verify_output_gateway_secret():
            return HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}

        payload = self.read_json_body()
        image_payload = payload.get("image_base64") or payload.get("image_data_url")
        if not isinstance(image_payload, str):
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "image_base64 or image_data_url is required"}

        metadata = payload.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "metadata must be an object"}

        result = deliver_image_output(
            image_payload,
            filename=payload.get("filename"),
            content_type=payload.get("content_type"),
            title=payload.get("task_title") or payload.get("title") or "Image output",
            task_id=payload.get("task_id"),
            metadata=metadata,
        )
        return HTTPStatus.OK, result

    def verify_output_gateway_secret(self) -> bool:
        if env_bool("ALLOW_UNSIGNED_OUTPUT_REQUESTS", False):
            return True

        expected = os.getenv("OUTPUT_GATEWAY_SHARED_SECRET")
        if not expected:
            raise ConfigError("OUTPUT_GATEWAY_SHARED_SECRET is required")

        provided = self.headers.get("X-Output-Gateway-Secret", "")
        authorization = self.headers.get("Authorization", "")
        if not provided and authorization.lower().startswith("bearer "):
            provided = authorization[7:].strip()

        return hmac.compare_digest(expected, provided)

    def read_json_body(self) -> dict[str, Any]:
        body = self.read_body()
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise DeliveryError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise DeliveryError("request body must be a JSON object")
        return payload

    def read_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        return self.rfile.read(content_length)

    def write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer((host, port), SlackN8nGatewayHandler)
    LOGGER.info("listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    run()
