#!/usr/bin/env python3
"""Verify n8n connectivity and trigger card-news backfill for missed runs."""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.n8n_schedule_sync import (  # noqa: E402
    DEFAULT_CATCHUP_SCHEDULES,
    MISSING_CONTENT_DEFAULT,
    build_catchup_payload,
    default_webhook_url,
    diagnose_schedules,
    parse_schedules,
    post_schedule_triggers,
    resolve_channel_id,
    slack_context,
)
from common.slack_n8n_gateway import post_json  # noqa: E402


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def webhook_url() -> str:
    from common.n8n_schedule_sync import primary_webhook_url, webhook_url_candidates

    urls = webhook_url_candidates()
    if not urls:
        return required_env("N8N_WEBHOOK_URL")
    return primary_webhook_url()


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
    return parse_schedules(raw, default=DEFAULT_CATCHUP_SCHEDULES)


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
        trigger="manual",
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


def cmd_trigger(args: argparse.Namespace) -> int:
    schedules = parse_schedules(args.only, default=MISSING_CONTENT_DEFAULT)
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30"))
    return post_schedule_triggers(
        schedules,
        fallback_url=webhook_url(),
        post_json=post_json,
        channel_id=args.channel_id,
        trigger="manual_trigger",
        skip_if_posted=not args.force,
        timeout_seconds=timeout,
    )


def cmd_diagnose(_: argparse.Namespace) -> int:
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "15"))
    return diagnose_schedules(
        fallback_url=webhook_url(),
        post_json=post_json,
        timeout_seconds=timeout,
    )


def cmd_startup(args: argparse.Namespace) -> int:
    if not wait_for_n8n_ready(max_seconds=args.wait_seconds, interval_seconds=args.poll_seconds):
        return 1
    if args.verify_first and cmd_verify(argparse.Namespace()) != 0:
        return 1

    # Prefer direct per-schedule triggers (works when catchup branch missing).
    trigger_schedules = parse_schedules(args.schedules, default=MISSING_CONTENT_DEFAULT)
    print("Step 1: direct run_schedule triggers (news/regular/… — skips weather by default)")
    trigger_rc = post_schedule_triggers(
        trigger_schedules,
        fallback_url=webhook_url(),
        post_json=post_json,
        channel_id=args.channel_id,
        trigger="n8n_startup",
        skip_if_posted=not args.include_posted,
        timeout_seconds=float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30")),
    )

    print("\nStep 2: card_news_catchup (needs n8n catchup branch)")
    catchup_schedules = parse_catchup_schedules(None)
    payload = build_catchup_payload(
        args.hours,
        channel_id=args.channel_id,
        skip_already_posted=not args.include_posted,
        schedules=catchup_schedules,
        trigger="n8n_startup",
    )
    catchup = payload["catchup"]
    print(f"since: {catchup['since']}")
    catchup_rc = post_action_payload(
        payload,
        ok_message="OK: startup catchup accepted by n8n.",
        fail_message="WARN: catchup webhook failed (run_schedule above may still work).",
    )

    if trigger_rc != 0 and catchup_rc != 0:
        print(
            "\nBoth trigger and catchup failed. See docs/n8n-run-schedule-workflow.md",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or sync card-news automation with n8n.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify", help="POST a ping payload to the n8n webhook.").set_defaults(func=cmd_verify)

    backfill_parser = sub.add_parser("backfill", help="Request n8n to publish missed card news.")
    backfill_parser.add_argument("--hours", type=float, default=1.0)
    backfill_parser.add_argument("--channel-id", dest="channel_id", default=None)
    backfill_parser.set_defaults(func=cmd_backfill)

    catchup_parser = sub.add_parser("catchup", help="Run missed schedules via card_news_catchup.")
    catchup_parser.add_argument("--hours", type=float, default=24.0)
    catchup_parser.add_argument("--channel-id", dest="channel_id", default=None)
    catchup_parser.add_argument("--schedules", default=None)
    catchup_parser.add_argument("--include-posted", action="store_true")
    catchup_parser.set_defaults(func=cmd_catchup)

    trigger_parser = sub.add_parser(
        "trigger",
        help="Fire run_schedule per type (use when weather OK but news/regular missing).",
    )
    trigger_parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated: news,regular,monday_weekly,economy (default: those four, no weather).",
    )
    trigger_parser.add_argument("--channel-id", dest="channel_id", default=None)
    trigger_parser.add_argument("--force", action="store_true", help="Post even if already posted today.")
    trigger_parser.set_defaults(func=cmd_trigger)

    sub.add_parser("diagnose", help="Probe webhook + each schedule; explain likely n8n gaps.").set_defaults(
        func=cmd_diagnose
    )

    startup_parser = sub.add_parser("startup", help="Wait for n8n, trigger missing schedules + catchup.")
    startup_parser.add_argument(
        "--hours",
        type=float,
        default=float(os.getenv("N8N_STARTUP_CATCHUP_HOURS", "24")),
    )
    startup_parser.add_argument(
        "--wait-seconds",
        type=float,
        default=float(os.getenv("N8N_STARTUP_WAIT_SECONDS", "180")),
    )
    startup_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=float(os.getenv("N8N_STARTUP_POLL_SECONDS", "5")),
    )
    startup_parser.add_argument("--no-verify", dest="verify_first", action="store_false")
    startup_parser.set_defaults(verify_first=True)
    startup_parser.add_argument("--channel-id", dest="channel_id", default=None)
    startup_parser.add_argument(
        "--schedules",
        default=None,
        help="Schedules for Step 1 trigger (default: news,regular,monday_weekly,economy).",
    )
    startup_parser.add_argument("--include-posted", action="store_true")
    startup_parser.set_defaults(func=cmd_startup)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
