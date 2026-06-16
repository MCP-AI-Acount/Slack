#!/usr/bin/env bash
# VM 홈에 저녁 뉴스 복구 스크립트 설치 후 실행
#
#   curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/main/scripts/fetch_evening_vm.sh" | bash -s -- --no-wait
#
# MCP-Auto가 ~/MCP-Auto 에 있으면 repo 스크립트를 우선 사용합니다.
# 없으면 Slack standalone 배치(n8n daily 트리거)로 폴백합니다.
set -euo pipefail

HOME_SCRIPT="${HOME}/sync_topic_news_evening_vm.sh"
MCP_SCRIPT="${HOME}/MCP-Auto/EXE/sync_topic_news_evening_vm.sh"
SLACK_RAW_BASE="${SLACK_RAW_BASE:-https://raw.githubusercontent.com/MCP-AI-Acount/Slack}"
SLACK_RAW_REFS="${SLACK_RAW_REFS:-main master}"

_download_script() {
  local dest="$1"
  local name="$2"
  local ref url
  for ref in $SLACK_RAW_REFS; do
    url="${SLACK_RAW_BASE}/${ref}/scripts/${name}"
    if curl -fsSL "$url" -o "$dest" 2>/dev/null; then
      echo ">>> fetched ${name} (ref=${ref})"
      return 0
    fi
  done
  echo "[fail] could not download ${name} (tried refs: ${SLACK_RAW_REFS})" >&2
  echo "  MCP-Auto raw URLs are private (404). Use Slack refs above." >&2
  return 1
}

if [[ -f "$MCP_SCRIPT" ]]; then
  exec bash "$MCP_SCRIPT" "$@"
fi

if [[ -f "$HOME_SCRIPT" ]]; then
  exec bash "$HOME_SCRIPT" "$@"
fi

echo ">>> downloading ${HOME_SCRIPT} (Slack public repo)"
_download_script "${HOME_SCRIPT}" "sync_topic_news_evening_vm.sh"
chmod +x "${HOME_SCRIPT}"
exec bash "${HOME_SCRIPT}" "$@"
