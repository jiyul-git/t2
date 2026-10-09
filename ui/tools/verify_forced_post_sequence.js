'use strict';
// Exercise the actual deal -> ante -> SB -> BB functions with deterministic
// timers, including a player whose entire stack is paid as an ante.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const path = require('path');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../web/style.css'), 'utf8');
const frames = [], timers = [], labels = [];
const box = {appendChild: el => labels.push(el)};
const ctx = {
  S: {epoch: 1}, SHUFFLE_MS: 700, DEAL_ANIM: 500, FORCED_POST_MS: 500,
  performance: {now: () => 1}, dealMs: () => 100,
  dealOrder: v => v.seats.map(s => s.seat), dealAppend: () => true,
  epochAlive: () => true, epochTimer: fn => timers.push(fn),
  deckShow() {}, deckHide() {}, renderSeats() {}, renderChips() {}, renderHero() {},
  renderPot: v => frames.push(JSON.parse(JSON.stringify(v))),
  requestAnimationFrame: fn => fn(), positionRightChips() {},
  chipPosition: () => ({p: {x: 78, y: 50}, side: ' side-right'}),
  $: () => box, fmt: String,
  document: {createElement: () => ({style: {}, dataset: {}, remove() {}})},
};
vm.createContext(ctx);
for (const name of ['frameView', 'applyEntry', 'blindSeat', 'blindAmount',
  'forcedStartState', 'renderForced', 'makeAnteChip', 'postBlindsThen', 'dealThen']) {
  const fn = source.match(new RegExp('^function ' + name + '\\([^]*?^}', 'm'));
  assert(fn, name);
  vm.runInContext(fn[0], ctx);
}
for (const short of [false, true]) {
  frames.length = timers.length = labels.length = 0;
  const seats = Array.from({length: 9}, (_, i) => {
    const seat = i + 1, original = short && seat === 3 ? 10 : 10000;
    const ante = Math.min(original, seat === 1 ? 112 : 111);
    const bet = seat === 1 ? 1000 : seat === 9 ? 500 : seat === 4 ? 2300 : 0;
    return {seat, stack: original - ante - bet, bet, ante,
      pos: seat === 1 ? 'BB' : seat === 9 ? 'SB' : 'UTG', in_hand: true};
  });
  const ante = seats.reduce((sum, s) => sum + s.ante, 0);
  const v = {seats, hero_seat: 9, level: {sb: 500, bb: 1000, ante: 1000},
    pot_center: ante, pot_total: ante + 3800};
  const original = short ? 80010 : 90000;
  let done = false;
  ctx.dealThen(v, () => {done = true;});
  assert.equal(frames[0].pot_total, 0, 'deal must start before ante posting');
  assert.equal(frames[0].seats.reduce((sum, s) => sum + s.stack, 0), original);
  assert.equal(frames[0].seats[2].allin, false, 'ante has not yet been paid');
  let steps = 0;
  while (timers.length) { assert(++steps < 100); timers.shift()(); }
  assert(done);
  const totals = frames.map(v => v.pot_total);
  assert.deepEqual(totals, [0, 0, ante, ante, ante + 500, ante + 1500]);
  for (const frame of frames) {
    assert.equal(frame.seats.reduce((sum, s) => sum + s.stack, 0) + frame.pot_total,
      original, 'displayed chips must be conserved in every posting frame');
  }
  assert.equal(labels.length, 9);
  assert(labels.every(el => el.className === 'chips forced-ante side-right'));
  assert.equal(frames.at(-1).seats[2].allin, short);
}
assert(css.includes('.chips.side-right:not(.toPot) { transition: none; }'));
assert(css.includes('transition: left .35s ease-in, top .35s ease-in, opacity .35s;'));
console.log('PASS: complete 9-seat deal/ante/blind sequence, monotonic pot, chip conservation, ante all-in');
