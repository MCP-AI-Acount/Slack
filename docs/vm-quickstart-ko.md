# VM 빠른 실행 (폴더 없음 에러 해결)

`~/Slack` 이나 `scripts/sync_n8n.py` 가 **없으면** "그 디렉토리에서 파일을 찾을 수 없음" 이 납니다.  
**git clone 없이** 아래만 쓰세요.

---

## DNS 에러 (`Temporary failure in name resolution`)

`N8N_WEBHOOK_URL` 이 **외부 도메인**(https://something.example.com/...) 이면 VM DNS가 안 될 때 이 에러가 납니다.

**n8n이 같은 VM(mcp-auto-worker)에서 돌면 localhost 쓰세요:**

```bash
# n8n Webhook 노드 Production URL의 path 확인 (예: slack-command)
export N8N_WEBHOOK_URL="http://127.0.0.1:5678/webhook/slack-command"
python3 ~/trigger_cardnews.py trigger
```

또는:

```bash
export N8N_USE_LOCAL=true
export N8N_WEBHOOK_PATH=slack-command
python3 ~/trigger_cardnews.py trigger
```

n8n 살아 있는지:

```bash
curl -s http://127.0.0.1:5678/healthz
```

스크립트 v2.1+ 는 DNS 실패 시 **자동으로 localhost 재시도**합니다.  
`/home/GCP/trigger_cardnews.py` 를 **다시 받으세요**:

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/cursor/vm-downtime-catchup-1c89/scripts/standalone_startup_catchup.py" -o ~/trigger_cardnews.py
```

---

## 1. 한 줄 (권장)

VM 터미널 — **어느 디렉토리에서든**:

```bash
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/cursor/card-schedule-afternoon-fix-73c1/scripts/fetch_and_run.sh" | bash
```

- 파일 위치: `~/.local/bin/trigger_cardnews.py` (자동 다운로드)
- 기사+정규일정+경제 (금요일 등엔 월요일주간 제외, 일기예보 제외)
- **같은 VM에 n8n이 있으면** `N8N_WEBHOOK_URL` 없이도 localhost 자동 감지

### 오후 정규일정만 안 올라갔을 때 (14시 KST 이후)

```bash
curl -fsSL "https://raw.githubusercontent.com/MCP-AI-Acount/Slack/cursor/card-schedule-afternoon-fix-73c1/scripts/fetch_and_run.sh" | bash -s afternoon
```

또는 repo가 있을 때:

```bash
python3 ~/Slack/scripts/sync_n8n.py afternoon
```

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
| `Temporary failure in name resolution` | 외부 URL + VM DNS 없음 | `N8N_WEBHOOK_URL=http://127.0.0.1:5678/webhook/slack-command` |
