'use strict';

const MODES = Object.freeze({
  ALLOWED: 'allowed',
  DENIED: 'denied',
  WAITING: 'waiting',
  UNDECIDED: 'undecided',
});

const DECISIONS = Object.freeze({
  ALLOW: 'allow',
  DENY: 'deny',
  WAIT: 'wait',
  NONE: 'none',
});

const EXACT_ALLOW = new Set([
  '그래',
  '그럼',
  '응',
  'ㅇ',
  '어',
  '네',
  '예',
  '좋아',
  '참여',
  '들어와',
  '해',
  'yes',
  'y',
  'ok',
  'okay',
  'join',
  'start',
]);

const EXACT_DENY = new Set([
  '아니',
  '아니요',
  '아뇨',
  'ㄴ',
  '노',
  '싫어',
  '됐어',
  '필요없어',
  '필요없음',
  'no',
  'nope',
  'n',
  'stop',
  'cancel',
]);

const EXACT_WAIT = new Set([
  '기다려',
  '잠깐',
  '보류',
  '나중에',
  'wait',
  'hold',
  'later',
]);

const PHRASE_DENY = [
  '끼지 마',
  '끼지마',
  '오지 마',
  '오지마',
  '부르지 마',
  '부르지마',
  '필요 없어',
  '필요없',
  '그만',
  '중지',
  '하지 마',
  '하지마',
];

const PHRASE_ALLOW = [
  '참여해',
  '참여해줘',
  '들어와',
  '같이 해',
  '같이해',
  '진행해',
  '시작해',
];

const PHRASE_WAIT = [
  '잠깐만',
  '조금 기다려',
  '일단 기다려',
  '아직 기다려',
];

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
  if (!normalized) {
    return DECISIONS.NONE;
  }

  if (EXACT_DENY.has(normalized)) {
    return DECISIONS.DENY;
  }
  if (EXACT_WAIT.has(normalized)) {
    return DECISIONS.WAIT;
  }
  if (EXACT_ALLOW.has(normalized)) {
    return DECISIONS.ALLOW;
  }

  if (PHRASE_DENY.some((phrase) => normalized.includes(phrase))) {
    return DECISIONS.DENY;
  }
  if (PHRASE_WAIT.some((phrase) => normalized.includes(phrase))) {
    return DECISIONS.WAIT;
  }
  if (PHRASE_ALLOW.some((phrase) => normalized.includes(phrase))) {
    return DECISIONS.ALLOW;
  }

  return DECISIONS.NONE;
}

function createThreadKey(event) {
  const channel = event.channel || event.channel_id || event.channelId;
  const threadTs = event.thread_ts || event.threadTs || event.ts;

  if (!channel || !threadTs) {
    throw new Error('Slack event must include channel and ts/thread_ts.');
  }

  return `${channel}:${threadTs}`;
}

function isBotEvent(event, autoBotUserId) {
  return Boolean(
    event.bot_id ||
      event.botId ||
      event.subtype === 'bot_message' ||
      (autoBotUserId && event.user === autoBotUserId),
  );
}

function modeForDecision(decision) {
  if (decision === DECISIONS.ALLOW) {
    return MODES.ALLOWED;
  }
  if (decision === DECISIONS.DENY) {
    return MODES.DENIED;
  }
  if (decision === DECISIONS.WAIT) {
    return MODES.WAITING;
  }
  return MODES.UNDECIDED;
}

function evaluateSlackAutoParticipation(event, options = {}) {
  const stateStore = options.stateStore || {};
  const threadKey = createThreadKey(event);
  const now = options.now || new Date().toISOString();
  const existingState = stateStore[threadKey] || {
    mode: MODES.UNDECIDED,
  };

  if (isBotEvent(event, options.autoBotUserId)) {
    return {
      threadKey,
      mode: existingState.mode,
      decision: DECISIONS.NONE,
      shouldRespond: false,
      silent: true,
      reason: 'bot_event_ignored',
      state: existingState,
    };
  }

  const decision = classifyDecision(event.text);
  if (decision !== DECISIONS.NONE) {
    const mode = modeForDecision(decision);
    const nextState = {
      mode,
      decidedBy: event.user || null,
      decidedAt: now,
      lastDecisionText: event.text || '',
    };
    stateStore[threadKey] = nextState;

    return {
      threadKey,
      mode,
      decision,
      shouldRespond: decision === DECISIONS.ALLOW,
      silent: decision !== DECISIONS.ALLOW,
      reason: `user_${decision}`,
      state: nextState,
    };
  }

  if (existingState.mode === MODES.DENIED) {
    return {
      threadKey,
      mode: MODES.DENIED,
      decision: DECISIONS.NONE,
      shouldRespond: false,
      silent: true,
      reason: 'thread_denied',
      state: existingState,
    };
  }

  if (existingState.mode === MODES.WAITING) {
    return {
      threadKey,
      mode: MODES.WAITING,
      decision: DECISIONS.NONE,
      shouldRespond: false,
      silent: true,
      reason: 'thread_waiting',
      state: existingState,
    };
  }

  if (existingState.mode === MODES.ALLOWED) {
    return {
      threadKey,
      mode: MODES.ALLOWED,
      decision: DECISIONS.NONE,
      shouldRespond: true,
      silent: false,
      reason: 'thread_allowed',
      state: existingState,
    };
  }

  return {
    threadKey,
    mode: MODES.UNDECIDED,
    decision: DECISIONS.NONE,
    shouldRespond: Boolean(options.defaultRespond),
    silent: !options.defaultRespond,
    reason: options.defaultRespond ? 'default_respond' : 'awaiting_explicit_opt_in',
    state: existingState,
  };
}

function evaluateN8nItems(items, options = {}) {
  const stateStore = options.stateStore || {};

  return items.map((item) => {
    const event = item.json.event || item.json;
    const participation = evaluateSlackAutoParticipation(event, {
      ...options,
      stateStore,
    });

    return {
      json: {
        ...item.json,
        autoParticipation: participation,
      },
    };
  });
}

module.exports = {
  DECISIONS,
  MODES,
  classifyDecision,
  createThreadKey,
  evaluateN8nItems,
  evaluateSlackAutoParticipation,
  normalizeText,
};
