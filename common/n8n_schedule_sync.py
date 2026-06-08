"""Shared n8n schedule trigger helpers for card-news sync scripts."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

DEFAULT_CARD_NEWS_CHANNEL_ID = "C0B4JUZPX2L"
VALID_SCHEDULES = frozenset({"weather", "economy", "news", "regular", "monday_weekly", "daily"})
DEFAULT_CATCHUP_SCHEDULES = [
    "weather",
    "economy",
    "news",
    "regular",
    "monday_weekly",
    "daily",
]
# When weather already posted, trigger these for "기사+일정만" recovery.
MISSING_CONTENT_DEFAULT = ["news", "regular", "monday_weekly", "economy"]

SCHEDULE_WEBHOOK_ENV: dict[str, str] = {
    "weather": "N8N_WEBHOOK_URL_WEATHER",
    "economy": "N8N_WEBHOOK_URL_ECONOMY",
    "news": "N8N_WEBHOOK_URL_NEWS",
    "regular": "N8N_WEBHOOK_URL_REGULAR",
    "monday_weekly": "N8N_WEBHOOK_URL_MONDAY_WEEKLY",
    "daily": "N8N_WEBHOOK_URL_DAILY",
}

SCHEDULE_LABELS_KO: dict[str, str] = {
    "weather": "일기예보(날씨)",
    "economy": "경제",
    "news": "기사/뉴스",
    "regular": "정규일정",
    "monday_weekly": "월요일 주간",
    "daily": "매일",
}


def parse_schedules(raw: str | None, *, default: list[str]) -> list[str]:
    if not raw or not raw.strip():
        return list(default)
    schedules = [part.strip().lower() for part in raw.split(",") if part.strip()]
    unknown = sorted(set(schedules) - VALID_SCHEDULES)
    if unknown:
        allowed = ", ".join(sorted(VALID_SCHEDULES))
        raise SystemExit(f"Unknown schedule(s): {', '.join(unknown)}. Allowed: {allowed}")
    return schedules


def resolve_channel_id(channel_id: str | None) -> str:
    return (channel_id or os.getenv("SLACK_CARD_NEWS_CHANNEL_ID") or DEFAULT_CARD_NEWS_CHANNEL_ID).strip()


def slack_context(*, channel_id: str, text: str) -> dict[str, str]:
    return {
        "channel_id": channel_id,
        "channel_name": os.getenv("SLACK_CARD_NEWS_CHANNEL_NAME", "자동화_날씨7경제5"),
        "command": os.getenv("SLACK_CARD_NEWS_COMMAND", "/cursor"),
        "text": text,
    }


def default_webhook_url() -> str:
    return (
        os.getenv("N8N_CARD_NEWS_WEBHOOK_URL")
        or os.getenv("N8N_WEBHOOK_URL")
        or ""
    ).strip()


def schedule_webhook_url(schedule: str, *, fallback_url: str) -> str:
    env_name = SCHEDULE_WEBHOOK_ENV.get(schedule, "")
    if env_name:
        override = os.getenv(env_name, "").strip()
        if override:
            return override
    return fallback_url


def build_run_schedule_payload(
    schedule: str,
    *,
    channel_id: str | None,
    trigger: str = "manual",
    skip_if_posted: bool = True,
) -> dict[str, Any]:
    channel = resolve_channel_id(channel_id)
    label = SCHEDULE_LABELS_KO.get(schedule, schedule)
    return {
        "source": "cursor",
        "gateway": "sync-n8n",
        "action": "run_schedule",
        "schedule": schedule,
        "received_at": int(time.time()),
        "run": {
            "schedule": schedule,
            "trigger": trigger,
            "skip_if_posted": skip_if_posted,
            "force": not skip_if_posted,
        },
        "slack": slack_context(
            channel_id=channel,
            text=f"run schedule: {label} ({schedule})",
        ),
    }


def build_catchup_payload(
    hours: float,
    *,
    channel_id: str | None,
    skip_already_posted: bool,
    schedules: list[str],
    trigger: str = "manual",
    gateway: str = "sync-n8n",
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    channel = resolve_channel_id(channel_id)
    schedule_label = "+".join(schedules)
    return {
        "source": "cursor",
        "gateway": gateway,
        "action": "card_news_catchup",
        "received_at": int(time.time()),
        "catchup": {
            "hours": hours,
            "since": since.isoformat(),
            "skip_already_posted": skip_already_posted,
            "schedules": schedules,
            "trigger": trigger,
            "auto": trigger != "manual",
        },
        "slack": slack_context(
            channel_id=channel,
            text=f"card news catchup {schedule_label} skip_posted={skip_already_posted} last {hours:g}h",
        ),
    }


def post_schedule_triggers(
    schedules: list[str],
    *,
    fallback_url: str,
    post_json: Callable[..., tuple[int, str]],
    channel_id: str | None,
    trigger: str,
    skip_if_posted: bool,
    timeout_seconds: float,
) -> int:
    if not fallback_url:
        raise SystemExit("N8N_WEBHOOK_URL is required")

    shared_secret = os.getenv("N8N_SHARED_SECRET")
    authorization = os.getenv("N8N_AUTHORIZATION")
    failures = 0

    for schedule in schedules:
        url = schedule_webhook_url(schedule, fallback_url=fallback_url)
        payload = build_run_schedule_payload(
            schedule,
            channel_id=channel_id,
            trigger=trigger,
            skip_if_posted=skip_if_posted,
        )
        label = SCHEDULE_LABELS_KO.get(schedule, schedule)
        print(f"\n--- trigger {schedule} ({label}) ---")
        print(f"webhook: {url}")
        status, body = post_json(
            url,
            payload,
            shared_secret=shared_secret,
            authorization=authorization,
            timeout_seconds=timeout_seconds,
        )
        print(f"action: run_schedule")
        print(f"status: {status}")
        print(f"body: {body[:500]}")
        if 200 <= status < 300:
            print(f"OK: {schedule} trigger accepted (check n8n Executions for actual post).")
        else:
            print(f"FAIL: {schedule} trigger rejected.", file=sys.stderr)
            failures += 1
        time.sleep(0.3)

    if failures:
        print(
            f"\n{failures}/{len(schedules)} triggers failed at HTTP level.",
            file=sys.stderr,
        )
        return 1

    print(
        "\nAll triggers returned HTTP 2xx. If Slack still empty, n8n workflow "
        "likely has no branch for action=run_schedule — see docs/n8n-run-schedule-workflow.md"
    )
    return 0


def diagnose_schedules(
    *,
    fallback_url: str,
    post_json: Callable[..., tuple[int, str]],
    timeout_seconds: float,
) -> int:
    if not fallback_url:
        raise SystemExit("N8N_WEBHOOK_URL is required")

    print("=== n8n card-news diagnose ===\n")
    print(f"default webhook: {fallback_url}")
    for schedule, env_name in SCHEDULE_WEBHOOK_ENV.items():
        override = os.getenv(env_name, "").strip()
        if override:
            print(f"  {schedule}: {override} (from {env_name})")
        else:
            print(f"  {schedule}: (uses default webhook)")

    shared_secret = os.getenv("N8N_SHARED_SECRET")
    authorization = os.getenv("N8N_AUTHORIZATION")

    ping = {
        "source": "cursor",
        "gateway": "sync-n8n",
        "action": "ping",
        "received_at": int(time.time()),
    }
    status, body = post_json(
        fallback_url,
        ping,
        shared_secret=shared_secret,
        authorization=authorization,
        timeout_seconds=timeout_seconds,
    )
    print(f"\nping status: {status} body: {body[:200]}")

    print("\n--- per-schedule run_schedule probe ---")
    print("(HTTP 200 only means webhook received — not that Slack posted)\n")

    issues: list[str] = []
    for schedule in DEFAULT_CATCHUP_SCHEDULES:
        url = schedule_webhook_url(schedule, fallback_url=fallback_url)
        payload = build_run_schedule_payload(schedule, channel_id=None, trigger="diagnose")
        status, body = post_json(
            url,
            payload,
            shared_secret=shared_secret,
            authorization=authorization,
            timeout_seconds=timeout_seconds,
        )
        label = SCHEDULE_LABELS_KO.get(schedule, schedule)
        ok = 200 <= status < 300
        mark = "OK" if ok else "FAIL"
        print(f"[{mark}] {schedule:14} ({label}) status={status}")
        if not ok:
            issues.append(f"{schedule}: HTTP {status}")

    print("\n=== likely cause when weather OK but news/schedule missing ===")
    print("1. Weather uses its own Schedule Trigger workflow (works).")
    print("2. News/regular use OTHER workflows — cron missed or workflow inactive/failed.")
    print("3. card_news_catchup / run_schedule branches may NOT exist on this webhook.")
    print("   → webhook returns 200 but n8n does nothing after Webhook node.")
    print("4. Fix: n8n Executions tab → find news/regular workflow errors.")
    print("   Add IF/Switch on action=run_schedule — see docs/n8n-run-schedule-workflow.md")

    if issues:
        print(f"\nHTTP failures: {', '.join(issues)}", file=sys.stderr)
        return 1
    return 0
