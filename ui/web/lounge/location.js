/* Where the viewer is, for sun position (docs/LOUNGE_SCENE_DESIGN.md 5.3).
   Starts from the device time zone with no permission prompt; precise position only after
   an explicit tap. Coordinates are rounded to ~1 km, kept on this device, never sent anywhere.
   Browser objects are injected so the logic runs under Node. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeLocation = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const LOC_KEY = 't2_lounge_loc';
  const DISMISS_KEY = 't2_lounge_locate_dismissed';
  const DAY_MS = 86400000;
  const REFRESH_MS = DAY_MS;
  const REDISPLAY_MS = 30 * DAY_MS;

  const TIMEZONES = {
    'Asia/Seoul': [37.5665, 126.978], 'Asia/Tokyo': [35.6762, 139.6503],
    'Asia/Shanghai': [31.2304, 121.4737], 'Asia/Hong_Kong': [22.3193, 114.1694],
    'Asia/Taipei': [25.033, 121.5654], 'Asia/Singapore': [1.3521, 103.8198],
    'Asia/Bangkok': [13.7563, 100.5018], 'Asia/Ho_Chi_Minh': [10.8231, 106.6297],
    'Asia/Manila': [14.5995, 120.9842], 'Asia/Jakarta': [-6.2088, 106.8456],
    'Asia/Kolkata': [22.5726, 88.3639], 'Asia/Dubai': [25.2048, 55.2708],
    'Europe/London': [51.5074, -0.1278], 'Europe/Paris': [48.8566, 2.3522],
    'Europe/Berlin': [52.52, 13.405], 'Europe/Madrid': [40.4168, -3.7038],
    'Europe/Rome': [41.9028, 12.4964], 'Europe/Moscow': [55.7558, 37.6173],
    'America/New_York': [40.7128, -74.006], 'America/Chicago': [41.8781, -87.6298],
    'America/Denver': [39.7392, -104.9903], 'America/Los_Angeles': [34.0522, -118.2437],
    'America/Toronto': [43.6532, -79.3832], 'America/Vancouver': [49.2827, -123.1207],
    'America/Sao_Paulo': [-23.5505, -46.6333], 'America/Mexico_City': [19.4326, -99.1332],
    'Australia/Sydney': [-33.8688, 151.2093], 'Australia/Melbourne': [-37.8136, 144.9631],
    'Australia/Perth': [-31.9505, 115.8605], 'Pacific/Auckland': [-36.8485, 174.7633],
    'Pacific/Honolulu': [21.3069, -157.8583],
  };

  const round2 = v => Math.round(v * 100) / 100;
  const validCoords = (lat, lon) => Number.isFinite(lat) && Number.isFinite(lon) &&
    Math.abs(lat) <= 90 && Math.abs(lon) <= 180;

  function createLocation(env) {
    const nav = env.navigator || null;
    const storage = env.storage || null;
    const now = env.now || (() => Date.now());
    const intl = env.intl || (typeof Intl !== 'undefined' ? Intl : null);
    const secure = env.isSecureContext !== undefined ? !!env.isSecureContext : true;
    let state = null;          // { lat, lon, source, ts }
    let debugState = null;     // never persisted

    const read = key => { try { return storage ? storage.getItem(key) : null; } catch (e) { return null; } };
    const write = (key, val) => { try { if (storage) storage.setItem(key, val); } catch (e) { /* private mode */ } };

    function fromTimezone() {
      let tz = '';
      try { tz = intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) { tz = ''; }
      const hit = TIMEZONES[tz];
      if (hit) return { lat: hit[0], lon: hit[1], source: 'timezone', ts: now() };
      const offsetMin = new Date(now()).getTimezoneOffset();      // minutes behind UTC
      return { lat: 35, lon: Math.max(-180, Math.min(180, -offsetMin / 4)), source: 'offset', ts: now() };
    }

    function fromStorage() {
      const raw = read(LOC_KEY);
      if (!raw) return null;
      try {
        const v = JSON.parse(raw);
        if (validCoords(v.lat, v.lon) && Number.isFinite(v.ts)) {
          return { lat: v.lat, lon: v.lon, source: 'geolocation', ts: v.ts };
        }
      } catch (e) { /* corrupt entry is ignored */ }
      return null;
    }

    function init() {
      state = fromStorage() || fromTimezone();
      return get();
    }

    function get() {
      if (debugState) return debugState;
      if (!state) init();
      return state;
    }

    function setDebug(lat, lon) {
      if (lat === null || lat === undefined) { debugState = null; return get(); }
      if (!validCoords(lat, lon)) throw new RangeError('bad coordinates');
      debugState = { lat, lon, source: 'debug', ts: now() };
      return debugState;
    }

    async function permissionState() {
      try {
        if (nav && nav.permissions && nav.permissions.query) {
          return (await nav.permissions.query({ name: 'geolocation' })).state;
        }
      } catch (e) { /* unsupported */ }
      return 'unknown';
    }

    async function chipVisible() {
      if (!secure || !nav || !nav.geolocation) return false;
      if (get().source === 'geolocation') return false;
      const dismissed = Number(read(DISMISS_KEY));
      if (Number.isFinite(dismissed) && dismissed > 0 && now() - dismissed < REDISPLAY_MS) return false;
      return (await permissionState()) !== 'denied';
    }

    function dismissChip() { write(DISMISS_KEY, String(now())); }

    function position(options) {
      return new Promise((resolve, reject) => nav.geolocation.getCurrentPosition(resolve, reject, options));
    }

    function store(pos) {
      const lat = round2(pos.coords.latitude), lon = round2(pos.coords.longitude);
      if (!validCoords(lat, lon)) return null;
      state = { lat, lon, source: 'geolocation', ts: now() };
      write(LOC_KEY, JSON.stringify({ lat, lon, ts: state.ts }));
      return state;
    }

    // Called from the user's tap on the locate chip.
    async function request() {
      if (!secure || !nav || !nav.geolocation) return { ok: false, reason: 'unsupported' };
      try {
        const pos = await position({ enableHighAccuracy: false, maximumAge: DAY_MS, timeout: 10000 });
        const s = store(pos);
        return s ? { ok: true, location: s } : { ok: false, reason: 'invalid' };
      } catch (e) {
        const denied = !!e && e.code === 1;
        if (denied) dismissChip();          // a refusal is remembered for 30 days; other failures only hide it now
        return { ok: false, reason: denied ? 'denied' : 'failed' };
      }
    }

    // On later visits: if permission was already granted and the saved position is a day old,
    // refresh it without showing a prompt.
    async function refreshIfStale() {
      const cur = get();
      if (!secure || !nav || !nav.geolocation || cur.source !== 'geolocation') return false;
      if (now() - cur.ts < REFRESH_MS) return false;
      if ((await permissionState()) !== 'granted') return false;
      try {
        return !!store(await position({ enableHighAccuracy: false, maximumAge: DAY_MS, timeout: 10000 }));
      } catch (e) { return false; }
    }

    return { init, get, setDebug, chipVisible, dismissChip, request, refreshIfStale };
  }

  return { createLocation, TIMEZONES, LOC_KEY, DISMISS_KEY };
});
