/* Character behaviour for the lobby lounge scene (docs/LOUNGE_SCENE_DESIGN.md 7).
   Pure logic: no DOM, no timers. The caller feeds elapsed milliseconds to step() and draws
   what it returns. Every clip change happens on a shared pose node (clip.to === next clip.from);
   anything else throws. Randomness comes from a seeded PRNG so runs can be replayed. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeBehavior = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const REQUIRED_CLIPS = ['walk_r', 'walk_l', 'turn_r_front', 'turn_l_front', 'turn_front_r', 'turn_front_l',
    'sit_down', 'stand_up', 'sit_idle'];
  const TICK_MS = 25;                       // internal simulation step; results do not depend on the caller's dt
  const SEAT_SECONDS = [120, 360];
  const DURATIONS = {                       // seconds [min, max]
    idle: [6, 15], phone: [20, 60], call: [15, 40], eat: [30, 60], doze: [40, 120], chat: [20, 50],
  };
  const CHAT_SEGMENT_SECONDS = [4, 8];
  const ACTIVITY_KINDS = ['idle', 'phone', 'call', 'eat', 'sunglasses', 'fix_clothes', 'doze', 'chat'];
  const HOLD_TIMEOUT_MS = 8000;
  // Faces (docs/LOUNGE_SCENE_DESIGN.md 7.6): blinks for everyone, now and then a short expression for a
  // character whose frames carry it (manifest frame.v). Own PRNG stream, so the rest is unchanged.
  const FACE = {
    blinkEvery: [2200, 6000], blinkMs: [120, 170], doubleChance: 0.15, doubleGap: [110, 200],
    exprEvery: [15000, 40000], exprMs: [800, 1600], firstExpr: [6000, 30000],
  };
  const TARGET_RECHECK_MS = 10 * 60 * 1000;

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // A walker (manifest.walker) crosses the lounge: it needs nothing but its two walking clips. A
  // character with the full clip set can go to a seat; one with both (walker + full set, the real
  // animals) does either, one thing at a time.
  const WALKER_CLIPS = ['walk_r', 'walk_l'];
  const canSit = m => !!(m && m.clips) && REQUIRED_CLIPS.every(id => m.clips[id]);
  const canPass = m => !!(m && m.clips && m.walker) && WALKER_CLIPS.every(id => m.clips[id]);
  function isActive(manifest) { return canSit(manifest) || canPass(manifest); }
  // Movement lock (docs/LOUNGE_SCENE_DESIGN.md 7.7): the event that holds it after a quiet spell.
  const LEAVE_WAIT_MS = 60000;               // past its seat time a sitter is sent off within this

  // Face variants a manifest offers: the keys of its frames' "v" maps (e.g. blink, smile, laugh).
  function faceKinds(manifest) {
    const out = new Set();
    for (const f of (manifest && manifest.frames) || []) {
      if (f && f.v && typeof f.v === 'object') for (const k of Object.keys(f.v)) out.add(k);
    }
    return [...out].sort();
  }

  function createDirector(opts) {
    const scene = opts.scene;
    const seats = scene.seats.slice().sort((a, b) => a.x - b.x);
    const entries = scene.entries;
    const clock = opts.clock || Date.now;
    const minuteOfDay = opts.minuteOfDay || function () {
      const d = new Date(clock());
      return d.getHours() * 60 + d.getMinutes();
    };
    const solar = opts.solar || function () { return { elevation: 0 }; };
    const emit = opts.onEvent || null;
    const seed = opts.seed === undefined ? Date.now() : opts.seed;
    const rand = mulberry32(seed);
    const rnd = (lo, hi) => lo + (hi - lo) * rand();
    const faceRand = mulberry32((seed ^ 0x9e3779b9) >>> 0);
    const frnd = (lo, hi) => lo + (hi - lo) * faceRand();
    const pick = list => list[Math.floor(rand() * list.length)];

    const chars = (opts.characters || []).filter(isActive).map(m => ({
      name: m.name, clips: m.clips, walker: canPass(m), sitter: canSit(m), pass: m.pass || 'both', state: 'OFFSCREEN', seat: -1, x: 0, clip: null, total: 0, wraps: 0, leaving: false,
      walk: null, exitSide: null, seatedUntil: 0, activity: '', plan: [], stage: null, sunglassesUsed: false,
      holding: false, holdSince: 0, pending: null, chatRole: '', segEnd: 0, chatEnd: 0, chatSide: '',
      frames: Array.isArray(m.frames) ? m.frames : [], exprs: faceKinds(m).filter(k => k !== 'blink'),
      face: '', faceUntil: 0, nextBlink: 0, nextExpr: 0, secondBlink: false, isSecond: false, forcedFace: null,
    }));
    for (const c of chars) {
      c.nextBlink = frnd(300, FACE.blinkEvery[1]);
      c.nextExpr = frnd(FACE.firstExpr[0], FACE.firstExpr[1]);
    }
    const sitters = chars.filter(c => c.sitter), walkers = chars.filter(c => c.walker);
    const passEvery = Array.isArray(scene.passEvery) ? scene.passEvery : [40, 120];   // quiet seconds between events
    const seatOwner = seats.map(() => null);
    let now = 0, acc = 0, target = 0, nextTargetRoll = 0;
    // Movement lock (7.7): one thing moves at a time - a walker crossing, a sitter walking in, turning,
    // sitting down, standing up, turning away and walking out, or the plane taxiing past the window -
    // so moving layers never overlap. Seated people stay put and do not count. passEvery after the
    // mover has finished, the next event is picked at random (a pass-by, the plane, someone going to a
    // seat, someone leaving, or nobody for a while), never the same one twice in a row and never the
    // same character twice in a row. Each opening of the app starts a new random run. scene.preview lists
    // events to show first, right away: a name passes by, 'arrive:<name>' goes to a seat.
    const planes = scene.planes || null;
    const preview = (Array.isArray(scene.preview) ? scene.preview : []).map(p => (String(p).includes(':') ? String(p).split(':') : ['pass', String(p)]))
      .filter(([k, n]) => chars.some(c => c.name === n && (k === 'pass' ? c.walker : k === 'arrive' && c.sitter)));
    let nextEventAt = 0, lastEvent = null, lastWho = null, queue = [], plane = null, mover = null;

    // ------------------------------------------------------------------ time of day
    const isDay = () => { const m = minuteOfDay(); return m >= 7 * 60 && m < 23 * 60; };
    function rollTarget() {                  // people seated: 1-3 by day, 1-2 at night
      const t = isDay() ? 1 + Math.floor(rand() * 3) : 1 + Math.floor(rand() * 2);
      return Math.min(t, sitters.length, seats.length);
    }

    // ------------------------------------------------------------------ clips
    function startClip(c, id) {
      const clip = c.clips[id];
      if (!clip) throw new Error('missing clip ' + id + ' for ' + c.name);
      if (c.clip) {
        const prev = c.clips[c.clip];
        if (prev.to !== clip.from) {
          throw new Error('illegal transition ' + c.clip + ' (ends on ' + prev.to + ') -> ' + id + ' (starts on ' + clip.from + ') for ' + c.name);
        }
      }
      if (emit) emit({ type: 'clip', t: now, name: c.name, from: c.clip, to: id, state: c.state, activity: c.activity, seat: c.seat });
      c.clip = id; c.total = 0; c.wraps = 0;
    }
    const has = (c, ...ids) => ids.every(id => c.clips[id]);

    // ------------------------------------------------------------------ seats
    function freeSeats() { return seats.map((s, i) => i).filter(i => seatOwner[i] === null); }
    function chooseSeat() {
      const free = freeSeats();
      if (!free.length) return -1;
      const beside = free.filter(i => (i > 0 && seatOwner[i - 1] !== null) || (i < seats.length - 1 && seatOwner[i + 1] !== null));
      if (beside.length && rand() < 0.4) return pick(beside);
      return pick(free);
    }
    const nearSide = x => (x < (entries.left + entries.right) / 2 ? 'l' : 'r');

    // ------------------------------------------------------------------ walking
    function beginWalk(c, clipId, x0, dir, total) {
      c.walk = { x0, dir, total };
      c.x = x0;
      startClip(c, clipId);
    }

    function spawn(c, seatIdx) {
      const seat = seats[seatIdx];
      seatOwner[seatIdx] = c;
      c.seat = seatIdx;
      c.exitSide = null;
      const near = nearSide(seat.x);
      const side = rand() < 0.7 ? near : (near === 'l' ? 'r' : 'l');
      c.entrySide = side;
      c.sunglassesUsed = false;
      c.clip = null;
      c.state = 'ENTERING';
      c.activity = '';
      const id = side === 'l' ? 'walk_r' : 'walk_l';
      const clip = c.clips[id];
      const n = clip.frames.length;
      const cycle = n * clip.advance;
      if (side === 'l') {
        const cycles = Math.ceil((seat.x - entries.left) / cycle);
        beginWalk(c, id, seat.x - cycles * cycle, 1, cycles * n);
      } else {
        const cycles = Math.ceil((entries.right - seat.x) / cycle);
        beginWalk(c, id, seat.x + cycles * cycle, -1, cycles * n);
      }
    }

    // A walker crosses from one edge to the other and is gone; it reuses the leaving walk.
    function startPass(c) {
      const toRight = c.pass === 'r' || (c.pass !== 'l' && rand() < 0.5);
      c.seat = -1; c.activity = ''; c.clip = null; c.state = 'EXITING';
      beginWalk(c, toRight ? 'walk_r' : 'walk_l', toRight ? entries.left : entries.right, toRight ? 1 : -1, Infinity);
    }

    // ------------------------------------------------------------------ events and the movement lock
    const seatedNow = () => sitters.filter(c => c.state === 'SEATED');
    function release() {                     // the mover is done: a quiet spell, then the next event
      mover = null;
      nextEventAt = now + (queue.length ? rnd(2, 5) : rnd(passEvery[0], passEvery[1])) * 1000;
    }
    // The leave of a seated character: it finishes what it is doing (a loop ends at its next wrap,
    // an activity goes through its _out clip) and stands up at its next decision.
    function sendOff(c) {
      c.leaving = true;
      if (c.state === 'SEATED' && c.stage && c.stage.kind === 'loop') c.stage.until = 0;
      if (c.holding || c.pending) {          // drop a conversation that has not started
        const o = c.pending;
        unhold(c);
        if (o && o.pending === c) unhold(o);
      }
    }
    // Stop waiting for a conversation partner: back to a plain sit_idle loop that ends at its next wrap
    // (someone who chose the chat waits on sit_idle without a plan of its own).
    function unhold(x) {
      x.holding = false; x.pending = null;
      if (!x.stage) { x.plan = [{ kind: 'loop', clip: 'sit_idle', ms: 0, until: now }]; x.stage = x.plan[0]; x.total = 0; x.wraps = 0; }
    }
    function candidates() {
      const off = c => c.state === 'OFFSCREEN';
      const out = [];
      for (const c of walkers) if (off(c)) out.push(['pass', c, 1]);
      if (planes) out.push(['plane', null, 1]);
      out.push(['none', null, 1]);
      const seated = seatedNow();
      const free = freeSeats().length;
      if (free && seated.length < target) {
        const away = sitters.filter(off);
        for (const c of away) out.push(['arrive', c, (seated.length ? 2 : 6) / away.length]);
      }
      for (const c of seated) if (now >= c.seatedUntil && !c.leaving) out.push(['leave', c, 3]);
      return out;
    }
    const keyOf = (kind, c) => kind + (c ? ':' + c.name : '');
    function startEvent(kind, c, seatWish = -1) {
      if (kind === 'none') { nextEventAt = now + rnd(passEvery[0], passEvery[1]) * 1000; return; }   // a quiet spell
      lastEvent = keyOf(kind, c); lastWho = c ? c.name : null;
      if (kind === 'plane') { plane = { start: now, ms: planes.duration * 1000, right: rand() < 0.5 }; mover = { kind, c: null }; return; }
      mover = { kind, c };
      if (kind === 'pass') startPass(c);
      else if (kind === 'arrive') spawn(c, seatWish >= 0 ? seatWish : chooseSeat());
      else if (kind === 'leave') sendOff(c);
    }
    function tryEvent() {
      if (plane && now >= plane.start + plane.ms) { plane = null; release(); }
      if (mover || now < nextEventAt) return;
      // a queued event (the preview walkers, a debug request) goes first while it is still possible
      while (queue.length) {
        const [kind, name, wish] = queue.shift();
        const seatWish = Number.isInteger(wish) && seatOwner[wish] === null ? wish : -1;
        const c = chars.find(x => x.name === name);
        if (!c) continue;
        if (kind === 'pass' && c.walker && c.state === 'OFFSCREEN') return startEvent('pass', c);
        if (kind === 'arrive' && c.sitter && c.state === 'OFFSCREEN' && freeSeats().length) return startEvent('arrive', c, seatWish);
        if (kind === 'leave' && c.state === 'SEATED') return startEvent('leave', c);
      }
      let opts = candidates();
      // someone who has been due to leave for a while goes now; nobody seated: somebody comes
      const overdue = opts.filter(o => o[0] === 'leave' && now - o[1].seatedUntil >= LEAVE_WAIT_MS);
      if (overdue.length) return startEvent('leave', overdue[0][1]);
      if (!seatedNow().length && opts.some(o => o[0] === 'arrive')) opts = opts.filter(o => o[0] === 'arrive');
      const fresh = opts.filter(o => keyOf(o[0], o[1]) !== lastEvent && !(o[1] && o[1].name === lastWho));
      if (fresh.length) opts = fresh;
      let total = 0;
      for (const o of opts) total += o[2];
      let r = rand() * total, chosen = opts[opts.length - 1];
      for (const o of opts) { if (r < o[2]) { chosen = o; break; } r -= o[2]; }
      startEvent(chosen[0], chosen[1]);
    }

    // ------------------------------------------------------------------ seated activities
    function startStage(c, st) {
      c.stage = st;
      startClip(c, st.kind === 'chatloop' ? 'chat_' + c.chatRole + '_' + c.chatSide : st.clip);
      if (st.kind === 'loop') st.until = now + st.ms;
    }
    function runPlan(c, plan) {
      c.plan = plan;
      startStage(c, plan[0]);
    }
    function nextStage(c) {
      c.plan.shift();
      if (c.plan.length) startStage(c, c.plan[0]);
      else decide(c);
    }

    function duration(kind, c) {
      const [lo, hi] = DURATIONS[kind];
      const d = rnd(lo, hi);
      const remaining = (c.seatedUntil - now) / 1000;
      return remaining < d ? Math.max(lo, remaining) : d;
    }

    // Seat index of a chat partner who is sitting beside c and can be pulled into a conversation.
    function chatPartner(c) {
      const sideOf = (a, b) => (a < b ? 'r' : 'l');   // the left-hand sitter faces right
      const mine = (id, s) => id + s;
      const need = s => ['chat_in_', 'chat_talk_', 'chat_listen_', 'chat_out_'].map(p => mine(p, s));
      const options = [];
      for (const j of [c.seat - 1, c.seat + 1]) {
        const o = seatOwner[j];
        if (!o || o === c || o.state !== 'SEATED' || o.activity !== 'idle' || o.holding || o.pending || o.leaving) continue;
        if (has(c, ...need(sideOf(c.seat, j))) && has(o, ...need(sideOf(j, c.seat)))) options.push(o);
      }
      return options.length ? pick(options) : null;
    }

    function decide(c) {
      c.stage = null;
      if (c.leaving) {                       // its turn to move (the movement lock): stand up
        c.state = 'STAND_UP'; c.activity = '';
        startClip(c, 'stand_up');
        return;
      }
      const m = minuteOfDay();
      const night = m >= 23 * 60 || m < 7 * 60;
      const meal = (m >= 11 * 60 + 30 && m < 13 * 60 + 30) || (m >= 18 * 60 && m < 20 * 60);
      const deepNight = m < 5 * 60;
      const partner = chatPartner(c);
      const forced = c.forced; c.forced = null;
      const possible = {
        idle: true,
        phone: has(c, 'phone_in', 'phone_loop', 'phone_out'), call: has(c, 'call_in', 'call_loop', 'call_out'),
        eat: has(c, 'eat_in', 'eat_loop', 'eat_out'), sunglasses: has(c, 'sunglasses'), fix_clothes: has(c, 'fix_clothes'),
        doze: has(c, 'doze_in', 'doze_loop', 'doze_out'), chat: !!partner,
      };
      const options = [
        ['idle', 3],
        ['phone', has(c, 'phone_in', 'phone_loop', 'phone_out') ? 3 : 0],
        ['call', has(c, 'call_in', 'call_loop', 'call_out') ? (night ? 0.3 : 1) : 0],
        ['eat', has(c, 'eat_in', 'eat_loop', 'eat_out') ? (meal ? 3 : 0.3) : 0],
        ['sunglasses', has(c, 'sunglasses') && !c.sunglassesUsed && solar().elevation > 10 ? 1.5 : 0],
        ['fix_clothes', has(c, 'fix_clothes') ? 1 : 0],
        ['doze', has(c, 'doze_in', 'doze_loop', 'doze_out') ? (deepNight ? 3 : 0.2) : 0],
        ['chat', partner ? 4 : 0],
      ];
      let total = 0;
      for (const o of options) total += o[1];
      let r = rand() * total, kind = 'idle';
      for (const o of options) { if (r < o[1]) { kind = o[0]; break; } r -= o[1]; }
      if (forced && possible[forced]) kind = forced;
      c.activity = kind;
      if (kind === 'idle') {
        runPlan(c, [{ kind: 'loop', clip: 'sit_idle', ms: duration('idle', c) * 1000 }]);
      } else if (kind === 'sunglasses' || kind === 'fix_clothes') {
        if (kind === 'sunglasses') c.sunglassesUsed = true;
        runPlan(c, [{ kind: 'once', clip: kind }]);
      } else if (kind === 'chat') {
        // Both sitters wait on the resting pose, then start together (see resolveChats).
        c.activity = 'idle';
        c.plan = [];
        startClip(c, 'sit_idle');
        c.holding = true; c.holdSince = now; c.pending = partner;
        partner.pending = c;
      } else {
        runPlan(c, [{ kind: 'once', clip: kind + '_in' },
          { kind: 'loop', clip: kind + '_loop', ms: duration(kind, c) * 1000 },
          { kind: 'once', clip: kind + '_out' }]);
      }
    }

    function resolveChats() {
      for (const c of chars) {
        if (c.pending && c.holding && c.pending.holding && c.pending.pending === c) {
          const o = c.pending;
          const left = c.seat < o.seat ? c : o, right = left === c ? o : c;
          const limit = Math.min(left.seatedUntil, right.seatedUntil) - now;
          const [lo, hi] = DURATIONS.chat;
          const d = Math.max(lo, Math.min(rnd(lo, hi), limit / 1000));
          const seg = rnd(CHAT_SEGMENT_SECONDS[0], CHAT_SEGMENT_SECONDS[1]) * 1000;
          for (const [p, side, role] of [[left, 'r', 'talk'], [right, 'l', 'listen']]) {
            p.holding = false; p.pending = null;
            p.activity = 'chat'; p.chatSide = side; p.chatRole = role;
            p.chatEnd = now + d * 1000; p.segEnd = now + seg;
            runPlan(p, [{ kind: 'once', clip: 'chat_in_' + side }, { kind: 'chatloop' }, { kind: 'once', clip: 'chat_out_' + side }]);
          }
        }
      }
      for (const c of chars) {                // give up on a conversation that never lines up
        if (c.holding && now - c.holdSince > HOLD_TIMEOUT_MS) {
          const o = c.pending;
          c.holding = false; c.pending = null;
          if (o && o.pending === c) unhold(o);       // o keeps looping and decides at its next wrap
          c.plan = [{ kind: 'loop', clip: 'sit_idle', ms: 0 }]; c.stage = c.plan[0];
          c.stage.until = now; c.total = 0; c.wraps = 0;
        }
      }
    }

    // A clip finished (one-shot) or a loop wrapped, while seated.
    function seatedBoundary(c, ended) {
      const st = c.stage;
      if (!st) return;
      if (st.kind === 'chatloop') {
        if (now >= c.chatEnd) { nextStage(c); return; }
        if (now >= c.segEnd) {
          c.chatRole = c.chatRole === 'talk' ? 'listen' : 'talk';
          c.segEnd = now + rnd(CHAT_SEGMENT_SECONDS[0], CHAT_SEGMENT_SECONDS[1]) * 1000;
          startClip(c, 'chat_' + c.chatRole + '_' + c.chatSide);
        }
        return;
      }
      if (st.kind === 'loop') {
        if (c.pending && c.activity === 'idle' && !ended) { c.holding = true; c.holdSince = now; c.total = 0; c.wraps = 0; return; }
        if (now < st.until) return;
      }
      nextStage(c);
    }

    function onClipEnd(c) {                   // one-shot clip finished
      switch (c.state) {
        case 'TURN_IN': c.state = 'SIT_DOWN'; startClip(c, 'sit_down'); break;
        case 'SIT_DOWN':
          c.state = 'SEATED';
          c.seatedUntil = now + rnd(SEAT_SECONDS[0], SEAT_SECONDS[1]) * 1000;
          if (mover && mover.c === c) release();       // seated: it no longer moves
          decide(c);
          break;
        case 'SEATED': seatedBoundary(c, true); break;
        case 'STAND_UP': {
          const near = nearSide(seats[c.seat].x);
          c.exitSide = rand() < 0.7 ? near : (near === 'l' ? 'r' : 'l');
          seatOwner[c.seat] = null;
          c.state = 'TURN_OUT';
          startClip(c, c.exitSide === 'l' ? 'turn_front_l' : 'turn_front_r');
          break;
        }
        case 'TURN_OUT': {
          c.state = 'EXITING';
          const id = c.exitSide === 'l' ? 'walk_l' : 'walk_r';
          beginWalk(c, id, seats[c.seat].x, c.exitSide === 'l' ? -1 : 1, Infinity);
          break;
        }
        default: break;
      }
    }

    function tickChar(c) {
      if (c.state === 'OFFSCREEN' || c.holding) return;
      const clip = c.clips[c.clip];
      const n = clip.frames.length;
      c.total += TICK_MS / 1000 * clip.fps;
      if (c.state === 'ENTERING') {
        const steps = Math.min(Math.floor(c.total), c.walk.total);
        c.x = c.walk.x0 + c.walk.dir * clip.advance * steps;
        if (steps >= c.walk.total) {
          c.x = seats[c.seat].x;
          c.state = 'TURN_IN';
          startClip(c, c.entrySide === 'l' ? 'turn_r_front' : 'turn_l_front');
        }
        return;
      }
      if (c.state === 'EXITING') {
        c.x = c.walk.x0 + c.walk.dir * clip.advance * Math.floor(c.total);
        if ((c.walk.dir < 0 && c.x <= entries.left) || (c.walk.dir > 0 && c.x >= entries.right)) {
          c.state = 'OFFSCREEN'; c.clip = null; c.seat = -1; c.activity = ''; c.walk = null; c.leaving = false;
          if (mover && mover.c === c) release();
        }
        return;
      }
      if (!clip.loop) {
        if (c.total >= n) onClipEnd(c);
      } else {
        const wraps = Math.floor(c.total / n);
        if (wraps > c.wraps) {
          c.wraps = wraps;
          if (c.state === 'SEATED') seatedBoundary(c, false);
        }
      }
    }

    // ------------------------------------------------------------------ faces
    function tickFace(c) {
      if (c.face && now >= c.faceUntil) {
        const was = c.face;
        c.face = '';
        if (was === 'blink' && c.secondBlink) {          // a double blink: the second one follows right away
          c.secondBlink = false; c.isSecond = true;
          c.nextBlink = now + frnd(FACE.doubleGap[0], FACE.doubleGap[1]);
        } else c.nextBlink = now + frnd(FACE.blinkEvery[0], FACE.blinkEvery[1]);
      }
      if (c.face) return;
      if (c.exprs.length && now >= c.nextExpr) {
        c.face = c.exprs[Math.floor(faceRand() * c.exprs.length)];
        c.faceUntil = now + frnd(FACE.exprMs[0], FACE.exprMs[1]);
        c.nextExpr = c.faceUntil + frnd(FACE.exprEvery[0], FACE.exprEvery[1]);
        c.secondBlink = false; c.isSecond = false;
      } else if (now >= c.nextBlink) {
        c.face = 'blink';
        c.faceUntil = now + frnd(FACE.blinkMs[0], FACE.blinkMs[1]);
        if (c.isSecond) c.isSecond = false;
        else c.secondBlink = faceRand() < FACE.doubleChance;
      }
    }
    // The face drawn on atlas frame idx: '' unless that frame has the variant.
    function faceOn(c, idx) {
      const face = c.forcedFace !== null ? c.forcedFace : c.face;
      const f = c.frames[idx];
      return face && f && f.v && Number.isInteger(f.v[face]) ? face : '';
    }

    function tick() {
      now += TICK_MS;
      for (const c of chars) tickFace(c);
      if (now >= nextTargetRoll) { target = rollTarget(); nextTargetRoll = now + TARGET_RECHECK_MS; }
      for (const c of chars) tickChar(c);
      resolveChats();
      tryEvent();
    }

    // ------------------------------------------------------------------ warm start
    function warmStart() {
      for (const c of chars) {
        c.state = 'OFFSCREEN'; c.clip = null; c.seat = -1; c.activity = ''; c.plan = []; c.stage = null;
        c.holding = false; c.pending = null; c.walk = null; c.leaving = false;
      }
      for (let i = 0; i < seatOwner.length; i++) seatOwner[i] = null;
      target = rollTarget();
      nextTargetRoll = now + TARGET_RECHECK_MS;
      nextEventAt = now + rnd(1, 4) * 1000; lastEvent = null; lastWho = null; plane = null; mover = null;   // the first one comes soon
      queue = preview.map(e => e.slice());
      // half the target (rounded up) already seated; the preview characters are kept free for their turn
      const pool = sitters.filter(c => !preview.some(e => e[1] === c.name));
      const count = Math.min(Math.ceil(target / 2), pool.length, seats.length);
      for (let k = 0; k < count; k++) {
        const c = pool.splice(Math.floor(rand() * pool.length), 1)[0];
        const idx = chooseSeat();
        seatOwner[idx] = c;
        c.seat = idx; c.x = seats[idx].x; c.state = 'SEATED'; c.activity = 'idle'; c.sunglassesUsed = false;
        c.clip = null;
        startClip(c, 'sit_idle');
        c.total = rand() * c.clips.sit_idle.frames.length;         // random point in the loop
        c.wraps = Math.floor(c.total / c.clips.sit_idle.frames.length);
        c.plan = [{ kind: 'loop', clip: 'sit_idle', ms: rnd(DURATIONS.idle[0], DURATIONS.idle[1]) * 1000 }];
        c.plan[0].until = now + c.plan[0].ms;
        c.stage = c.plan[0];
        c.seatedUntil = now + rnd(20, 300) * 1000;
      }
    }

    // ------------------------------------------------------------------ output
    function snapshot() {
      const out = [];
      for (const c of chars) {
        if (c.state === 'OFFSCREEN') continue;
        const clip = c.clips[c.clip];
        const n = clip.frames.length;
        let frame = c.holding ? 0 : (clip.loop ? Math.floor(c.total) % n : Math.min(Math.floor(c.total), n - 1));
        const switchAt = Number.isInteger(clip.laneSwitchAt) ? clip.laneSwitchAt : Math.floor(n / 2);
        let lane = 'aisle', x = c.x;
        if (c.state === 'SEATED') lane = 'seat';
        else if (c.state === 'SIT_DOWN') lane = frame >= switchAt ? 'seat' : 'aisle';
        else if (c.state === 'STAND_UP') lane = frame >= switchAt ? 'aisle' : 'seat';
        if (c.state !== 'ENTERING' && c.state !== 'EXITING') x = seats[c.seat].x;
        // where to draw: the walk advances in whole steps, the picture glides between them
        let drawX = x;
        if (c.walk && (c.state === 'ENTERING' || c.state === 'EXITING')) {
          const t = c.total + acc / 1000 * clip.fps;
          drawX = c.walk.x0 + c.walk.dir * clip.advance * (c.state === 'ENTERING' ? Math.min(t, c.walk.total) : t);
        }
        out.push({ name: c.name, clip: c.clip, frame, x, drawX, lane, mirrored: false, state: c.state,
          face: faceOn(c, clip.frames[Math.min(frame, n - 1)]),
          activity: c.activity, seat: c.seat >= 0 && seatOwner[c.seat] === c ? scene.seats.indexOf(seats[c.seat]) : -1,
          spot: c.seat >= 0 ? scene.seats.indexOf(seats[c.seat]) : -1 });   // seat it is heading to or leaving, even once released
      }
      return out;
    }

    warmStart();

    return {
      step(dtMs) {
        acc += Math.max(0, dtMs);
        while (acc >= TICK_MS) { acc -= TICK_MS; tick(); }
        return snapshot();
      },
      warmStart() { acc = 0; warmStart(); return snapshot(); },
      // The plane taxiing past the window right now: {u: 0..1 along its run, right: heading right}, or null.
      plane() {
        if (!plane) return null;
        const u = (now + acc - plane.start) / plane.ms;
        return u >= 0 && u <= 1 ? { u, right: plane.right } : null;
      },
      // Debug helper: make `name` do `kind` at its next decision. A character who is away is called to a
      // seat as the next event (right away when nothing is moving; otherwise as soon as the mover is done -
      // the movement lock still holds). Returns false when there is no such character, it cannot sit,
      // the activity is unknown or no seat is free.
      force(name, kind) {
        const c = chars.find(x => x.name === name);
        if (!c || !c.sitter || !ACTIVITY_KINDS.includes(kind)) return false;
        if (c.state === 'OFFSCREEN') {
          if (!freeSeats().length) return false;
          queue.unshift(['arrive', c.name]);
          if (!mover) nextEventAt = now;
        }
        c.forced = kind;
        if (c.state === 'SEATED' && c.stage && c.stage.kind === 'loop' && c.activity === 'idle') c.stage.until = 0;
        return true;
      },
      // Debug helpers: queue an event for `name` - 'pass' (walk across), 'arrive' (go to a seat; seatIndex
      // into scene.seats picks the seat when it is free) or 'leave' (a seated one stands up and goes) - as the
      // next one, right away when nothing moves. false if unknown.
      request(name, kind, seatIndex) {
        const c = chars.find(x => x.name === name);
        if (!c || !['pass', 'arrive', 'leave'].includes(kind)) return false;
        if ((kind === 'pass' && !c.walker) || (kind !== 'pass' && !c.sitter)) return false;
        const wish = Number.isInteger(seatIndex) && scene.seats[seatIndex] ? seats.indexOf(scene.seats[seatIndex]) : -1;
        queue.unshift([kind, c.name, wish]);
        if (!mover) nextEventAt = now;
        return true;
      },
      // What holds the movement lock: {kind: 'pass'|'arrive'|'leave'|'plane', name} or null.
      mover() { return mover ? { kind: mover.kind, name: mover.c ? mover.c.name : null } : null; },
      get lastEvent() { return lastEvent; },
      // Debug helper: hold `name`'s face on a variant ('blink', 'smile', ...), or '' for the plain face;
      // null gives the face back to the timers. Returns false for an unknown character.
      setFace(name, face) {
        const c = chars.find(x => x.name === name);
        if (!c) return false;
        c.forcedFace = face === null || face === undefined ? null : String(face);
        return true;
      },
      faceKinds(name) { const c = chars.find(x => x.name === name); return c ? ['blink', ...c.exprs] : []; },
      get now() { return now; },
      get target() { return target; },
      characterNames() { return chars.map(c => c.name); },
    };
  }

  return { createDirector, mulberry32, isActive, canSit, canPass, faceKinds, REQUIRED_CLIPS, WALKER_CLIPS, ACTIVITY_KINDS, TICK_MS, DURATIONS, SEAT_SECONDS, FACE };
});
