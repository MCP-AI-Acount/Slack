# AGENTS.md

## Cursor Cloud specific instructions

### Repository structure

All application code lives on **feature branches** (not `main`). Each branch is a standalone mini-project:

| Branch | Component | Language | Test command |
|---|---|---|---|
| `cursor/fix-auto-canva-flow-3727` | Slack ↔ n8n Command Gateway | Python 3.12 | `python3 -m pytest tests/ -v` |
| `cursor/slack-thread-replies-a474` | Slack Thread Reply MCP Server | Python 3 | `python3 -m pytest tests/ -v` |
| `cursor/slack-auto-opt-out-guard-7e17` | Slack Auto-Participation Guard | Node.js | `node test/slackAutoParticipationGuard.test.js` |
| `cursor/slack-command-gateway-4803` | Gateway (earlier revision) | Python 3.12 | `python3 -m pytest tests/ -v` |

To work on a branch, check out its files with `git checkout origin/<branch> -- .` or switch to it.

### Running the gateway server

```bash
SLACK_SIGNING_SECRET=<secret> N8N_WEBHOOK_URL=<url> python3 -m common.slack_n8n_gateway
```

The server listens on port 8080 by default (`PORT` env var). Health check: `GET /health`.

Required env vars (only needed for live requests, not for tests):
- `SLACK_SIGNING_SECRET` – Slack request signing secret
- `N8N_WEBHOOK_URL` – n8n webhook destination
- `GCS_OUTPUT_BUCKET` – GCS bucket for `/outputs/image` endpoint
- `OUTPUT_GATEWAY_SHARED_SECRET` – auth secret for `/outputs/image`

### Python dependencies

Only one pip dependency: `google-cloud-storage`. Tests also require `pytest`. Both are installed by the update script.

### Node.js guard

Zero npm dependencies. Tests use only Node.js built-in `assert` module.

### Gotchas

- The `main` branch contains only `README.md`. Always check out a feature branch to get actual code.
- Python tests are pure unit tests with mocks; no external services required.
- The gateway `run()` function does NOT validate env vars at startup — missing vars only error when handling matching requests.
