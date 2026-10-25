'use strict';
// docs/LOUNGE_SCENE_DESIGN.md 7.5 / 7.7: invariants over 24 simulated hours, several seeds, two clip sets
// (the old programmatic placeholders, kept as test fixtures in lounge_placeholder_manifests.json), and
// the real animals of scene.json, which both pass by and sit, under the one-mover-at-a-time lock.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const B = require(path.join(__dirname, '../web/lounge/behavior.js'));
const Sun = require(path.join(__dirname, '../web/lounge/sun.js'));

const ASSETS = path.join(__dirname, '../web/lounge/assets');
const scene = JSON.parse(fs.readFileSync(path.join(ASSETS, 'scene.json'), 'utf8'));
const NAMES = ['tiger', 'rabbit', 'turtle', 'penguin'];
const FIXTURES = JSON.parse(fs.readFileSync(path.join(__dirname, 'lounge_placeholder_manifests.json'), 'utf8'));
const full = NAMES.map(n => FIXTURES[n]);           // placeholders: every clip of 6.3 incl. chat, sunglasses, fix_clothes
const REAL = scene.characters.map(n => JSON.parse(fs.readFileSync(path.join(ASSETS, 'chars', n, 'manifest.json'), 'utf8')));
const minimal = full.map(m => ({ ...m, clips: Object.fromEntries(B.REQUIRED_CLIPS.map(id => [id, m.clips[id]])) }));
const START = Date.UTC(2026, 2, 19, 15, 0);          // 2026-03-20 00:00 KST
const SEOUL = [37.5665, 126.978];
// a sitter past its seat time waits for the movement lock (a plane takes 80 s, then a quiet spell) and
// is sent off at the latest LEAVE_WAIT later, then finishes its activity
const SEATED_MAX_MS = (B.SEAT_SECONDS[1] + 240) * 1000;
const MOVING = new Set(['ENTERING', 'TURN_IN', 'SIT_DOWN', 'STAND_UP', 'TURN_OUT', 'EXITING']);
const OTHER_MAX_MS = 120 * 1000;
let checks = 0;
const ok = (c, m) => { checks++; if (!c) throw new Error(m); };

// The placeholder fixtures have one front-facing pose set; they get the scene's seats without facings
// or blocks (all four usable, side by side, so conversations can happen).
const placeholderScene = { ...scene, seats: scene.seats.map(s => ({ id: s.id, x: s.x, y: s.y })) };
function makeDirector(characters, seed, extra) {
  let d = null;
  const now = () => (d ? d.now : 0);
  const events = [];
  d = B.createDirector({
    seed, scene: characters.length && characters.every(m => m.placeholder) ? placeholderScene : scene, characters,
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
  const seatX = (characters.length && characters.every(m => m.placeholder) ? placeholderScene : scene).seats.map(s => s.x);
  const stepMs = 100, steps = hours * 3600 * 1000 / stepMs;
  const dwell = {};                        // name -> {state, since}
  const lastWalk = {};                     // name -> {x, state}
  const walkInfo = {};                     // name -> {x0, dir} learned from the first ENTERING sample
  let zeroRun = 0, maxZeroRun = 0, minPresent = 99, maxPresent = 0;
  const used = new Set();
  let maxMovers = 0;

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

    // movement lock: at most one moving character, and never one while the plane is out
    const movers = out.filter(c => MOVING.has(c.state));
    maxMovers = Math.max(maxMovers, movers.length + (d.plane() ? 1 : 0));
    ok(movers.length + (d.plane() ? 1 : 0) <= 1, label + ': two things move at once at t=' + t + ': ' + movers.map(c => c.name + ' ' + c.state) + (d.plane() ? ' + plane' : ''));
    ok(new Set(out.map(c => c.name)).size === out.length, label + ': a character is on screen twice');
    for (const n of Object.keys(dwell)) if (!out.some(c => c.name === n)) delete dwell[n];   // went away: a new visit starts over
    for (const n of Object.keys(lastWalk)) if (!out.some(c => c.name === n)) delete lastWalk[n];
    // seats (7.8): a character sits only at a facing it has clips for, and never next to a seat it blocks
    const sc = characters.length && characters.every(m => m.placeholder) ? placeholderScene : scene;
    const held = out.filter(c => c.seat >= 0).map(c => sc.seats[c.seat]);
    for (const a of held) for (const b of held) ok(a === b || !((a.blocks || []).includes(b.id)), label + ': seats ' + a.id + ' and ' + b.id + ' are taken together');
    for (const c of out) if (c.seat >= 0) {
      const f = sc.seats[c.seat].facing || 'f';
      ok(B.sitFacings(characters.find(m => m.name === c.name)).includes(f), label + ': ' + c.name + ' sits facing ' + f);
      if (c.state === 'SEATED') ok(c.clip === B.clipAt(c.clip.split('@')[0], f), label + ': ' + c.name + ' plays ' + c.clip + ' at a seat facing ' + f);
    }
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
          if (/^hop_/.test(c.clip) || /^hop_/.test(prev.clip)) {
            // across a hop (a pass only): whole walk and hop steps, at most two of them
            const cs = clipsOf[c.name], w = cs[c.clip.replace('hop_', 'walk_')] || clip, h = cs[(/^hop_/.test(c.clip) ? c.clip : prev.clip)];
            const sums = [0, 1, 2].flatMap(a => [0, 1, 2].filter(b => a + b <= 2).map(b => a * w.advance + b * h.advance));
            ok(c.state === 'EXITING' && sums.includes(dx), label + ': moved ' + dx + ' px in one step around a hop');
          } else ok(dx % clip.advance === 0 && dx <= 2 * clip.advance, label + ': walked ' + dx + ' px in one step');
          if (c.state === 'ENTERING' && c.x !== prev.x) ok((c.x > prev.x) === (walkInfo[c.name].dir === 1), label + ': walks toward the seat');
        }
        lastWalk[c.name] = { x: c.x, state: c.state, clip: c.clip };
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
  ok(maxMovers <= 1, label + ': movement lock');
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
  const rr = seed <= 3 ? simulate(REAL, seed, 'real seed ' + seed) : null;
  if (rr) console.log('  real seed %d: %d clip changes, max %d present, longest empty spell %d s', seed, rr.events.length, rr.maxPresent, rr.maxZeroRun / 1000);
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

{
  // Debug helper: forcing an activity works for seated and absent characters, and refuses unknown ones.
  const { d, events } = makeDirector(full, 21);
  for (let i = 0; i < 3000; i++) d.step(100);
  ok(d.force('rabbit', 'doze') && d.force('tiger', 'eat') && d.force('penguin', 'sunglasses'), 'force accepts known characters');
  ok(!d.force('nobody', 'eat') && !d.force('rabbit', 'dance'), 'force refuses unknown characters and activities');
  for (let i = 0; i < 4000; i++) d.step(100);
  const played = name => new Set(events.filter(e => e.name === name).map(e => e.to));
  ok(played('rabbit').has('doze_in') && played('tiger').has('eat_in') && played('penguin').has('sunglasses'), 'forced activities were played');
}

{
  // A walker crosses in its pass direction, never sits, never holds a seat, and comes back later.
  // (A pure walker: the real tiger with only its walking clips.)
  const tiger = REAL.find(m => m.name === 'tiger');
  const walker = { ...tiger, name: 'tiger_walker', clips: { walk_r: tiger.clips.walk_r, walk_l: tiger.clips.walk_l } };
  ok(B.isActive(walker) && !B.isActive({ ...walker, walker: false }), 'walker is active only as a walker');
  ok(B.canPass(tiger) && B.canSit(tiger) && !B.canSit(walker) && !B.canPass(full[0]), 'hybrid / walker / sitter roles');
  const { d } = makeDirector([walker, ...full.slice(1)], 31);
  let crossings = 0, prevX = null, wasOn = false;
  for (let i = 0; i < 18000; i++) {
    const w = d.step(100).find(c => c.name === 'tiger_walker');
    if (w) {
      ok(w.clip === 'walk_r' && w.lane === 'aisle' && w.seat === -1 && w.state === 'EXITING', 'walker only walks right: ' + JSON.stringify(w));
      ok(prevX === null || w.x >= prevX, 'walker moves left to right');
      if (!wasOn) ok(w.x <= scene.entries.left + 2 * walker.clips.walk_r.advance, 'walker enters at the left edge, x=' + w.x);
      prevX = w.x;
    } else if (wasOn) { crossings++; prevX = null; }
    wasOn = !!w;
  }
  ok(crossings >= 2, 'walker crossed ' + crossings + ' times in 30 minutes');
  ok(!d.force('tiger_walker', 'eat'), 'a walker cannot be sent to a seat');
}

{
  // The real animals of scene.json (7.7): each one passes by or goes to a seat - never both at once,
  // never on screen twice. One thing moves at a time, the plane included; the preview event comes
  // first; the same event never twice in a row; each opening is a different random run.
  ok(REAL.length >= 3 && ['tiger', 'rabbit', 'turtle'].every(n => scene.characters.includes(n)), 'scene has the real tiger, rabbit and turtle: ' + scene.characters);
  for (const m of REAL) {
    // a plain walker (walk_r / walk_l, maybe hop_r / hop_l; no seat facings: the penguin until its sitting art comes)
    // only passes by; every other real animal both passes by and sits
    const plainWalker = !m.facings && Object.keys(m.clips).every(id => /^(walk|hop)_[lr]$/.test(id));
    ok(B.canPass(m) && (B.canSit(m) || plainWalker), m.name + ' both passes by and sits (or is a plain walker)');
    ok(m.clips.walk_r.advance > 0 && m.clips.walk_r.frames.length === m.clips.walk_l.frames.length, m.name + ' walks');
    // pose-graph legality of the clips (the frames themselves are checked by lounge_check_assets.py):
    // every clip starts on its from-pose frame, a one-shot ends on its to-pose frame, and its pose nodes exist
    for (const [id, c] of Object.entries(m.clips)) {
      ok(Number.isInteger(m.poses[c.from]) && Number.isInteger(m.poses[c.to]), m.name + ' ' + id + ' uses known poses');
      ok(c.frames[0] === m.poses[c.from], m.name + ' ' + id + ' starts on pose ' + c.from);
      if (!c.loop) ok(c.frames[c.frames.length - 1] === m.poses[c.to], m.name + ' ' + id + ' ends on pose ' + c.to);
    }
    // every facing it claims is complete, and every seat facing in the scene is used by someone
    ok(plainWalker ? !B.canSit(m) : B.sitFacings(m).length === (m.facings || ['f']).length, m.name + ' has every clip for its facings ' + m.facings);
    for (const f of B.sitFacings(m)) for (const id of ['sit_down', 'stand_up']) ok(Number.isInteger(m.clips[B.clipAt(id, f)].laneSwitchAt), m.name + ' ' + id + '@' + f + ' has laneSwitchAt');
  }
  for (const f of new Set(scene.seats.map(s => s.facing || 'f'))) ok(REAL.some(m => B.sitFacings(m).includes(f)), 'someone can sit facing ' + f);
  const runs = [];
  for (const seed of [5, 77]) {
    const { d, events } = makeDirector(REAL, seed);
    const order = [];                    // events as they start: 'pass:x', 'arrive:x', 'leave:x', 'plane'
    let prevMover = null;
    for (let i = 0; i < 18000; i++) {
      const out = d.step(100);
      const moving = out.filter(c => MOVING.has(c.state));
      const pl = d.plane();
      ok(moving.length + (pl ? 1 : 0) <= 1, 'one thing moves at a time: ' + moving.map(c => c.name + ' ' + c.state) + (pl ? ' + plane' : ''));
      ok(new Set(out.map(c => c.name)).size === out.length, 'nobody is on screen twice');
      for (const c of out) if (c.state === 'EXITING' && c.seat === -1 && c.spot === -1) ok(c.lane === 'aisle', c.name + ' passes in the aisle');
      const mv = d.mover();
      const key = mv ? mv.kind + (mv.name ? ':' + mv.name : '') : null;
      if (key && key !== prevMover) order.push(key);
      prevMover = key;
    }
    for (let k = 1; k < order.length; k++) ok(order[k] !== order[k - 1], 'the same event twice in a row: ' + order.join());
    const firstPreview = scene.preview[0].includes(':') ? scene.preview[0] : 'pass:' + scene.preview[0];
    eq(order[0], firstPreview, 'the preview event comes first: ' + order.slice(0, 3).join());
    for (const n of scene.characters) ok(order.some(e => e.endsWith(':' + n)), n + ' came by in 30 minutes (seed ' + seed + '): ' + order.join());
    ok(order.includes('plane'), 'the plane came by in 30 minutes (seed ' + seed + ')');
    ok(order.some(e => e.startsWith('pass:')) && order.some(e => e.startsWith('arrive:')), 'both pass-bys and arrivals happen: ' + order.join());
    runs.push(order.join() + hashEvents(events));
  }
  ok(runs[0] !== runs[1], 'each opening is a different random run');
}

{
  // A long run (3 h of director time per seed): every real character that can sit completes a whole
  // sit cycle - walk in, turn, sit down, sit, stand up, turn away, walk out - a plain walker passes by;
  // and the event mix is reported.
  const mix = {};
  const cycles = {}, passes = {};
  for (const seed of [3, 11, 29]) {
    const { d, events } = makeDirector(REAL, seed);
    let prev = null;
    for (let i = 0; i < 3 * 3600 * 10; i++) {
      d.step(100);
      const mv = d.mover();
      const key = mv ? mv.kind : null;
      if (key && (!prev || prev.kind !== mv.kind || prev.name !== mv.name)) mix[key] = (mix[key] || 0) + 1;
      prev = mv;
    }
    const by = {};
    for (const e of events) (by[e.name] = by[e.name] || []).push(e.to);
    for (const e of events) if (/^walk_/.test(e.to) && e.from !== e.to) passes[e.name] = (passes[e.name] || 0) + 1;
    for (const n of scene.characters) {
      const seq = (by[n] || []).join(' ');
      const re = /walk_[lr] turn_[lr]_front(@\w+)? sit_down(@\w+)? sit_idle(@\w+)? .*?stand_up(@\w+)? turn_front_[lr](@\w+)? walk_[lr]/;
      if (re.test(seq)) cycles[n] = (cycles[n] || 0) + 1;
    }
  }
  for (const m of REAL) {
    if (B.canSit(m)) ok(cycles[m.name] >= 1, m.name + ' completed a full sit cycle in a long run');
    else ok(passes[m.name] >= 1, m.name + ' (a plain walker) passed by in a long run');
  }
  ok(mix.pass > 0 && mix.arrive > 0 && mix.leave > 0 && mix.plane > 0, 'event mix: ' + JSON.stringify(mix));
  console.log('  9 h of director time (3 seeds): event mix %s; full sit cycles %s', JSON.stringify(mix), JSON.stringify(cycles));
}

{
  // Debug requests keep the lock: an arrival asked for while something moves waits for it.
  const { d, events } = makeDirector(REAL, 8);
  for (let i = 0; i < 50; i++) d.step(100);
  ok(d.request('turtle', 'arrive') && !d.request('nobody', 'pass') && !d.request('turtle', 'dance'), 'request validates its input');
  let seated = false;
  for (let i = 0; i < 6000 && !seated; i++) {
    const out = d.step(100);
    ok(out.filter(c => MOVING.has(c.state)).length + (d.plane() ? 1 : 0) <= 1, 'a requested arrival keeps the lock');
    seated = out.some(c => c.name === 'turtle' && c.state === 'SEATED');
  }
  ok(seated, 'the requested turtle sat down');
  ok(d.request('turtle', 'leave'), 'request a leave');
  let gone = false;
  for (let i = 0; i < 6000 && !gone; i++) {
    const out = d.step(100);
    gone = !out.some(c => c.name === 'turtle') && events.some(e => e.name === 'turtle' && /^stand_up/.test(e.to));
  }
  ok(gone, 'the turtle stood up and left');
}

{
  // Faces (design doc 7.6): blinks happen and are short, expressions only where the frames have them,
  // a frame without the variant never shows a face, the face timers are deterministic and do not touch
  // the characters' own random sequence.
  const strip = m => ({ ...m, frames: m.frames.map(f => { const g = { ...f }; delete g.v; return g; }) });
  for (const w of REAL) ok(B.faceKinds(w).includes('blink'), w.name + ' offers a blink');
  function run(chars, seed, minutes) {
    const { d, events } = makeDirector(chars, seed);
    const faces = [];                           // per sample: name -> face of characters on screen
    const runs = {};                            // name -> [{face, ms}] finished face spells
    const cur = {};
    const byName = Object.fromEntries(chars.map(m => [m.name, m]));
    // a face only shows on frames that carry it: a spell that begins or ends at a change to a frame
    // without the variant (a cross-fade, a turn) is cut short there and not timed
    const carries = (c, face) => { const m = byName[c.name], f = m.frames[m.clips[c.clip].frames[c.frame]]; return !!(f && f.v && Number.isInteger(f.v[face])); };
    for (let i = 0; i < minutes * 60000 / B.TICK_MS; i++) {
      const out = d.step(B.TICK_MS);
      const seen = new Set();
      for (const c of out) {
        ok(typeof c.face === 'string', 'snapshot has a face field: ' + JSON.stringify(c));
        seen.add(c.name);
        const r = cur[c.name];
        if (r && r.face === c.face) r.ms += B.TICK_MS;
        else {
          if (r && r.face && !r.partial && carries(c, r.face)) (runs[c.name] = runs[c.name] || []).push(r);
          cur[c.name] = { face: c.face, ms: B.TICK_MS, partial: !r || (c.face && !carries(r.last, c.face)) };   // seen from its start only if it was on screen before
        }
        cur[c.name].last = c;
      }
      for (const n of Object.keys(cur)) if (!seen.has(n)) delete cur[n];   // went off screen: spell cut short
      faces.push(out.map(c => c.name + ':' + c.face + ':' + c.frame).join(','));
    }
    return { runs, faces, hash: hashEvents(events) };
  }
  const a = run(REAL, 5, 30);
  for (const w of REAL) {
    const r = a.runs[w.name] || [];
    const blinks = r.filter(x => x.face === 'blink');
    ok(blinks.length >= 3, w.name + ' blinked ' + blinks.length + ' times in 30 minutes');
    for (const b of blinks) ok(b.ms >= 100 && b.ms < 250, w.name + ' blink lasted ' + b.ms + ' ms');
    const kinds = B.faceKinds(w);
    for (const x of r) {
      ok(kinds.includes(x.face), w.name + ' showed a face it does not have: ' + x.face);
      if (x.face !== 'blink') ok(x.ms <= 1650, w.name + ' ' + x.face + ' lasted ' + x.ms + ' ms');
    }
  }
  // the old placeholder characters have no variants: their face is always ''
  const seatedOnly = run(full, 5, 10);
  ok(Object.keys(seatedOnly.runs).length === 0, 'no face on frames without a variant: ' + Object.keys(seatedOnly.runs));
  // deterministic, and the faces do not change who comes by when
  const b = run(REAL, 5, 30);
  eq(b.faces, a.faces, 'the same seed gives the same faces');
  const c = run(REAL.map(strip), 5, 30);
  ok(c.hash === a.hash, 'face variants do not change the clip sequence');
  // expressions do show up over a longer run (rare: every 15-40 s of the face clock)
  const long = run(REAL, 77, 120);
  const exprs = Object.values(long.runs).flat().filter(x => x.face !== 'blink');
  ok(exprs.length >= 1, 'an expression appeared in two hours: ' + exprs.length);
  // the debug hook holds a face
  const { d } = makeDirector(REAL, 3);
  let w = null;
  for (let i = 0; i < 20000 && !w; i++) w = d.step(100).find(x => x.name === 'rabbit' && x.state === 'EXITING');
  if (w) {
    ok(d.setFace('rabbit', 'smile') && d.step(25).find(x => x.name === 'rabbit').face === 'smile', 'setFace holds a face');
    ok(d.setFace('rabbit', 'laugh') && d.step(25).find(x => x.name === 'rabbit').face === '', 'a face the frame lacks is not shown');
    d.setFace('rabbit', null);
  }
  ok(!d.setFace('nobody', 'blink'), 'setFace refuses unknown characters');
}

{
  // A walker with hop clips (the penguin): now and then it hops in the middle of a pass. The hop starts and
  // ends on the walk (walk -> hop -> walk, on walk frame 0), and the drawn x never jumps: every 100 ms it moves
  // about as far as a walk or hop frame takes it, never backwards.
  const hoppers = REAL.filter(m => m.clips.hop_r && m.clips.hop_l);
  for (const m of hoppers) {
    for (const id of ['hop_r', 'hop_l']) {
      const c = m.clips[id], w = m.clips[c.from];
      ok(c.from === c.to && /^walk_[lr]$/.test(c.from) && !c.loop, m.name + ' ' + id + ' goes from a walk back to it');
      ok(c.frames[0] === w.frames[0] && c.frames[c.frames.length - 1] === w.frames[0], m.name + ' ' + id + ' starts and ends on walk frame 0');
      ok(c.advance >= w.advance, m.name + ' ' + id + ' moves at least as fast as the walk');
    }
    const { d, events } = makeDirector([m], 13);
    let hops = 0, passes = 0, prev = null, maxStep = 0;
    const fastest = Math.max(m.clips.walk_r.advance * m.clips.walk_r.fps, m.clips.hop_r.advance * m.clips.hop_r.fps);
    for (let i = 0; i < 2 * 3600 * 10; i++) {
      const c = d.step(100).find(x => x.name === m.name);
      if (!c || (c.state !== 'EXITING' && c.state !== 'ENTERING')) { prev = null; continue; }
      if (prev !== null) {
        const dx = Math.abs(c.drawX - prev);
        maxStep = Math.max(maxStep, dx);
        ok(dx <= fastest * 0.1 * 1.05 + 1e-6, m.name + ' jumps ' + dx.toFixed(1) + ' px in 100 ms (' + c.clip + ')');
      }
      prev = c.drawX;
    }
    for (let i = 1; i < events.length; i++) {
      const e = events[i];
      if (e.name !== m.name) continue;
      if (/^hop_/.test(e.to)) { hops++; ok(/^walk_/.test(e.from) && e.state === 'EXITING', m.name + ' hops only while passing: ' + JSON.stringify(e)); }
      if (/^hop_/.test(e.from)) ok(e.to === m.clips[e.from].to, m.name + ' goes back to its walk after a hop');
      if (/^walk_/.test(e.to) && !e.from) passes++;
    }
    ok(hops >= 1 && hops < passes, m.name + ' hopped in some passes, not all: ' + hops + ' hops in ' + passes + ' passes');
    console.log('  %s: %d hops in %d passes (2 h), largest move in 100 ms %s px', m.name, hops, passes, maxStep.toFixed(1));
  }
}

{
  // Seated faces and tempo (docs/LOUNGE_SCENE_DESIGN.md 7.9, art/README.md): what each pose faces, a blink on every
  // frame of every open-eyed seated loop, how often each character blinks in each activity, and a slow doze.
  const OK_FACING = { f: ['F', 'Fl', 'Fr'], l: ['L', 'Fl'] };
  const seatFacings = [...new Set(scene.seats.map(s => s.facing || 'f'))];
  const loopsOf = m => Object.entries(m.clips).filter(([id, c]) => c.loop && !B.WALKER_CLIPS.includes(id));
  const dur = c => c.frames.length / c.fps;
  // (seated life: the characters that can sit; a plain walker has none)
  for (const m of REAL.filter(m => B.canSit(m))) {
    // 1. the facing table: every pose of a facing has a recorded facing that the seats of that facing accept
    ok(m.poseInfo && typeof m.poseInfo === 'object', m.name + ' records what its poses face (poseInfo)');
    for (const f of B.sitFacings(m)) {
      ok(seatFacings.includes(f), m.name + ' has poses for a facing no seat has: ' + f);
      const suffix = f === 'f' ? '' : '@' + f;
      const posesHere = Object.keys(m.poses).filter(p => !p.startsWith('walk') && (suffix ? p.endsWith(suffix) : !p.includes('@')));
      ok(posesHere.length >= 3, m.name + '/' + f + ' has seated poses');
      for (const p of posesHere) {
        const rec = m.poseInfo[p];
        ok(rec, m.name + ' pose ' + p + ' has a recorded facing');
        for (const part of ['head', 'torso', 'legs']) ok(OK_FACING[f].includes(rec[part]), m.name + ' pose ' + p + ': ' + part + ' faces ' + rec[part] + ' but the seat faces ' + f);
        ok(rec.eyes === 'open' || rec.eyes === 'closed', m.name + ' pose ' + p + ' says whether its eyes are open');
      }
      // a clip never starts or ends on a pose of another facing
      for (const [id, c] of Object.entries(m.clips)) {
        if (!(suffix ? id.endsWith(suffix) : !id.includes('@')) || B.WALKER_CLIPS.includes(id)) continue;
        for (const p of [c.from, c.to]) if (!p.startsWith('walk')) ok(suffix ? p.endsWith(suffix) : !p.includes('@'), m.name + ' clip ' + id + ' touches pose ' + p + ' of another facing');
      }
    }
    // 2. blink coverage: every frame of every seated loop whose pose has open eyes can blink
    let covered = 0;
    for (const [id, c] of loopsOf(m)) {
      const rec = m.poseInfo[c.to];
      ok(rec, m.name + ' loop ' + id + ' ends on a pose with a record');
      if (rec.eyes === 'open') {
        for (const i of c.frames) ok(m.frames[i].v && Number.isInteger(m.frames[i].v.blink), m.name + ' ' + id + ' frame ' + i + ' has no blink');
        covered += c.frames.length;
      } else ok(/^doze/.test(id), m.name + ' ' + id + ' has closed eyes but is not a doze loop');
    }
    ok(covered > 0, m.name + ' has open-eyed loops');
    // 3. tempo: a breath takes about 4 s everywhere; a doze hold is 6-12 s, settling 1.5-2.5 s, a nod 0.6-1.3 s
    for (const [id, c] of loopsOf(m)) {
      if (/^doze_loop/.test(id)) ok(dur(c) >= 6 && dur(c) <= 12, m.name + ' ' + id + ' holds ' + dur(c) + ' s');
      else ok(dur(c) >= 3.5 && dur(c) <= 5, m.name + ' ' + id + ' breathes in ' + dur(c) + ' s');
    }
    for (const [id, c] of Object.entries(m.clips)) {
      if (/^doze_(in|out)/.test(id)) ok(dur(c) >= 1.5 && dur(c) <= 2.5, m.name + ' ' + id + ' lasts ' + dur(c) + ' s');
      if (/^doze_(nod|back)_/.test(id)) ok(dur(c) >= 0.6 && dur(c) <= 1.3, m.name + ' ' + id + ' lasts ' + dur(c) + ' s');
    }
  }
  // 4. simulated blink rate: three minutes of every activity the character has, seated, eyes open
  function blinkRate(m, kind, minOpenMs) {
    const { d } = makeDirector([m], 11);
    const clips = m.clips, facingClip = c => clips[c.clip];
    let open = 0, blinks = 0, prev = '', episodes = 0, last = '';
    for (let i = 0; i < 4 * 3600 * 1000 / 100 && open < minOpenMs; i++) {
      if (i % 50 === 0) d.force(m.name, kind);
      const c = d.step(100).find(x => x.name === m.name);
      if (!c) { prev = ''; continue; }
      const cl = facingClip(c);
      const inKind = c.state === 'SEATED' && c.activity === kind && cl.loop && m.poseInfo[cl.to] && m.poseInfo[cl.to].eyes === 'open';
      if (c.state === 'SEATED' && c.activity === kind && c.clip !== last) { last = c.clip; episodes++; }
      if (!inKind) { prev = ''; continue; }
      open += 100;
      if (c.face === 'blink' && prev !== 'blink') blinks++;
      prev = c.face;
    }
    return { open, blinks, interval: blinks ? open / blinks : Infinity, episodes };
  }
  for (const m of REAL.filter(m => B.canSit(m))) {
    const kinds = ['idle', ...['phone', 'call', 'eat'].filter(k => m.clips[k + '_loop'] || m.clips[k + '_loop@l'])];
    for (const kind of kinds) {
      const r = blinkRate(m, kind, 180000);
      ok(r.open >= 180000, m.name + ' ' + kind + ': only ' + r.open + ' ms of open-eyed seated time');
      ok(r.interval >= 2200 && r.interval <= 6000, m.name + ' ' + kind + ' blinks every ' + Math.round(r.interval) + ' ms on average (' + r.blinks + ' blinks in ' + r.open + ' ms)');
    }
  }
  // 5. a doze through the director: holds are whole wraps, nods come every 20-60 s, a leaving sleeper does not nod on
  for (const m of REAL) {
    if (!B.sitFacings(m).some(f => m.clips[B.clipAt('doze_loop', f)])) continue;
    const { d, events } = makeDirector([m], 5);
    for (let i = 0; i < 3 * 3600 * 1000 / 100; i++) { if (i % 20 === 0) d.force(m.name, 'doze'); d.step(100); }
    const seq = events.filter(e => /^doze/.test(e.to));
    ok(seq.length > 0, m.name + ' dozed');
    for (let i = 0; i + 1 < seq.length; i++) {
      const e = seq[i], n = seq[i + 1];
      if (/^doze_loop/.test(e.to)) {
        const held = (n.t - e.t) / 1000, wrap = dur(m.clips[e.to]);
        ok(held >= wrap - 0.2, m.name + ' ' + e.to + ' held ' + held + ' s, less than one wrap');
        ok(held <= 48 + wrap, m.name + ' ' + e.to + ' held ' + held + ' s');
      }
    }
    const nods = seq.filter(e => /^doze_nod_/.test(e.to));
    for (let i = 0; i + 1 < nods.length; i++) {
      const gap = (nods[i + 1].t - nods[i].t) / 1000;
      if (nods[i + 1].seat === nods[i].seat && gap < 200) ok(gap >= 18, m.name + ' nodded again after only ' + gap + ' s');
    }
    if (m.clips['doze_nod_b@l'] || m.clips['doze_nod_b']) ok(nods.length > 0, m.name + ' nods now and then');
  }
}

{
  // Determinism with the real characters: same seed, same history, whatever the step size.
  const run = (seed, dt, ms) => { const { d, events } = makeDirector(REAL, seed); for (let t = 0; t < ms; t += dt) d.step(dt); return hashEvents(events); };
  const h1 = run(7, 100, 3600e3);
  ok(h1 === run(7, 100, 3600e3) && h1 === run(7, 25, 3600e3) && h1 === run(7, 250, 3600e3), 'real characters: same seed, same history');
  ok(h1 !== run(8, 100, 3600e3), 'real characters: different seed, different history');
}

{
  // Shared timeline (7.9): every device derives the same episode from the server clock; an episode starts
  // with an empty room, ends with an empty room and lets nobody new in during its last minutes.
  const EP = 30 * 60000, QUIET = 5 * 60000;
  const real = scene.characters.map(n => JSON.parse(fs.readFileSync(path.join(ASSETS, 'chars', n, 'manifest.json'), 'utf8')));
  const T0 = Date.UTC(2026, 9, 21, 3, 17, 42);
  const e1 = B.sharedEpisode(T0, EP), e2 = B.sharedEpisode(T0, EP), nx = B.sharedEpisode(e1.endMs, EP);
  eq(e1, e2, 'the same server time gives the same episode');
  ok(e1.startMs % EP === 0 && e1.endMs - e1.startMs === EP && e1.elapsedMs === T0 - e1.startMs && e1.elapsedMs >= 0 && e1.elapsedMs < EP, 'episode slot arithmetic');
  ok(nx.slot === e1.slot + 1 && nx.startMs === e1.endMs && nx.elapsedMs === 0 && nx.seed !== e1.seed, 'the next episode starts where this one ends, with its own seed');
  eq(B.seoulMinuteOfDay(Date.UTC(2026, 9, 21, 0, 0)), 9 * 60, 'Seoul minute of day (UTC+9)');
  eq(B.seoulMinuteOfDay(Date.UTC(2026, 9, 21, 15, 30)), 30, 'Seoul minute of day wraps past midnight');

  const make = (startMs, seed) => {
    let d = null;
    const clock = () => startMs + (d ? d.time : 0);
    d = B.createDirector({
      seed, scene, characters: real, clock, minuteOfDay: () => B.seoulMinuteOfDay(clock()),
      solar: () => Sun.sunPosition(new Date(clock()), SEOUL[0], SEOUL[1]), episode: { lengthMs: EP, quietMs: QUIET },
    });
    return d;
  };
  let arrivalsSeen = 0;
  for (const startHour of [3, 13]) {                       // a night slot and a day slot
    for (let k = 0; k < 6; k++) {
      const start = Math.floor((Date.UTC(2026, 9, 21, startHour, 0) + k * EP * 7) / EP) * EP;
      const d = make(start, B.sharedEpisode(start, EP).seed);
      ok(d.step(0).length === 0 && !d.plane(), 'an episode starts with an empty room (' + startHour + 'h #' + k + ')');
      let before = new Set(), planeBefore = false;
      for (let t = 1000; t <= EP; t += 1000) {
        const snap = d.step(1000), on = new Set(snap.map(c => c.name)), pl = !!d.plane();
        if (t > EP - QUIET + 1000) {
          for (const n of on) ok(before.has(n), 'nobody new comes in during the quiet end of an episode: ' + n + ' at ' + t / 1000 + ' s');
          ok(!(pl && !planeBefore), 'no plane starts during the quiet end of an episode');
        }
        if (t > EP - QUIET && t <= EP - QUIET + 1000) ok(d.winding, 'the quiet end begins on time');
        if (t === EP - 60000) ok(on.size === 0 && !pl, 'the room is already empty a minute before an episode ends (' + startHour + 'h #' + k + '): ' + [...on]);
        for (const c of snap) if (c.state === 'ENTERING') arrivalsSeen++;
        before = on; planeBefore = pl;
      }
      ok(before.size === 0 && !d.plane() && !d.mover(), 'an episode ends with an empty room and nothing moving (' + startHour + 'h #' + k + '): ' + [...before]);
    }
  }
  ok(arrivalsSeen > 0, 'people do come during episodes');

  // the same moment looks the same however it was reached (fast-forward on opening vs watching live)
  const start = Math.floor(Date.UTC(2026, 9, 21, 12, 0) / EP) * EP, seed = B.sharedEpisode(start, EP).seed;
  const look = d => JSON.stringify(d.step(0).map(c => [c.name, c.clip, c.frame, Math.round(c.drawX), c.face, c.state]).concat([d.plane()]));
  const A = make(start, seed), Bd = make(start, seed), Cd = make(start, seed);
  A.advance(16 * 60000);                                    // opened 16 min into the episode
  for (let t = 0; t < 16 * 60; t++) Bd.step(1000);          // watched for 16 min, one frame per second
  for (let t = 0; t < 16 * 60 * 4; t++) Cd.step(250);       // watched at a different frame rate
  eq(look(A), look(Bd), 'fast-forward equals watching live (1 s steps)');
  eq(look(A), look(Cd), 'fast-forward equals watching live (250 ms steps)');
  A.advance(5 * 60000); for (let t = 0; t < 300; t++) Bd.step(1000);
  eq(look(A), look(Bd), 'staying in step after more time');
  // coming back after being away: a late fast-forward lands on the same state as never leaving
  const Late = make(start, seed); Late.advance(16 * 60000); Late.advance(5 * 60000);
  eq(look(Late), look(A), 'catching up in two parts equals one long run');
}

function eq(a, b, m) { checks++; assert.deepStrictEqual(a, b, m); }
console.log('verify_lounge_behavior OK (' + checks + ' checks)');
