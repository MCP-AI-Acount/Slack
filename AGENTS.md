# AGENTS.md

## Cursor Cloud specific instructions

### Repository structure

Application code is on feature branches; **`main` may be empty** until PRs merge.

| Branch | Component |
|--------|-----------|
| `cursor/fix-auto-canva-flow-3727` | Slack ↔ n8n gateway + GCS image delivery |
| `cursor/slack-thread-replies-a474` | Thread-aware Slack MCP server |
| `cursor/slack-auto-opt-out-guard-7e17` | Auto opt-out guard (`docs/n8n-slack-auto-guard.md`) |

### Tests

```bash
pip install --user -r requirements.txt
python3 -m pytest tests/ -v
```

### n8n / card news

```bash
export N8N_WEBHOOK_URL="..."
python3 scripts/sync_n8n.py verify
python3 scripts/sync_n8n.py backfill --hours 1
```

See `docs/card-news-n8n-reconnect.md`.

### Gateway

```bash
export SLACK_SIGNING_SECRET="..." N8N_WEBHOOK_URL="..." GCS_OUTPUT_BUCKET="..." OUTPUT_GATEWAY_SHARED_SECRET="..."
python3 -m common.slack_n8n_gateway
```

Health: `GET /health` on port `8080`.

### Gotchas

- Do not commit secrets; use Secret Manager or `/home/ubuntu/.config/agent-secrets.env`.
- Gateway `run()` does not validate env at startup — errors appear on first request.
- `card_news_settings.py` (MCP-Auto harness) is **not** in this repo; edit on the harness machine only.
