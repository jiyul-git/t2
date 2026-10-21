/* Current weather for the lounge window (docs/LOUNGE_SCENE_DESIGN.md 13).
   Asks Open-Meteo (https://open-meteo.com, no key) what the sky is doing at the scene's place and maps
   the WMO weather code to what the scene can draw: clear, cloudy, fog, rain (light / moderate /
   heavy, thunderstorm = heavy rain with lightning) or snow (light / heavy).

   Privacy: the only thing sent is the place rounded to two decimals (about 1 km), in the URL of one
   GET request to api.open-meteo.com, at most every 15 minutes while the page is visible. Nothing
   else leaves the device. Every failure is silent: the last known weather stays, or clear.
   The result is kept in localStorage for 15 minutes so a reopened app shows the right weather at once.
   Switch it off: localStorage['t2_lounge_wx_off'] = '1' (or setEnabled(false)); then nothing is fetched.
   Browser objects are injected so the logic runs under Node (see ui/tools/verify_lounge_weather.js). */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeWeather = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const CACHE_KEY = 't2_lounge_wx';
  const OFF_KEY = 't2_lounge_wx_off';
  const ENDPOINT = 'https://api.open-meteo.com/v1/forecast';
  const FIELDS = 'weather_code,rain,showers,snowfall,cloud_cover,wind_speed_10m,wind_direction_10m,is_day';
  const FRESH_MS = 15 * 60000;          // a cached answer is used as is for this long, and the poll period
  const STALE_MAX_MS = 3 * 3600000;     // an older answer still beats nothing while a new one is fetched
  const RETRY_MS = 5 * 60000;           // after a failed request
  const FETCH_TIMEOUT_MS = 10000;
  const CLEAR = Object.freeze({ kind: 'clear', intensity: 'none', thunder: false, cloud: 0, windSpeed: 0, windDir: 0, isDay: true, code: 0 });

  const round2 = v => Math.round(v * 100) / 100;
  const num = (v, d) => (typeof v === 'number' && Number.isFinite(v) ? v : d);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  // WMO code -> [kind, intensity, thunder]. Drizzle and freezing rain count as rain.
  const CODES = {
    0: ['clear', 'none'], 1: ['clear', 'none'], 2: ['partly', 'none'], 3: ['cloudy', 'none'],
    45: ['fog', 'moderate'], 48: ['fog', 'heavy'],
    51: ['rain', 'light'], 53: ['rain', 'light'], 55: ['rain', 'moderate'],
    56: ['rain', 'light'], 57: ['rain', 'moderate'],
    61: ['rain', 'light'], 63: ['rain', 'moderate'], 65: ['rain', 'heavy'],
    66: ['rain', 'light'], 67: ['rain', 'moderate'],
    71: ['snow', 'light'], 73: ['snow', 'light'], 75: ['snow', 'heavy'], 77: ['snow', 'light'],
    80: ['rain', 'light'], 81: ['rain', 'moderate'], 82: ['rain', 'heavy'],
    85: ['snow', 'light'], 86: ['snow', 'heavy'],
    95: ['rain', 'heavy', true], 96: ['rain', 'heavy', true], 99: ['rain', 'heavy', true],
  };
  const KINDS = ['clear', 'cloudy', 'fog', 'rain', 'snow'];
  const INTENSITIES = ['none', 'light', 'moderate', 'heavy'];

  // Open-Meteo "current" block -> what the scene draws. Anything unknown is read as the cloud cover alone.
  function fromCurrent(cur) {
    cur = cur && typeof cur === 'object' ? cur : {};
    const code = Math.round(num(cur.weather_code, 0));
    const cover = clamp(num(cur.cloud_cover, code >= 3 ? 100 : 0), 0, 100) / 100;
    const hit = CODES[code];
    let kind, intensity = 'none', thunder = false;
    if (hit) {
      kind = hit[0]; intensity = hit[1]; thunder = !!hit[2];
      if (kind === 'partly') kind = cover >= 0.6 ? 'cloudy' : 'clear';
    } else {
      kind = cover >= 0.85 ? 'cloudy' : 'clear';         // a code we do not know: only the cloud cover counts
    }
    // measured precipitation can raise a plain rain / snow class (mm per hour, cm per hour)
    const mm = num(cur.rain, 0) + num(cur.showers, 0), cm = num(cur.snowfall, 0);
    if (kind === 'rain' && !thunder) {
      if (mm >= 4 && intensity !== 'heavy') intensity = 'heavy';
      else if (mm >= 1 && intensity === 'light') intensity = 'moderate';
    }
    if (kind === 'snow') intensity = cm >= 0.5 || intensity === 'heavy' ? 'heavy' : 'light';
    // whatever falls from the sky, the sky is covered
    const cloud = kind === 'rain' || kind === 'snow' || kind === 'fog' ? Math.max(cover, 0.9) : (kind === 'cloudy' ? Math.max(cover, 0.7) : cover * 0.5);
    return {
      kind, intensity, thunder, cloud: round2(cloud), code,
      windSpeed: round2(Math.max(0, num(cur.wind_speed_10m, 0))),       // km/h
      windDir: round2(((num(cur.wind_direction_10m, 0) % 360) + 360) % 360),   // degrees the wind comes from, north = 0
      isDay: cur.is_day === undefined ? true : !!cur.is_day,
    };
  }

  // The same, from a debug request: setWeather('rain', 'heavy').
  function synthetic(kind, intensity) {
    if (!KINDS.includes(kind)) return CLEAR;
    const thunder = kind === 'rain' && intensity === 'thunder';
    let inten = thunder ? 'heavy' : (INTENSITIES.includes(intensity) ? intensity : (kind === 'rain' || kind === 'snow' ? 'moderate' : 'none'));
    if (kind === 'snow' && inten === 'moderate') inten = 'light';
    if (kind === 'clear' || kind === 'cloudy') inten = 'none';
    const wet = kind === 'rain' || kind === 'snow' || kind === 'fog';
    return { kind, intensity: inten, thunder, cloud: kind === 'clear' ? 0 : (wet ? 0.95 : 0.8),
      windSpeed: kind === 'rain' ? 14 : 6, windDir: 270, isDay: true, code: -1 };
  }

  const same = (a, b) => !!a && !!b && a.kind === b.kind && a.intensity === b.intensity && a.thunder === b.thunder;

  const urlFor = (lat, lon) => ENDPOINT + '?latitude=' + round2(lat) + '&longitude=' + round2(lon) + '&current=' + FIELDS;

  // env: { fetch, storage, now, getPlace: () => {lat, lon}, onChange(cond), isVisible: () => bool,
  //        setTimeout, clearTimeout }
  function createWeather(env) {
    const fetchFn = env.fetch || null;
    const storage = env.storage || null;
    const now = env.now || (() => Date.now());
    const getPlace = env.getPlace || (() => null);
    const onChange = env.onChange || (() => {});
    const isVisible = env.isVisible || (() => true);
    const setT = env.setTimeout || (typeof setTimeout === 'function' ? setTimeout : null);
    const clearT = env.clearTimeout || (typeof clearTimeout === 'function' ? clearTimeout : null);
    let current = CLEAR, override = null, started = false, timer = null, inflight = null, due = false, lastTry = 0;

    const read = k => { try { return storage ? storage.getItem(k) : null; } catch (e) { return null; } };
    const write = (k, v) => { try { if (storage) storage.setItem(k, v); } catch (e) { /* private mode */ } };
    const enabled = () => read(OFF_KEY) !== '1';

    function cached() {
      const raw = read(CACHE_KEY);
      if (!raw) return null;
      try {
        const v = JSON.parse(raw);
        if (v && Number.isFinite(v.ts) && Number.isFinite(v.lat) && Number.isFinite(v.lon) && v.cond && KINDS.includes(v.cond.kind)) return v;
      } catch (e) { /* a damaged entry counts as none */ }
      return null;
    }
    function set(cond) {
      const changed = !same(current, cond) || current.cloud !== cond.cloud || current.windDir !== cond.windDir;
      current = cond;
      if (changed && !override) onChange(effective());
      return changed;
    }
    const effective = () => (override || (enabled() ? current : CLEAR));

    function place() {
      const p = getPlace();
      if (!p || !Number.isFinite(p.lat) || !Number.isFinite(p.lon)) return null;
      return { lat: round2(p.lat), lon: round2(p.lon) };
    }

    // Use what is saved for this place right away (fresh, or stale but not old); true when it is fresh.
    function init() {
      if (!enabled()) return false;
      const p = place(), c = cached();
      if (!p || !c || c.lat !== p.lat || c.lon !== p.lon) return false;
      const age = now() - c.ts;
      if (age < 0 || age > STALE_MAX_MS) return false;
      set(c.cond);
      return age < FRESH_MS;
    }

    // Ask for the current weather. Resolves to the condition in use, never rejects.
    function refresh(force) {
      if (!enabled() || !fetchFn) return Promise.resolve(effective());
      const p = place();
      if (!p) return Promise.resolve(effective());
      const c = cached();
      if (!force && c && c.lat === p.lat && c.lon === p.lon && now() - c.ts >= 0 && now() - c.ts < FRESH_MS) { set(c.cond); return Promise.resolve(effective()); }
      if (inflight) return inflight;
      lastTry = now();
      const ctl = typeof AbortController === 'function' ? new AbortController() : null;
      const guard = ctl && setT ? setT(() => ctl.abort(), FETCH_TIMEOUT_MS) : null;
      inflight = Promise.resolve()
        .then(() => fetchFn(urlFor(p.lat, p.lon), ctl ? { signal: ctl.signal, cache: 'no-store' } : { cache: 'no-store' }))
        .then(r => { if (!r || !r.ok) throw new Error('HTTP ' + (r && r.status)); return r.json(); })
        .then(j => {
          if (!j || typeof j.current !== 'object' || j.current === null || !Number.isFinite(j.current.weather_code)) throw new Error('no current weather');
          const cond = fromCurrent(j.current);
          write(CACHE_KEY, JSON.stringify({ ts: now(), lat: p.lat, lon: p.lon, cond }));
          due = false;
          set(cond);
        })
        .catch(() => { due = true; })                       // silent: the last known weather stays
        .then(() => { if (guard && clearT) clearT(guard); inflight = null; return effective(); });
      return inflight;
    }

    function schedule() {
      if (!setT || !started) return;
      if (timer && clearT) clearT(timer);
      timer = setT(() => { timer = null; if (isVisible()) refresh(true).then(schedule); else { due = true; schedule(); } }, due ? RETRY_MS : FRESH_MS);
    }

    // Begin: show what is saved, then fetch if it is not fresh, then poll every 15 minutes while visible.
    function start() {
      if (started) return Promise.resolve(effective());
      started = true;
      const fresh = init();
      const first = fresh ? Promise.resolve(effective()) : refresh(false);
      schedule();
      return first;
    }
    // The page came back to the foreground: a poll that was due while hidden is done now.
    function visible() {
      if (!started || !isVisible() || !enabled()) return;
      const c = cached();
      if (due || !c || now() - c.ts >= FRESH_MS) refresh(true).then(schedule);
    }
    function setEnabled(on) {
      write(OFF_KEY, on ? '0' : '1');
      if (on) { start(); refresh(true); } else onChange(effective());
    }
    function setOverride(kind, intensity) { override = kind ? synthetic(kind, intensity) : null; onChange(effective()); }
    function stop() { started = false; if (timer && clearT) clearT(timer); timer = null; }

    return { start, stop, init, refresh, visible, setEnabled, setOverride, get: effective, enabled, urlFor, lastTry: () => lastTry };
  }

  return { createWeather, fromCurrent, synthetic, urlFor, CLEAR, CODES, CACHE_KEY, OFF_KEY, FRESH_MS, STALE_MAX_MS, RETRY_MS, KINDS, INTENSITIES };
});
