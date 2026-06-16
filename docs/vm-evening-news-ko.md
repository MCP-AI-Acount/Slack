# 저녁 토픽 뉴스 안 올라왔을 때 (Mac 슬립 · VM 복구)

## 404 나올 때

| URL | 결과 |
|-----|------|
| `raw.githubusercontent.com/.../MCP-Auto/...` | **404** (private repo) |
| `.../Slack/main/...` | 일부 환경에서 **404** |
| `.../Slack/master/...` | **200** (public, 사용 권장) |

## VM에서 즉시 올리기

**MCP-Auto(`~/MCP-Auto`) 없어도 됩니다.** Slack public 스크립트가 n8n `daily` 슬롯을 트리거합니다.

### A. 한 줄 (권장 — curl만)

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/master/scripts/fetch_evening_vm.sh" | bash -s -- --no-wait
```

### B. 이미 받아 둔 홈 스크립트

```bash
bash ~/sync_topic_news_evening_vm.sh --no-wait
```

### C. MCP-Auto가 VM에 있을 때만 (curl 없이)

```bash
bash ~/MCP-Auto/EXE/run_topic_news_evening_batch.sh --no-wait
```

### D. 한 줄 직접 실행

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/master/scripts/run_evening_on_vm.sh" | bash -s -- --no-wait
```

`--no-wait` 없이 실행하면 18:00 KST 전에는 게시 시각까지 대기합니다.

## Mac에서 VM 원격 실행

```bash
cd ~/Documents/MCP-Auto && git pull
bash EXE/sync_topic_news_evening_vm.sh --no-wait
```

## 그래도 안 올라가면

1. n8n 살아 있는지: `curl -s http://127.0.0.1:5678/healthz`
2. Webhook에 `action=run_schedule` + `schedule=daily` 분기 있는지 → `docs/n8n-run-schedule-workflow.md`
3. n8n **Executions** 에서 evening/daily 워크플로 에러 확인
