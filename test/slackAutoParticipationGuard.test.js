'use strict';

const assert = require('node:assert/strict');
const {
  DECISIONS,
  MODES,
  classifyDecision,
  evaluateSlackAutoParticipation,
} = require('../src/slackAutoParticipationGuard');

function event(overrides) {
  return {
    channel: 'C123',
    thread_ts: '1716250000.000100',
    ts: '1716250001.000200',
    user: 'U123',
    text: 'hello',
    ...overrides,
  };
}

function test(name, run) {
  try {
    run();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    throw error;
  }
}

test('classifies Korean opt-out reply', () => {
  assert.equal(classifyDecision('아니'), DECISIONS.DENY);
  assert.equal(classifyDecision('Auto 아니요'), DECISIONS.DENY);
  assert.equal(classifyDecision('필요 없어'), DECISIONS.DENY);
});

test('persists denied state and blocks later thread messages', () => {
  const stateStore = {};

  const first = evaluateSlackAutoParticipation(event({ text: '아니' }), {
    stateStore,
    now: '2026-05-21T03:11:00.000Z',
  });
  assert.equal(first.mode, MODES.DENIED);
  assert.equal(first.shouldRespond, false);
  assert.equal(first.silent, true);

  const later = evaluateSlackAutoParticipation(event({ text: '그 뒤에 일반 대화' }), {
    stateStore,
  });
  assert.equal(later.mode, MODES.DENIED);
  assert.equal(later.shouldRespond, false);
  assert.equal(later.reason, 'thread_denied');
});

test('waiting state stays silent until the user opts in', () => {
  const stateStore = {};

  const wait = evaluateSlackAutoParticipation(event({ text: '기다려' }), {
    stateStore,
  });
  assert.equal(wait.mode, MODES.WAITING);
  assert.equal(wait.shouldRespond, false);

  const later = evaluateSlackAutoParticipation(event({ text: '아직 보는 중' }), {
    stateStore,
  });
  assert.equal(later.mode, MODES.WAITING);
  assert.equal(later.shouldRespond, false);

  const allow = evaluateSlackAutoParticipation(event({ text: '그래' }), {
    stateStore,
  });
  assert.equal(allow.mode, MODES.ALLOWED);
  assert.equal(allow.shouldRespond, true);
});

test('allowed state lets Auto answer subsequent human messages', () => {
  const stateStore = {};

  evaluateSlackAutoParticipation(event({ text: '그래' }), {
    stateStore,
  });

  const later = evaluateSlackAutoParticipation(event({ text: '이제 도와줘' }), {
    stateStore,
  });
  assert.equal(later.mode, MODES.ALLOWED);
  assert.equal(later.shouldRespond, true);
  assert.equal(later.reason, 'thread_allowed');
});

test('bot messages are ignored and never trigger Auto', () => {
  const stateStore = {};

  const result = evaluateSlackAutoParticipation(
    event({
      text: '이 스레드에 Auto도 참여할까요?',
      user: 'UAUTO',
      bot_id: 'B123',
      subtype: 'bot_message',
    }),
    {
      stateStore,
      autoBotUserId: 'UAUTO',
    },
  );

  assert.equal(result.shouldRespond, false);
  assert.equal(result.reason, 'bot_event_ignored');
  assert.deepEqual(stateStore, {});
});

