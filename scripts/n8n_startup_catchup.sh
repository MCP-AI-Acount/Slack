#!/usr/bin/env bash
# Auto-run missed card-news schedules after n8n starts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SECRETS="${AGENT_SECRETS_FILE:-${HOME}/.config/agent-secrets.env}"

if [[ -f "${SECRETS}" ]]; then
  # shellcheck disable=SC1090
  source "${SECRETS}"
fi

if [[ -f "${REPO_ROOT}/scripts/sync_n8n.py" && -f "${REPO_ROOT}/common/slack_n8n_gateway.py" ]]; then
  exec python3 "${REPO_ROOT}/scripts/sync_n8n.py" startup "$@"
fi

if [[ -f "${SCRIPT_DIR}/standalone_startup_catchup.py" ]]; then
  exec python3 "${SCRIPT_DIR}/standalone_startup_catchup.py" "$@"
fi

cat >&2 <<EOF
ERROR: Slack startup scripts not found in ${SCRIPT_DIR}.

Install on this VM:
  bash scripts/install_on_vm.sh
  # or clone manually:
  git clone -b cursor/vm-downtime-catchup-1c89 https://github.com/MCP-AI-Acount/Slack.git ~/Slack

Single-file option (copy standalone_startup_catchup.py anywhere):
  export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
  python3 ~/standalone_startup_catchup.py
EOF
exit 1
