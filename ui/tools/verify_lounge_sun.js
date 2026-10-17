'use strict';
// docs/LOUNGE_SCENE_DESIGN.md 5.1 reference values.
const assert = require('assert');
const path = require('path');
const sun = require(path.join(__dirname, '../web/lounge/sun.js'));

const SEOUL = [37.5665, 126.9780];
const KST = 9 * 60;                                   // minutes east of UTC
const localMs = (y, m, d, hh, mm, offMin) => Date.UTC(y, m - 1, d, hh, mm) - offMin * 60000;
const hhmm = min => String(Math.floor(min / 60)).padStart(2, '0') + ':' + String(min % 60).padStart(2, '0');
const toMin = s => Number(s.slice(0, 2)) * 60 + Number(s.slice(3));
const angDiff = (a, b) => Math.abs(((a - b + 540) % 360) - 180);
let checks = 0;
const near = (got, want, tol, label) => {
  checks++;
  assert(Math.abs(got - want) <= tol, `${label}: got ${got.toFixed(3)}, want ${want} +-${tol}`);
};
const nearAz = (got, want, tol, label) => {
  checks++;
  assert(angDiff(got, want) <= tol, `${label}: got ${got.toFixed(3)}, want ${want} +-${tol}`);
};

// Scan a local day minute by minute for sunrise/sunset (-0.833 deg) and the maximum.
function scanDay(y, m, d, lat, lon, offMin) {
  let prev = null, rise = null, set = null, max = { el: -99 };
  for (let i = 0; i < 1440; i++) {
    const p = sun.sunPosition(new Date(localMs(y, m, d, 0, i, offMin)), lat, lon);
    if (p.elevation > max.el) max = { el: p.elevation, min: i, az: p.azimuth };
    if (prev !== null) {
      if (prev < -0.833 && p.elevation >= -0.833) rise = { min: i, az: p.azimuth };
      if (prev >= -0.833 && p.elevation < -0.833) set = { min: i, az: p.azimuth };
    }
    prev = p.elevation;
  }
  return { rise, set, max };
}

const days = [
  ['2026-03-20', 2026, 3, 20, '06:37', 89.8, '18:44', 270.6, 52.25, '12:40'],
  ['2026-06-21', 2026, 6, 21, '05:11', 59.1, '19:57', 300.9, 75.87, '12:34'],
  ['2026-12-21', 2026, 12, 21, '07:43', 119.4, '17:18', 240.8, 29.00, '12:30'],
];
for (const [label, y, m, d, rise, riseAz, set, setAz, maxEl, maxAt] of days) {
  const r = scanDay(y, m, d, SEOUL[0], SEOUL[1], KST);
  assert(r.rise && r.set, `${label}: sunrise/sunset not found`);
  near(r.rise.min, toMin(rise), 3, `Seoul ${label} sunrise ${hhmm(r.rise.min)}`);
  nearAz(r.rise.az, riseAz, 1.5, `Seoul ${label} sunrise azimuth`);
  near(r.set.min, toMin(set), 3, `Seoul ${label} sunset ${hhmm(r.set.min)}`);
  nearAz(r.set.az, setAz, 1.5, `Seoul ${label} sunset azimuth`);
  near(r.max.el, maxEl, 0.3, `Seoul ${label} max elevation`);
  near(r.max.min, toMin(maxAt), 3, `Seoul ${label} max at ${hhmm(r.max.min)}`);
  nearAz(r.max.az, 180, 2, `Seoul ${label} noon azimuth`);
}

// Spot checks, Seoul 2026-03-20 KST.
for (const [hh, mm, el, az] of [[12, 0, 51.15, 164.08], [18, 0, 7.77, 263.86], [6, 40, -0.11, 90.27]]) {
  const p = sun.sunPosition(new Date(localMs(2026, 3, 20, hh, mm, KST)), SEOUL[0], SEOUL[1]);
  near(p.elevation, el, 0.3, `Seoul 03-20 ${hh}:${mm} elevation`);
  nearAz(p.azimuth, az, 1.5, `Seoul 03-20 ${hh}:${mm} azimuth`);
}

// Reykjavik midsummer: the sun never gets far below the horizon.
{
  let min = 99;
  for (let i = 0; i < 1440; i += 2) {
    const p = sun.sunPosition(new Date(Date.UTC(2026, 5, 21, 0, i)), 64.15, -21.94);
    min = Math.min(min, p.elevation);
  }
  near(min, -2.41, 0.3, 'Reykjavik 06-21 minimum elevation');
}

// Sydney winter noon, sun is to the north.
{
  const p = sun.sunPosition(new Date(Date.UTC(2026, 5, 21, 2, 0)), -33.87, 151.21);
  near(p.elevation, 32.69, 0.3, 'Sydney 06-21 12:00 AEST elevation');
  nearAz(p.azimuth, 359.15, 1.5, 'Sydney 06-21 12:00 AEST azimuth');
}

// Accepts Date or epoch ms; output ranges.
{
  const ms = Date.UTC(2026, 9, 16, 3, 0);
  const a = sun.sunPosition(new Date(ms), 37.5665, 126.978), b = sun.sunPosition(ms, 37.5665, 126.978);
  assert.deepStrictEqual(a, b); checks++;
  for (let i = 0; i < 2000; i++) {
    const p = sun.sunPosition(ms + i * 7919000, -80 + (i % 160), -180 + (i * 37) % 360);
    assert(p.elevation >= -90 && p.elevation <= 90 && p.azimuth >= 0 && p.azimuth < 360, 'range'); checks++;
  }
}

// Moon phase: known new moon (2000-01-06 18:14 UTC) and a later full moon (2026-10-26 04:12 UTC is
// close to full; the mean-cycle model is only expected to be within about a day).
{
  near(sun.moonPhase(Date.UTC(2000, 0, 6, 18, 14)), 0, 1e-9, 'moonPhase epoch');
  const ph = sun.moonPhase(Date.UTC(2026, 9, 26, 4, 12));
  near(ph, 0.5, 0.05, 'moonPhase near 2026-10-26 full moon');
  for (let i = 0; i < 400; i++) {
    const v = sun.moonPhase(Date.UTC(2020, 0, 1) + i * 86400000 * 3.7);
    assert(v >= 0 && v < 1, 'phase range'); checks++;
  }
  // Moon trails the sun: at full phase the moon is roughly opposite the sun.
  const t = Date.UTC(2026, 9, 26, 4, 12) + 12 * 3600000;
  const s = sun.sunPosition(t, 37.5665, 126.978), mo = sun.moonPosition(t, 37.5665, 126.978);
  assert(Math.abs(s.elevation + mo.elevation) < 25, 'full moon opposes the sun'); checks++;
}

console.log(`verify_lounge_sun OK (${checks} checks)`);
