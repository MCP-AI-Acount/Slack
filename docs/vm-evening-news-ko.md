# 저녁 토픽 뉴스 안 올라왔을 때 (Mac 슬립 · VM 복구)

## 원인 (2026-06-16 기준)

| 구간 | 상태 |
|------|------|
| **Mac n8n** | `wf_topic_evening` Schedule **17:40 KST** — 맥 슬립 시 cron 미실행 |
| **VM `mcp-auto-worker`** | Cloud Scheduler **17:30** 기동 예정이나, n8n·브릿지(`:8798`) 미응답 시 17:40 배치도 실패 |
| **저녁 콘텐츠** | 기술·문화·건강 3장 → **18:00 KST** 일괄 SNS 게시 (`topic_news_evening_batch.py`) |

맥에서 `sync_local_daily.sh` 로 돌리는 n8n은 **VM이 아니라 로컬**입니다. 슬립 = 저녁 뉴스 누락.

## VM 홈에서 즉시 올리기 (권장)

`mcp-auto-worker` SSH 접속 후 **홈(`~`)에서**:

```bash
bash ~/sync_topic_news_evening_vm.sh --no-wait
```

처음 한 번만 스크립트가 없으면:

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/MCP-Auto/main/EXE/sync_topic_news_evening_vm.sh" \
  -o ~/sync_topic_news_evening_vm.sh && chmod +x ~/sync_topic_news_evening_vm.sh
bash ~/sync_topic_news_evening_vm.sh --no-wait
```

또는 MCP-Auto repo 경로:

```bash
cd ~/MCP-Auto && git pull
bash EXE/sync_topic_news_evening_vm.sh --no-wait
```

- `--no-wait`: 18시 이후면 대기 없이 바로 게시
- `--dry-run`: SNS 게시 없이 생성만

동작: `vm_boot_services` → `run_topic_news_evening_batch.sh` (VM에서는 gcloud 불필요)

## Mac에서 VM으로 원격 실행

```bash
cd ~/Documents/MCP-Auto && git pull
bash EXE/sync_topic_news_evening_vm.sh --no-wait
```

## n8n 수동 테스트 (VM Docker n8n 살아 있을 때)

```bash
curl -sf -X POST http://127.0.0.1:8798/v1/run \
  -H 'Content-Type: application/json' \
  -d '{"batch":true,"topics":["tech","culture","health"],"publish_hour":18,"publish_minute":0}'
```

## 맥 슬립 방지 (운영)

1. **저녁은 VM만** — `setup_vm_scheduler.sh` 의 17:30 start + VM n8n `wf_topic_evening`
2. 맥 `sync_local_daily` 의 evening 스케줄 **비활성** 또는 Mac에서 n8n 미사용
3. VM 부팅 시 `vm_boot_services.sh` 가 `~/sync_topic_news_evening_vm.sh` 심볼릭 링크 생성

## 관련

- `MCP-Auto/EXE/run_topic_news_evening_batch.sh`
- `MCP-Auto/EXE/sync_topic_news_evening_vm.sh` — VM 홈·Mac 양쪽 지원
- `scripts/fetch_evening_vm.sh` — VM 홈 설치 헬퍼
