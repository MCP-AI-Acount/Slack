# Slack

Slack automation helpers for Auto.

## Auto participation guard

Auto must not keep replying in a thread after a user answers `아니` to the
participation prompt. The guard in `src/slackAutoParticipationGuard.js` stores a
per-thread decision and returns `shouldRespond: false` for denied or waiting
threads.

See `docs/n8n-slack-auto-guard.md` for the n8n Code node and IF node wiring.
