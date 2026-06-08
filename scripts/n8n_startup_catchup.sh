#!/usr/bin/env bash
# Auto-run missed card-news schedules after n8n starts.
# Wire into New-MCP-Unity EXE/start_n8n.sh:
#   bash EXE/start_n8n.sh &
#   bash /path/to/Slack/scripts/n8n_startup_catchup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS="${AGENT_SECRETS_FILE:-/home/ubuntu/.config/agent-secrets.env}"

if [[ -f "${SECRETS}" ]]; then
  # shellcheck disable=SC1090
  source "${SECRETS}"
fi

exec python3 "${ROOT}/scripts/sync_n8n.py" startup "$@"
