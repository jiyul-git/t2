'use strict';
/* Contract: genuine preflop all-in displays 3 -> 4 -> 5 cards at 0/1500/3000ms
 * and the FIRST winner at 3800ms. No board or winner spoilers. */
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const code = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');

function isolate(start, end) {
  const a = code.indexOf(start);
  const b = code.indexOf(end, a + start.length);
  assert(a >= 0 && b > a, 'missing ' + start);
  return code.slice(a, b);
}
const constants = isolate('const RUNOUT_HOLD =', 'const COLLECT_MS =');
const fn = isolate('function runoutThen(res, done)', 'function finishResult(');

function scenario({shown, allin, street, target = 5, expect, wait, winnerTime}) {
  const board = ['As', 'Kd', 'Qc', '2h', '3s'].slice(0, target);
  const seen = [];
  const timers = [];
  let now = 0, wins = 0, painted = shown;
  const S = {epoch: 7, boardLen: shown, view0: {board:board.slice(0, shown)}};
  const ctx = {
    S,
    epochAlive: e => e === S.epoch,
    epochTimer(fn, delta, epoch) { assert.strictEqual(epoch,7); timers.push({due:now+delta,fn}); },
    revealView: () => ({seats:[],board:[],stage:'preflop'}),
    renderSeats() {},
    renderChips() {},
    renderBoard(v) {
      const n = v.board.length;
      if (n > shown) seen.push({at:now,cards:n});
      S.boardLen = n;
    },
    renderPot() {},
    renderHero() {},
    actualLastStreet: () => street,
    $: () => ({set innerHTML(v) {}}),
    Math, Array, Object, Boolean
  };
  vm.createContext(ctx);
  vm.runInContext(constants + '\n' + fn, ctx);
  const res={showdown:true,allin_show:allin,runout_start_street:street,board};
  ctx.runoutThen(res,()=>wins++);
  function advance(targetTime) {
    while (true) {
      timers.sort((a,b)=>a.due-b.due);
      if (!timers.length || timers[0].due>targetTime) break;
      const next=timers.shift();
      now=next.due;
      next.fn();
    }
    now=targetTime;
  }
  for(const mark of wait) {
    advance(mark.t);
    assert.strictEqual(S.boardLen,mark.cards,
      'incorrect card count at t='+mark.t+'ms');
    assert.strictEqual(wins,mark.winners,
      'winner must NOT show until requested time, at t='+mark.t);
  }
  assert.deepStrictEqual(seen, expect);
  assert.strictEqual(wins, 1);
  assert.strictEqual(now,winnerTime);
}

scenario({
  shown:0,allin:true,street:'preflop',
  expect:[{at:0,cards:3},{at:1500,cards:4},{at:3000,cards:5}],
  wait:[{t:0,cards:3,winners:0},{t:1499,cards:3,winners:0},
        {t:1500,cards:4,winners:0},{t:2999,cards:4,winners:0},
        {t:3000,cards:5,winners:0},{t:3799,cards:5,winners:0},
        {t:3800,cards:5,winners:1}],
  winnerTime:3800
});
scenario({
  shown:3,allin:true,street:'flop',
  expect:[{at:2000,cards:4},{at:4000,cards:5}],
  wait:[{t:1999,cards:3,winners:0},{t:2000,cards:4,winners:0},
        {t:3999,cards:4,winners:0},{t:4000,cards:5,winners:0},
        {t:6000,cards:5,winners:1}],
  winnerTime:6000
});
scenario({
  shown:0,allin:false,street:'preflop',
  expect:[{at:0,cards:3},{at:2000,cards:4},{at:4000,cards:5}],
  wait:[{t:0,cards:3,winners:0},{t:2000,cards:4,winners:0},
        {t:4000,cards:5,winners:0},{t:6000,cards:5,winners:1}],
  winnerTime:6000
});
assert(code.includes('allin_show: Boolean(e.allin_show)'),
       'early result loses all-in state and incorrectly reveals 5 cards at once');
assert(code.includes('runout_start_street: e.runout_start_street || null'),
       'early result loses preflop/turn runout boundary');
assert(code.includes('revealShowdown(preview, runout)') &&
       code.includes('runoutThen(preview, showConfirmed)'),
       'early stream bypasses staged board runout');
assert(code.includes('const fv = revealView(preview, true)'),
       'early stream may erase fully shown river when confirming winner');
console.log('PASS: preflop allin exact 0/1.5/3/3.8s, nonpreflop behavior, no early winner or 5-card leak');
