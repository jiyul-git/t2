'use strict';
// docs/LOUNGE_SCENE_DESIGN.md 5.3
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const file = path.join(__dirname, '../web/lounge/location.js');
const { createLocation, TIMEZONES, LOC_KEY, DISMISS_KEY } = require(file);
let checks = 0;
const ok = (c, m) => { checks++; assert(c, m); };
const eq = (a, b, m) => { checks++; assert.deepStrictEqual(a, b, m); };

const DAY = 86400000;
const memStorage = (init = {}) => {
  const m = new Map(Object.entries(init));
  return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), _m: m };
};
const intlFor = tz => ({ DateTimeFormat: () => ({ resolvedOptions: () => ({ timeZone: tz }) }) });
function fakeNav({ perm = 'prompt', pos = { latitude: 37.56649, longitude: 126.97801 }, error = null, noPerms = false } = {}) {
  const calls = { get: 0, opts: null, query: 0 };
  return {
    calls,
    geolocation: { getCurrentPosition(ok, fail, opts) { calls.get++; calls.opts = opts; error ? fail(error) : ok({ coords: pos }); } },
    permissions: noPerms ? undefined : { query: async () => { calls.query++; return { state: perm }; } },
  };
}
const T0 = Date.UTC(2026, 9, 16, 3, 0);
const make = (o = {}) => createLocation({ navigator: o.navigator, storage: o.storage || memStorage(), now: o.now || (() => T0),
  intl: o.intl || intlFor('Asia/Seoul'), isSecureContext: o.secure !== undefined ? o.secure : true });

(async () => {
  // Time zone table: required zones are present and plausible.
  const REQUIRED = ['Asia/Seoul', 'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Hong_Kong', 'Asia/Taipei', 'Asia/Singapore', 'Asia/Bangkok',
    'Asia/Ho_Chi_Minh', 'Asia/Manila', 'Asia/Jakarta', 'Asia/Kolkata', 'Asia/Dubai', 'Europe/London', 'Europe/Paris', 'Europe/Berlin',
    'Europe/Madrid', 'Europe/Rome', 'Europe/Moscow', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
    'America/Toronto', 'America/Vancouver', 'America/Sao_Paulo', 'America/Mexico_City', 'Australia/Sydney', 'Australia/Melbourne',
    'Australia/Perth', 'Pacific/Auckland', 'Pacific/Honolulu'];
  for (const tz of REQUIRED) {
    ok(TIMEZONES[tz], tz);
    const [lat, lon] = TIMEZONES[tz];
    ok(Math.abs(lat) <= 90 && Math.abs(lon) <= 180, tz + ' range');
  }
  ok(Object.keys(TIMEZONES).length === REQUIRED.length, 'table matches the documented list');

  // 1. Start: time zone, no prompt, no permission query.
  {
    const nav = fakeNav(); const l = make({ navigator: nav });
    eq(l.init(), { lat: 37.5665, lon: 126.978, source: 'timezone', ts: T0 }, 'seoul by time zone');
    eq(nav.calls.get, 0, 'no geolocation call at start'); eq(nav.calls.query, 0, 'no permission query at start');
  }
  // Unknown zone: longitude from the clock offset, latitude 35.
  {
    const l = make({ navigator: fakeNav(), intl: intlFor('Africa/Nowhere') });
    const g = l.init(); eq(g.source, 'offset', 'offset fallback');
    eq(g.lat, 35, 'fallback latitude'); eq(g.lon, -new Date(T0).getTimezoneOffset() / 4, 'longitude from offset');
  }
  // Broken Intl is survivable.
  eq(make({ intl: { DateTimeFormat() { throw new Error('x'); } } }).init().source, 'offset', 'intl failure');

  // 2. Chip visibility rules.
  {
    ok(await make({ navigator: fakeNav() }).chipVisible(), 'visible: secure, supported, prompt');
    ok(await make({ navigator: fakeNav({ noPerms: true }) }).chipVisible(), 'visible when the permissions API is missing');
    ok(!(await make({ navigator: fakeNav(), secure: false }).chipVisible()), 'hidden on an insecure origin');
    ok(!(await make({ navigator: {} }).chipVisible()), 'hidden without geolocation');
    ok(!(await make({ navigator: null }).chipVisible()), 'hidden without navigator');
    ok(!(await make({ navigator: fakeNav({ perm: 'denied' }) }).chipVisible()), 'hidden when denied');
    ok(await make({ navigator: fakeNav({ perm: 'granted' }) }).chipVisible(), 'visible when granted but nothing saved');
    const saved = memStorage({ [LOC_KEY]: JSON.stringify({ lat: 35.1, lon: 129.04, ts: T0 }) });
    ok(!(await make({ navigator: fakeNav(), storage: saved }).chipVisible()), 'hidden once a real position is saved');
    // Dismissed: hidden for 30 days, then visible again.
    const dis = memStorage({ [DISMISS_KEY]: String(T0 - 29 * DAY) });
    ok(!(await make({ navigator: fakeNav(), storage: dis }).chipVisible()), 'hidden 29 days after dismissal');
    const dis2 = memStorage({ [DISMISS_KEY]: String(T0 - 31 * DAY) });
    ok(await make({ navigator: fakeNav(), storage: dis2 }).chipVisible(), 'visible 31 days after dismissal');
    // dismissChip persists.
    const st = memStorage(); const l = make({ navigator: fakeNav(), storage: st });
    l.dismissChip(); ok(!(await l.chipVisible()), 'dismissChip hides'); eq(st._m.get(DISMISS_KEY), String(T0), 'dismissal stored');
    // Permission query that throws counts as unknown, not denied.
    const nav = fakeNav(); nav.permissions = { query: async () => { throw new Error('nope'); } };
    ok(await make({ navigator: nav }).chipVisible(), 'permissions failure treated as unknown');
  }

  // 3. Tap: rounding to 2 decimals, saved, options, source.
  {
    const nav = fakeNav(); const st = memStorage(); const l = make({ navigator: nav, storage: st });
    const r = await l.request();
    ok(r.ok, 'request ok'); eq(l.get(), { lat: 37.57, lon: 126.98, source: 'geolocation', ts: T0 }, 'rounded to ~1 km');
    eq(JSON.parse(st._m.get(LOC_KEY)), { lat: 37.57, lon: 126.98, ts: T0 }, 'persisted rounded value only');
    eq(nav.calls.opts, { enableHighAccuracy: false, maximumAge: 86400000, timeout: 10000 }, 'low accuracy, cached ok, 10 s');
    ok(!(await l.chipVisible()), 'chip hidden after success');
    // Survives reload.
    eq(make({ navigator: fakeNav(), storage: st }).init().source, 'geolocation', 'restored from storage');
  }
  // Denied: remembered. Other failure: not remembered.
  {
    const st = memStorage(); const l = make({ navigator: fakeNav({ error: { code: 1 } }), storage: st });
    eq(await l.request(), { ok: false, reason: 'denied' }, 'denied'); ok(st._m.has(DISMISS_KEY), 'denial recorded');
    eq(l.get().source, 'timezone', 'stays on time zone');
    const st2 = memStorage(); const l2 = make({ navigator: fakeNav({ error: { code: 3 } }), storage: st2 });
    eq(await l2.request(), { ok: false, reason: 'failed' }, 'timeout'); ok(!st2._m.has(DISMISS_KEY), 'timeout is not remembered');
    eq(await make({ navigator: fakeNav(), secure: false }).request(), { ok: false, reason: 'unsupported' }, 'insecure origin');
    eq(await make({ navigator: fakeNav({ pos: { latitude: 200, longitude: 0 } }) }).request(), { ok: false, reason: 'invalid' }, 'bad coords rejected');
  }
  // Storage that throws or holds garbage does not break anything.
  {
    const bad = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
    const l = make({ navigator: fakeNav(), storage: bad });
    eq(l.init().source, 'timezone', 'blocked storage'); ok((await l.request()).ok, 'request still works');
    for (const junk of ['not json', '{"lat":"x"}', JSON.stringify({ lat: 99, lon: 0, ts: 1 }), JSON.stringify({ lat: 1, lon: 1 })]) {
      eq(make({ storage: memStorage({ [LOC_KEY]: junk }) }).init().source, 'timezone', 'junk ignored: ' + junk);
    }
  }

  // 4. Silent refresh after 24 h only when permission is already granted.
  {
    const old = JSON.stringify({ lat: 35.1, lon: 129.04, ts: T0 - 25 * DAY / 24 });
    const nav = fakeNav({ perm: 'granted' }); const st = memStorage({ [LOC_KEY]: old });
    const l = make({ navigator: nav, storage: st }); l.init();
    ok(await l.refreshIfStale(), 'refreshed'); eq(l.get().lat, 37.57, 'new position'); eq(nav.calls.get, 1, 'one lookup');
    const fresh = memStorage({ [LOC_KEY]: JSON.stringify({ lat: 35.1, lon: 129.04, ts: T0 - 23 * DAY / 24 }) });
    const nav2 = fakeNav({ perm: 'granted' }); const l2 = make({ navigator: nav2, storage: fresh }); l2.init();
    ok(!(await l2.refreshIfStale()), 'not stale yet'); eq(nav2.calls.get, 0, 'no lookup when fresh');
    const nav3 = fakeNav({ perm: 'prompt' }); const l3 = make({ navigator: nav3, storage: memStorage({ [LOC_KEY]: old }) }); l3.init();
    ok(!(await l3.refreshIfStale()), 'no refresh without granted permission'); eq(nav3.calls.get, 0, 'no prompt-triggering lookup');
    const nav4 = fakeNav({ perm: 'granted' }); const l4 = make({ navigator: nav4 }); l4.init();
    ok(!(await l4.refreshIfStale()), 'time-zone source is never refreshed'); eq(nav4.calls.get, 0, 'nothing to refresh');
    const nav5 = fakeNav({ perm: 'granted', error: { code: 2 } }); const l5 = make({ navigator: nav5, storage: memStorage({ [LOC_KEY]: old }) }); l5.init();
    ok(!(await l5.refreshIfStale()), 'failed refresh keeps the old position'); eq(l5.get().lat, 35.1, 'old position kept');
  }

  // 5. Debug override is not persisted and can be cleared.
  {
    const st = memStorage(); const l = make({ navigator: fakeNav(), storage: st });
    eq(l.setDebug(64.15, -21.94).source, 'debug', 'debug source'); eq(l.get().lat, 64.15, 'debug wins');
    eq(st._m.size, 0, 'debug position not stored');
    l.setDebug(null); eq(l.get().source, 'timezone', 'cleared');
    assert.throws(() => l.setDebug(95, 0), RangeError); checks++;
  }

  // 6. Nothing here may talk to the network.
  const src = fs.readFileSync(file, 'utf8');
  for (const word of ['fetch', 'XMLHttpRequest', 'sendBeacon', 'WebSocket', 'EventSource']) ok(!src.includes(word), 'source mentions ' + word);

  console.log(`verify_lounge_location OK (${checks} checks)`);
})().catch(e => { console.error(e); process.exit(1); });
