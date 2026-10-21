'use strict';
// docs/LOUNGE_SCENE_DESIGN.md 13-14: weather.js (code mapping, cache, failures, rounding, off switch, polling),
// the cloud factor of the lighting, the rain slant and the taxiing plane's lane geometry, and the
// director's lane choice (deterministic, a run keeps the movement lock for its lane's duration).
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const W = require(path.join(__dirname, '../web/lounge/weather.js'));
const Light = require(path.join(__dirname, '../web/lounge/lighting.js'));
const R = require(path.join(__dirname, '../web/lounge/renderer.js'));
const B = require(path.join(__dirname, '../web/lounge/behavior.js'));
const Sun = require(path.join(__dirname, '../web/lounge/sun.js'));
const ASSETS = path.join(__dirname, '../web/lounge/assets');
const scene = JSON.parse(fs.readFileSync(path.join(ASSETS, 'scene.json'), 'utf8'));
let checks = 0;
const ok = (c, m) => { checks++; if (!c) throw new Error(m); };
const eq = (a, b, m) => { checks++; assert.deepStrictEqual(a, b, m); };
const near = (a, b, tol, m) => { checks++; assert(Math.abs(a - b) <= tol, `${m}: got ${a}, want ${b}`); };

// ---------------------------------------------------------------- WMO code mapping
{
  const kind = (code, extra) => { const c = W.fromCurrent(Object.assign({ weather_code: code, cloud_cover: code >= 3 ? 100 : 20 }, extra)); return c.kind + '/' + c.intensity + (c.thunder ? '/thunder' : ''); };
  const table = {
    0: 'clear/none', 1: 'clear/none', 3: 'cloudy/none', 45: 'fog/moderate', 48: 'fog/heavy',
    51: 'rain/light', 53: 'rain/light', 55: 'rain/moderate', 56: 'rain/light', 57: 'rain/moderate',
    61: 'rain/light', 63: 'rain/moderate', 65: 'rain/heavy', 66: 'rain/light', 67: 'rain/moderate',
    71: 'snow/light', 73: 'snow/light', 75: 'snow/heavy', 77: 'snow/light',
    80: 'rain/light', 81: 'rain/moderate', 82: 'rain/heavy', 85: 'snow/light', 86: 'snow/heavy',
    95: 'rain/heavy/thunder', 96: 'rain/heavy/thunder', 99: 'rain/heavy/thunder',
  };
  for (const [code, want] of Object.entries(table)) eq(kind(Number(code)), want, 'WMO ' + code);
  eq(W.fromCurrent({ weather_code: 2, cloud_cover: 80 }).kind, 'cloudy', 'partly cloudy with a lot of cloud');
  eq(W.fromCurrent({ weather_code: 2, cloud_cover: 30 }).kind, 'clear', 'partly cloudy with little cloud');
  eq(W.fromCurrent({ weather_code: 61, rain: 6 }).intensity, 'heavy', 'measured rain raises light rain');
  eq(W.fromCurrent({ weather_code: 61, rain: 1.5 }).intensity, 'moderate', 'measured rain raises light rain a step');
  eq(W.fromCurrent({ weather_code: 73, snowfall: 0.8 }).intensity, 'heavy', 'heavy snowfall');
  eq(W.fromCurrent({ weather_code: 999, cloud_cover: 95 }).kind, 'cloudy', 'unknown code: only the cloud cover counts');
  eq(W.fromCurrent({}).kind, 'clear', 'empty block is clear');
  eq(W.fromCurrent(null).kind, 'clear', 'null block is clear');
  ok(W.fromCurrent({ weather_code: 63 }).cloud >= 0.9, 'a rainy sky is covered');
  near(W.fromCurrent({ weather_code: 0, cloud_cover: 0 }).cloud, 0, 1e-9, 'clear sky has no cloud');
  const wind = W.fromCurrent({ weather_code: 61, wind_speed_10m: 22.5, wind_direction_10m: 370 });
  eq([wind.windSpeed, wind.windDir], [22.5, 10], 'wind speed and direction (wrapped)');
  eq(W.synthetic('rain', 'thunder').thunder, true, 'debug thunder');
  eq(W.synthetic('snow', 'moderate').intensity, 'light', 'snow has no moderate');
  eq(W.synthetic('nonsense').kind, 'clear', 'debug nonsense');
}

// ---------------------------------------------------------------- controller
const memStorage = (init) => { const m = new Map(Object.entries(init || {})); return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), m }; };
const reply = (cur, status) => async () => ({ ok: (status || 200) < 400, status: status || 200, json: async () => ({ current: cur }) });
function rig(opts) {
  opts = opts || {};
  const clock = { t: 1e12 }, calls = [], changes = [], timers = [];
  const storage = opts.storage || memStorage();
  const w = W.createWeather({
    fetch: opts.fetch ? (url, o) => { calls.push(url); return opts.fetch(url, o); } : null,
    storage, now: () => clock.t, getPlace: () => opts.place || { lat: 37.56654, lon: 126.97796 },
    onChange: c => changes.push(c), isVisible: () => opts.visible !== false,
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; }, clearTimeout: () => {},
  });
  return { w, clock, calls, changes, storage, timers };
}
const settle = () => new Promise(r => setTimeout(r, 5));
(async () => {
  // rounding: the place goes out with two decimals only
  {
    const r = rig({ fetch: reply({ weather_code: 61 }) });
    await r.w.start();
    eq(r.calls.length, 1, 'one request');
    const u = new URL(r.calls[0]);
    eq(u.origin + u.pathname, 'https://api.open-meteo.com/v1/forecast', 'endpoint');
    eq([u.searchParams.get('latitude'), u.searchParams.get('longitude')], ['37.57', '126.98'], 'coordinates rounded to 2 decimals');
    eq(u.searchParams.get('current'), 'weather_code,rain,showers,snowfall,cloud_cover,wind_speed_10m,wind_direction_10m,is_day', 'fields');
    ok(!/37\.566|126\.977/.test(r.calls[0]), 'no unrounded coordinate in the URL');
    eq(r.w.get().kind, 'rain', 'rain applied');
    eq(r.changes.length, 1, 'onChange once');
  }
  // cache: fresh answers are used without a request, expired ones fetch again, stale ones show meanwhile
  {
    const r = rig({ fetch: reply({ weather_code: 75 }) });
    await r.w.start();
    const saved = r.storage.getItem(W.CACHE_KEY);
    ok(saved && JSON.parse(saved).cond.kind === 'snow', 'cache written');
    const r2 = rig({ fetch: reply({ weather_code: 0 }), storage: r.storage });
    r2.clock.t = r.clock.t + 10 * 60000;
    await r2.w.start();
    eq(r2.calls.length, 0, 'fresh cache: no request');
    eq(r2.w.get().kind, 'snow', 'fresh cache shown at once');
    const r3 = rig({ fetch: reply({ weather_code: 0 }), storage: r.storage });
    r3.clock.t = r.clock.t + 16 * 60000;
    r3.w.init();
    eq(r3.w.get().kind, 'snow', 'a stale answer shows while the new one is fetched');
    await r3.w.start();
    eq(r3.calls.length, 1, 'expired cache: one request');
    eq(r3.w.get().kind, 'clear', 'new answer replaces the stale one');
    const r4 = rig({ fetch: reply({ weather_code: 0 }), storage: r.storage });
    r4.clock.t = r.clock.t + 4 * 3600000;
    r4.w.init();
    eq(r4.w.get().kind, 'clear', 'an answer older than 3 hours is not used');
    const r5 = rig({ fetch: reply({ weather_code: 0 }), storage: r.storage, place: { lat: 35.18, lon: 129.07 } });
    r5.clock.t = r.clock.t + 60000;
    await r5.w.start();
    eq(r5.calls.length, 1, 'another place does not use the cache');
  }
  // failures are silent: network error, HTTP error, bad JSON, missing block, thrown fetch
  {
    const bad = [
      ['network error', async () => { throw new Error('offline'); }], ['HTTP 403', reply({}, 403)],
      ['no current block', async () => ({ ok: true, status: 200, json: async () => ({}) })],
      ['bad json', async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('x'); } })],
      ['no weather code', reply({ cloud_cover: 50 })], ['sync throw', () => { throw new Error('boom'); }],
    ];
    for (const [name, f] of bad) {
      const r = rig({ fetch: f });
      const got = await r.w.start();
      eq(got.kind, 'clear', name + ': clear stays');
      eq(r.changes.length, 0, name + ': no change reported');
      eq(r.storage.getItem(W.CACHE_KEY), null, name + ': nothing cached');
    }
    // after a good answer a later failure keeps the last known weather
    let fail = false;
    const r = rig({ fetch: (u, o) => (fail ? Promise.reject(new Error('x')) : reply({ weather_code: 65 })(u, o)) });
    await r.w.start();
    fail = true; r.clock.t += 20 * 60000;
    eq((await r.w.refresh(true)).kind, 'rain', 'last known weather kept after a failure');
    eq(r.timers.length > 0, true, 'a retry is scheduled');
    // a corrupt cache entry is ignored
    const r2 = rig({ fetch: reply({ weather_code: 0 }), storage: memStorage({ [W.CACHE_KEY]: '{oops' }) });
    eq(r2.w.init(), false, 'corrupt cache ignored');
    // no localStorage at all still works
    const r3 = rig({ fetch: reply({ weather_code: 71 }), storage: { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } } });
    eq((await r3.w.start()).kind, 'snow', 'works without storage');
  }
  // off switch: nothing fetched, clear
  {
    const r = rig({ fetch: reply({ weather_code: 65 }), storage: memStorage({ [W.OFF_KEY]: '1' }) });
    const got = await r.w.start();
    eq([got.kind, r.calls.length], ['clear', 0], 'off switch: no request, clear');
    eq(r.w.enabled(), false, 'enabled() false');
    r.w.setEnabled(true); await settle();
    eq([r.storage.getItem(W.OFF_KEY), r.calls.length, r.w.get().kind], ['0', 1, 'rain'], 'switched on again: fetches');
    r.w.setEnabled(false);
    eq(r.w.get().kind, 'clear', 'switched off again: clear');
    const n = r.calls.length; r.clock.t += 3600000; await r.w.refresh(true);
    eq(r.calls.length, n, 'switched off: no more requests');
  }
  // debug override
  {
    const r = rig({ fetch: reply({ weather_code: 0 }) });
    await r.w.start();
    r.w.setOverride('rain', 'heavy');
    eq([r.w.get().kind, r.w.get().intensity], ['rain', 'heavy'], 'override wins');
    r.w.setOverride(null);
    eq(r.w.get().kind, 'clear', 'override cleared');
  }
  // polling: every 15 minutes while visible; while hidden it waits until the page is back
  {
    let code = 0;
    const r = rig({ fetch: async () => ({ ok: true, status: 200, json: async () => ({ current: { weather_code: code } }) }) });
    await r.w.start();
    eq(r.timers[r.timers.length - 1].ms, W.FRESH_MS, 'poll period is 15 minutes');
    code = 61; r.clock.t += W.FRESH_MS + 1;
    r.timers[r.timers.length - 1].fn(); await settle();
    eq(r.calls.length, 2, 'poll fetched again');
    eq(r.w.get().kind, 'rain', 'poll changed the weather');
    const h = rig({ fetch: reply({ weather_code: 61 }), visible: false });
    await h.w.start();
    h.clock.t += W.FRESH_MS + 1;
    h.timers[h.timers.length - 1].fn(); await settle();
    eq(h.calls.length, 1, 'hidden page: no poll');
  }

  // ---------------------------------------------------------------- lighting: the cloud factor
  {
    const L = Light.lighting(30);
    ok(Light.withWeather(L, 0) === L && Light.withWeather(L, undefined) === L, 'no cloud: the very same object');
    near(Light.sunTransmit(0), 1, 1e-9, 'clear sky passes all sun'); near(Light.sunTransmit(0.5), 1, 1e-9, 'half cover still passes it');
    near(Light.sunTransmit(1), 0, 1e-9, 'overcast passes none');
    ok(Light.sunTransmit(0.7) > Light.sunTransmit(0.9), 'sun falls with cloud');
    const o = Light.withWeather(L, 1);
    ok(o.ambientStr > L.ambientStr, 'overcast room is dimmer (stronger ambient multiply)');
    ok(parseInt(o.ambient.slice(5, 7), 16) >= parseInt(o.ambient.slice(1, 3), 16) - 40 && o.ambient !== L.ambient, 'ambient changes');
    const b = (h, i) => parseInt(h.slice(i, i + 2), 16);
    ok(b(o.ambient, 5) - b(o.ambient, 1) > b(L.ambient, 5) - b(L.ambient, 1), 'ambient is cooler (more blue than red)');
    ok(o.indoorA > 0 && o.stars === 0 && o.lamp >= L.lamp, 'wash, no stars, lamps up');
    eq(Light.plateGrade(30), '#ffffff', 'plate untouched by day');
    ok(Light.plateGrade(-20) !== '#ffffff' && b(Light.plateGrade(-20), 1) < 80, 'plate dark at night');
    // direct sun: the renderer's directLight takes the cloud factor
    const rel = 0, h = 40;
    near(R.directLight(rel, h), R.directLight(rel, h, 0), 1e-12, 'cloud 0 = no argument');
    ok(R.directLight(rel, h, 0) > 0.9, 'clear: direct sun');
    near(R.directLight(rel, h, 1), 0, 1e-9, 'overcast: no direct sun');
    ok(R.directLight(rel, h, 0.75) < R.directLight(rel, h, 0.5), 'direct falls with cloud');
    // lighting() itself is unchanged by weather (the table tests stay valid)
    eq(Object.keys(L).sort().join(), 'ambient,ambientStr,city,dayness,h,horizonAway,horizonSun,lamp,stars,sunColor,zenith', 'lighting() keys');
  }

  // ---------------------------------------------------------------- rain slant from the wind
  {
    const f = scene.windowFacing;
    const toRight = (f + 90 + 180) % 360;            // wind coming from where it blows toward the screen's right
    ok(R.windSlant(40, toRight, f) > 0.3, 'strong wind toward the right slants right');
    ok(R.windSlant(40, (toRight + 180) % 360, f) < -0.3, 'toward the left slants left');
    ok(R.windSlant(0, 0, f) < 0 && R.windSlant(0, 0, f) > -0.2, 'calm: a small default tilt');
    for (const s of [0, 10, 60, 200]) for (let d = 0; d < 360; d += 45) ok(Math.abs(R.windSlant(s, d, f)) <= 0.55, 'slant bounded');
  }

  // ---------------------------------------------------------------- taxi lanes
  {
    const pl = scene.planes, win = scene.window, aspect = 922 / 400;
    ok(pl.lanes.length === 2, 'two lanes');
    for (let lane = 0; lane < pl.lanes.length; lane++) {
      for (const right of [true, false]) {
        let prev = null;
        for (let i = 0; i <= 100; i++) {
          const q = R.planePose(pl, lane, right, i / 100, aspect, win);
          ok(q.h > 80 && q.h < pl.ref.h * 1.05, 'height in range ' + q.h);
          near(q.y, pl.horizon + q.s * (pl.ref.y - pl.horizon), 1e-6, 'wheel line follows the scale');
          near(q.h, pl.ref.h * q.s, 1e-6, 'height follows the scale');
          ok(q.y > pl.horizon + 60 && q.y < pl.ref.y + 1, 'wheels on the apron, above the sofa line: ' + q.y);
          if (prev) {
            ok(q.y >= prev.y - 1e-9, 'the plane only comes nearer along its run');
            ok(q.haze <= prev.haze + 1e-9, 'haze falls as it comes nearer');
            ok(right ? q.x >= prev.x - 1e-9 : q.x <= prev.x + 1e-9, 'moves in its heading');
          }
          prev = q;
        }
        const a = R.planePose(pl, lane, right, 0, aspect, win), z = R.planePose(pl, lane, right, 1, aspect, win);
        const half = (q) => 0.5 * aspect * q.h;
        ok(right ? a.x + half(a) < win.x : a.x - half(a) > win.x + win.w, 'starts fully outside the glass');
        ok(right ? z.x - half(z) > win.x + win.w : z.x + half(z) < win.x, 'ends fully outside the glass');
        // the wheel line is straight on the screen: y is linear in x
        const m = R.planePose(pl, lane, right, 0.5, aspect, win), t = (m.x - a.x) / (z.x - a.x);
        near(m.y, a.y + (z.y - a.y) * t, 1e-6, 'wheels run along a straight line');
        // screen speed follows the scale: ground speed (dx / s) is constant apart from the ease
        const e1 = R.planePose(pl, lane, right, 0.45, aspect, win), e2 = R.planePose(pl, lane, right, 0.46, aspect, win);
        const speed = Math.abs(e2.x - e1.x) / 0.01 / ((e1.s + e2.s) / 2);
        const f1 = R.planePose(pl, lane, right, 0.6, aspect, win), f2 = R.planePose(pl, lane, right, 0.61, aspect, win);
        const speedB = Math.abs(f2.x - f1.x) / 0.01 / ((f1.s + f2.s) / 2);
        near(speed / speedB, 1, 0.08, 'ground speed is constant along a lane (mid run)');
      }
    }
    const far = R.planePose(pl, 0, true, 0.5, aspect, win), near1 = R.planePose(pl, 1, true, 0.5, aspect, win);
    ok(far.h < near1.h * 0.75 && far.y < near1.y && far.haze > near1.haze, 'the far lane is smaller, higher on the screen and hazier');
    ok(pl.lanes[0].duration > pl.lanes[1].duration, 'the far lane takes longer (slower on the screen)');
    // ease: slow at both ends
    const s0 = R.planePose(pl, 1, true, 0.01, aspect, win).x - R.planePose(pl, 1, true, 0, aspect, win).x;
    const sm = R.planePose(pl, 1, true, 0.51, aspect, win).x - R.planePose(pl, 1, true, 0.5, aspect, win).x;
    ok(s0 < sm * 0.8, 'eases in');
  }

  // ---------------------------------------------------------------- the director's lane choice
  {
    const REAL = scene.characters.map(n => JSON.parse(fs.readFileSync(path.join(ASSETS, 'chars', n, 'manifest.json'), 'utf8')));
    const START = Date.UTC(2026, 2, 19, 15, 0);
    function runPlanes(seed) {
      let d = null; const log = []; const now = () => (d ? d.now : 0);
      d = B.createDirector({ seed, scene, characters: REAL, clock: () => START + now(), minuteOfDay: () => Math.floor(now() / 60000) % 1440,
        solar: () => Sun.sunPosition(new Date(START + now()), 37.5665, 126.978) });
      let cur = null;
      for (let t = 0; t < 4 * 3600e3; t += 500) {
        d.step(500);
        const p = d.plane();
        if (p && !cur) { cur = { start: d.now, lane: p.lane, right: p.right, u0: p.u }; ok(d.mover() && d.mover().kind === 'plane', 'a plane run holds the movement lock'); }
        if (cur && !p) { log.push([cur.lane, cur.right, Math.round((d.now - cur.start) / 1000)]); cur = null; }
        if (p) ok(Number.isInteger(p.lane) && p.lane >= 0 && p.lane < scene.planes.lanes.length && typeof p.right === 'boolean', 'plane state has lane and heading');
      }
      return log;
    }
    const a = runPlanes(7), b = runPlanes(7), c = runPlanes(8);
    ok(a.length >= 4, 'planes came by: ' + a.length);
    eq(a, b, 'the same seed gives the same lanes, headings and durations');
    ok(JSON.stringify(a) !== JSON.stringify(c), 'another seed differs');
    const lanes = new Set(), dur = {};
    for (const seed of [1, 2, 3, 4, 5, 6]) for (const [lane, , secs] of runPlanes(seed)) { lanes.add(lane); (dur[lane] = dur[lane] || []).push(secs); }
    eq([...lanes].sort(), [0, 1], 'both lanes get used');
    for (const lane of [0, 1]) {
      const want = scene.planes.lanes[lane].duration;
      ok(dur[lane].every(s => Math.abs(s - want) <= 2), 'lane ' + lane + ' run lasts its own duration (' + want + ' s): ' + dur[lane].join(','));
    }
  }
  console.log('verify_lounge_weather OK (' + checks + ' checks)');
})().catch(e => { console.error('FAILED:', e.stack || e); process.exit(1); });
