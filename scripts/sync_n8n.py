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
VALID_CATCHUP_SCHEDULES = frozenset({"regular", "monday_weekly", "daily"})


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def webhook_url() -> str:
    return os.getenv("N8N_CARD_NEWS_WEBHOOK_URL") or required_env("N8N_WEBHOOK_URL")


def resolve_channel_id(channel_id: str | None) -> str:
    return (channel_id or os.getenv("SLACK_CARD_NEWS_CHANNEL_ID") or DEFAULT_CARD_NEWS_CHANNEL_ID).strip()


def slack_context(*, channel_id: str, text: str) -> dict[str, str]:
    return {
        "channel_id": channel_id,
        "channel_name": os.getenv("SLACK_CARD_NEWS_CHANNEL_NAME", "자동화_날씨7경제5"),
        "command": os.getenv("SLACK_CARD_NEWS_COMMAND", "/cursor"),
        "text": text,
    }


def build_backfill_payload(hours: float, *, channel_id: str | None) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    channel = resolve_channel_id(channel_id)
    return {
        "source": "cursor",
        "gateway": "sync-n8n",
        "action": "card_news_backfill",
        "received_at": int(time.time()),
        "backfill": {
            "hours": hours,
            "since": since.isoformat(),
        },
        "slack": slack_context(channel_id=channel, text=f"card news backfill last {hours:g}h"),
    }


def parse_catchup_schedules(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return ["regular", "monday_weekly"]
    schedules = [part.strip().lower() for part in raw.split(",") if part.strip()]
    unknown = sorted(set(schedules) - VALID_CATCHUP_SCHEDULES)
    if unknown:
        allowed = ", ".join(sorted(VALID_CATCHUP_SCHEDULES))
        raise SystemExit(f"Unknown schedule(s): {', '.join(unknown)}. Allowed: {allowed}")
    return schedules


def build_catchup_payload(
    hours: float,
    *,
    channel_id: str | None,
    skip_already_posted: bool,
    schedules: list[str],
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    channel = resolve_channel_id(channel_id)
    schedule_label = "+".join(schedules)
    return {
        "source": "cursor",
        "gateway": "sync-n8n",
        "action": "card_news_catchup",
        "received_at": int(time.time()),
        "catchup": {
            "hours": hours,
            "since": since.isoformat(),
            "skip_already_posted": skip_already_posted,
            "schedules": schedules,
        },
        "slack": slack_context(
            channel_id=channel,
            text=f"card news catchup {schedule_label} skip_posted={skip_already_posted} last {hours:g}h",
        ),
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


def post_action_payload(payload: dict[str, Any], *, ok_message: str, fail_message: str) -> int:
    url = webhook_url()
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30"))
    status, body = post_json(
        url,
        payload,
        shared_secret=os.getenv("N8N_SHARED_SECRET"),
        authorization=os.getenv("N8N_AUTHORIZATION"),
        timeout_seconds=timeout,
    )
    print(f"n8n webhook: {url}")
    print(f"payload action: {payload['action']}")
    print(f"status: {status}")
    print(f"body: {body[:500]}")
    if 200 <= status < 300:
        print(ok_message)
        return 0
    print(fail_message, file=sys.stderr)
    return 1


def cmd_backfill(args: argparse.Namespace) -> int:
    payload = build_backfill_payload(args.hours, channel_id=args.channel_id)
    print(f"since: {payload['backfill']['since']}")
    return post_action_payload(
        payload,
        ok_message="OK: backfill request accepted by n8n.",
        fail_message="FAIL: n8n rejected the backfill request.",
    )


def cmd_catchup(args: argparse.Namespace) -> int:
    schedules = parse_catchup_schedules(args.schedules)
    payload = build_catchup_payload(
        args.hours,
        channel_id=args.channel_id,
        skip_already_posted=not args.include_posted,
        schedules=schedules,
    )
    catchup = payload["catchup"]
    print(f"since: {catchup['since']}")
    print(f"schedules: {', '.join(catchup['schedules'])}")
    print(f"skip_already_posted: {catchup['skip_already_posted']}")
    return post_action_payload(
        payload,
        ok_message="OK: catchup request accepted by n8n.",
        fail_message="FAIL: n8n rejected the catchup request.",
    )


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

    catchup_parser = sub.add_parser(
        "catchup",
        help="Run missed regular + Monday weekly schedules, skipping items already posted.",
    )
    catchup_parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Look back this many hours (default: 24).",
    )
    catchup_parser.add_argument(
        "--channel-id",
        dest="channel_id",
        default=None,
        help="Slack channel ID for #자동화_날씨7경제5 (overrides SLACK_CARD_NEWS_CHANNEL_ID).",
    )
    catchup_parser.add_argument(
        "--schedules",
        default=None,
        help="Comma-separated schedule keys: regular, monday_weekly, daily (default: regular,monday_weekly).",
    )
    catchup_parser.add_argument(
        "--include-posted",
        action="store_true",
        help="Also republish items that were already posted in the lookback window.",
    )
    catchup_parser.set_defaults(func=cmd_catchup)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
