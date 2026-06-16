#!/usr/bin/env bash
# VM에서 저녁 배치만 즉시 (MCP-Auto repo만 있으면 됨, curl 불필요)
set -euo pipefail

ENVF="${ENVF:-$HOME/n8n-secrets.env}"
[[ -f "$ENVF" ]] && { set -a; source "$ENVF"; set +a; }

for root in "${VM_MCP_AUTO_ROOT:-}" "$HOME/MCP-Auto" "$HOME/Documents/MCP-Auto"; do
  [[ -z "$root" ]] && continue
  root="${root/#\~/$HOME}"
  batch="$root/EXE/run_topic_news_evening_batch.sh"
  boot="$root/EXE/vm_boot_services.sh"
  if [[ -f "$batch" ]]; then
    [[ -f "$boot" ]] && DAILY_OPS_RESET_ON_BOOT=0 bash "$boot" || true
    exec bash "$batch" "$@"
  fi
done

echo "[fail] ~/MCP-Auto/EXE/run_topic_news_evening_batch.sh not found" >&2
echo "  Or install: curl -fsSL https://raw.githubusercontent.com/MCP-AI-Acount/Slack/master/scripts/fetch_evening_vm.sh | bash -s -- --no-wait" >&2
exit 1
