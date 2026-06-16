#!/usr/bin/env bash
# VM 홈에 저녁 뉴스 복구 스크립트 설치 (MCP-Auto clone 없이도 동작)
#
#   curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/MCP-Auto/main/EXE/sync_topic_news_evening_vm.sh" \
#     -o ~/sync_topic_news_evening_vm.sh && chmod +x ~/sync_topic_news_evening_vm.sh
#   bash ~/sync_topic_news_evening_vm.sh --no-wait
#
# repo가 ~/MCP-Auto 에 있으면 EXE 버전을 우선 사용합니다.
set -euo pipefail

RAW_BASE="${MCP_AUTO_RAW_BASE:-https://raw.githubusercontent.com/MCP-AI-Acount/MCP-Auto/main/EXE}"
HOME_SCRIPT="${HOME}/sync_topic_news_evening_vm.sh"
MCP_SCRIPT="${HOME}/MCP-Auto/EXE/sync_topic_news_evening_vm.sh"

if [[ -f "$MCP_SCRIPT" ]]; then
  exec bash "$MCP_SCRIPT" "$@"
fi

echo ">>> installing ${HOME_SCRIPT}"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "${RAW_BASE}/sync_topic_news_evening_vm.sh" -o "${HOME_SCRIPT}"
else
  wget -qO "${HOME_SCRIPT}" "${RAW_BASE}/sync_topic_news_evening_vm.sh"
fi
chmod +x "${HOME_SCRIPT}"
exec bash "${HOME_SCRIPT}" "$@"
