# Slack

Slack slash-command gateway for forwarding verified Slack commands to an n8n
Webhook.

## Flow

```text
Slack slash command -> /slack/command -> this gateway -> n8n Webhook
n8n/image generator -> /outputs/image -> GCS Output/Image -> progress webhook
```

The gateway returns a quick ephemeral acknowledgement to Slack and sends the
command payload to n8n as JSON. The n8n workflow can use Slack's `response_url`
from the forwarded payload when it needs to post the final result back to the
same Slack command request. When an image is ready, n8n can call `/outputs/image`
to store it under `Output/Image/` in Google Cloud Storage and notify a progress
website webhook with the completed task link.

## Runtime configuration

Required environment variables:

- `SLACK_SIGNING_SECRET`: Slack app signing secret. Used to verify Slack request
  signatures.
- `N8N_WEBHOOK_URL`: n8n Webhook URL that receives the command payload.
- `GCS_OUTPUT_BUCKET`: Google Cloud Storage bucket used by `/outputs/image`.
- `OUTPUT_GATEWAY_SHARED_SECRET`: shared secret required for `/outputs/image`.

Optional environment variables:

- `N8N_SHARED_SECRET`: sent to n8n as `X-Slack-Gateway-Secret` so the n8n
  workflow can reject unknown callers.
- `N8N_AUTHORIZATION`: sent to n8n as the `Authorization` header.
- `N8N_FORWARD_TIMEOUT_SECONDS`: n8n request timeout. Default: `2.0`.
- `SLACK_ACK_TEXT`: Slack acknowledgement text. Default:
  `Command received. n8n will continue processing it.`
- `PORT`: HTTP port. Default: `8080`.
- `ALLOW_UNSIGNED_SLACK_REQUESTS`: set to `true` only for local testing.
- `GCS_OUTPUT_PREFIX`: top-level GCS prefix. Default: `Output`.
- `GCS_IMAGE_PREFIX`: image GCS prefix inside the output prefix. Default:
  `Image`.
- `GCS_PUBLIC_BASE_URL`: optional CDN or public bucket base URL used when
  returning links. If omitted, links use `https://storage.googleapis.com`.
- `PROGRESS_WEBHOOK_URL`: optional webhook for the progress website.
- `PROGRESS_SHARED_SECRET`: sent to the progress webhook as `X-Progress-Secret`.
- `PROGRESS_AUTHORIZATION`: sent to the progress webhook as `Authorization`.
- `PROGRESS_TIMEOUT_SECONDS`: progress webhook timeout. Default: `5.0`.
- `SLACK_RESPONSE_TIMEOUT_SECONDS`: timeout for posting final output links to
  Slack `response_url` values. Default: `5.0`.
- `ALLOW_UNSIGNED_OUTPUT_REQUESTS`: set to `true` only for local testing.

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

## Output image delivery

After n8n or another generator creates an image, call this gateway endpoint:

```text
POST https://YOUR_GATEWAY_HOST/outputs/image
```

Headers:

```text
Content-Type: application/json
X-Output-Gateway-Secret: YOUR_OUTPUT_GATEWAY_SHARED_SECRET
```

Body:

```json
{
  "task_id": "slack-20260519-001",
  "task_title": "Canva card news image",
  "filename": "card-news.png",
  "content_type": "image/png",
  "image_base64": "BASE64_IMAGE_BYTES",
  "slack_response_url": "https://hooks.slack.com/commands/...",
  "slack_text": "Cartoon completed: https://cdn.example.com/Output/Image/card-news.png",
  "metadata": {
    "source": "slack",
    "command": "/cursor"
  }
}
```

The gateway creates folder marker objects for `Output/` and `Output/Image/` if
they do not exist, uploads the image as an object under `Output/Image/`, and
returns JSON containing `output.link`. If `slack_response_url` is supplied, the
gateway posts the final link back to the originating Slack command response URL
after upload. Google Cloud Storage folders are object prefixes; the marker
objects make the prefixes visible in console-style UIs.

If `PROGRESS_WEBHOOK_URL` is configured, the gateway also posts this payload to
your progress website. Progress and Slack response webhook failures are returned
in the JSON response but do not undo a successful image upload:

```json
{
  "event": "task.completed",
  "status": "completed",
  "task_id": "slack-20260519-001",
  "title": "Canva card news image",
  "links": [
    {
      "type": "image",
      "url": "https://storage.googleapis.com/YOUR_BUCKET/Output/Image/..."
    }
  ]
}
```

The returned link is only publicly open if the bucket, CDN, or `GCS_PUBLIC_BASE_URL`
serves it publicly. Otherwise it is an authenticated GCS object URL.

### CLI upload

The same delivery path can be used from a shell or n8n Execute Command node:

```bash
python3 -m common.output_delivery \
  --image ./card-news.png \
  --task-title "Canva card news image" \
  --task-id "slack-20260519-001"
```

## n8n sync (verify / card-news backfill)

Use `scripts/sync_n8n.py` when scheduled card news did not run. This POSTs to
`N8N_WEBHOOK_URL` (or `N8N_CARD_NEWS_WEBHOOK_URL`) so n8n can republish missed
items for `#자동화_날씨7경제5`.

```bash
export N8N_WEBHOOK_URL="https://n8n.example.com/webhook/slack-command"
python3 scripts/sync_n8n.py verify
python3 scripts/sync_n8n.py backfill --hours 1
python3 scripts/sync_n8n.py catchup --hours 24
python3 scripts/sync_n8n.py startup
```

After `EXE/start_n8n.sh`, run `scripts/n8n_startup_catchup.sh` in the background so missed
economy/news schedules auto-publish while skipping weather that already posted.

See `docs/card-news-n8n-reconnect.md` and `docs/vm-downtime-recovery.md` for the full reconnect checklist.

## Run locally

```bash
export SLACK_SIGNING_SECRET="..."
export N8N_WEBHOOK_URL="https://n8n.example.com/webhook/slack-command"
export GCS_OUTPUT_BUCKET="your-output-bucket"
export OUTPUT_GATEWAY_SHARED_SECRET="..."
python3 -m common.slack_n8n_gateway
```

Health check:

```bash
curl http://localhost:8080/health
```

## Deploy

Build and deploy the included Dockerfile on your preferred host, for example
Cloud Run. Configure secrets as environment variables or Secret Manager
references, not as tracked files.
