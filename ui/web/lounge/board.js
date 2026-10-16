/* Departure-board rows from the tournament catalog (docs/LOUNGE_SCENE_DESIGN.md 9).
   Pure functions: no DOM. Real tournaments become flights; empty rows are filled with
   made-up flights that stay the same for the whole day. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeBoard = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const ROWS = 5;
  const KST_MIN = 9 * 60;
  const DESTINATIONS = {
    standard: 'SEOUL', turbo: 'TOKYO', deep: 'NEW YORK', hyper: 'SINGAPORE',
    lowbuyin: 'BANGKOK', main: 'PARIS',
  };
  const FALLBACK_DEST = 'T2 CITY';
  const FAKE_CITIES = ['OSAKA', 'HONG KONG', 'SYDNEY', 'LONDON', 'HAWAII', 'DUBAI', 'TAIPEI', 'VANCOUVER'];
  const STATUS_COLORS = {
    time: '#ffd27a', 'BOARDING': '#7dffb0', 'LAST CALL': '#ff9d6a', 'DEPARTED': '#8a97a6', 'ON TIME': '#ffffff',
  };
  const COLUMN_RATIOS = [0.22, 0.34, 0.18, 0.26];       // flight, destination, time, status
  const BOARDING_WINDOW_SEC = 30 * 60;

  function fnv1a(str) {
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h >>> 0;
  }
  const pad2 = n => String(n).padStart(2, '0');
  const fmtMin = m => { const v = ((m % 1440) + 1440) % 1440; return pad2(Math.floor(v / 60)) + ':' + pad2(v % 60); };
  const kstMinuteOfDay = ms => Math.floor(((ms / 60000) + KST_MIN) % 1440 + 1440) % 1440;
  function kstDateKey(ms) {
    const d = new Date(ms + KST_MIN * 60000);
    return d.getUTCFullYear() + pad2(d.getUTCMonth() + 1) + pad2(d.getUTCDate());
  }

  function statusFor(t, nowSec) {
    if (t.status === 'closed') return 'DEPARTED';
    if (t.status === 'late_registration') return 'LAST CALL';
    if (t.status === 'scheduled' && t.registration_open && t.starts_at - nowSec <= BOARDING_WINDOW_SEC) return 'BOARDING';
    return 'ON TIME';
  }

  function boardRows(tournaments, serverNowSec, nowMs) {
    const nowSec = Number.isFinite(serverNowSec) ? serverNowSec : nowMs / 1000;
    const sorted = (Array.isArray(tournaments) ? tournaments : [])
      .filter(t => t && Number.isFinite(t.starts_at) && !['finished', 'retired'].includes(t.status))
      .sort((a, b) => a.starts_at - b.starts_at)
      .slice(0, ROWS);
    const real = sorted.map(t => ({
      flight: 'T2 ' + (fnv1a(String(t.id)) % 900 + 100),
      dest: DESTINATIONS[t.key || t.fmt] || FALLBACK_DEST,
      time: fmtMin(kstMinuteOfDay(t.starts_at * 1000)),
      status: statusFor(t, nowSec),
      mine: !!(t.my_entry && t.my_entry.status !== 'cancelled'),
      virtual: false,
    }));

    const rows = real.slice();
    const day = kstDateKey(nowMs);
    const cityOffset = fnv1a(day) % FAKE_CITIES.length;
    let minute = sorted.length ? kstMinuteOfDay(sorted[sorted.length - 1].starts_at * 1000) : kstMinuteOfDay(nowMs);
    for (let i = real.length, j = 0; i < ROWS; i++, j++) {
      minute = Math.ceil((minute + 25) / 5) * 5;
      rows.push({
        flight: 'TT ' + (fnv1a(day + ':' + i) % 900 + 100),
        dest: FAKE_CITIES[(cityOffset + j * 3) % FAKE_CITIES.length],   // 3 is coprime with 8: no repeats
        time: fmtMin(minute),
        status: 'ON TIME',
        mine: false,
        virtual: true,
      });
    }
    return rows;
  }

  return { boardRows, statusFor, fnv1a, DESTINATIONS, FAKE_CITIES, STATUS_COLORS, COLUMN_RATIOS, ROWS };
});
