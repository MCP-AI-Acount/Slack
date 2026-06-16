#!/usr/bin/env bash
# 저녁 토픽 뉴스(기술·문화·건강) 수동 복구 — Mac/Cloud Agent → VM SSH 또는 VM 홈에서 직접
#
# VM 홈에서 (권장):
#   bash ~/sync_topic_news_evening_vm.sh --no-wait
#   bash ~/MCP-Auto/EXE/sync_topic_news_evening_vm.sh --no-wait
#
# Mac (gcloud):
#   cd ~/Documents/MCP-Auto && bash EXE/sync_topic_news_evening_vm.sh --no-wait
set -euo pipefail

_BIN="$(cd "$(dirname "$0")" && pwd)"
_AUTO_ROOT=""
if [[ -f "$_BIN/../EXE/run_topic_news_evening_batch.sh" ]]; then
  _AUTO_ROOT="$(cd "$_BIN/.." && pwd)"
fi
AGENT_SECRETS="${AGENT_SECRETS:-$HOME/.config/agent-secrets.env}"
ENVF="${ENVF:-$HOME/n8n-secrets.env}"
EXTRA_ARGS=("$@")

for f in "$AGENT_SECRETS" "$ENVF"; do
  if [[ -f "$f" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
  fi
done

_resolve_mcp_auto_root() {
  local candidate
  for candidate in "${VM_MCP_AUTO_ROOT:-}" "$_AUTO_ROOT" "$HOME/MCP-Auto" "$HOME/Documents/MCP-Auto"; do
    [[ -z "$candidate" ]] && continue
    candidate="${candidate/#\~/$HOME}"
    if [[ -f "$candidate/EXE/run_topic_news_evening_batch.sh" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

_on_gcp_vm() {
  if curl -sf -m 2 -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/name >/dev/null 2>&1; then
    return 0
  fi
  local host
  host="$(hostname -s 2>/dev/null || hostname 2>/dev/null || true)"
  [[ "$host" == *mcp-auto* ]]
}

_ensure_home_shortcut() {
  local script_path="$1"
  local link="$HOME/sync_topic_news_evening_vm.sh"
  if [[ "$script_path" != "$link" && ! -L "$link" ]]; then
    ln -sf "$script_path" "$link"
    echo "[sync-evening] installed shortcut → $link"
  fi
}

_evening_wait_flag() {
  local flag="--no-wait"
  local kst_hour
  kst_hour="$(TZ=Asia/Seoul date '+%H')"
  if [[ "$kst_hour" -lt 18 ]]; then
    flag=""
    echo "[info] before 18:00 KST — batch waits until publish time unless you pass --no-wait"
  fi
  local arg
  for arg in "${EXTRA_ARGS[@]}"; do
    [[ "$arg" == "--no-wait" ]] && flag="--no-wait"
    [[ "$arg" == "--wait" ]] && flag=""
  done
  printf '%s' "$flag"
}

_run_evening_on_vm() {
  local auto_root="$1"
  local wait_flag="$2"
  echo "[sync-evening] on-vm auto_root=${auto_root} (${wait_flag:-wait-until-18:00})"
  _ensure_home_shortcut "$auto_root/EXE/sync_topic_news_evening_vm.sh"
  if [[ -f "$auto_root/EXE/vm_boot_services.sh" ]]; then
    DAILY_OPS_RESET_ON_BOOT=0 bash "$auto_root/EXE/vm_boot_services.sh" || true
  fi
  # shellcheck disable=SC2086
  bash "$auto_root/EXE/run_topic_news_evening_batch.sh" $wait_flag "${EXTRA_ARGS[@]}"
}

_run_evening_via_gcloud() {
  local auto_root="$1"
  local wait_flag="$2"
  # shellcheck disable=SC1091
  source "$_BIN/gcp_project_env.sh"

  ZONE="${ZONE:-asia-northeast3-a}"
  VM_NAME="${VM_NAME:-mcp-auto-worker}"
  VM_REPO="${VM_MCP_AUTO_ROOT:-~/MCP-Auto}"

  if ! command -v gcloud >/dev/null 2>&1; then
    echo "[fail] gcloud required off-VM (Mac: brew install google-cloud-sdk)" >&2
    exit 1
  fi

  echo "[sync-evening] remote VM=${VM_NAME} zone=${ZONE} project=${PROJECT_ID} (${wait_flag:-wait})"
  bash "$_BIN/vm_start.sh" || true

  local remote_cmd="set -euo pipefail
export ENVF=~/n8n-secrets.env
if [[ -f ~/n8n-secrets.env ]]; then set -a; source ~/n8n-secrets.env; set +a; fi
bash ${VM_REPO}/EXE/sync_topic_news_evening_vm.sh ${wait_flag}"
  if ((${#EXTRA_ARGS[@]})); then
    remote_cmd+=" $(printf '%q ' "${EXTRA_ARGS[@]}")"
  fi

  gcloud compute ssh "$VM_NAME" --zone "$ZONE" --project "$PROJECT_ID" --command="${remote_cmd}"
}

AUTO_ROOT="$(_resolve_mcp_auto_root || true)"
WAIT_FLAG="$(_evening_wait_flag)"

if [[ -z "$AUTO_ROOT" ]]; then
  echo "[fail] MCP-Auto not found — expected ~/MCP-Auto/EXE/run_topic_news_evening_batch.sh" >&2
  echo "  curl -fsSL https://raw.githubusercontent.com/MCP-AI-Acount/Slack/main/scripts/fetch_evening_vm.sh | bash -s -- --no-wait" >&2
  exit 1
fi

if _on_gcp_vm; then
  _run_evening_on_vm "$AUTO_ROOT" "$WAIT_FLAG"
elif command -v gcloud >/dev/null 2>&1; then
  _run_evening_via_gcloud "$AUTO_ROOT" "$WAIT_FLAG"
else
  _run_evening_on_vm "$AUTO_ROOT" "$WAIT_FLAG"
fi

echo "[sync-evening] done"
