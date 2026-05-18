# Slack

Thread-aware Slack MCP server for replying inside existing Slack threads.

## Tools

- `reply_in_thread`: posts a Slack message with `thread_ts`, using one of:
  - explicit `thread_ts`
  - `parent_ts` from the root Slack message
  - previously saved `thread_key`
- `remember_thread`: stores a `thread_key` -> `thread_ts` mapping for later replies.

## Configuration

Set these environment variables in the MCP server environment:

- `SLACK_BOT_TOKEN`: Slack bot token used for `chat.postMessage`.
- `SLACK_THREAD_STORE` optional: JSON file used to remember thread keys. Defaults to
  `temp/slack_threads.json`, which is ignored by git.

Run the server with:

```bash
python3 MCP_Server/slack_thread_server.py
```
