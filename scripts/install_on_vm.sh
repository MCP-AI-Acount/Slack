#!/usr/bin/env bash
# Install or update the Slack repo on the harness VM.
set -euo pipefail

SLACK_REPO_ROOT="${SLACK_REPO_ROOT:-${HOME}/Slack}"
SLACK_REPO_URL="${SLACK_REPO_URL:-https://github.com/MCP-AI-Acount/Slack.git}"
SLACK_REPO_BRANCH="${SLACK_REPO_BRANCH:-cursor/vm-downtime-catchup-1c89}"
SECRETS="${AGENT_SECRETS_FILE:-${HOME}/.config/agent-secrets.env}"

if [[ -d "${SLACK_REPO_ROOT}/.git" ]]; then
  echo "Updating ${SLACK_REPO_ROOT} ..."
  git -C "${SLACK_REPO_ROOT}" fetch origin
  git -C "${SLACK_REPO_ROOT}" checkout "${SLACK_REPO_BRANCH}"
  git -C "${SLACK_REPO_ROOT}" pull --ff-only origin "${SLACK_REPO_BRANCH}"
else
  echo "Cloning into ${SLACK_REPO_ROOT} ..."
  git clone -b "${SLACK_REPO_BRANCH}" "${SLACK_REPO_URL}" "${SLACK_REPO_ROOT}"
fi

chmod +x "${SLACK_REPO_ROOT}/scripts/n8n_startup_catchup.sh" 2>/dev/null || true
chmod +x "${SLACK_REPO_ROOT}/scripts/standalone_startup_catchup.py" 2>/dev/null || true

cat <<EOF

Installed at: ${SLACK_REPO_ROOT}

Run once (needs N8N_WEBHOOK_URL):
  export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
  bash ${SLACK_REPO_ROOT}/scripts/n8n_startup_catchup.sh

Or copy only one file (no git repo needed):
  python3 ${SLACK_REPO_ROOT}/scripts/standalone_startup_catchup.py

Add to EXE/start_n8n.sh:
  bash ${SLACK_REPO_ROOT}/scripts/n8n_startup_catchup.sh &

Secrets file (optional): ${SECRETS}
EOF
