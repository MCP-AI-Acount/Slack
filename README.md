# Slack

Slack slash-command gateway for forwarding verified Slack commands to an n8n
Webhook.

## Flow

```text
Slack slash command -> /slack/command -> this gateway -> n8n Webhook
```

The gateway returns a quick ephemeral acknowledgement to Slack and sends the
command payload to n8n as JSON. The n8n workflow can use Slack's `response_url`
from the forwarded payload when it needs to post the final result back to the
same Slack command request.

## Runtime configuration

Required environment variables:

- `SLACK_SIGNING_SECRET`: Slack app signing secret. Used to verify Slack request
  signatures.
- `N8N_WEBHOOK_URL`: n8n Webhook URL that receives the command payload.

Optional environment variables:

- `N8N_SHARED_SECRET`: sent to n8n as `X-Slack-Gateway-Secret` so the n8n
  workflow can reject unknown callers.
- `N8N_AUTHORIZATION`: sent to n8n as the `Authorization` header.
- `N8N_FORWARD_TIMEOUT_SECONDS`: n8n request timeout. Default: `2.0`.
- `SLACK_ACK_TEXT`: Slack acknowledgement text. Default:
  `Command received. n8n will continue processing it.`
- `PORT`: HTTP port. Default: `8080`.
- `ALLOW_UNSIGNED_SLACK_REQUESTS`: set to `true` only for local testing.

Do not commit real secret values. Put local secret files under `Core/` or use
your deployment platform's secret manager.

## Slack setup

1. Create or open a Slack app.
2. Add a slash command such as `/cursor`.
3. Set the request URL to:

   ```text
   https://YOUR_GATEWAY_HOST/slack/command
   ```

4. Copy the Slack app signing secret into `SLACK_SIGNING_SECRET`.

## n8n setup

Create a Webhook trigger that accepts `POST` JSON. If `N8N_SHARED_SECRET` is
configured, check the incoming `X-Slack-Gateway-Secret` header before running
the rest of the workflow.

The forwarded JSON shape is:

```json
{
  "source": "slack",
  "gateway": "slack-n8n-gateway",
  "received_at": 1779170000,
  "slack": {
    "team_id": "T123",
    "channel_id": "C123",
    "user_id": "U123",
    "command": "/cursor",
    "text": "make a canva post",
    "response_url": "https://hooks.slack.com/commands/..."
  }
}
```

## Run locally

```bash
export SLACK_SIGNING_SECRET="..."
export N8N_WEBHOOK_URL="https://n8n.example.com/webhook/slack-command"
python -m common.slack_n8n_gateway
```

Health check:

```bash
curl http://localhost:8080/health
```

## Deploy

Build and deploy the included Dockerfile on your preferred host, for example
Cloud Run. Configure secrets as environment variables or Secret Manager
references, not as tracked files.
