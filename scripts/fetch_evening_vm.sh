#!/usr/bin/env bash
# VM 홈에 저녁 뉴스 복구 스크립트 설치 후 실행
#
#   curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/main/scripts/fetch_evening_vm.sh" | bash -s -- --no-wait
#
# MCP-Auto가 ~/MCP-Auto 에 있으면 repo 스크립트를 우선 사용합니다.
set -euo pipefail

HOME_SCRIPT="${HOME}/sync_topic_news_evening_vm.sh"
MCP_SCRIPT="${HOME}/MCP-Auto/EXE/sync_topic_news_evening_vm.sh"
SLACK_RAW_BASE="${SLACK_RAW_BASE:-https://raw.githubusercontent.com/MCP-AI-Acount/Slack/main/scripts}"

if [[ -f "$MCP_SCRIPT" ]]; then
  exec bash "$MCP_SCRIPT" "$@"
fi

if [[ -f "$HOME_SCRIPT" ]]; then
  exec bash "$HOME_SCRIPT" "$@"
fi

echo ">>> downloading ${HOME_SCRIPT} (Slack public repo)"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "${SLACK_RAW_BASE}/sync_topic_news_evening_vm.sh" -o "${HOME_SCRIPT}"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "${HOME_SCRIPT}" "${SLACK_RAW_BASE}/sync_topic_news_evening_vm.sh"
else
  echo "[fail] curl or wget required" >&2
  exit 1
fi
chmod +x "${HOME_SCRIPT}"
exec bash "${HOME_SCRIPT}" "$@"
