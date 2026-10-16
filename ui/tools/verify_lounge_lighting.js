'use strict';
// docs/LOUNGE_SCENE_DESIGN.md 8.1: exact key values, interpolation, clamping, CSS variables.
const assert = require('assert');
const path = require('path');
const L = require(path.join(__dirname, '../web/lounge/lighting.js'));
let checks = 0;
const eq = (a, b, m) => { checks++; assert.strictEqual(a, b, m); };
const near = (a, b, tol, m) => { checks++; assert(Math.abs(a - b) <= tol, `${m}: got ${a}, want ${b}`); };

// Table text of the design doc, restated independently of lighting.js.
const KEYS = {
  '-18': ['#070b1c', '#121a33', '#0e1530', '#4a5a8c', 0.55, '#000000', 1.00, 1.00, 1.00],
  '-12': ['#0d1430', '#26305a', '#1d2650', '#55608f', 0.50, '#000000', 1.00, 1.00, 0.75],
  '-6':  ['#1b2a5c', '#b0566a', '#3a3f78', '#6b6a9a', 0.40, '#000000', 1.00, 0.90, 0.25],
  '-2':  ['#2d3f7c', '#ff7a45', '#6d5f99', '#a77a8a', 0.30, '#ff6a3a', 0.90, 0.60, 0.00],
  '2':   ['#4a6db0', '#ff9b55', '#9a8cbc', '#e0a27e', 0.20, '#ff8a4a', 0.70, 0.30, 0.00],
  '8':   ['#5b8fd6', '#ffc985', '#b3c8e6', '#ffd9b0', 0.12, '#ffb36b', 0.40, 0.10, 0.00],
  '20':  ['#4b8fe0', '#d9ecff', '#c2dcf7', '#fff4e6', 0.04, '#ffe2b8', 0.15, 0.00, 0.00],
  '45':  ['#3a86e3', '#d2e8ff', '#c8e1fa', '#ffffff', 0.00, '#fff4e0', 0.10, 0.00, 0.00],
};
for (const [h, v] of Object.entries(KEYS)) {
  const l = L.lighting(Number(h));
  eq(l.zenith, v[0], `zenith @${h}`); eq(l.horizonSun, v[1], `horizonSun @${h}`);
  eq(l.horizonAway, v[2], `horizonAway @${h}`); eq(l.ambient, v[3], `ambient @${h}`);
  near(l.ambientStr, v[4], 1e-9, `ambientStr @${h}`); eq(l.sunColor, v[5], `sunColor @${h}`);
  near(l.lamp, v[6], 1e-9, `lamp @${h}`); near(l.city, v[7], 1e-9, `city @${h}`);
  near(l.stars, v[8], 1e-9, `stars @${h}`);
}

// Midpoints between keys are the plain average (numbers) or per-channel average (colors).
{
  const m = L.lighting(-9);                       // halfway between -12 and -6
  near(m.ambientStr, 0.45, 1e-9, 'ambientStr mid'); near(m.stars, 0.5, 1e-9, 'stars mid');
  near(m.city, 0.95, 1e-9, 'city mid');
  eq(m.zenith, '#141f46', 'zenith mid');          // per channel: (0d+1b)/2=14h, (14+2a)/2=1fh, (30+5c)/2=46h
  const q = L.lighting(5);                          // halfway between the 2 and 8 keys
  eq(q.horizonSun, '#ffb26d', 'horizonSun mid');    // (ff+ff)/2, (9b+c9)/2=b2h, (55+85)/2=6dh
  near(q.lamp, 0.55, 1e-9, 'lamp mid');
  // A quarter of the way, 2 -> 8 at h=3.5: t=0.25.
  near(L.lighting(3.5).ambientStr, 0.20 + (0.12 - 0.20) * 0.25, 1e-9, 'ambientStr quarter');
}

// Out of range clamps to the end keys; bad input falls back to full daylight.
eq(JSON.stringify(L.lighting(-90)), JSON.stringify({ ...L.lighting(-18), h: -90 }), 'below range clamps');
eq(JSON.stringify(L.lighting(90)), JSON.stringify({ ...L.lighting(45), h: 90 }), 'above range clamps');
eq(L.lighting(NaN).zenith, '#3a86e3', 'NaN falls back to the daylight key');

// Continuous and bounded across the whole range, and stars/lamp only fall as the sun rises.
{
  let prev = L.lighting(-30);
  for (let h = -29.9; h <= 60; h += 0.1) {
    const cur = L.lighting(h);
    for (const k of ['ambientStr', 'lamp', 'city', 'stars', 'dayness']) {
      checks++; assert(cur[k] >= -1e-9 && cur[k] <= 1 + 1e-9, `${k} bounded @${h}`);
      checks++; assert(Math.abs(cur[k] - prev[k]) < 0.12, `${k} continuous @${h}`);
    }
    for (const k of ['stars', 'city', 'dayness']) { checks++; assert(cur[k] <= prev[k] + 1e-9 || k === 'dayness', `${k} monotone @${h}`); }
    checks++; assert(cur.dayness >= prev.dayness - 1e-12, 'dayness monotone');
    for (const k of ['zenith', 'ambient', 'sunColor']) { checks++; assert(/^#[0-9a-f]{6}$/.test(cur[k]), `${k} hex`); }
    prev = cur;
  }
}

// dayness = smoothstep(-8, 8, h).
near(L.lighting(-8).dayness, 0, 1e-12, 'dayness at -8'); near(L.lighting(0).dayness, 0.5, 1e-12, 'dayness at 0');
near(L.lighting(8).dayness, 1, 1e-12, 'dayness at 8'); near(L.lighting(4).dayness, 0.84375, 1e-12, 'dayness at 4');

// CSS variables: night / day ends and midpoint.
{
  const n = L.cssVars(-20), d = L.cssVars(20), m = L.cssVars(0);
  eq(n['--airport-surface-top'], '#122e32', 'top night'); eq(d['--airport-surface-top'], '#3c6762', 'top day');
  eq(n['--airport-surface-mid'], '#061b1f', 'mid night'); eq(d['--airport-surface-mid'], '#113c3c', 'mid day');
  eq(n['--airport-surface-bottom'], '#081f22', 'bottom night'); eq(d['--airport-surface-bottom'], '#0f2b30', 'bottom day');
  eq(m['--airport-surface-top'], '#274b4a', 'top at dayness 0.5');   // (18+60)/2=39, (46+103)/2=74.5->75, (50+98)/2=74
  eq(m['--airport-surface-mid'], '#0c2c2e', 'mid at dayness 0.5');
  eq(n['--lounge-glow'], '#c98a4a', 'lamp glow at night'); eq(d['--lounge-glow'], '#e9e2cf', 'window light by day');
  eq(n['--lounge-window'], '#2f5a78', 'window night'); eq(d['--lounge-window'], '#bfe0ee', 'window day');
  eq(Object.keys(m).length, 5, 'five variables');
}

console.log(`verify_lounge_lighting OK (${checks} checks)`);
