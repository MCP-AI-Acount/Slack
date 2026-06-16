#!/usr/bin/env bash
# 저녁 토픽 뉴스(기술·문화·건강) — MCP-Auto 없이 VM에서 실행 가능.
#
#   bash ~/sync_topic_news_evening_vm.sh --no-wait
#   bash scripts/run_topic_news_evening_batch.sh --no-wait
set -euo pipefail

_BIN="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${CARDNEWS_BIN_DIR:-${HOME}/.local/bin}"
TRIGGER="${INSTALL_DIR}/trigger_cardnews.py"
SLACK_RAW_BASE="${SLACK_RAW_BASE:-https://raw.githubusercontent.com/MCP-AI-Acount/Slack}"
SLACK_RAW_REFS="${SLACK_RAW_REFS:-master main}"
ENVF="${ENVF:-$HOME/n8n-secrets.env}"
AGENT_SECRETS="${AGENT_SECRETS:-$HOME/.config/agent-secrets.env}"

for f in "$AGENT_SECRETS" "$ENVF"; do
  if [[ -f "$f" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
  fi
done

WAIT_UNTIL_18=1
FORCE=""
EXTRA=()
for arg in "$@"; do
  case "$arg" in
    --no-wait) WAIT_UNTIL_18=0; FORCE="--force" ;;
    --wait) WAIT_UNTIL_18=1 ;;
    *) EXTRA+=("$arg") ;;
  esac
done

if [[ $WAIT_UNTIL_18 -eq 1 ]]; then
  kst_hour="$(TZ=Asia/Seoul date '+%H')"
  kst_min="$(TZ=Asia/Seoul date '+%M')"
  if [[ "$kst_hour" -lt 18 ]]; then
    secs=$(( (18 - kst_hour) * 3600 - kst_min * 60 ))
    echo "[evening] before 18:00 KST — sleeping ${secs}s (pass --no-wait to publish now)"
    sleep "$secs"
  fi
fi

_ensure_trigger() {
  mkdir -p "$INSTALL_DIR"
  if [[ -f "$_BIN/standalone_startup_catchup.py" ]]; then
    cp "$_BIN/standalone_startup_catchup.py" "$TRIGGER"
    echo "[evening] using bundled standalone_startup_catchup.py"
    return 0
  fi
  if [[ -f "$TRIGGER" ]]; then
    return 0
  fi
  local ref url
  for ref in $SLACK_RAW_REFS; do
    url="${SLACK_RAW_BASE}/${ref}/scripts/standalone_startup_catchup.py"
    if curl -fsSL "$url" -o "$TRIGGER" 2>/dev/null; then
      echo "[evening] fetched trigger_cardnews.py (ref=${ref})"
      return 0
    fi
  done
  echo "[fail] could not fetch standalone_startup_catchup.py" >&2
  return 1
}

N8N_HEALTH_URL="${N8N_HEALTH_URL:-http://127.0.0.1:5678/healthz}"
if curl -fsS --connect-timeout 2 "${N8N_HEALTH_URL}" >/dev/null 2>&1; then
  echo "[evening] local n8n detected at ${N8N_HEALTH_URL}"
  export N8N_USE_LOCAL="${N8N_USE_LOCAL:-true}"
fi

if [[ -z "${N8N_WEBHOOK_URL:-}" && -z "${N8N_CARD_NEWS_WEBHOOK_URL:-}" && "${N8N_USE_LOCAL:-}" != "true" ]]; then
  echo "[fail] set N8N_WEBHOOK_URL or run on a VM with local n8n (127.0.0.1:5678)" >&2
  exit 1
fi

_ensure_trigger
chmod +x "$TRIGGER"

echo "[evening] triggering daily (18:00 KST topic batch) via n8n"
# shellcheck disable=SC2086
exec python3 "$TRIGGER" evening ${FORCE:+$FORCE} "${EXTRA[@]}"
