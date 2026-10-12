'use strict';
// Regression for 2026-10-09 HAND 89 live-screen review.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const path = require('path');
const ui = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../web/style.css'), 'utf8');
function between(a,b) {
  const i = ui.indexOf(a), j = ui.indexOf(b, i);
  assert(i >= 0 && j > i, a);
  return ui.slice(i,j);
}
const ctx = {}; vm.createContext(ctx);
vm.runInContext(between('function mergePots(', 'function awardLabelFor('),ctx);
assert.equal(ctx.potAwards({pots:[{amount:2800,eligible:[2,8,9],winners:[2]}],
  winners:[2]})['2'][0].label,'승리');
assert.equal(ctx.potAwards({pots:[],winners:[3]})['3'][0].label,'승리');
const multi = ctx.potAwards({pots:[
  {amount:1000,eligible:[2,3,4],winners:[2]},
  {amount:500,eligible:[2,3],winners:[3]}]});
assert.equal(multi['2'][0].label,'MAIN');
assert.equal(multi['3'][0].label,'SIDE 1');

assert(css.includes('#seats .pod.bubble-front { z-index: 12; }'));
let cls = '', bubble = null;
const pod = {classList:{add:x=>{cls=x}},appendChild:x=>{bubble=x}};
const dom = {querySelector:q=>q.includes('data-slot="2"')?pod:null,
  createElement:()=>({className:'',textContent:''})};
const c2 = {document:dom,actionText:()=> '체크'};
vm.createContext(c2);
vm.runInContext(between('function bubbleAt(', '/* ---------------- 봇 액션 순차'), c2);
c2.bubbleAt(2, {action:'check'});
assert.equal(cls, 'bubble-front');
assert.equal(bubble.textContent,'체크');

assert(ui.includes('const BOT_ACTION_FEEDBACK_MS = 550;'));
assert(ui.includes('}, e.act_at_ms ? BOT_ACTION_FEEDBACK_MS'));
assert(ui.includes('봇 판단 계산 중…'));
console.log('PASS: normal/fold/side-pot labels, bubble stacking, scheduled action visibility and non-fabricated compute status');

// Expired HERO clocks use the same legal action as the server. A request
// expiring in transit must also undo an optimistic fold/call in replay state.
const c3 = {S: {token: 1, view: null}, serverNow: () => 2000,
  closeRaise: () => {}, stopActionClock: () => {},
  fullActionLog: v => (v.log || []).slice(),
  BOARD_AT: {flop: 3}, $: () => null};
vm.createContext(c3);
vm.runInContext(between('function heroTimeoutAction(', 'function noteTiming('), c3);
vm.runInContext(between('function applyEntry(', 'function renderSpectate('), c3);
vm.runInContext(between('function send(', 'function markQueued('), c3);
let displayed, sent;
c3.previewHeroAction = action => { displayed = action; };
c3.callStepStream = payload => { sent = payload.action; };
for (const expected of ['check', 'fold']) {
  const view = {type: 'decision', hero_seat: 9, stage: 'flop', pot_center: 400,
    legal: {check: expected === 'check', fold: expected === 'fold'},
    seats: [{seat: 9, stack: 1000, bet: 0, in_hand: true}], log: []};
  Object.assign(c3.S, {view, actionDeadlineMs: 1000, actionToken: 1,
    timeoutSubmitting: false, replayDone: false});
  c3.send('call', 999);
  assert.equal(displayed, expected);
  assert.equal(sent, expected);
  c3.S.timeoutSubmitting = false;
  c3.$ = () => ({classList: {toggle() {}}, style: {}, textContent: ''});
  c3.send = action => { sent = action; };
  c3.paintActionClock();
  assert.equal(sent, expected);
  const ss = {seats: [{seat: 9, stack: 1, bet: 999, in_hand: false}], potCenter: 999};
  const log = [{action: 'call', amount: 999}];
  c3.replaceHeroReplay(ss, log, view, expected, 0);
  assert.equal(ss.seats[0].in_hand, expected === 'check');
  assert.equal(ss.seats[0].stack, 1000);
  assert.equal(ss.seats[0].bet, 0);
  assert.equal(ss.potCenter, 400);
  assert.equal(log.length, 1);
  assert.equal(log[0].action, expected);
  // Restore the actual send function for the next fixture.
  vm.runInContext(between('function send(', 'function markQueued('), c3);
}
console.log('PASS: expired clock display and replay match accepted check/fold action');

const c4 = {S: {historyHand: {hand_no: 10, hash: 'current'}, historyHandComplete: false}};
vm.createContext(c4);
vm.runInContext(between('function visibleHistory(', 'function renderHistoryList('), c4);
const history = [{hand_no: 11, hash: 'future'}, {hand_no: 10, hash: 'current'},
  {hand_no: 9, hash: 'previous'}];
// Engine finished; UI is still replaying actions, runout or card reveals.
assert.deepEqual(Array.from(c4.visibleHistory(history), v => v.hand_no), [9]);
c4.S.historyHandComplete = true;
assert.deepEqual(Array.from(c4.visibleHistory(history), v => v.hand_no), [10, 9]);
c4.S.historyHand = {hand_no: 11, hash: 'future'};
c4.S.historyHandComplete = false;
assert.deepEqual(Array.from(c4.visibleHistory(history), v => v.hand_no), [10, 9]);
c4.S.historyHand = null;
assert.equal(c4.visibleHistory(history).length, 3); // standalone history page
assert(!between('function finishResult(', 'function finishResult2(').includes('histPush('));
const finish = between('function finishResult2(', '/* 사이드팟은');
assert(finish.indexOf('histPush(v)') > finish.indexOf('renderResult(v)'));
assert(ui.includes('S.historyHand = v;\n  S.historyHandComplete = false;'));
console.log('PASS: history hides current/future results until visible hand completion');
