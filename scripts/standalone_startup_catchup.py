#!/usr/bin/env python3
"""Standalone n8n startup catchup — no repo checkout required.

Copy this single file to the VM and run:

  export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
  python3 standalone_startup_catchup.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_CARD_NEWS_CHANNEL_ID = "C0B4JUZPX2L"
DEFAULT_CATCHUP_SCHEDULES = [
    "weather",
    "economy",
    "news",
    "regular",
    "monday_weekly",
    "daily",
]


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def webhook_url() -> str:
    return os.getenv("N8N_CARD_NEWS_WEBHOOK_URL") or required_env("N8N_WEBHOOK_URL")


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    shared_secret: str | None,
    authorization: str | None,
    timeout_seconds: float,
) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "standalone-startup-catchup/1.0",
    }
    if shared_secret:
        headers["X-Slack-Gateway-Secret"] = shared_secret
    if authorization:
        headers["Authorization"] = authorization

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def n8n_health_url() -> str:
    return os.getenv("N8N_HEALTH_URL", "http://localhost:5678/healthz").strip()


def wait_for_n8n_ready(*, max_seconds: float, interval_seconds: float) -> bool:
    deadline = time.time() + max_seconds
    url = n8n_health_url()
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 300:
                    print(f"OK: n8n ready at {url}")
                    return True
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"waiting for n8n ({url}): {exc}")
        time.sleep(interval_seconds)
    print(f"FAIL: n8n not ready after {max_seconds:g}s", file=sys.stderr)
    return False


def build_catchup_payload(hours: float) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    channel = (os.getenv("SLACK_CARD_NEWS_CHANNEL_ID") or DEFAULT_CARD_NEWS_CHANNEL_ID).strip()
    schedules = DEFAULT_CATCHUP_SCHEDULES
    schedule_label = "+".join(schedules)
    return {
        "source": "cursor",
        "gateway": "standalone-startup-catchup",
        "action": "card_news_catchup",
        "received_at": int(time.time()),
        "catchup": {
            "hours": hours,
            "since": since.isoformat(),
            "skip_already_posted": True,
            "schedules": schedules,
            "trigger": "n8n_startup",
            "auto": True,
        },
        "slack": {
            "channel_id": channel,
            "channel_name": os.getenv("SLACK_CARD_NEWS_CHANNEL_NAME", "자동화_날씨7경제5"),
            "command": os.getenv("SLACK_CARD_NEWS_COMMAND", "/cursor"),
            "text": f"card news catchup {schedule_label} skip_posted=true last {hours:g}h",
        },
    }


def ping_webhook() -> int:
    url = webhook_url()
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "10"))
    payload = {
        "source": "cursor",
        "gateway": "standalone-startup-catchup",
        "action": "ping",
        "received_at": int(time.time()),
    }
    status, body = post_json(
        url,
        payload,
        shared_secret=os.getenv("N8N_SHARED_SECRET"),
        authorization=os.getenv("N8N_AUTHORIZATION"),
        timeout_seconds=timeout,
    )
    print(f"n8n webhook: {url}")
    print(f"status: {status}")
    print(f"body: {body[:500]}")
    if 200 <= status < 300:
        print("OK: n8n webhook accepted the ping.")
        return 0
    print("FAIL: n8n webhook did not return success.", file=sys.stderr)
    return 1


def main() -> int:
    hours = float(os.getenv("N8N_STARTUP_CATCHUP_HOURS", "24"))
    wait_seconds = float(os.getenv("N8N_STARTUP_WAIT_SECONDS", "180"))
    poll_seconds = float(os.getenv("N8N_STARTUP_POLL_SECONDS", "5"))

    if not wait_for_n8n_ready(max_seconds=wait_seconds, interval_seconds=poll_seconds):
        return 1
    if ping_webhook() != 0:
        return 1

    payload = build_catchup_payload(hours)
    catchup = payload["catchup"]
    print("Auto catchup after n8n startup")
    print(f"since: {catchup['since']}")
    print(f"schedules: {', '.join(catchup['schedules'])}")
    print(f"skip_already_posted: {catchup['skip_already_posted']}")

    url = webhook_url()
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30"))
    status, body = post_json(
        url,
        payload,
        shared_secret=os.getenv("N8N_SHARED_SECRET"),
        authorization=os.getenv("N8N_AUTHORIZATION"),
        timeout_seconds=timeout,
    )
    print(f"payload action: {payload['action']}")
    print(f"status: {status}")
    print(f"body: {body[:500]}")
    if 200 <= status < 300:
        print("OK: startup catchup accepted by n8n.")
        return 0
    print("FAIL: n8n rejected the startup catchup request.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
