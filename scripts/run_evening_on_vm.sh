#!/usr/bin/env bash
# VM에서 저녁 배치만 즉시 (MCP-Auto 없어도 Slack standalone 사용)
set -euo pipefail

_BIN="$(cd "$(dirname "$0")" && pwd)"
ENVF="${ENVF:-$HOME/n8n-secrets.env}"
[[ -f "$ENVF" ]] && { set -a; source "$ENVF"; set +a; }

for root in "${VM_MCP_AUTO_ROOT:-}" "$HOME/MCP-Auto" "$HOME/Documents/MCP-Auto" "$_BIN"; do
  [[ -z "$root" ]] && continue
  root="${root/#\~/$HOME}"
  for batch in "$root/EXE/run_topic_news_evening_batch.sh" "$root/run_topic_news_evening_batch.sh"; do
    if [[ -f "$batch" ]]; then
      boot="$root/EXE/vm_boot_services.sh"
      [[ -f "$boot" ]] && DAILY_OPS_RESET_ON_BOOT=0 bash "$boot" || true
      exec bash "$batch" "$@"
    fi
  done
done

standalone="${HOME}/.local/bin/run_topic_news_evening_batch.sh"
if [[ -f "$standalone" ]]; then
  exec bash "$standalone" "$@"
fi

echo "[fail] evening batch script not found" >&2
echo "  curl -fsSL https://raw.githubusercontent.com/MCP-AI-Acount/Slack/master/scripts/fetch_evening_vm.sh | bash -s -- --no-wait" >&2
exit 1
