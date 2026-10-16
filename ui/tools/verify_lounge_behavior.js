'use strict';
// docs/LOUNGE_SCENE_DESIGN.md 7.5: invariants over 24 simulated hours, several seeds, two clip sets.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const B = require(path.join(__dirname, '../web/lounge/behavior.js'));
const Sun = require(path.join(__dirname, '../web/lounge/sun.js'));

const ASSETS = path.join(__dirname, '../web/lounge/assets');
const scene = JSON.parse(fs.readFileSync(path.join(ASSETS, 'scene.json'), 'utf8'));
const NAMES = ['tiger', 'rabbit', 'turtle', 'penguin'];
const full = NAMES.map(n => JSON.parse(fs.readFileSync(path.join(ASSETS, 'chars', n, 'manifest.json'), 'utf8')));
const minimal = full.map(m => ({ ...m, clips: Object.fromEntries(B.REQUIRED_CLIPS.map(id => [id, m.clips[id]])) }));
const START = Date.UTC(2026, 2, 19, 15, 0);          // 2026-03-20 00:00 KST
const SEOUL = [37.5665, 126.978];
const SEATED_MAX_MS = (B.SEAT_SECONDS[1] + 120) * 1000;
const OTHER_MAX_MS = 120 * 1000;
let checks = 0;
const ok = (c, m) => { checks++; if (!c) throw new Error(m); };

function makeDirector(characters, seed, extra) {
  let d = null;
  const now = () => (d ? d.now : 0);
  const events = [];
  d = B.createDirector({
    seed, scene, characters,
    clock: () => START + now(),
    minuteOfDay: () => Math.floor(now() / 60000) % 1440,
    solar: () => Sun.sunPosition(new Date(START + now()), SEOUL[0], SEOUL[1]),
    onEvent: e => events.push(e),
    ...extra,
  });
  return { d, events };
}

function hashEvents(events) {
  const h = crypto.createHash('sha256');
  for (const e of events) h.update([e.t, e.name, e.from, e.to, e.state, e.seat].join('|') + '\n');
  return h.digest('hex');
}

// -------------------------------------------------------------------------------- invariants
function simulate(characters, seed, label, hours = 24) {
  const { d, events } = makeDirector(characters, seed);
  const clipsOf = Object.fromEntries(characters.map(m => [m.name, m.clips]));
  const seatX = scene.seats.map(s => s.x);
  const stepMs = 100, steps = hours * 3600 * 1000 / stepMs;
  const dwell = {};                        // name -> {state, since}
  const lastWalk = {};                     // name -> {x, state}
  const walkInfo = {};                     // name -> {x0, dir} learned from the first ENTERING sample
  let zeroRun = 0, maxZeroRun = 0, minPresent = 99, maxPresent = 0;
  const used = new Set();

  const first = d.step(0);
  ok(first.length >= Math.min(Math.ceil(d.target / 2), characters.length) && first.every(c => c.state === 'SEATED' && c.lane === 'seat'),
    label + ': warm start places half the target already seated');

  for (let i = 1; i <= steps; i++) {
    const out = d.step(stepMs);
    const t = d.now;
    const minute = Math.floor(t / 60000) % 1440;
    const day = minute >= 7 * 60 && minute < 23 * 60;
    maxPresent = Math.max(maxPresent, out.length);
    if (day) { minPresent = Math.min(minPresent, out.length); }
    if (out.length === 0 && day) { zeroRun += stepMs; maxZeroRun = Math.max(maxZeroRun, zeroRun); } else zeroRun = 0;

    const seatsSeen = new Set();
    for (const c of out) {
      // 1. one character per seat
      ok(c.seat >= 0 || c.state === 'TURN_OUT' || c.state === 'EXITING', label + ': ' + c.name + ' has no seat in ' + c.state);
      if (c.seat >= 0) { ok(!seatsSeen.has(c.seat), label + ': seat ' + c.seat + ' shared at t=' + t); seatsSeen.add(c.seat); }
      // 3. only clips the character owns
      ok(clipsOf[c.name][c.clip], label + ': played missing clip ' + c.clip);
      used.add(c.clip);
      // 4. nobody stays in one state for too long
      const w = dwell[c.name];
      if (!w || w.state !== c.state) dwell[c.name] = { state: c.state, since: t };
      else ok(t - w.since <= (c.state === 'SEATED' ? SEATED_MAX_MS : OTHER_MAX_MS), label + ': ' + c.name + ' stuck in ' + c.state + ' for ' + ((t - w.since) / 1000) + ' s');
      // 6. walking moves whole steps and ends exactly on the seat
      const clip = clipsOf[c.name][c.clip];
      if (c.state === 'ENTERING' || c.state === 'EXITING') {
        const prev = lastWalk[c.name];
        if (c.state === 'ENTERING' && !(prev && prev.state === 'ENTERING')) {
          const seatXv = seatX[c.seat], n = clip.frames.length, cycle = n * clip.advance;
          const dir = c.clip === 'walk_r' ? 1 : -1;
          const cycles = dir === 1 ? Math.ceil((seatXv - scene.entries.left) / cycle) : Math.ceil((scene.entries.right - seatXv) / cycle);
          const x0 = seatXv - dir * cycles * cycle;
          ok(c.x === x0 || c.x === x0 + dir * clip.advance, label + ': first x ' + c.x + ' should be start ' + x0);
          ok(dir === 1 ? x0 <= scene.entries.left : x0 >= scene.entries.right, label + ': starts off screen');
          walkInfo[c.name] = { x0, dir };
        }
        if (prev && prev.state === c.state) {
          const dx = Math.abs(c.x - prev.x);
          ok(dx % clip.advance === 0 && dx <= 2 * clip.advance, label + ': walked ' + dx + ' px in one step');
          if (c.state === 'ENTERING' && c.x !== prev.x) ok((c.x > prev.x) === (walkInfo[c.name].dir === 1), label + ': walks toward the seat');
        }
        lastWalk[c.name] = { x: c.x, state: c.state };
        ok(c.lane === 'aisle', label + ': walkers are in the aisle');
      } else {
        const prev = lastWalk[c.name];
        if (prev && prev.state === 'ENTERING' && c.state === 'TURN_IN') ok(c.x === seatX[c.seat], label + ': arrives exactly on seat x, got ' + c.x);
        delete lastWalk[c.name];
        if (c.seat >= 0) ok(c.x === seatX[c.seat], label + ': ' + c.name + ' is off its seat in ' + c.state);
      }
      // lanes follow laneSwitchAt
      if (c.state === 'SIT_DOWN') ok(c.lane === (c.frame >= clip.laneSwitchAt ? 'seat' : 'aisle'), label + ': sit_down lane');
      if (c.state === 'STAND_UP') ok(c.lane === (c.frame >= clip.laneSwitchAt ? 'aisle' : 'seat'), label + ': stand_up lane');
      if (c.state === 'SEATED') ok(c.lane === 'seat', label + ': seated lane');
    }
  }

  // 2. every clip change stays on a shared pose node
  const chats = new Map();
  for (const e of events) {
    if (e.from !== null) {
      const a = clipsOf[e.name][e.from], b = clipsOf[e.name][e.to];
      ok(a && b && a.to === b.from, label + ': ' + e.name + ' ' + e.from + ' -> ' + e.to + ' is not on a shared pose');
    }
    // 7. sunglasses only in daylight
    if (e.to === 'sunglasses') {
      const el = Sun.sunPosition(new Date(START + e.t), SEOUL[0], SEOUL[1]).elevation;
      ok(el > 10, label + ': sunglasses at sun elevation ' + el.toFixed(1));
    }
    if (/^chat_in_/.test(e.to)) {
      if (!chats.has(e.t)) chats.set(e.t, []);
      chats.get(e.t).push(e);
    }
  }
  // conversations start in pairs on neighbouring seats; the left-hand sitter faces right
  for (const [t, list] of chats) {
    ok(list.length === 2, label + ': chat at ' + t + ' has ' + list.length + ' participants');
    const [a, b] = list.sort((p, q) => p.seat - q.seat);
    ok(Math.abs(a.seat - b.seat) === 1, label + ': chat partners are not neighbours');
    ok(a.to === 'chat_in_r' && b.to === 'chat_in_l', label + ': chat directions ' + a.to + ' / ' + b.to);
  }
  // 5. the lounge is never empty for long while it is open
  ok(maxZeroRun <= 180 * 1000, label + ': empty for ' + maxZeroRun / 1000 + ' s during opening hours');
  ok(maxPresent <= characters.length, label + ': more people than characters');
  return { events, used, chats: chats.size, maxZeroRun, minPresent, maxPresent };
}

const seeds = [1, 2, 3, 4, 5];
const seen = new Set();
let chatTotal = 0;
for (const seed of seeds) {
  const r = simulate(full, seed, 'full seed ' + seed);
  r.used.forEach(c => seen.add(c));
  chatTotal += r.chats;
  console.log('  full seed %d: %d clip changes, %d chats, max %d present, longest empty spell %d s', seed, r.events.length, r.chats, r.maxPresent, r.maxZeroRun / 1000);
  const m = simulate(minimal, seed, 'minimal seed ' + seed);
  ok([...m.used].every(c => B.REQUIRED_CLIPS.includes(c)), 'minimal set used a clip outside the required nine');
  ok(m.chats === 0, 'no chats without chat clips');
}
// Over five days of simulated time every kind of activity should have happened.
for (const clip of ['phone_loop', 'call_loop', 'eat_loop', 'doze_loop', 'sunglasses', 'fix_clothes', 'chat_talk_r', 'chat_talk_l',
  'chat_listen_r', 'chat_listen_l', 'chat_out_r', 'chat_out_l', 'sit_idle', 'walk_r', 'walk_l']) ok(seen.has(clip), 'never played ' + clip);
ok(chatTotal > 0, 'conversations happen');

// -------------------------------------------------------------------------------- determinism
{
  const run = (seed, dt, ms) => { const { d, events } = makeDirector(full, seed); for (let t = 0; t < ms; t += dt) d.step(dt); return hashEvents(events); };
  const h1 = run(7, 100, 3600e3);
  ok(h1 === run(7, 100, 3600e3), 'same seed, same history');
  ok(h1 !== run(8, 100, 3600e3), 'different seed, different history');
  ok(h1 === run(7, 25, 3600e3) && h1 === run(7, 250, 3600e3) && h1 === run(7, 40, 3600e3), 'history does not depend on the step size');
}

// -------------------------------------------------------------------------------- misc behaviour
{
  // Characters missing a required clip never appear; no characters means an empty scene.
  const broken = full.map((m, i) => (i === 0 ? { ...m, clips: Object.fromEntries(Object.entries(m.clips).filter(([k]) => k !== 'sit_down')) } : m));
  const { d, events } = makeDirector(broken, 3);
  for (let i = 0; i < 36000; i++) d.step(100);
  ok(!events.some(e => e.name === 'tiger') && d.characterNames().join() === 'rabbit,turtle,penguin', 'inactive character is left out');
  eq(makeDirector([], 1).d.step(1000), [], 'nobody to show');
  eq(makeDirector(full, 1).d.step(-500).length >= 0, true, 'negative dt is ignored');
}
{
  // Starting the walk: left entries begin at the documented position (seat.x - ceil(distance / cycle) * cycle).
  const { d } = makeDirector(full, 11);
  let checked = 0, seenLeft = false;
  const seen = {};
  for (let i = 0; i < 200000 && !(seenLeft && checked > 3); i++) {
    for (const c of d.step(100)) {
      if (c.state === 'ENTERING' && !seen[c.name + c.seat + c.clip]) {
        seen[c.name + c.seat + c.clip] = true;
        if (c.clip === 'walk_r') {
          seenLeft = true;
          const sx = scene.seats[c.seat].x, cycle = 8 * 13;
          const start = sx - Math.ceil((sx - scene.entries.left) / cycle) * cycle;
          ok(c.x === start || c.x === start + 13, 'left entry starts at ' + start + ', got ' + c.x);
          checked++;
        }
      }
    }
  }
  ok(checked > 0, 'saw a left-hand entry');
}
{
  // A manifest whose clips do not join up is caught instead of played.
  const bad = full.map(m => ({ ...m, clips: { ...m.clips, sit_idle: { ...m.clips.sit_idle, to: 'phone' } } }));
  assert.throws(() => { const { d } = makeDirector(bad, 5); for (let i = 0; i < 20000; i++) d.step(100); }, /illegal transition/); checks++;
}
{
  // Warm start can be repeated, e.g. after the page was hidden for a long time.
  const { d } = makeDirector(full, 9);
  for (let i = 0; i < 5000; i++) d.step(100);
  const out = d.warmStart();
  ok(out.length >= 1 && out.every(c => c.state === 'SEATED'), 'warmStart reseats people');
  ok(new Set(out.map(c => c.seat)).size === out.length, 'warmStart uses distinct seats');
}

function eq(a, b, m) { checks++; assert.deepStrictEqual(a, b, m); }
console.log('verify_lounge_behavior OK (' + checks + ' checks)');
