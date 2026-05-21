# n8n Slack Auto participation guard

This guard fixes the failure mode where Auto keeps joining a Slack thread after a
user answers `아니` to the invitation prompt.

## Required workflow shape

Put a guard step before any AI/Auto response node:

1. Slack event trigger
2. Code node: evaluate participation state
3. IF node: continue only when `autoParticipation.shouldRespond` is `true`
4. AI/Auto response nodes
5. Slack response node

The guard stores one state per Slack thread:

- `allowed`: user answered `그래`, `네`, `yes`, etc.
- `denied`: user answered `아니`, `아니요`, `no`, etc.
- `waiting`: user answered `기다려`, `잠깐`, `wait`, etc.
- `undecided`: no explicit answer yet

`denied` and `waiting` must be silent. Do not post a new Slack message for those
states.

## n8n Code node example

Use workflow static data so the decision persists across later messages in the
same thread:

```js
const stateStore = $getWorkflowStaticData('global').autoParticipation || {};
$getWorkflowStaticData('global').autoParticipation = stateStore;

function normalizeText(text) {
  return String(text || '')
    .replace(/<@[A-Z0-9]+>/gi, '')
    .replace(/\bauto\b/gi, '')
    .replace(/[()[\]{}'"`*_~.,!?;:<>|/\\，。！？、]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function classifyDecision(text) {
  const normalized = normalizeText(text);
  const allow = new Set(['그래', '그럼', '응', 'ㅇ', '어', '네', '예', '좋아', '참여', '들어와', '해', 'yes', 'y', 'ok', 'okay', 'join', 'start']);
  const deny = new Set(['아니', '아니요', '아뇨', 'ㄴ', '노', '싫어', '됐어', '필요없어', '필요없음', 'no', 'nope', 'n', 'stop', 'cancel']);
  const wait = new Set(['기다려', '잠깐', '보류', '나중에', 'wait', 'hold', 'later']);

  if (deny.has(normalized) || ['끼지 마', '끼지마', '오지 마', '오지마', '부르지 마', '부르지마', '필요 없어', '필요없', '그만', '중지', '하지 마', '하지마'].some((phrase) => normalized.includes(phrase))) {
    return 'deny';
  }
  if (wait.has(normalized) || ['잠깐만', '조금 기다려', '일단 기다려', '아직 기다려'].some((phrase) => normalized.includes(phrase))) {
    return 'wait';
  }
  if (allow.has(normalized) || ['참여해', '참여해줘', '들어와', '같이 해', '같이해', '진행해', '시작해'].some((phrase) => normalized.includes(phrase))) {
    return 'allow';
  }
  return 'none';
}

function evaluate(event) {
  const channel = event.channel || event.channel_id || event.channelId;
  const threadTs = event.thread_ts || event.threadTs || event.ts;
  const threadKey = `${channel}:${threadTs}`;
  const existing = stateStore[threadKey] || { mode: 'undecided' };

  if (event.bot_id || event.botId || event.subtype === 'bot_message') {
    return { threadKey, mode: existing.mode, decision: 'none', shouldRespond: false, silent: true, reason: 'bot_event_ignored' };
  }

  const decision = classifyDecision(event.text);
  if (decision !== 'none') {
    const mode = decision === 'allow' ? 'allowed' : decision === 'deny' ? 'denied' : 'waiting';
    stateStore[threadKey] = {
      mode,
      decidedBy: event.user || null,
      decidedAt: new Date().toISOString(),
      lastDecisionText: event.text || '',
    };
    return { threadKey, mode, decision, shouldRespond: decision === 'allow', silent: decision !== 'allow', reason: `user_${decision}` };
  }

  if (existing.mode === 'denied') {
    return { threadKey, mode: 'denied', decision: 'none', shouldRespond: false, silent: true, reason: 'thread_denied' };
  }
  if (existing.mode === 'waiting') {
    return { threadKey, mode: 'waiting', decision: 'none', shouldRespond: false, silent: true, reason: 'thread_waiting' };
  }
  if (existing.mode === 'allowed') {
    return { threadKey, mode: 'allowed', decision: 'none', shouldRespond: true, silent: false, reason: 'thread_allowed' };
  }

  return { threadKey, mode: 'undecided', decision: 'none', shouldRespond: false, silent: true, reason: 'awaiting_explicit_opt_in' };
}

return items.map((item) => ({
  json: {
    ...item.json,
    autoParticipation: evaluate(item.json.event || item.json),
  },
}));
```

## IF node condition

Only continue to AI/Auto response nodes when:

```text
{{$json.autoParticipation.shouldRespond}} is true
```

All other cases should end the workflow without posting to Slack.

