# 카드뉴스 · Cursor · n8n 재연결

## 현재 상태 (2026-06-05)

| 구간 | 상태 | 비고 |
|------|------|------|
| Slack → 게이트웨이 | **미배포** | `main`에 코드 없음, Cloud Run 등 미설정 |
| 게이트웨이 → n8n | **시크릿 없음** | `N8N_WEBHOOK_URL` 미주입 |
| n8n → GCS `/outputs/image` | **미검증** | `GCS_OUTPUT_BUCKET` 필요 |
| Cursor MCP → n8n | **미설정** | `~/.cursor/mcp.json`에 n8n MCP 없음 |

즉 **Cursor–n8n–카드뉴스 파이프라인은 이 저장소 기준으로 아직 연결 완료가 아닙니다.**

## 1시간 이내 분 임시 업로드

n8n 워크플로에 `action === "card_news_backfill"` 분기를 두고, 아래를 실행합니다.

```bash
export N8N_WEBHOOK_URL="https://YOUR-N8N/webhook/..."
export N8N_SHARED_SECRET="..."   # 선택
python3 scripts/sync_n8n.py backfill --hours 1
```

채널 `#자동화_날씨7경제5` 기본 ID: `C0B4JUZPX2L` (`SLACK_CARD_NEWS_CHANNEL_ID`로 변경 가능).

### n8n Webhook에서 처리할 JSON 예시

```json
{
  "action": "card_news_backfill",
  "backfill": { "hours": 1, "since": "2026-06-05T08:33:00+00:00" },
  "slack": { "channel_id": "C0B4JUZPX2L", "text": "card news backfill last 1h" }
}
```

워크플로 권장 순서:

1. Webhook 수신
2. `since` 이후 뉴스/날씨·경제 소스 조회
3. 카드뉴스 이미지 생성
4. `POST https://YOUR_GATEWAY/outputs/image` (또는 Slack `chat.postMessage`)

## 연결 점검

```bash
python3 scripts/sync_n8n.py verify
```

## Cursor MCP (n8n)

로컬 n8n API가 켜져 있을 때 `~/.cursor/mcp.json` 예시:

```json
{
  "mcpServers": {
    "n8n": {
      "command": "npx",
      "args": ["-y", "@leonardsellem/n8n-mcp-server"],
      "env": {
        "N8N_API_URL": "http://localhost:5678/api/v1",
        "N8N_API_KEY": "YOUR_KEY"
      }
    }
  }
}
```

`New-MCP-Unity`의 `EXE/start_n8n.sh`로 n8n을 띄운 뒤 MCP를 연결합니다.

## 배포 체크리스트

1. 이 PR을 `main`에 머지
2. `slack_n8n_gateway`를 Cloud Run 등에 배포 (`Dockerfile` 참고)
3. Slack 슬래시 커맨드 URL → `https://HOST/slack/command`
4. Secret Manager에 `N8N_WEBHOOK_URL`, `SLACK_SIGNING_SECRET`, `GCS_OUTPUT_BUCKET` 등 주입
5. n8n 워크플로 Webhook URL을 게이트웨이와 동일하게 맞춤
6. `python3 scripts/sync_n8n.py verify` 성공 후 스케줄 재개
