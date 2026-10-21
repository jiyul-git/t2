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
      // the lounge continues below the picture: lamp glow at night, window light by day
      '--lounge-glow': mix('#c98a4a', '#e9e2cf', d),
      '--lounge-window': mix('#2f5a78', '#bfe0ee', d),
    };
  }

  // ---- weather (docs/LOUNGE_SCENE_DESIGN.md 13.3). cloud 0 = clear sky, 1 = overcast.
  // Share of the direct sun that reaches the room: full until half the sky is covered, gone when it is overcast.
  const sunTransmit = cloud => (Number.isFinite(cloud) ? 1 - smoothstep(0.5, 1.0, cloud) : 1);
  // What the overcast plates (outside_rain / outside_snow) are multiplied with, by sun elevation: the plates are
  // painted in grey daylight, this turns them into dusk and night.
  const PLATE_GRADE = [
    [-18, '#262f50'], [-12, '#2e3a5c'], [-6, '#464e7c'], [-2, '#7f6a86'], [2, '#cf9f86'], [8, '#efd6c0'], [16, '#ffffff'],
  ];
  function plateGrade(h) {
    const e = Number.isFinite(h) ? h : 45;
    if (e <= PLATE_GRADE[0][0]) return PLATE_GRADE[0][1];
    for (let i = 1; i < PLATE_GRADE.length; i++) {
      if (e <= PLATE_GRADE[i][0]) {
        const a = PLATE_GRADE[i - 1], b = PLATE_GRADE[i];
        return mix(a[1], b[1], (e - a[0]) / (b[0] - a[0]));
      }
    }
    return '#ffffff';
  }
  // The lighting for a sky with clouds in it: a copy of `L` (the result of lighting(h)) with
  //   cloud       the cloud factor itself, 0..1
  //   sunTransmit share of direct sun left (0 under a full overcast)
  //   ambient / ambientStr  cooler and a little darker (the characters are multiplied by them)
  //   indoor, indoorA  a cool grey wash (colour, alpha) laid over the room's layers: a little cooler and dimmer
  //   plate       multiply colour for the overcast window plates at this time of day
  //   lamp, city, stars     lamps look brighter under a grey sky, stars are hidden
  // Without clouds the very same object comes back, so clear weather costs nothing and changes nothing.
  function withWeather(L, cloud) {
    const c = Number.isFinite(cloud) ? clamp(cloud, 0, 1) : 0;
    if (c <= 0.001) return L;
    const day = L.dayness;
    const dim = c * (0.35 + 0.65 * day);          // by night the sky is dark anyway; the grey matters by day
    return Object.assign({}, L, {
      cloud: c,
      sunTransmit: sunTransmit(c),
      ambient: mix(L.ambient, '#8493ad', 0.30 * dim),
      ambientStr: clamp(L.ambientStr + 0.10 * dim, 0, 1),
      indoor: mix('#3c4a66', '#5e6f8c', L.dayness),           // the grey wash laid over the room's layers ...
      indoorA: 0.2 * dim,                                      // ... and how strongly (0 clear .. 0.2 overcast by day)
      plate: plateGrade(L.h),
      lamp: clamp(L.lamp + 0.18 * c * day, 0, 1),
      city: L.city,
      stars: L.stars * (1 - c),
    });
  }

  return { lighting, cssVars, mix, smoothstep, TABLE, sunTransmit, plateGrade, withWeather, PLATE_GRADE };
});
