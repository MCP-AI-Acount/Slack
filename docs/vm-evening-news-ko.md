# 저녁 토픽 뉴스 안 올라왔을 때 (Mac 슬립 · VM 복구)

## 404 나올 때

`MCP-Auto`는 **private** repo라 `raw.githubusercontent.com/MCP-AI-Acount/MCP-Auto/...` 는 **404** 입니다.  
아래 **Slack(public)** URL 또는 `~/MCP-Auto` 직접 실행을 쓰세요.

## VM에서 즉시 올리기

### A. MCP-Auto 이미 있음 (curl 없이, 가장 빠름)

```bash
bash ~/MCP-Auto/EXE/run_topic_news_evening_batch.sh --no-wait
```

브릿지까지 올리려면:

```bash
DAILY_OPS_RESET_ON_BOOT=0 bash ~/MCP-Auto/EXE/vm_boot_services.sh
bash ~/MCP-Auto/EXE/run_topic_news_evening_batch.sh --no-wait
```

### B. Slack public 스크립트 설치

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/main/scripts/fetch_evening_vm.sh" | bash -s -- --no-wait
```

설치 후:

```bash
bash ~/sync_topic_news_evening_vm.sh --no-wait
```

### C. 한 줄 직접 실행 (repo만 있으면)

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/main/scripts/run_evening_on_vm.sh" | bash -s -- --no-wait
```

## Mac에서 VM 원격 실행

```bash
cd ~/Documents/MCP-Auto && git pull
bash EXE/sync_topic_news_evening_vm.sh --no-wait
```

## 원인 요약

| 구간 | 설명 |
|------|------|
| Mac n8n | 17:40 KST 스케줄 — 맥 슬립 시 미실행 |
| VM | 기술·문화·건강 3장 → 18:00 KST 게시 |

## 관련 파일

- `scripts/fetch_evening_vm.sh` — VM 홈 설치 (public)
- `scripts/sync_topic_news_evening_vm.sh` — 동기화 래퍼 (public)
- `scripts/run_evening_on_vm.sh` — 최소 실행기 (public)
- `MCP-Auto/EXE/run_topic_news_evening_batch.sh` — 실제 배치 (private repo)
