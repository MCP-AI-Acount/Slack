# VM 다운타임 후 카드뉴스 복구

## 날씨만 올라가고 나머지는 안 올라갈 때

VM·n8n이 **완전히 죽은 게 아닐 수 있습니다.** `#자동화_날씨7경제5` 채널명처럼 날씨·경제·뉴스는 **n8n 워크플로가 분리**돼 있는 경우가 많습니다.

| 증상 | 가능 원인 |
|------|-----------|
| 날씨만 올라감 | `weather` 워크플로만 정상, `economy`/`news`/`monday_weekly` 워크플로 실패·비활성·cron 불일치 |
| VM 꺼짐 직후 일부만 올라감 | VM 기동 시점에 맞은 cron만 실행, 이전 슬롯은 catch-up 없음 |
| 수동 catchup 필요 | n8n startup hook 미연결, `card_news_catchup` 분기 없음 |

**해결:** n8n 기동 후 **자동 catchup**을 붙이면, 이미 올라간 날씨는 `skip_already_posted`로 건너뛰고 경제·뉴스·정규일정만 올립니다.

## 일기예보는 되는데 기사·일정만 안 될 때

**VM 스크립트 문제가 아닙니다.** webhook이 200을 돌려줘도 n8n에 **`run_schedule` / `catchup` 분기가 없으면** Slack에 아무 것도 안 올라갑니다.

| 증상 | 원인 |
|------|------|
| 일기예보 ✓ | `weather` Schedule Trigger 워크플로 — **별도로 정상** |
| 기사 ✗ | `news` 워크플로 — 실패·비활성·cron 놓침 |
| 정규일정 ✗ | `regular` / `monday_weekly` 워크플로 — 동일 |

### VM에서 (기사+일정만, 날씨 제외)

```bash
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
python3 ~/Slack/scripts/sync_n8n.py trigger --only news,regular,monday_weekly,economy
python3 ~/Slack/scripts/sync_n8n.py diagnose
```

### n8n에서 고칠 것

Webhook 뒤 Switch에 `action === "run_schedule"` 추가 → `$json.schedule`별 워크플로 Execute.

**상세:** `docs/n8n-run-schedule-workflow.md`

---

## VM에 폴더 없음 / `scripts/sync_n8n.py` 없음

명령만 복사해서 VM **홈 디렉터리**에서 실행하면 `scripts/` 폴더가 없어 에러가 납니다. 아래 **셋 중 하나**를 쓰세요.

### A. 설치 스크립트 (권장)

VM에서 한 번:

```bash
git clone -b cursor/vm-downtime-catchup-1c89 https://github.com/MCP-AI-Acount/Slack.git ~/Slack
bash ~/Slack/scripts/install_on_vm.sh
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
bash ~/Slack/scripts/n8n_startup_catchup.sh
```

### B. 파일 하나만 (git 없이)

`scripts/standalone_startup_catchup.py` **한 파일**만 VM에 복사:

```bash
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
python3 ~/standalone_startup_catchup.py
```

### C. repo 전체가 있는 경우

```bash
cd ~/Slack   # clone한 경로
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
python3 scripts/sync_n8n.py startup
```

## 자동으로 올리게 하기 (권장)

`EXE/start_n8n.sh` 끝에 아래 한 줄을 추가합니다 (`~/Slack`은 clone 경로).

```bash
bash ~/Slack/scripts/n8n_startup_catchup.sh &
```

또는 standalone 파일만 쓸 때:

```bash
python3 ~/standalone_startup_catchup.py &
```

동작:

1. n8n `/healthz` 준비될 때까지 대기 (기본 180초)
2. webhook ping
3. **전체 스케줄** (`weather`, `economy`, `news`, `regular`, `monday_weekly`, `daily`) 중 **아직 안 올라간 것만** catchup

환경 변수:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `N8N_STARTUP_CATCHUP_HOURS` | `24` | lookback 시간 |
| `N8N_STARTUP_WAIT_SECONDS` | `180` | n8n 대기 |
| `N8N_HEALTH_URL` | `http://localhost:5678/healthz` | health check URL |

## 왜 안 올라왔나

| 원인 | 설명 |
|------|------|
| **VM 꺼짐** | n8n Schedule Trigger는 VM이 켜져 있을 때만 동작합니다. 꺼진 동안 예정된 실행은 **자동으로 재시도되지 않습니다**. |
| **Google Calendar 기동 실패** | 캘린더 이벤트는 VM을 직접 켜지 않습니다. GCP Compute 스케줄러·Cloud Scheduler·별도 wake 스크립트가 연결돼 있어야 합니다. |
| **백업 AI(Gemini) 오응답** | VM/n8n 준비 전·주 AI 장애 시 백업 AI가 `@auto 일정대로 올려` 같은 요청을 n8n에 전달하지 않고 도움말만 답할 수 있습니다. |
| **파이프라인 미연결** | `N8N_WEBHOOK_URL` 미설정, n8n 워크플로 미배포, `card_news_catchup` 분기 없음 → 복구 명령도 무시됩니다. |

## 즉시 복구 (하네스 VM에서)

### 1. VM + n8n 기동

```bash
# New-MCP-Unity 경로
bash EXE/start_n8n.sh
```

n8n UI → **Executions** 탭에서 실패·누락 실행을 확인합니다.

### 2. 연결 확인

```bash
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
python3 scripts/sync_n8n.py verify
```

### 3. 오늘 정규일정 + 월요일 주간 (이미 올라간 것 제외)

Slack에서 `@auto 오늘 일정대로 올려. 이미 올라간거 빼고`와 동일한 동작:

```bash
python3 scripts/sync_n8n.py catchup --hours 24
```

옵션:

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--hours` | `24` | 몇 시간 전까지 누락분을 볼지 |
| `--schedules` | 전체 (`weather`~`daily`) | `weather` 날씨, `economy` 경제, `news` 뉴스, `regular` 정규, `monday_weekly` 월요일 주간 |
| `--include-posted` | off | 이미 올라간 항목도 다시 올림 |
| `--channel-id` | `C0B4JUZPX2L` | `#자동화_날씨7경제5` |

### 4. n8n 워크플로에 필요한 분기

Webhook에서 `action` 값으로 분기:

```json
{
  "action": "card_news_catchup",
  "catchup": {
    "hours": 24,
    "since": "2026-06-07T01:00:00+00:00",
    "skip_already_posted": true,
    "schedules": ["weather", "economy", "news", "regular", "monday_weekly", "daily"],
    "trigger": "n8n_startup",
    "auto": true
  },
  "slack": {
    "channel_id": "C0B4JUZPX2L",
    "text": "card news catchup regular+monday_weekly skip_posted=true last 24h"
  }
}
```

권장 n8n 로직:

1. `schedules`에 따라 `card_news_settings.py`(하네스)의 해당 슬롯만 선택
2. `skip_already_posted === true`이면 Slack 채널 히스토리·GCS Output/Image 타임스탬프로 중복 제외
3. 남은 항목만 카드 생성 → `#자동화_날씨7경제5` 업로드

## Google Calendar VM 자동 기동 점검

캘린더 MCP는 **이벤트 읽기/쓰기**만 합니다. VM wake는 아래 중 하나가 별도로 있어야 합니다.

- GCP Compute Engine **인스턴스 스케줄** (start/stop)
- **Cloud Scheduler** → HTTP/gcloud로 VM start API 호출
- Mac `launchd` / 하네스 cron이 VM IP에 wake ping

캘린더에 이벤트만 넣고 VM start가 연결되지 않았다면 **VM은 자동으로 켜지지 않습니다**.

## Slack에서 같은 요청 보내기

n8n Slack 이벤트 워크플로에 아래 키워드를 `card_news_catchup`으로 매핑:

- `일정대로 올려`, `정규일정`, `월요일 주간`, `이미 올라간거 빼고`

백업 AI 경로에서는 **도움말 대신** 위 payload를 n8n Webhook에 POST하도록 Code 노드를 추가합니다.

## 관련 문서

- `docs/card-news-n8n-reconnect.md` — 게이트웨이·시크릿 배포 체크리스트
- `AGENTS.md` — `card_news_settings.py`는 하네스 머신에서만 편집
