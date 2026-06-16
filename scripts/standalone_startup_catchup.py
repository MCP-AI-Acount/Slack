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
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

MISSING_CONTENT_DEFAULT = ["news", "regular", "monday_weekly", "economy"]
KST = ZoneInfo("Asia/Seoul")
SCHEDULE_SLOTS_KST = {"news": 9, "economy": 11, "regular": 14, "monday_weekly": 9}
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


def explicit_webhook_url() -> str:
    return (
        os.getenv("N8N_CARD_NEWS_WEBHOOK_URL")
        or os.getenv("N8N_WEBHOOK_URL")
        or os.getenv("N8N_LOCAL_WEBHOOK_URL")
        or ""
    ).strip()


def local_n8n_webhook_url() -> str:
    host = os.getenv("N8N_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.getenv("N8N_PORT", "5678").strip() or "5678"
    path = (os.getenv("N8N_WEBHOOK_PATH") or "slack-command").strip().strip("/")
    return f"http://{host}:{port}/webhook/{path}"


def webhook_url_candidates() -> list[str]:
    candidates: list[str] = []
    explicit = explicit_webhook_url()
    local = local_n8n_webhook_url()
    if os.getenv("N8N_USE_LOCAL", "").lower() in {"1", "true", "yes", "on"}:
        candidates.append(local)
    if explicit:
        candidates.append(explicit)
    if local not in candidates:
        candidates.append(local)
    if not explicit:
        host = os.getenv("N8N_HOST", "127.0.0.1").strip() or "127.0.0.1"
        port = os.getenv("N8N_PORT", "5678").strip() or "5678"
        for path in ("card-news", "slack-command", "cursor"):
            url = f"http://{host}:{port}/webhook/{path}"
            if url not in candidates:
                candidates.append(url)
    return candidates


def is_dns_resolution_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, OSError) and reason.errno in (-2, -3):
            return True
        text = str(reason).lower()
        if "name resolution" in text or "getaddrinfo" in text:
            return True
    return False


def print_dns_hint(failed_url: str) -> None:
    local = local_n8n_webhook_url()
    print(
        f"\nDNS failed: {failed_url}\n"
        "Same VM as n8n → use localhost (no external hostname):\n"
        f'  export N8N_WEBHOOK_URL="{local}"\n'
        "  export N8N_WEBHOOK_PATH=slack-command   # match n8n Webhook node path\n"
        "  curl -s http://127.0.0.1:5678/healthz\n",
        file=sys.stderr,
    )


def post_json(url: str, payload: dict[str, Any], *, timeout: float) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "standalone-startup-catchup/2.1"}
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


def post_json_try_urls(urls: list[str], payload: dict[str, Any], *, timeout: float) -> tuple[int, str, str]:
    last_error: BaseException | None = None
    for url in urls:
        try:
            status, body = post_json(url, payload, timeout=timeout)
            return status, body, url
        except urllib.error.URLError as exc:
            last_error = exc
            if is_dns_resolution_error(exc):
                print(f"WARN: DNS failed for {url}, trying next...", file=sys.stderr)
                continue
            raise
    print_dns_hint(urls[0] if urls else "")
    if last_error is not None:
        raise last_error
    raise SystemExit("No webhook URL")


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


def missing_content_schedules() -> list[str]:
    now = datetime.now(KST)
    if now.weekday() == 0:
        return list(MISSING_CONTENT_DEFAULT)
    return [s for s in MISSING_CONTENT_DEFAULT if s != "monday_weekly"]


def afternoon_recovery_schedules() -> list[str]:
    now = datetime.now(KST)
    regular_hour = SCHEDULE_SLOTS_KST["regular"]
    if now.hour < regular_hour:
        raise SystemExit(
            f"Afternoon recovery runs after {regular_hour}:00 KST (now {now.strftime('%H:%M')})"
        )
    schedules = ["regular"]
    if now.hour >= SCHEDULE_SLOTS_KST["news"]:
        schedules.insert(0, "news")
    if now.hour >= SCHEDULE_SLOTS_KST["economy"]:
        schedules.append("economy")
    if now.weekday() == 0 and now.hour >= SCHEDULE_SLOTS_KST["monday_weekly"]:
        schedules.append("monday_weekly")
    return schedules


def webhook_response_likely_noop(status: int, body: str) -> bool:
    if not (200 <= status < 300):
        return False
    text = body.strip()
    if not text:
        return True
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("ok") is True:
        return False
    message = str(payload.get("message", "")).lower()
    if "workflow was started" in message:
        return False
    if set(payload.keys()) <= {"headers", "params", "query", "body", "webhookUrl"}:
        return True
    return False


def parse_only(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return missing_content_schedules()
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def cmd_trigger(args: argparse.Namespace) -> int:
    urls = webhook_url_candidates()
    if not urls:
        raise SystemExit("Set N8N_WEBHOOK_URL or N8N_USE_LOCAL=true")
    print(f"Webhook candidates: {urls[0]}" + (f" (+{len(urls)-1} fallback)" if len(urls) > 1 else ""))

    schedules = parse_only(args.only)
    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30"))
    failures = 0
    for schedule in schedules:
        env_name = SCHEDULE_WEBHOOK_ENV.get(schedule, "")
        override = os.getenv(env_name, "").strip() if env_name else ""
        try_urls = [override, *urls] if override else urls

        payload = build_run_schedule_payload(schedule)
        label = SCHEDULE_LABELS_KO.get(schedule, schedule)
        print(f"\n--- {schedule} ({label}) ---")
        try:
            status, body, url_used = post_json_try_urls(try_urls, payload, timeout=timeout)
        except urllib.error.URLError:
            failures += 1
            continue
        print(f"webhook: {url_used}")
        print(f"status: {status} body: {body[:300]}")
        if not (200 <= status < 300) or webhook_response_likely_noop(status, body):
            if 200 <= status < 300:
                print(
                    f"WARN: {schedule} HTTP 200 but likely no run_schedule branch in n8n.",
                    file=sys.stderr,
                )
            failures += 1
    if failures:
        print(f"\n{failures} failed.", file=sys.stderr)
        return 1
    print("\nHTTP OK — if Slack still empty, fix n8n run_schedule branch.")
    return 0


def cmd_afternoon(args: argparse.Namespace) -> int:
    schedules = afternoon_recovery_schedules()
    if args.only:
        schedules = parse_only(args.only)
    print(f"afternoon recovery: {', '.join(schedules)}")
    return cmd_trigger(argparse.Namespace(only=",".join(schedules)))


def cmd_evening(args: argparse.Namespace) -> int:
    schedules = ["daily"]
    if args.only:
        schedules = [part.strip().lower() for part in args.only.split(",") if part.strip()]
    print(f"evening recovery: {', '.join(schedules)}")
    return _cmd_trigger_schedules(schedules, force=args.force)


def _cmd_trigger_schedules(schedules: list[str], *, force: bool) -> int:
    urls = webhook_url_candidates()
    if not urls:
        raise SystemExit("Set N8N_WEBHOOK_URL or N8N_USE_LOCAL=true")
    print(f"Webhook candidates: {urls[0]}" + (f" (+{len(urls)-1} fallback)" if len(urls) > 1 else ""))

    timeout = float(os.getenv("N8N_FORWARD_TIMEOUT_SECONDS", "30"))
    failures = 0
    for schedule in schedules:
        env_name = SCHEDULE_WEBHOOK_ENV.get(schedule, "")
        override = os.getenv(env_name, "").strip() if env_name else ""
        try_urls = [override, *urls] if override else urls

        payload = build_run_schedule_payload(schedule)
        payload["run"]["skip_if_posted"] = not force
        payload["run"]["force"] = force
        label = SCHEDULE_LABELS_KO.get(schedule, schedule)
        print(f"\n--- {schedule} ({label}) ---")
        try:
            status, body, url_used = post_json_try_urls(try_urls, payload, timeout=timeout)
        except urllib.error.URLError:
            failures += 1
            continue
        print(f"webhook: {url_used}")
        print(f"status: {status} body: {body[:300]}")
        if not (200 <= status < 300) or webhook_response_likely_noop(status, body):
            if 200 <= status < 300:
                print(
                    f"WARN: {schedule} HTTP 200 but likely no run_schedule branch in n8n.",
                    file=sys.stderr,
                )
            failures += 1
    if failures:
        print(f"\n{failures} failed.", file=sys.stderr)
        return 1
    print("\nHTTP OK — if Slack still empty, fix n8n run_schedule branch.")
    return 0


def cmd_startup(_: argparse.Namespace) -> int:
    return cmd_trigger(argparse.Namespace(only=",".join(missing_content_schedules())))


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone n8n schedule trigger")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("startup", help="Trigger news+regular+… (skip weather)").set_defaults(func=cmd_startup)
    afternoon_parser = sub.add_parser("afternoon", help="Recover missed afternoon regular schedule (KST)")
    afternoon_parser.add_argument("--only", default=None)
    afternoon_parser.set_defaults(func=cmd_afternoon)
    evening_parser = sub.add_parser("evening", help="Recover 18:00 KST daily/topic batch")
    evening_parser.add_argument("--only", default=None, help="Default: daily")
    evening_parser.add_argument("--force", action="store_true", help="Post even if already posted today.")
    evening_parser.set_defaults(func=cmd_evening)
    trigger_parser = sub.add_parser("trigger", help="Trigger specific schedules")
    trigger_parser.add_argument("--only", default=None)
    trigger_parser.set_defaults(func=cmd_trigger)
    args = parser.parse_args()
    if not args.command:
        args.command = "startup"
        args.func = cmd_startup
        args.only = ",".join(missing_content_schedules())
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
