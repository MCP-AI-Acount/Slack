# VM 빠른 실행 (폴더 없음 에러 해결)

`~/Slack` 이나 `scripts/sync_n8n.py` 가 **없으면** "그 디렉토리에서 파일을 찾을 수 없음" 이 납니다.  
**git clone 없이** 아래만 쓰세요.

---

## 1. 한 줄 (권장)

VM 터미널 — **어느 디렉토리에서든**:

```bash
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/cursor/vm-downtime-catchup-1c89/scripts/fetch_and_run.sh" | bash
```

- 파일 위치: `~/.local/bin/trigger_cardnews.py` (자동 다운로드)
- 기사+정규일정+경제+월요일주간만 (일기예보 제외)

---

## 2. 파일 하나만 수동 복사

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/cursor/vm-downtime-catchup-1c89/scripts/standalone_startup_catchup.py" -o ~/trigger_cardnews.py
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
python3 ~/trigger_cardnews.py trigger
```

`~/trigger_cardnews.py` — **홈에 파일 하나**면 끝. `~/Slack` 필요 없음.

---

## 3. repo 쓰고 싶을 때만

```bash
git clone -b cursor/vm-downtime-catchup-1c89 https://github.com/MCP-AI-Acount/Slack.git ~/Slack
ls ~/Slack/scripts/sync_n8n.py   # 이게 보여야 함
export N8N_WEBHOOK_URL="..."
python3 ~/Slack/scripts/sync_n8n.py trigger --only news,regular,monday_weekly,economy
```

`ls ~/Slack` 했을 때 **No such file** 이면 clone 안 된 것.

---

## 4. 그래도 Slack에 안 올라가면

스크립트는 **n8n webhook에 요청만** 보냅니다.  
일기예보는 되는데 기사/일정만 안 되면 → **n8n 워크플로** 문제.

→ `docs/n8n-run-schedule-workflow.md`  
→ n8n UI **Executions** 에서 news/regular 워크플로 에러 확인

---

## 자주 나는 에러

| 메시지 | 원인 | 해결 |
|--------|------|------|
| `No such file ... ~/Slack/scripts/...` | repo 미설치 | 위 **1번** 또는 **2번** |
| `N8N_WEBHOOK_URL is required` | URL 미설정 | `export N8N_WEBHOOK_URL=...` |
| HTTP 200인데 Slack 비어 있음 | n8n 분기 없음 | n8n `run_schedule` Switch 추가 |
