#!/usr/bin/env python3
"""Verify n8n connectivity and trigger card-news backfill for missed runs."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# Allow `python3 scripts/sync_n8n.py` without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.slack_n8n_gateway import post_json  # noqa: E402


DEFAULT_CARD_NEWS_CHANNEL_ID = "C0B4JUZPX2L"


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def webhook_url() -> str:
    return os.getenv("N8N_CARD_NEWS_WEBHOOK_URL") or required_env("N8N_WEBHOOK_URL")


def build_backfill_payload(hours: float, *, channel_id: str | None) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    channel = (channel_id or os.getenv("SLACK_CARD_NEWS_CHANNEL_ID") or DEFAULT_CARD_NEWS_CHANNEL_ID).strip()
    return {
        "source": "cursor",
        "gateway": "sync-n8n",
        "action": "card_news_backfill",
        "received_at": int(time.time()),
        "backfill": {
            "hours": hours,
            "since": since.isoformat(),
        },
        "slack": {
            "channel_id": channel,
            "channel_name": os.getenv("SLACK_CARD_NEWS_CHANNEL_NAME", "자동화_날씨7경제5"),
            "command": os.getenv("SLACK_CARD_NEWS_COMMAND", "/cursor"),
            "text": f"card news backfill last {hours:g}h",
        },
    }


def cmd_verify(_: argparse.Namespace) -> int:
    url = webhook_url()
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "10"))
    payload = {
        "source": "cursor",
        "gateway": "sync-n8n",
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


def cmd_backfill(args: argparse.Namespace) -> int:
    url = webhook_url()
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30"))
    payload = build_backfill_payload(args.hours, channel_id=args.channel_id)
    status, body = post_json(
        url,
        payload,
        shared_secret=os.getenv("N8N_SHARED_SECRET"),
        authorization=os.getenv("N8N_AUTHORIZATION"),
        timeout_seconds=timeout,
    )
    print(f"n8n webhook: {url}")
    print(f"payload action: {payload['action']}, since: {payload['backfill']['since']}")
    print(f"status: {status}")
    print(f"body: {body[:500]}")
    if 200 <= status < 300:
        print("OK: backfill request accepted by n8n.")
        return 0
    print("FAIL: n8n rejected the backfill request.", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or sync card-news automation with n8n.")
    sub = parser.add_subparsers(dest="command", required=True)

    verify_parser = sub.add_parser("verify", help="POST a ping payload to the n8n webhook.")
    verify_parser.set_defaults(func=cmd_verify)

    backfill_parser = sub.add_parser("backfill", help="Request n8n to publish missed card news.")
    backfill_parser.add_argument(
        "--hours",
        type=float,
        default=1.0,
        help="Look back this many hours (default: 1).",
    )
    backfill_parser.add_argument(
        "--channel-id",
        dest="channel_id",
        default=None,
        help="Slack channel ID for #자동화_날씨7경제5 (overrides SLACK_CARD_NEWS_CHANNEL_ID).",
    )
    backfill_parser.set_defaults(func=cmd_backfill)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
