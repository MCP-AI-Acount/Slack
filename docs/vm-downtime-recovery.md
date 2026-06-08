# VM 다운타임 후 카드뉴스 복구

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
| `--schedules` | `regular,monday_weekly` | `regular` 정규일정, `monday_weekly` 월요일 주간, `daily` 매일 |
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
    "schedules": ["regular", "monday_weekly"]
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
