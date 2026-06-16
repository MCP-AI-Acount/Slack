# 저녁 토픽 뉴스 안 올라왔을 때 (Mac 슬립 · VM 복구)

## 원인 (2026-06-16 기준)

| 구간 | 상태 |
|------|------|
| **Mac n8n** | `wf_topic_evening` Schedule **17:40 KST** — 맥 슬립 시 cron 미실행 |
| **VM `mcp-auto-worker`** | Cloud Scheduler **17:30** 기동 예정이나, n8n·브릿지(`:8798`) 미응답 시 17:40 배치도 실패 |
| **저녁 콘텐츠** | 기술·문화·건강 3장 → **18:00 KST** 일괄 SNS 게시 (`topic_news_evening_batch.py`) |

맥에서 `sync_local_daily.sh` 로 돌리는 n8n은 **VM이 아니라 로컬**입니다. 슬립 = 저녁 뉴스 누락.

## VM에서 즉시 올리기 (권장)

**gcloud 로그인된 Mac 또는 Cloud Agent**에서:

```bash
cd ~/Documents/MCP-Auto   # clone 경로
bash EXE/sync_topic_news_evening_vm.sh --no-wait
```

- `--no-wait`: 18시 이후면 대기 없이 바로 게시
- `--dry-run`: SNS 게시 없이 생성만

동작: VM start → `vm_boot_services` → `run_topic_news_evening_batch.sh`

## VM 안에서 직접

```bash
DAILY_OPS_RESET_ON_BOOT=0 bash ~/MCP-Auto/EXE/vm_boot_services.sh
bash ~/MCP-Auto/EXE/run_topic_news_evening_batch.sh --no-wait
```

## n8n 수동 테스트 (VM Docker n8n 살아 있을 때)

topic bridge:

```bash
curl -sf -X POST http://127.0.0.1:8798/v1/run \
  -H 'Content-Type: application/json' \
  -d '{"batch":true,"topics":["tech","culture","health"],"publish_hour":18,"publish_minute":0}'
```

## 맥 슬립 방지 (운영)

1. **저녁은 VM만** — `setup_vm_scheduler.sh` 의 17:30 start + VM n8n `wf_topic_evening`
2. 맥 `sync_local_daily` 의 evening 스케줄 **비활성** 또는 Mac에서 n8n 미사용
3. VM 기동 후 `vm_boot_services.sh` 가 cron/startup-script에 연결돼 있는지 확인

## 관련

- `MCP-Auto/EXE/run_topic_news_evening_batch.sh`
- `MCP-Auto/EXE/sync_topic_news_evening_vm.sh` (Cloud Agent·Mac → VM SSH)
- `.cursor/commands/topic-evening.md`
