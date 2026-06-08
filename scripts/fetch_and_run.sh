#!/usr/bin/env bash
# VM 한 줄 설치 — ~/Slack 폴더 없어도 됨. 어디서든 실행 가능.
#
#   export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
#   curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/cursor/vm-downtime-catchup-1c89/scripts/fetch_and_run.sh" | bash
#
# 기사+일정만 (일기예보 제외, 기본):
#   curl -fsSL ".../fetch_and_run.sh" | bash
#
# 진단:
#   curl -fsSL ".../fetch_and_run.sh" | bash -s diagnose
set -euo pipefail

RAW_BASE="${SLACK_RAW_BASE:-https://raw.githubusercontent.com/MCP-AI-Acount/Slack/cursor/vm-downtime-catchup-1c89/scripts}"
INSTALL_DIR="${CARDNEWS_BIN_DIR:-${HOME}/.local/bin}"
SCRIPT="${INSTALL_DIR}/trigger_cardnews.py"
MODE="${1:-trigger}"

mkdir -p "${INSTALL_DIR}"

echo ">>> downloading trigger_cardnews.py to ${SCRIPT}"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "${RAW_BASE}/standalone_startup_catchup.py" -o "${SCRIPT}"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "${SCRIPT}" "${RAW_BASE}/standalone_startup_catchup.py"
else
  echo "ERROR: curl or wget required" >&2
  exit 1
fi
if [[ ! -f "${SCRIPT}" ]]; then
  echo "ERROR: download failed — check network or branch name" >&2
  exit 1
fi
chmod +x "${SCRIPT}"

if [[ -z "${N8N_WEBHOOK_URL:-}" && -z "${N8N_CARD_NEWS_WEBHOOK_URL:-}" ]]; then
  if [[ -f "${HOME}/.config/agent-secrets.env" ]]; then
    # shellcheck disable=SC1090
    source "${HOME}/.config/agent-secrets.env"
  fi
fi

if [[ -z "${N8N_WEBHOOK_URL:-}" && -z "${N8N_CARD_NEWS_WEBHOOK_URL:-}" ]]; then
  echo "ERROR: set N8N_WEBHOOK_URL first, e.g.:" >&2
  echo '  export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."' >&2
  exit 1
fi

echo ">>> running: python3 ${SCRIPT} ${MODE}"
exec python3 "${SCRIPT}" "${MODE}" "${@:2}"
