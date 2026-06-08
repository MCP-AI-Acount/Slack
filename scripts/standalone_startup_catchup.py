#!/usr/bin/env python3
"""Standalone n8n startup catchup — no repo checkout required."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Inline copy of schedule keys (keep in sync with common/n8n_schedule_sync.py)
MISSING_CONTENT_DEFAULT = ["news", "regular", "monday_weekly", "economy"]
SCHEDULE_WEBHOOK_ENV = {
    "weather": "N8N_WEBHOOK_URL_WEATHER",
    "economy": "N8N_WEBHOOK_URL_ECONOMY",
    "news": "N8N_WEBHOOK_URL_NEWS",
    "regular": "N8N_WEBHOOK_URL_REGULAR",
    "monday_weekly": "N8N_WEBHOOK_URL_MONDAY_WEEKLY",
    "daily": "N8N_WEBHOOK_URL_DAILY",
}
SCHEDULE_LABELS_KO = {
    "weather": "일기예보",
    "economy": "경제",
    "news": "기사/뉴스",
    "regular": "정규일정",
    "monday_weekly": "월요일 주간",
    "daily": "매일",
}
DEFAULT_CHANNEL = "C0B4JUZPX2L"


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def default_webhook_url() -> str:
    return (os.getenv("N8N_CARD_NEWS_WEBHOOK_URL") or os.getenv("N8N_WEBHOOK_URL") or "").strip()


def schedule_webhook_url(schedule: str, *, fallback: str) -> str:
    env_name = SCHEDULE_WEBHOOK_ENV.get(schedule, "")
    if env_name:
        override = os.getenv(env_name, "").strip()
        if override:
            return override
    return fallback


def post_json(url: str, payload: dict[str, Any], *, timeout: float) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "standalone-startup-catchup/2.0"}
    secret = os.getenv("N8N_SHARED_SECRET")
    auth = os.getenv("N8N_AUTHORIZATION")
    if secret:
        headers["X-Slack-Gateway-Secret"] = secret
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def build_run_schedule_payload(schedule: str) -> dict[str, Any]:
    channel = (os.getenv("SLACK_CARD_NEWS_CHANNEL_ID") or DEFAULT_CHANNEL).strip()
    label = SCHEDULE_LABELS_KO.get(schedule, schedule)
    return {
        "source": "cursor",
        "gateway": "standalone-startup-catchup",
        "action": "run_schedule",
        "schedule": schedule,
        "received_at": int(time.time()),
        "run": {"schedule": schedule, "trigger": "standalone", "skip_if_posted": True},
        "slack": {
            "channel_id": channel,
            "channel_name": os.getenv("SLACK_CARD_NEWS_CHANNEL_NAME", "자동화_날씨7경제5"),
            "text": f"run schedule: {label}",
        },
    }


def parse_only(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return list(MISSING_CONTENT_DEFAULT)
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def cmd_trigger(args: argparse.Namespace) -> int:
    fallback = default_webhook_url() or required_env("N8N_WEBHOOK_URL")
    schedules = parse_only(args.only)
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30"))
    failures = 0
    for schedule in schedules:
        url = schedule_webhook_url(schedule, fallback=fallback)
        payload = build_run_schedule_payload(schedule)
        label = SCHEDULE_LABELS_KO.get(schedule, schedule)
        print(f"\n--- {schedule} ({label}) ---")
        print(f"webhook: {url}")
        status, body = post_json(url, payload, timeout=timeout)
        print(f"status: {status} body: {body[:300]}")
        if not (200 <= status < 300):
            failures += 1
    if failures:
        print(f"\n{failures} failed. n8n needs action=run_schedule branch.", file=sys.stderr)
        print("See: docs/n8n-run-schedule-workflow.md in Slack repo", file=sys.stderr)
        return 1
    print("\nHTTP OK — if Slack still empty, fix n8n workflow (not this script).")
    return 0


def cmd_startup(_: argparse.Namespace) -> int:
    return cmd_trigger(argparse.Namespace(only=",".join(MISSING_CONTENT_DEFAULT)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone n8n schedule trigger")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("startup", help="Trigger news+regular+… (default, skip weather)").set_defaults(
        func=cmd_startup
    )
    trigger_parser = sub.add_parser("trigger", help="Trigger specific schedules")
    trigger_parser.add_argument(
        "--only",
        default=None,
        help="news,regular,monday_weekly,economy (default: those four)",
    )
    trigger_parser.set_defaults(func=cmd_trigger)
    args = parser.parse_args()
    if not args.command:
        args.command = "startup"
        args.func = cmd_startup
        args.only = ",".join(MISSING_CONTENT_DEFAULT)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
