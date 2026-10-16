/* Sun elevation -> lighting values for the lounge scene (docs/LOUNGE_SCENE_DESIGN.md 8.1).
   Pure functions: no DOM. Colors are '#rrggbb'; they are interpolated per channel in sRGB. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeLighting = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const COLOR_KEYS = ['zenith', 'horizonSun', 'horizonAway', 'ambient', 'sunColor'];
  const NUM_KEYS = ['ambientStr', 'lamp', 'city', 'stars'];
  // [h, zenith, horizonSun, horizonAway, ambient, ambientStr, sunColor, lamp, city, stars]
  const TABLE = [
    [-18, '#070b1c', '#121a33', '#0e1530', '#4a5a8c', 0.55, '#000000', 1.00, 1.00, 1.00],
    [-12, '#0d1430', '#26305a', '#1d2650', '#55608f', 0.50, '#000000', 1.00, 1.00, 0.75],
    [-6,  '#1b2a5c', '#b0566a', '#3a3f78', '#6b6a9a', 0.40, '#000000', 1.00, 0.90, 0.25],
    [-2,  '#2d3f7c', '#ff7a45', '#6d5f99', '#a77a8a', 0.30, '#ff6a3a', 0.90, 0.60, 0.00],
    [2,   '#4a6db0', '#ff9b55', '#9a8cbc', '#e0a27e', 0.20, '#ff8a4a', 0.70, 0.30, 0.00],
    [8,   '#5b8fd6', '#ffc985', '#b3c8e6', '#ffd9b0', 0.12, '#ffb36b', 0.40, 0.10, 0.00],
    [20,  '#4b8fe0', '#d9ecff', '#c2dcf7', '#fff4e6', 0.04, '#ffe2b8', 0.15, 0.00, 0.00],
    [45,  '#3a86e3', '#d2e8ff', '#c8e1fa', '#ffffff', 0.00, '#fff4e0', 0.10, 0.00, 0.00],
  ].map(r => ({
    h: r[0], zenith: r[1], horizonSun: r[2], horizonAway: r[3], ambient: r[4],
    ambientStr: r[5], sunColor: r[6], lamp: r[7], city: r[8], stars: r[9],
  }));

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const smoothstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const parse = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  const toHex = rgb => '#' + rgb.map(v => clamp(Math.round(v), 0, 255).toString(16).padStart(2, '0')).join('');
  // mix(a, b, t): t=0 -> a, t=1 -> b.
  function mix(a, b, t) {
    const x = parse(a), y = parse(b);
    return toHex(x.map((v, i) => v + (y[i] - v) * t));
  }

  function lighting(h) {
    const elev = Number.isFinite(h) ? h : 45;
    const first = TABLE[0], last = TABLE[TABLE.length - 1];
    let lo = first, hi = first, t = 0;
    if (elev >= last.h) { lo = hi = last; }
    else if (elev > first.h) {
      let i = 0;
      while (i < TABLE.length - 2 && TABLE[i + 1].h <= elev) i++;
      lo = TABLE[i]; hi = TABLE[i + 1];
      t = (elev - lo.h) / (hi.h - lo.h);
    }
    const out = { h: elev, dayness: smoothstep(-8, 8, elev) };
    for (const k of COLOR_KEYS) out[k] = mix(lo[k], hi[k], t);
    for (const k of NUM_KEYS) out[k] = lo[k] + (hi[k] - lo[k]) * t;
    return out;
  }

  // CSS custom properties for <html>; they recolor the lobby page together with the scene.
  function cssVars(h) {
    const d = lighting(h).dayness;
    return {
      '--airport-surface-top': mix('#122e32', '#3c6762', d),
      '--airport-surface-mid': mix('#061b1f', '#113c3c', d),
      '--airport-surface-bottom': mix('#081f22', '#0f2b30', d),
    };
  }

  return { lighting, cssVars, mix, smoothstep, TABLE };
});
