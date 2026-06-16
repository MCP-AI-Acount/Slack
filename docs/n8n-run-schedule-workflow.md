# n8n: 기사·일정만 안 올라갈 때 (일기예보는 됨)

## 핵심

VM 스크립트가 **200 OK**를 받아도 Slack에 안 올라가면, **n8n Webhook 뒤에 처리 분기가 없거나** 기사/일정 **워크플로가 따로 실패**한 겁니다.

| 올라감 | n8n 쪽 |
|--------|--------|
| 일기예보 ✓ | `weather` Schedule Trigger 워크플로 — **정상** |
| 기사 ✗ | `news` 워크플로 — cron 놓침 / 비활성 / Executions 에러 |
| 정규일정 ✗ | `regular`, `monday_weekly` 워크플로 — 동일 |

`card_news_catchup` / `run_schedule` 을 Webhook에서 **아직 연결 안 했으면** 요청은 받고 **아무 것도 안 함**.

---

## VM에서 바로 (기사+일정만)

날씨는 이미 올라갔으니 **weather 제외**:

```bash
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
python3 ~/Slack/scripts/sync_n8n.py trigger --only news,regular,monday_weekly,economy
```

또는 standalone:

```bash
python3 ~/standalone_startup_catchup.py trigger --only news,regular,monday_weekly,economy
```

진단:

```bash
python3 ~/Slack/scripts/sync_n8n.py diagnose
```

---

## n8n Webhook 뒤에 붙일 Switch (필수)

Webhook 노드 다음 **Switch** 또는 **IF**:

| `action` 값 | 동작 |
|-------------|------|
| `ping` | 200 `{ "ok": true }` |
| `run_schedule` | `$json.schedule` 값으로 해당 워크플로 Execute |
| `card_news_catchup` | `$json.catchup.schedules` 각각 run |

### `run_schedule` 분기 예시 (Code node)

```javascript
const schedule = $json.schedule || $json.run?.schedule || '';
const map = {
  weather: 'WORKFLOW_ID_WEATHER',      // 또는 Execute Workflow 노드 이름
  news: 'WORKFLOW_ID_NEWS',
  economy: 'WORKFLOW_ID_ECONOMY',
  regular: 'WORKFLOW_ID_REGULAR',
  monday_weekly: 'WORKFLOW_ID_MONDAY_WEEKLY',
  daily: 'WORKFLOW_ID_DAILY',
};
const target = map[schedule];
if (!target) {
  return [{ json: { ok: false, error: `unknown schedule: ${schedule}` } }];
}
return [{ json: { ok: true, schedule, targetWorkflow: target } }];
```

이후 **Execute Workflow** 노드로 `news` / `regular` / `monday_weekly` 워크플로를 각각 호출.

### `skip_if_posted` (선택)

`$json.run.skip_if_posted === true` 이면 Slack 채널 `C0B4JUZPX2L` 오늘 메시지에 해당 타입 키워드가 있으면 skip.

---

## n8n Executions에서 확인할 것

1. **Weather workflow** — Success (오늘)
2. **News / Card news workflow** — Error? Skipped? 없음?
3. **Regular schedule workflow** — 월요일 주간 포함, Active + Published?

워크플로가 **Inactive** 또는 **Unpublished**면 cron·webhook 모두 안 탐.

---

## 워크플로별 Webhook URL이 다른 경우

```bash
export N8N_WEBHOOK_URL="https://.../webhook/main"
export N8N_WEBHOOK_URL_NEWS="https://.../webhook/news-only"
export N8N_WEBHOOK_URL_REGULAR="https://.../webhook/regular-only"
python3 scripts/sync_n8n.py trigger --only news,regular
```

---

## Slack 수동 확인 (n8n 살아 있을 때)

n8n이 Slack 명령을 받는 워크플로가 있다면:

- `@auto 뉴스` 또는 `@auto 만평`
- `@auto 경제`

이것도 안 되면 **news/economy 워크플로 자체**가 깨진 것 — catchup과 무관.
