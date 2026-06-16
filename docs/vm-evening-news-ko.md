# 저녁 토픽 뉴스 안 올라왔을 때 (Mac 슬립 · VM 복구)

## 404 나올 때

| URL | 결과 |
|-----|------|
| `raw.githubusercontent.com/.../MCP-Auto/...` | **404** (private repo) |
| `.../Slack/main/...` | 일부 환경에서 **404** |
| `.../Slack/master/...` | **200** (public, 사용 권장) |

## VM에서 즉시 올리기

### A. MCP-Auto 이미 있음 (curl 없이, 가장 빠름)

```bash
bash ~/MCP-Auto/EXE/run_topic_news_evening_batch.sh --no-wait
```

### B. Slack public 스크립트 (curl)

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/master/scripts/fetch_evening_vm.sh" | bash -s -- --no-wait
```

### C. 한 줄 직접 실행

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/master/scripts/run_evening_on_vm.sh" | bash -s -- --no-wait
```

## Mac에서 VM 원격 실행

```bash
cd ~/Documents/MCP-Auto && git pull
bash EXE/sync_topic_news_evening_vm.sh --no-wait
```
