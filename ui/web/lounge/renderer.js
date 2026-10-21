/* Canvas 2D drawing for the lounge scene (docs/LOUNGE_SCENE_DESIGN.md 8).
   Geometry helpers are pure and exported for tests; createRenderer() does the drawing and needs
   a browser canvas (or anything with the same 2D API). Everything is drawn in the scene's logical
   1440 x 1040 coordinates under a scale transform. */
(function (root, factory) {
  const api = factory(root.T2LoungeLighting || (typeof require === 'function' ? require('./lighting.js') : null));
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeRenderer = api;
})(typeof window !== 'undefined' ? window : globalThis, function (Lighting) {
  'use strict';
  const RAD = Math.PI / 180;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const wrap180 = a => ((((a + 180) % 360) + 360) % 360) - 180;
  const STATUS_COLORS = { time: '#ffd27a', BOARDING: '#7dffb0', 'LAST CALL': '#ff9d6a', DEPARTED: '#8a97a6', 'ON TIME': '#ffffff' };
  const COLUMN_RATIOS = [0.22, 0.34, 0.18, 0.26];
  const SUN_RADIUS = 26, SUN_GLOW = 90, MOON_RADIUS = 22;

  // ---------------------------------------------------------------- geometry (8.2, 8.3)
  // Fraction of the way between lighting stages for a layer's variants: [{index, alpha}] drawn in order.
  function blendVariants(variants, elev) {
    if (variants.length === 1 || elev <= variants[0].elev) return [{ index: 0, alpha: 1 }];
    const last = variants.length - 1;
    if (elev >= variants[last].elev) return [{ index: last, alpha: 1 }];
    let i = 0;
    while (i < last - 1 && variants[i + 1].elev <= elev) i++;
    const t = (elev - variants[i].elev) / (variants[i + 1].elev - variants[i].elev);
    return [{ index: i, alpha: 1 }, { index: i + 1, alpha: t }];
  }
  const sunRelative = (azimuth, facing) => wrap180(azimuth - facing);
  // 0 when the sun is behind the window or below the horizon, up to 1 for a high sun in front of it.
  // cloud (0..1, optional): the sky's cloud cover; direct sun is gone under a full overcast (Lighting.sunTransmit).
  const directLight = (rel, h, cloud) => clamp(Math.cos(rel * RAD), 0, 1) * Lighting.smoothstep(0, 6, h) * (cloud === undefined ? 1 : Lighting.sunTransmit(cloud));
  function discPosition(scene, rel, h) {
    const w = scene.window;
    return {
      x: w.x + w.w / 2 + (rel / 60) * (w.w / 2),
      y: scene.horizonY - h * 12,
      visible: Math.abs(rel) <= 60 && h > -2 && h < 40,
    };
  }
  // Cast shadow of a standing figure: flipped under the feet, leaning away from the sun.
  function sunShadow(rel, h) {
    return { skew: -Math.sin(rel * RAD), len: clamp(1 / Math.tan(Math.max(h, 0.1) * RAD), 0.3, 3) * 0.35 };
  }
  function floorPatch(rel, h) {
    return { skewDeg: clamp(-rel * 0.8, -40, 40), scaleY: clamp(0.25 / Math.tan(Math.max(h, 0.1) * RAD), 0.15, 1.0) };
  }
  // Nearest lamp that lights the foot point: {lamp, dist, dx} or null.
  function nearestLamp(lamps, fx, fy) {
    let best = null;
    for (const l of lamps) {
      const dist = Math.hypot(fx - l.x, fy - l.y);
      if (dist < l.r && (!best || dist < best.dist)) best = { lamp: l, dist, dx: fx - l.x };
    }
    return best;
  }
  function lampShadow(lamps, lighting, direct, fx, fy) {
    if (!(lighting.lamp > 0.5 && direct < 0.2)) return null;
    const n = nearestLamp(lamps, fx, fy);
    if (!n) return null;
    return { skew: clamp(n.dx / 300, -1, 1) * 0.8, len: 0.6 * 0.35, alpha: 0.22 * lighting.lamp * (1 - n.dist / n.lamp.r) };
  }
  // Offset of the dark disc that carves the lit part of the moon. phase: 0 new .. 0.5 full.
  function moonShadowOffset(phase, southern, r) {
    const lit = phase < 0.5 ? phase * 2 : (1 - phase) * 2;
    const waxing = phase < 0.5;
    const dir = (waxing ? -1 : 1) * (southern ? -1 : 1);
    return dir * 2 * r * lit;
  }
  const tintColor = (ambient, strength) => Lighting.mix('#ffffff', ambient, clamp(strength, 0, 1));

  // ---------------------------------------------------------------- weather geometry (docs 13)
  // Slant of falling rain on the screen (screen px right per px down) from the wind: `dir` is where the
  // wind comes from (degrees, north = 0), `facing` the compass direction the window looks toward. Looking
  // out, the screen's right-hand side is facing + 90. A calm sky still tilts the rain a little.
  // windRight: -1..1, how much the wind blows toward the screen's right-hand side (1 = straight right)
  const windRight = (dirDeg, facing) => Math.cos(((Number.isFinite(dirDeg) ? dirDeg : 0) + 180 - ((Number.isFinite(facing) ? facing : 225) + 90)) * RAD);
  const windStrength = speedKmh => clamp((Number.isFinite(speedKmh) ? speedKmh : 0) / 45, 0, 1);
  function windSlant(speedKmh, dirDeg, facing) {
    return clamp(-0.1 + windRight(dirDeg, facing) * windStrength(speedKmh) * 0.6, -0.55, 0.55);
  }
  // how much of the full rain / snow shows for an intensity word (also the plate's strength)
  const RAIN_AMT = { none: 0, light: 0.35, moderate: 0.68, heavy: 1 };
  const SNOW_AMT = { none: 0, light: 0.5, moderate: 0.5, heavy: 1 };
  const RAIN_PLATE = { none: 0, light: 0.72, moderate: 0.9, heavy: 1 };

  // ---------------------------------------------------------------- the taxiing plane (docs 14)
  // A lane is a straight line on the ground plane. The plane is drawn upright and unrotated, so it
  // only slides along the lane, and gets smaller, higher and hazier the farther away it is:
  //   s(y) = (y - horizon) / (ref.y - horizon)     scale of a plane whose wheels touch screen y
  // The lane's two y values (start, end of the run in the heading direction) fix s0 and s1. Progress
  // p (0..1, eased in time) is uniform along the ground, so the screen speed follows the scale:
  //   s(p) = s0 * (s1/s0)^p,   x(p) = xStart + (xEnd - xStart) * ((s1/s0)^p - 1) / (s1/s0 - 1)
  // x is then linear in s, i.e. the wheels run along a straight screen line.
  const laneScale = (pl, y) => (y - pl.horizon) / (pl.ref.y - pl.horizon);
  function laneRun(pl, lane, aspect, win) {
    const ln = pl.lanes[lane];
    const s0 = laneScale(pl, ln.y[0]), s1 = laneScale(pl, ln.y[1]);
    const half = 0.5 * aspect * pl.ref.h * Math.max(s0, s1) + (Number.isFinite(pl.margin) ? pl.margin : 30);
    return { s0, s1, xa: win.x - half, xb: win.x + win.w + half, ln };
  }
  const planeEase = u => { const c = clamp(u, 0, 1); return c * c * (3 - 2 * c) * 0.3 + c * 0.7; };
  // Pose of the plane at u (0..1 of its run): {x (centre), y (wheel contact line), h (sprite height), s, p, haze, world}
  function planePose(pl, lane, right, u, aspect, win) {
    const L = laneRun(pl, lane, aspect, win), p = planeEase(u);
    const r = L.s1 / L.s0, grow = Math.abs(r - 1) < 1e-6 ? p : (Math.pow(r, p) - 1) / (r - 1);
    const xs = right ? L.xa : L.xb, xe = right ? L.xb : L.xa;
    const s = L.s0 * Math.pow(r, p);
    const t = Math.abs(L.s1 - L.s0) < 1e-9 ? p : (s - L.s0) / (L.s1 - L.s0);
    const hz = L.ln.haze || [0.3, 0.3];
    return { x: xs + (xe - xs) * grow, y: pl.horizon + s * (pl.ref.y - pl.horizon), h: pl.ref.h * s, s, p,
      haze: hz[0] + (hz[1] - hz[0]) * t,
      world: Math.abs(L.s1 - L.s0) < 1e-9 ? Math.abs(xe - xs) / L.s0 : Math.abs(xe - xs) / (L.s1 - L.s0) * Math.abs(Math.log(r)) };      // ground distance of the whole run, in px at scale 1
  }

  // ---------------------------------------------------------------- renderer
  function createRenderer(opts) {
    const { canvas, assets } = opts;
    const scene = assets.scene;
    const W = scene.size[0], H = scene.size[1];
    const make = opts.createCanvas || function (w, h) {
      const c = document.createElement('canvas'); c.width = w; c.height = h; return c;
    };
    const ctx = canvas.getContext('2d');
    const chars = new Map(assets.chars.map(c => [c.manifest.name, c]));
    let pw = 0, ph = 0, k = 1;
    const caches = {};                 // group -> { canvas, ctx }
    let scratch = null;
    let lightKey = '', boardKey = '', cacheDirty = true;
    let tintCache = new Map();
    const silhouettes = new Map();
    let moonSprite = null, moonKey = '';
    const stars = (function () {       // fixed star field, in the sky area of the window
      let a = 12345;
      const r = () => { a = (a * 1664525 + 1013904223) >>> 0; return a / 4294967296; };
      const w = scene.window, out = [];
      for (let i = 0; i < 120; i++) out.push({ x: w.x + 12 + r() * (w.w - 24), y: w.y + 8 + r() * (scene.horizonY - w.y - 40), s: 1 + Math.floor(r() * 2.4), a: 0.5 + r() * 0.5 });
      return out;
    }());
    const clouds = [0, 1, 2, 3, 4].map(i => ({ x: i * 230, y: scene.window.y + 70 + (i * 53) % 210, w: 150 + (i * 37) % 90, speed: 3 + (i % 3) * 1.5 }));

    function ensureCache(group) {
      if (!caches[group] || caches[group].canvas.width !== pw || caches[group].canvas.height !== ph) {
        const c = make(pw, ph);
        caches[group] = { canvas: c, ctx: c.getContext('2d') };
        cacheDirty = true;
      }
      return caches[group];
    }

    function resize(cssWidth, dpr) {
      const scale = Math.min(dpr || 1, 2);       // sharper on phones; the cost stays well under a millisecond
      const w = Math.max(1, Math.round(cssWidth * scale)), h = Math.max(1, Math.round(w * H / W));
      if (w === pw && h === ph) return false;
      pw = w; ph = h; k = w / W; boardBox = null;
      canvas.width = w; canvas.height = h;
      scratch = make(w, h);
      for (const g of ['far', 'back', 'mid', 'arms', 'front', 'board']) ensureCache(g);
      dprNow = dpr || 1;
      layoutWx();
      tintCache = new Map();
      cacheDirty = true;
      return true;
    }

    // -------- background caches
    function drawLayer(target, layer, L) {
      const sc = scratch.getContext('2d');
      sc.setTransform(1, 0, 0, 1, 0, 0);
      sc.clearRect(0, 0, pw, ph);
      sc.setTransform(k, 0, 0, k, 0, 0);
      for (const b of blendVariants(layer.variants, L.h)) {
        sc.globalAlpha = b.alpha;
        sc.drawImage(layer.variants[b.index].img, 0, 0, W, H);
      }
      sc.globalAlpha = 1;
      if (layer.def.tint) {
        const strength = L.ambientStr * (layer.variants.length > 1 ? 0.5 : 1);
        if (strength > 0.001) {
          sc.globalCompositeOperation = 'multiply';
          sc.fillStyle = tintColor(L.ambient, strength);
          sc.fillRect(0, 0, W, H);
          sc.globalCompositeOperation = 'destination-in';
          sc.drawImage(layer.variants[0].img, 0, 0, W, H);
          sc.globalCompositeOperation = 'source-over';
        }
      }
      // under a grey sky the room is a little cooler and dimmer (Lighting.withWeather): the same grey wash
      // over every room layer so their seams stay invisible (source-atop keeps each layer's own alpha, soft
      // edges included); the window picture has its own grades
      if (L.indoorA > 0.002 && layer.def.group !== 'far') {
        sc.globalCompositeOperation = 'source-atop';
        sc.fillStyle = hexAlpha(L.indoor, L.indoorA);
        sc.fillRect(0, 0, W, H);
        sc.globalCompositeOperation = 'source-over';
      }
      target.save();
      target.setTransform(1, 0, 0, 1, 0, 0);
      target.drawImage(scratch, 0, 0);
      target.restore();
      if (layer.emission) {
        const a = clamp(L[layer.def.emissionKey] || 0, 0, 1);
        if (a > 0.01) {
          target.save();
          target.globalCompositeOperation = 'lighter';
          target.globalAlpha = a;
          target.drawImage(layer.emission, 0, 0, W, H);
          target.restore();
        }
      }
    }

    // Rows follow the painted panel: each row gets its own affine map from its left edge to its
    // right edge, which tracks the panel's slant and its slight perspective.
    function drawBoard(target, rows) {
      const b = scene.board;
      if (!rows || !rows.length) return;
      const lerp = (p, q, t) => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
      const n = b.rows;
      // Row i lies between boundary lines i and i+1: the painted ones, or an even split of the box.
      const line = i => (b.lines ? b.lines[i] : [lerp([b.x, b.y], [b.x, b.y + b.h], i / n), lerp([b.x + b.w, b.y], [b.x + b.w, b.y + b.h], i / n)]);
      rows.slice(0, n).forEach((row, i) => {
        const [L0, R0] = line(i), [L1, R1] = line(i + 1);
        const w = Math.hypot(R0[0] - L0[0], R0[1] - L0[1]), h = Math.hypot(L1[0] - L0[0], L1[1] - L0[1]);
        target.save();
        // clip to the real band between the two painted lines (they are not parallel), so a glyph
        // that reaches a line is cut along it
        target.beginPath(); target.moveTo(L0[0], L0[1]); target.lineTo(R0[0], R0[1]); target.lineTo(R1[0], R1[1]); target.lineTo(L1[0], L1[1]); target.closePath(); target.clip();
        target.transform((R0[0] - L0[0]) / w, (R0[1] - L0[1]) / w, (L1[0] - L0[0]) / h, (L1[1] - L0[1]) / h, L0[0], L0[1]);
        target.font = 'bold ' + Math.round(h * 0.5) + 'px monospace';
        target.textBaseline = 'middle';
        const pad = w * 0.035, inner = w - pad * 2;
        let cx = pad;
        const cells = [[row.flight, '#ffffff'], [row.dest, '#ffffff'], [row.time, STATUS_COLORS.time], [row.status, STATUS_COLORS[row.status] || '#ffffff']];
        if (row.statusKey) cells[3][1] = STATUS_COLORS[row.statusKey] || '#ffffff';
        cells.forEach(([text, color], j) => {
          target.fillStyle = color;
          target.fillText(text, cx, h / 2, inner * COLUMN_RATIOS[j] - 6);
          cx += inner * COLUMN_RATIOS[j];
        });
        if (row.mine) { target.fillStyle = '#ffd27a'; target.beginPath(); target.arc(pad * 0.45, h / 2, 4, 0, 6.2832); target.fill(); }
        target.restore();
      });
    }

    // Split-flap board. The text lives on its own layer; when a row changes its letters roll through
    // random characters and settle left to right, like the real thing. Idle, the layer is just copied.
    const FLAP_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    const FLAP_SETTLE = 0.16, FLAP_PER_CHAR = 0.035, FLAP_PER_ROW = 0.07, FLAP_TICK = 0.05;
    let shownRows = [], flip = null, boardBox = null;
    const state0Rows = () => (flip ? flapRows(flip, flip.t) : shownRows);
    function boardBounds() {
      if (boardBox) return boardBox;
      const b = scene.board, pts = b.lines ? b.lines.flat() : [[b.x, b.y], [b.x + b.w, b.y + b.h]];
      const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
      const x0 = Math.floor((Math.min(...xs) - 4) * k), y0 = Math.floor((Math.min(...ys) - 4) * k);
      boardBox = { x: Math.max(0, x0), y: Math.max(0, y0), w: Math.ceil((Math.max(...xs) + 4) * k) - Math.max(0, x0), h: Math.ceil((Math.max(...ys) + 4) * k) - Math.max(0, y0) };
      return boardBox;
    }
    function paintBoard(rows) {
      const c = caches.board.ctx, bb = boardBounds();
      c.setTransform(1, 0, 0, 1, 0, 0);
      c.clearRect(bb.x, bb.y, bb.w, bb.h);
      c.setTransform(k, 0, 0, k, 0, 0);
      drawBoard(c, rows);
    }
    function scramble(from, to, t0, t, seed) {
      if (from === to) return to;
      const n = Math.max(from.length, to.length), tick = Math.floor(t / FLAP_TICK);
      let out = '';
      for (let i = 0; i < n; i++) {
        const target = to[i] || ' ';
        if (t - t0 >= FLAP_SETTLE + i * FLAP_PER_CHAR) { out += target; continue; }
        let h = Math.imul(seed * 1013 + i * 7919 + tick * 104729, 2654435761); h = Math.imul(h ^ (h >>> 15), 2246822519) >>> 0;
        out += (target === ' ' && (from[i] || ' ') === ' ') ? ' ' : FLAP_CHARS[h % FLAP_CHARS.length];
      }
      return out.replace(/\s+$/, '');
    }
    function flapRows(f, t) {
      return f.to.map((row, r) => {
        const old = f.from[r] || { flight: '', dest: '', time: '', status: '' };
        const t0 = f.t0 + r * FLAP_PER_ROW;
        return { flight: scramble(old.flight, row.flight, t0, t, r * 4 + 1), dest: scramble(old.dest, row.dest, t0, t, r * 4 + 2),
          time: scramble(old.time, row.time, t0, t, r * 4 + 3), status: scramble(old.status, row.status, t0, t, r * 4 + 4),
          statusKey: row.status, mine: row.mine };
      });
    }
    function flipDone(f, t) {
      const longest = Math.max(1, ...f.to.flatMap(r => [r.flight, r.dest, r.time, r.status].map(x => String(x).length)));
      return t - f.t0 > FLAP_SETTLE + longest * FLAP_PER_CHAR + f.to.length * FLAP_PER_ROW + 0.05;
    }

    // Aviation lights in the window view pulse at night: a soft glow brightens over the painted lamp
    // and fades again (additive, so the painting underneath is never covered).
    function drawBeacons(c, L, t) {
      const list = scene.beacons;
      if (!list || !list.length || L.city < 0.05) return;
      c.save();
      c.globalCompositeOperation = 'lighter';
      for (const b of list) {
        const u = (((t + b.phase) % b.period) + b.period) % b.period / b.period;
        const pulse = Math.pow(Math.max(0, Math.sin(u * Math.PI)), 3);     // short bright flash
        const a = pulse * L.city * 0.9;
        if (a < 0.01) continue;
        const g = c.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r * 2.4);
        g.addColorStop(0, hexAlpha(b.color, a)); g.addColorStop(0.35, hexAlpha(b.color, a * 0.45)); g.addColorStop(1, hexAlpha(b.color, 0));
        c.fillStyle = g;
        c.fillRect(b.x - b.r * 2.4, b.y - b.r * 2.4, b.r * 4.8, b.r * 4.8);
      }
      c.restore();
    }

    // Aircraft taxiing past the window now and then. Deterministic in scene time, so a reload shows
    // the same plane at the same moment.
    const planeTint = new Map();
    let hazeColor = '#808080', planeHaze = '#808080';
    // Average colour of the apron behind the plane in the current window view; the plane is graded
    // toward it so a crisp white sprite sits inside the softer painting.
    // Average colour of a region of a cache, read from a tiny scaled copy: reading a large region
    // back from the GPU can stall a phone for several milliseconds.
    let probe = null;
    function averageColor(src, sx, sy, sw, sh) {
      if (!probe) probe = make(24, 16);
      const pc = probe.getContext('2d');
      pc.setTransform(1, 0, 0, 1, 0, 0);
      pc.clearRect(0, 0, 24, 16);
      pc.drawImage(src, sx, sy, Math.max(1, sw), Math.max(1, sh), 0, 0, 24, 16);
      const d = pc.getImageData(0, 0, 24, 16).data;
      let r = 0, g = 0, b = 0, n = 0;
      for (let i = 0; i < d.length; i += 4) { if (d[i + 3] > 200) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; } }
      return n ? [r / n, g / n, b / n] : null;
    }
    const toHex3 = c => '#' + c.map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
    function sampleHaze() {
      const p = scene.planes;
      if (!p || !caches.far) return hazeColor;
      try {
        // the apron the plane taxis on: from just below the horizon down to the bottom of the glass
        const y0 = Number.isFinite(p.horizon) ? p.horizon + 70 : p.y - p.height, y1 = p.ref ? p.ref.y + 5 : p.y;
        const x = Math.round(scene.window.x * k), y = Math.round(y0 * k);
        const w = Math.round(Math.min(scene.window.w, 600) * k), h = Math.round((y1 - y0) * k);
        const c = averageColor(caches.far.canvas, x, y, w, h);
        return c ? toHex3(c) : hazeColor;
      } catch (e) { return hazeColor; }
    }
    // Average colour and brightness of the room where people walk (sofas and floor). Characters are
    // graded toward it so a bright, clean sprite sits inside the painted light instead of on top of it.
    let room = { color: '#808080', lum: 0.5 };
    function sampleRoom() {
      try {
        const c = averageColor(caches.back.canvas, 0, Math.round(ph * 0.6), pw, Math.round(ph * 0.35));
        if (!c) return room;
        return { color: toHex3(c), lum: (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255 };
      } catch (e) { return room; }
    }
    // ps: the director's plane ({u, right, lane} or null). Without one (tests, old callers) it runs on a timer.
    // Scenes without scene.planes.lanes keep the old flat slide at constant size.
    function planeState(t, ps) {
      const p = scene.planes;
      if (!p || !assets.planes) return null;
      const lanes = Array.isArray(p.lanes) && p.lanes.length ? p.lanes : null;
      let u, right, lane = 0;
      if (ps !== undefined) {
        if (!ps) return null;
        u = ps.u; right = ps.right; lane = Number.isInteger(ps.lane) ? clamp(ps.lane, 0, lanes ? lanes.length - 1 : 0) : 0;
      } else {
        const n = Math.floor(t / p.period), phase = t - n * p.period;
        lane = lanes ? n % lanes.length : 0;
        const dur = lanes && Number.isFinite(lanes[lane].duration) ? lanes[lane].duration : p.duration;
        if (phase > dur) return null;
        u = phase / dur; right = n % 2 === 0;
      }
      const img = right ? assets.planes.right : assets.planes.left;
      if (!lanes) {
        const e = planeEase(u);
        return { x: right ? p.from + (p.to - p.from) * e : p.to - (p.to - p.from) * e, y: p.y, h: p.height, s: 1, p: e, haze: Number.isFinite(p.haze) ? p.haze : 0.3, world: 0, img, right, lane: 0 };
      }
      return Object.assign(planePose(p, lane, right, u, img.width / img.height, scene.window), { img, right, lane });
    }
    // The plane, in scene coordinates on context c (the window layer). wet: 0..1 how rainy / snowy it is.
    function drawPlane(c, L, t, ps, wet) {
      const st = planeState(t, ps);
      if (!st) return;
      const img = st.img, p = scene.planes;
      const haze = Math.round(clamp(st.haze + 0.14 * (wet || 0), 0, 0.75) * 30) / 30;       // a wet air is hazier
      const key = (st.right ? 'r' : 'l') + L.ambient + Math.round(L.ambientStr * 50) + planeHaze + haze;
      let tinted = planeTint.get(key);
      if (!tinted) {
        tinted = make(img.width, img.height);
        const g = tinted.getContext('2d');
        g.drawImage(img, 0, 0);
        const s2 = clamp(L.ambientStr * 1.3, 0, 1);
        if (s2 > 0.001) {
          g.globalCompositeOperation = 'multiply'; g.fillStyle = tintColor(L.ambient, s2); g.fillRect(0, 0, img.width, img.height);
          g.globalCompositeOperation = 'destination-in'; g.drawImage(img, 0, 0);
        }
        // grade toward the scene: pull colours toward the apron's average (distance haze) and soften
        g.globalCompositeOperation = 'source-atop';
        g.globalAlpha = haze;
        g.fillStyle = planeHaze; g.fillRect(0, 0, img.width, img.height);
        g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
        const soft = make(Math.max(1, Math.round(img.width * 0.55)), Math.max(1, Math.round(img.height * 0.55)));
        soft.getContext('2d').drawImage(tinted, 0, 0, soft.width, soft.height);
        tinted = soft;
        if (planeTint.size > 24) planeTint.clear();
        planeTint.set(key, tinted);
      }
      const h = st.h, w = h * img.width / img.height, ground = Number.isFinite(p.ground) ? p.ground : 1;
      // a taxiing plane is never perfectly still: a slow, tiny bounce on its gear (two mixed waves,
      // about a pixel at full size, smaller far away)
      const bob = (Math.sin(t * 2.3) * 0.7 + Math.sin(t * 5.9 + 1.3) * 0.35) * st.s;
      const top = st.y - ground * h + bob;                       // the wheels touch the lane's line (st.y)
      // soft contact shadow on the apron under the whole plane, scaled with it
      c.save();
      c.globalAlpha = 0.30 * (0.5 + 0.5 * L.dayness) * (1 - 0.35 * (wet || 0));
      c.translate(st.x + (st.right ? 1 : -1) * w * 0.01, st.y - 0.006 * h); c.scale(1, 0.085);
      const sg = c.createRadialGradient(0, 0, 0, 0, 0, w * 0.47);
      sg.addColorStop(0, '#000000'); sg.addColorStop(0.55, 'rgba(0,0,0,0.55)'); sg.addColorStop(1, 'rgba(0,0,0,0)');
      c.fillStyle = sg;
      c.beginPath(); c.arc(0, 0, w * 0.47, 0, 6.2832); c.fill();
      c.restore();
      c.drawImage(tinted, st.x - w / 2, top, w, h);
      // rolling gear: three spokes on each hub, turned by the distance travelled on the ground
      const wl = p.wheels && p.wheels[st.right ? 'right' : 'left'];
      if (wl) {
        const ox = st.x - w / 2;
        c.save();
        c.lineCap = 'round';
        c.strokeStyle = '#c9ced6';
        c.globalAlpha = 0.55 + 0.35 * L.dayness;
        for (const [fx, fy, frx, fry] of wl) {
          const cx = ox + fx * w, cy = top + fy * h, rx = frx * h, ry = fry * h;
          const dist = st.world ? st.p * st.world * (st.right ? 1 : -1) : st.x;       // ground distance, px at scale 1
          const ang = dist / (fry * (p.ref ? p.ref.h : h) * 1.9);                      // tyre radius ~1.9x the hub
          c.lineWidth = Math.max(0.8, ry * 0.22);
          c.beginPath();
          for (let k = 0; k < 3; k++) {
            const a = ang + k * 2.0944;
            c.moveTo(cx + Math.cos(a) * rx * 0.25, cy + Math.sin(a) * ry * 0.25);
            c.lineTo(cx + Math.cos(a) * rx * 0.85, cy + Math.sin(a) * ry * 0.85);
          }
          c.stroke();
        }
        c.restore();
      }
    }

    // ================================================================ weather (docs 13)
    // Three things are layered on top of the clear window picture, all inside `wr` (scene px) and
    // clipped to the glass (the alpha of the `outside` layer):
    //   1. grade caches, rect-sized: an overcast version of the clear plate (`cloudy`) and the rain and
    //      snow plates, graded for the time of day; crossfaded in by their mixes (0.8 s)
    //   2. one window layer per frame, only while something moves in it: the plane, the falling rain or
    //      snow (three depths each, from pre-rendered sprites, pooled typed arrays, no allocation per
    //      frame), the drops running down the glass, ripples on the apron, fog, lightning
    //   3. the room's light, through Lighting.withWeather (cool, dimmer, no direct sun)
    const wxScene = scene.weather || null;
    const plates = assets.weather || {};
    const wr = wxScene && Array.isArray(wxScene.rect) ? { x: wxScene.rect[0], y: wxScene.rect[1], w: wxScene.rect[2], h: wxScene.rect[3] }
      : { x: scene.window.x, y: scene.window.y, w: scene.window.w, h: scene.window.h };
    let box = { x: 0, y: 0, w: 1, h: 1 }, dprNow = 1, wxSeen = false;
    const CLEAR_WX = { kind: 'clear', intensity: 'none', thunder: false, cloud: 0, windSpeed: 0, windDir: 0 };
    let slayer = null, maskC = null;
    const wxc = { cloudy: null, rain: null, snow: null, lights: null };            // { canvas, key }
    let farVersion = 0;
    const WX = { cloud: 0, rain: 0, snow: 0, fog: 0, rainAmt: 0, snowAmt: 0, rainPlate: 0, kind: 'clear', intensity: 'none', thunder: false,
      slant: -0.1, drift: 0, lastT: null, lastKey: '', haze: { rain: '#6c7a88', snow: '#aeb9c4' } };
    // small deterministic generator (the particles are the same on every run)
    let rs = 20261021;
    const rnd = () => { rs = (rs + 0x6d2b79f5) | 0; let t = Math.imul(rs ^ (rs >>> 15), 1 | rs); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

    // ---- particle pools: [x, y, a, b] per particle in rect-local scene px; sized for heavy weather once
    const RAIN_LAYERS = [   // far, mid, near: count at full rain, length, width, speed (px/s), alpha
      { n: 170, len: 24, wid: 1.1, vy: 600, a: 0.26 }, { n: 105, len: 42, wid: 1.6, vy: 900, a: 0.40 }, { n: 42, len: 70, wid: 2.4, vy: 1350, a: 0.55 }];
    const SNOW_LAYERS = [   // far, mid, near: count at full snow, radius, fall speed, sway amplitude, alpha
      { n: 150, r: 1.7, vy: 24, sw: 5, a: 0.7 }, { n: 95, r: 3.0, vy: 40, sw: 9, a: 0.85 }, { n: 38, r: 5.2, vy: 68, sw: 15, a: 0.95 }];
    const makePool = (n, fill) => { const a = new Float32Array(n * 4); for (let i = 0; i < n; i++) fill(a, i * 4); return a; };
    const rainPool = RAIN_LAYERS.map(l => makePool(l.n, (a, o) => { a[o] = rnd() * (wr.w + 200) - 100; a[o + 1] = rnd() * (wr.h + l.len * 2) - l.len; a[o + 2] = 0.8 + rnd() * 0.4; a[o + 3] = rnd(); }));
    const snowPool = SNOW_LAYERS.map(l => makePool(l.n, (a, o) => { a[o] = rnd() * (wr.w + 100) - 50; a[o + 1] = rnd() * (wr.h + 20) - 10; a[o + 2] = rnd() * 6.2832; a[o + 3] = 0.6 + rnd() * 0.8; }));
    const NDRIP = 14, NBEAD = 40, NRIP = 14;
    // drops running down the glass: [x, y, speed, state] + [trail, wait, stop at, phase]
    const drips = new Float32Array(NDRIP * 8), beads = new Float32Array(NBEAD * 4), ripples = new Float32Array(NRIP * 4);
    for (let i = 0; i < NDRIP; i++) { const o = i * 8; drips[o] = 30 + rnd() * (wr.w - 60); drips[o + 1] = rnd() * wr.h * 0.7; drips[o + 2] = 10 + rnd() * 18; drips[o + 3] = rnd() < 0.5 ? 1 : 0; drips[o + 4] = 0; drips[o + 5] = rnd() * 6; drips[o + 6] = drips[o + 1] + 60 + rnd() * 260; drips[o + 7] = rnd() * 6.28; }
    for (let i = 0; i < NBEAD; i++) { const o = i * 4; beads[o] = 20 + rnd() * (wr.w - 40); beads[o + 1] = 20 + rnd() * (wr.h - 120); beads[o + 2] = 0.9 + rnd() * 1.4; beads[o + 3] = rnd() * 6.28; }
    for (let i = 0; i < NRIP; i++) { const o = i * 4; ripples[o] = 0; ripples[o + 1] = 0; ripples[o + 2] = -1; ripples[o + 3] = 0; }
    // lightning: next flash time, current flash start and strength
    const bolt = { next: 6, t0: -9, amp: 0, t1: -9, amp1: 0 };

    // ---- sprites, rebuilt when the slant, the colours or the canvas scale change
    let sprKey = '', rainSpr = [], snowSpr = [], dripSpr = null, beadSpr = null;
    function ensureSprites(L) {
      const slant = Math.round(WX.slant * 50) / 50, day = L.dayness;
      const key = [slant, k.toFixed(3), Math.round(day * 6)].join('|');
      if (key === sprKey) return;
      sprKey = key;
      // colours: the rain is light against a dark sky and a little dimmer by night
      const rainC = Lighting.mix('#8da0bd', '#eef4fb', day), flake = Lighting.mix('#aab8d8', '#ffffff', day);
      rainSpr = RAIN_LAYERS.map(l => {
        const lenPx = l.len * k, wPx = Math.max(1, l.wid * k), dx = slant * lenPx;
        const w = Math.ceil(Math.abs(dx) + wPx + 2), h = Math.ceil(lenPx + wPx + 2);
        const c = make(w, h), g = c.getContext('2d');
        const x0 = dx >= 0 ? wPx / 2 + 1 : w - wPx / 2 - 1, y0 = wPx / 2 + 1;       // tail at the top
        const grad = g.createLinearGradient(x0, y0, x0 + dx, y0 + lenPx);
        grad.addColorStop(0, hexAlpha(rainC, 0)); grad.addColorStop(1, hexAlpha(rainC, 1));
        g.strokeStyle = grad; g.lineWidth = wPx; g.lineCap = 'round';
        g.beginPath(); g.moveTo(x0, y0); g.lineTo(x0 + dx, y0 + lenPx); g.stroke();
        return { c, w, h, tailX: x0 };
      });
      snowSpr = SNOW_LAYERS.map(l => {
        const r = Math.max(1, l.r * k), s = Math.ceil(r * 2 + 2), c = make(s, s), g = c.getContext('2d');
        const grad = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, r);
        grad.addColorStop(0, hexAlpha(flake, 1)); grad.addColorStop(0.55, hexAlpha(flake, 0.75)); grad.addColorStop(1, hexAlpha(flake, 0));
        g.fillStyle = grad; g.fillRect(0, 0, s, s);
        return { c, s };
      });
      // a drop on the glass: bright core with a dark rim underneath, like the painted ones
      const bs = Math.max(6, Math.ceil(7 * k)), b = make(bs, bs), bg2 = b.getContext('2d');
      const rim = bg2.createRadialGradient(bs / 2, bs / 2 + 0.5, bs * 0.18, bs / 2, bs / 2 + 0.5, bs / 2);
      rim.addColorStop(0, 'rgba(20,30,45,0)'); rim.addColorStop(0.8, 'rgba(20,30,45,0.45)'); rim.addColorStop(1, 'rgba(20,30,45,0)');
      bg2.fillStyle = rim; bg2.fillRect(0, 0, bs, bs);
      const core = bg2.createRadialGradient(bs * 0.42, bs * 0.38, 0, bs / 2, bs / 2, bs * 0.34);
      core.addColorStop(0, 'rgba(255,255,255,0.95)'); core.addColorStop(1, 'rgba(210,225,240,0.25)');
      bg2.fillStyle = core; bg2.beginPath(); bg2.arc(bs / 2, bs / 2, bs * 0.34, 0, 6.2832); bg2.fill();
      beadSpr = { c: b, s: bs };
      const ts = Math.max(2, Math.ceil(2 * k)), tl = Math.max(16, Math.ceil(64 * k)), t = make(ts, tl), tg = t.getContext('2d');
      const tgr = tg.createLinearGradient(0, 0, 0, tl); tgr.addColorStop(0, 'rgba(235,243,252,0)'); tgr.addColorStop(1, 'rgba(235,243,252,0.9)');
      tg.fillStyle = tgr; tg.fillRect(0, 0, ts, tl);
      dripSpr = { c: t, w: ts, h: tl };
    }

    // ---- layout: rect in canvas px, the window layer and the glass mask
    function layoutWx() {
      box = { x: Math.max(0, Math.floor(wr.x * k)), y: Math.max(0, Math.floor(wr.y * k)), w: 1, h: 1 };
      box.w = Math.max(1, Math.min(pw - box.x, Math.ceil(wr.w * k))); box.h = Math.max(1, Math.min(ph - box.y, Math.ceil(wr.h * k)));
      slayer = make(box.w, box.h);
      maskC = null;
      const ml = wxScene && assets.layers.find(l => l.def.id === (wxScene.mask || 'outside'));
      if (ml) {
        maskC = make(box.w, box.h);
        const m = maskC.getContext('2d');
        m.drawImage(ml.variants[0].img, wr.x, wr.y, wr.w, wr.h, 0, 0, box.w, box.h);
      }
      wxc.cloudy = wxc.rain = wxc.snow = wxc.lights = null;
      sprKey = '';
    }

    // ---- grade caches (rect-sized)
    function gradeKey(L) { return Math.round(L.h * 10) + '|' + L.zenith + '|' + Math.round(L.dayness * 20); }
    function rectCanvas() { const c = make(box.w, box.h); return { canvas: c, ctx: c.getContext('2d'), key: '' }; }
    function ensurePlate(kind, L) {
      const img = plates[kind];
      if (!img) return null;
      const key = Lighting.plateGrade(L.h);
      let e = wxc[kind];
      if (!e) e = wxc[kind] = rectCanvas();
      if (e.key !== key) {
        const c = e.ctx;
        c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, box.w, box.h);
        c.drawImage(img, wr.x, wr.y, wr.w, wr.h, 0, 0, box.w, box.h);
        if (key !== '#ffffff') {
          c.globalCompositeOperation = 'multiply'; c.fillStyle = key; c.fillRect(0, 0, box.w, box.h);
          c.globalCompositeOperation = 'destination-in'; c.drawImage(img, wr.x, wr.y, wr.w, wr.h, 0, 0, box.w, box.h);
          c.globalCompositeOperation = 'source-over';
        }
        e.key = key;
        try { const col = averageColor(e.canvas, 0, Math.round(box.h * 0.72), box.w, Math.round(box.h * 0.2)); if (col) WX.haze[kind] = toHex3(col); } catch (err) { /* keep the guess */ }
      }
      return e;
    }
    // the overcast picture for a sky that is only cloudy: the clear plate for this time of day, drained of
    // colour and lifted toward a flat grey light
    function ensureCloudy(L) {
      const key = farVersion + '|' + Math.round(L.dayness * 20);
      let e = wxc.cloudy;
      if (!e) e = wxc.cloudy = rectCanvas();
      if (e.key !== key && caches.far) {
        const c = e.ctx;
        c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1; c.clearRect(0, 0, box.w, box.h);
        c.drawImage(caches.far.canvas, box.x, box.y, box.w, box.h, 0, 0, box.w, box.h);
        c.globalCompositeOperation = 'saturation'; c.fillStyle = '#808080'; c.globalAlpha = 0.72; c.fillRect(0, 0, box.w, box.h);
        c.globalCompositeOperation = 'source-atop'; c.globalAlpha = 0.34; c.fillStyle = Lighting.mix('#262e48', '#c3ccd8', L.dayness); c.fillRect(0, 0, box.w, box.h);
        c.globalCompositeOperation = 'multiply'; c.globalAlpha = 1; c.fillStyle = Lighting.mix('#ffffff', '#cdd6e2', L.dayness); c.fillRect(0, 0, box.w, box.h);
        c.globalCompositeOperation = 'destination-in'; c.drawImage(caches.far.canvas, box.x, box.y, box.w, box.h, 0, 0, box.w, box.h);
        c.globalCompositeOperation = 'source-over';
        e.key = key;
      }
      return e;
    }

    // The lit terminal windows, apron lights and lamp glows of the clear night picture (everything below the
    // horizon band), laid over the dark rain / snow plate with 'lighten' so a wet night still has its lights
    function ensureLights() {
      const key = String(farVersion);
      let e = wxc.lights;
      if (!e) e = wxc.lights = rectCanvas();
      if (e.key !== key && caches.far) {
        const c = e.ctx;
        c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = 'source-over'; c.clearRect(0, 0, box.w, box.h);
        c.drawImage(caches.far.canvas, box.x, box.y, box.w, box.h, 0, 0, box.w, box.h);
        const g = c.createLinearGradient(0, (430 - wr.y) * k, 0, (475 - wr.y) * k);
        g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,1)');
        c.globalCompositeOperation = 'destination-in'; c.fillStyle = g; c.fillRect(0, 0, box.w, box.h);
        c.globalCompositeOperation = 'source-over';
        e.key = key;
      }
      return e;
    }

    // ---- state: ease the mixes toward what the weather asks for
    const toward = (v, target, up, down, dt) => (target > v ? Math.min(target, v + dt / up) : Math.max(target, v - dt / down));
    function updateWx(wx, t, snap) {
      const kind = wx.kind, inten = wx.intensity;
      const dt = WX.lastT === null || snap ? 0 : clamp(t - WX.lastT, 0, 0.25);
      WX.lastT = t;
      const tCloud = kind === 'clear' ? clamp(wx.cloud || 0, 0, 0.5) : (kind === 'cloudy' ? clamp(Math.max(wx.cloud || 0, 0.75), 0, 1) : 1);
      const tRain = kind === 'rain' ? 1 : 0, tSnow = kind === 'snow' ? 1 : 0, tFog = kind === 'fog' ? (inten === 'heavy' ? 1 : 0.75) : 0;
      const tRainAmt = kind === 'rain' ? RAIN_AMT[inten] || RAIN_AMT.moderate : 0, tSnowAmt = kind === 'snow' ? SNOW_AMT[inten] || SNOW_AMT.light : 0;
      const tPlate = kind === 'rain' ? RAIN_PLATE[inten] || 0.9 : 0;
      if (snap) {
        WX.cloud = tCloud; WX.rain = tRain; WX.snow = tSnow; WX.fog = tFog; WX.rainAmt = tRainAmt; WX.snowAmt = tSnowAmt; WX.rainPlate = tPlate;
      } else {
        WX.cloud = toward(WX.cloud, tCloud, 2.5, 2.5, dt);
        WX.rain = toward(WX.rain, tRain, 0.8, 0.8, dt); WX.snow = toward(WX.snow, tSnow, 0.8, 0.8, dt);
        WX.fog = toward(WX.fog, tFog, 2, 2, dt);
        WX.rainAmt = toward(WX.rainAmt, tRainAmt, 1.5, 3.5, dt); WX.snowAmt = toward(WX.snowAmt, tSnowAmt, 1.5, 3.5, dt);
        WX.rainPlate = toward(WX.rainPlate, tPlate, 0.8, 0.8, dt);
      }
      WX.kind = kind; WX.intensity = inten; WX.thunder = !!wx.thunder;
      WX.slant = windSlant(wx.windSpeed, wx.windDir, scene.windowFacing);
      WX.drift = windRight(wx.windDir, scene.windowFacing) * windStrength(wx.windSpeed) * 60;       // px/s sideways, snow
      return dt;
    }
    const smooth01 = v => { const c = clamp(v, 0, 1); return c * c * (3 - 2 * c); };

    // ---- the window layer: plane, rain / snow, drops, ripples, fog, lightning
    function stepRain(c, L, dt, vis, amt) {
      const slant = WX.slant;
      for (let li = 0; li < RAIN_LAYERS.length; li++) {
        const l = RAIN_LAYERS[li], pool = rainPool[li], spr = rainSpr[li];
        const n = Math.min(l.n, Math.round(l.n * amt * vis)), alpha = clamp(l.a * (0.55 + 0.45 * amt) * (0.55 + 0.45 * L.dayness) * 1.25, 0, 1);
        c.globalAlpha = alpha;
        const wide = wr.w + 200, hh = wr.h + l.len * 2;
        for (let i = 0; i < n; i++) {
          const o = i * 4, vy = l.vy * pool[o + 2];
          pool[o + 1] += vy * dt; pool[o] += slant * vy * dt;
          if (pool[o + 1] > wr.h + l.len || pool[o] < -120 || pool[o] > wr.w + 120) {
            pool[o + 1] = -l.len - rnd() * 40; pool[o] = rnd() * wide - 100 - (slant > 0 ? slant * hh * 0.5 : slant * hh * 0.5); pool[o + 2] = 0.8 + rnd() * 0.4;
          }
          c.drawImage(spr.c, pool[o] * k - spr.tailX, pool[o + 1] * k);
        }
      }
      c.globalAlpha = 1;
    }
    function stepSnow(c, L, t, dt, vis, amt) {
      for (let li = 0; li < SNOW_LAYERS.length; li++) {
        const l = SNOW_LAYERS[li], pool = snowPool[li], spr = snowSpr[li];
        const n = Math.min(l.n, Math.round(l.n * amt * vis)), depth = 0.4 + 0.3 * li;
        c.globalAlpha = clamp(l.a * (0.6 + 0.4 * L.dayness) * (0.5 + 0.5 * amt), 0, 1);
        for (let i = 0; i < n; i++) {
          const o = i * 4;
          pool[o + 1] += l.vy * pool[o + 3] * dt; pool[o] += WX.drift * depth * dt * 0.5;
          if (pool[o + 1] > wr.h + 8) { pool[o + 1] = -8 - rnd() * 20; pool[o] = rnd() * (wr.w + 100) - 50; pool[o + 2] = rnd() * 6.2832; pool[o + 3] = 0.6 + rnd() * 0.8; }
          if (pool[o] < -60) pool[o] += wr.w + 120; else if (pool[o] > wr.w + 60) pool[o] -= wr.w + 120;
          const sway = Math.sin(t * (0.55 + 0.5 * pool[o + 3]) + pool[o + 2]) * l.sw;
          c.drawImage(spr.c, (pool[o] + sway) * k - spr.s / 2, pool[o + 1] * k - spr.s / 2);
        }
      }
      c.globalAlpha = 1;
    }
    // drops creeping down the glass: slow, stopping and starting, leaving a thin wet trail that fades
    function stepDrips(c, L, t, dt, amt) {
      const n = Math.round(NDRIP * amt), bn = Math.round(NBEAD * (0.3 + 0.7 * amt));
      const dayA = 0.55 + 0.45 * L.dayness;
      for (let i = 0; i < bn; i++) {              // beads that sit on the glass: they come and go over a minute or so
        const o = i * 4, life = 0.5 + 0.5 * Math.sin(t * 0.09 + beads[o + 3]);
        const a = smooth01(life * 1.6 - 0.2) * 0.8 * dayA;
        if (a < 0.03) continue;
        const sz = beads[o + 2] * k * 2.2;
        c.globalAlpha = a;
        c.drawImage(beadSpr.c, beads[o] * k - sz / 2, beads[o + 1] * k - sz / 2, sz, sz);
      }
      for (let i = 0; i < n; i++) {
        const o = i * 8;
        if (drips[o + 3] === 1) {                 // running
          const pace = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * 0.9 + drips[o + 7]));
          drips[o + 1] += drips[o + 2] * pace * dt;
          drips[o + 4] = Math.min(drips[o + 4] + drips[o + 2] * pace * dt, 70);
          if (drips[o + 1] >= drips[o + 6] || drips[o + 1] > wr.h - 30) { drips[o + 3] = 2; drips[o + 5] = 1; }      // stops: the trail fades
        } else if (drips[o + 3] === 2) {
          drips[o + 5] -= dt / 3.5;
          if (drips[o + 5] <= 0) { drips[o + 3] = 0; drips[o + 5] = 1 + rnd() * 5; }
        } else {                                  // waits, then starts again somewhere higher
          drips[o + 5] -= dt;
          if (drips[o + 5] <= 0) { drips[o] = 30 + rnd() * (wr.w - 60); drips[o + 1] = rnd() * wr.h * 0.45; drips[o + 2] = 10 + rnd() * 18; drips[o + 4] = 0; drips[o + 6] = drips[o + 1] + 60 + rnd() * 280; drips[o + 3] = 1; }
          continue;
        }
        const fade = drips[o + 3] === 2 ? clamp(drips[o + 5], 0, 1) : 1;
        const x = drips[o] * k, y = drips[o + 1] * k, len = drips[o + 4] * k;
        c.globalAlpha = 0.5 * fade * dayA;
        if (len > 2) c.drawImage(dripSpr.c, 0, 0, dripSpr.w, dripSpr.h, x - dripSpr.w / 2, y - len, dripSpr.w, len);
        if (drips[o + 3] === 1 || fade > 0.5) { const sz = 3.2 * k * 1.7; c.globalAlpha = 0.9 * fade * dayA; c.drawImage(beadSpr.c, x - sz / 2, y - sz / 2, sz, sz); }
      }
      c.globalAlpha = 1;
    }
    // small rings on the wet apron far away: they open, thin and vanish
    function stepRipples(c, L, t, dt, amt) {
      const n = Math.round(NRIP * amt);
      c.save();
      c.lineWidth = Math.max(1, 1.1 * k);
      for (let i = 0; i < n; i++) {
        const o = i * 4;
        if (ripples[o + 2] < 0 || t - ripples[o + 2] > ripples[o + 3]) {
          if (ripples[o + 2] >= 0 && rnd() < 0.5) { ripples[o + 2] = -1; continue; }      // rest a moment
          const y = 575 + rnd() * 110;                                                    // on the apron, left of the stairs truck
          ripples[o] = 40 + rnd() * (wr.w - 80); ripples[o + 1] = y - wr.y; ripples[o + 2] = t; ripples[o + 3] = 0.7 + rnd() * 0.5;
        }
        const u = (t - ripples[o + 2]) / ripples[o + 3];
        if (u < 0 || u > 1) continue;
        const persp = (ripples[o + 1] + wr.y - 470) / 215;                                // nearer the glass = bigger
        const r = (1.5 + u * 9) * persp * k;
        c.strokeStyle = 'rgba(' + (L.dayness > 0.5 ? '220,232,245' : '150,170,205') + ',' + ((1 - u) * 0.42).toFixed(3) + ')';
        c.beginPath(); c.ellipse(ripples[o] * k, ripples[o + 1] * k, r, r * 0.28, 0, 0, 6.2832); c.stroke();
      }
      c.restore();
    }
    // thunder: two quick flashes now and then; returns the strength 0..1 at time t
    function lightning(t, thunder) {
      if (!thunder) { bolt.t0 = bolt.t1 = -9; return 0; }
      if (t >= bolt.next) { bolt.t0 = t; bolt.amp = 0.55 + rnd() * 0.45; bolt.t1 = t + 0.13 + rnd() * 0.1; bolt.amp1 = 0.3 + rnd() * 0.4; bolt.next = t + 7 + rnd() * 16; }
      const f = (t0, a) => { const d = t - t0; return d < 0 || d > 0.7 ? 0 : a * Math.exp(-d / 0.11) * Math.min(1, d / 0.02 + 0.2); };
      return Math.max(f(bolt.t0, bolt.amp), f(bolt.t1, bolt.amp1));
    }

    // Draws the window layer onto `ctx` (the main canvas). Does nothing when nothing moves in the window.
    function drawWindowLayer(ctxMain, L, t, dt, ps, still) {
      const amtR = WX.rainAmt, amtS = WX.snowAmt, fog = WX.fog;
      const planeOn = !!(ps && scene.planes && assets.planes);
      const flash = lightning(t, WX.thunder && amtR > 0.2);
      if (!(planeOn || amtR > 0.01 || amtS > 0.01 || fog > 0.01 || flash > 0.01) || !slayer) return;
      ensureSprites(L);
      const c = slayer.getContext('2d');
      c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1; c.clearRect(0, 0, box.w, box.h);
      const vis = still ? 0.45 : 1;                      // reduced motion: a few streaks and flakes in one still picture
      if (planeOn) {
        c.setTransform(k, 0, 0, k, -box.x, -box.y);
        drawPlane(c, L, t, ps, Math.max(WX.rain, WX.snow));
        c.setTransform(1, 0, 0, 1, 0, 0);
      }
      if (fog > 0.01) {                                  // a veil, thicker toward the ground
        const g = c.createLinearGradient(0, 0, 0, box.h), col = Lighting.mix('#2a3350', '#cfd6df', L.dayness);
        g.addColorStop(0, hexAlpha(col, 0.28 * fog)); g.addColorStop(0.6, hexAlpha(col, 0.55 * fog)); g.addColorStop(1, hexAlpha(col, 0.7 * fog));
        c.fillStyle = g; c.fillRect(0, 0, box.w, box.h);
      }
      const wdt = still ? 0 : dt;
      if (amtS > 0.01) stepSnow(c, L, t, wdt, vis, amtS);
      if (amtR > 0.01) {
        stepRain(c, L, wdt, vis, amtR);
        if (amtR > 0.2) stepRipples(c, L, t, wdt, still ? 0.4 : amtR);
        stepDrips(c, L, t, wdt, amtR);
      }
      if (flash > 0.01) { c.fillStyle = 'rgba(214,226,255,' + (flash * 0.5).toFixed(3) + ')'; c.fillRect(0, 0, box.w, box.h); }
      if (maskC) { c.globalCompositeOperation = 'destination-in'; c.drawImage(maskC, 0, 0); c.globalCompositeOperation = 'source-over'; }
      ctxMain.save(); ctxMain.setTransform(1, 0, 0, 1, 0, 0);
      ctxMain.drawImage(slayer, box.x, box.y);
      ctxMain.restore();
      return flash;
    }
    // the plates under the window layer: clear (cache `far`, already drawn) -> overcast -> rain -> snow
    function drawWxPlates(ctxMain, L) {
      if (!slayer) return;
      ctxMain.save(); ctxMain.setTransform(1, 0, 0, 1, 0, 0);
      drawWxPlatesPx(ctxMain, L);
      ctxMain.restore();
    }
    function drawWxPlatesPx(ctxMain, L) {
      const cm = smooth01(WX.cloud / 0.9);
      if (cm > 0.01 && (WX.rain < 0.99 || WX.rainPlate < 0.99) && (WX.snow < 0.99)) {
        const e = ensureCloudy(L);
        if (e) { ctxMain.globalAlpha = cm; ctxMain.drawImage(e.canvas, box.x, box.y); ctxMain.globalAlpha = 1; }
      }
      if (WX.rain > 0.01 && WX.rainPlate > 0.01) {
        const e = ensurePlate('rain', L);
        if (e) { ctxMain.globalAlpha = smooth01(WX.rain) * clamp(WX.rainPlate, 0, 1); ctxMain.drawImage(e.canvas, box.x, box.y); ctxMain.globalAlpha = 1; }
      }
      if (WX.snow > 0.01) {
        const e = ensurePlate('snow', L);
        if (e) { ctxMain.globalAlpha = smooth01(WX.snow); ctxMain.drawImage(e.canvas, box.x, box.y); ctxMain.globalAlpha = 1; }
      }
      const wet = Math.max(smooth01(WX.rain) * WX.rainPlate, smooth01(WX.snow));
      if (wet > 0.01 && L.city > 0.05) {
        const e = ensureLights();
        if (e) { ctxMain.globalCompositeOperation = 'lighten'; ctxMain.globalAlpha = clamp(L.city * wet * 0.8, 0, 1); ctxMain.drawImage(e.canvas, box.x, box.y); ctxMain.globalAlpha = 1; ctxMain.globalCompositeOperation = 'source-over'; }
      }
    }
    function mixHex(a, b, t) { return Lighting.mix(a, b, clamp(t, 0, 1)); }
    // colour the plane is hazed toward: the clear apron, or the wet / snowy one while that plate is up
    function hazeNow() {
      let c = hazeColor;
      const r = Math.round(smooth01(WX.rain) * clamp(WX.rainPlate, 0, 1) * 8) / 8, sn = Math.round(smooth01(WX.snow) * 8) / 8;
      if (r > 0) c = mixHex(c, WX.haze.rain, r);
      if (sn > 0) c = mixHex(c, WX.haze.snow, sn);
      return c;
    }

    let pending = [], pendingL = null, builtKey = '';
    const stages = {};
    function stepRebuild() {
      const g = pending.shift();
      if (!stages[g] || stages[g].canvas.width !== pw || stages[g].canvas.height !== ph) {
        const c = make(pw, ph); stages[g] = { canvas: c, ctx: c.getContext('2d') };
      }
      const st = stages[g];
      st.ctx.setTransform(1, 0, 0, 1, 0, 0);
      st.ctx.clearRect(0, 0, pw, ph);
      st.ctx.setTransform(k, 0, 0, k, 0, 0);
      for (const layer of assets.layers) if (layer.def.group === g) drawLayer(st.ctx, layer, pendingL);
      stages[g] = caches[g]; caches[g] = st;
      if (g === 'far') { hazeColor = sampleHaze(); planeTint.clear(); farVersion++; }
      if (g === 'back') { room = sampleRoom(); tintCache = new Map(); }
    }
    function rebuild(L, rows) {
      for (const g of ['far', 'back', 'mid', 'arms', 'front']) {
        const c = ensureCache(g).ctx;
        c.setTransform(1, 0, 0, 1, 0, 0);
        c.clearRect(0, 0, pw, ph);
        c.setTransform(k, 0, 0, k, 0, 0);
      }
      for (const layer of assets.layers) drawLayer(caches[layer.def.group].ctx, layer, L);
      paintBoard(state0Rows());
      hazeColor = sampleHaze();
      room = sampleRoom();
      planeTint.clear();
      farVersion++;
      cacheDirty = false;
    }

    // -------- per-frame pieces
    function drawSky(c, L, sun, moon, t) {
      const w = scene.window, hy = scene.horizonY;
      const g = c.createLinearGradient(0, w.y, 0, hy);
      g.addColorStop(0, L.zenith); g.addColorStop(1, L.horizonAway);
      c.fillStyle = g;
      c.fillRect(w.x, w.y, w.w, w.h);
      // glow toward the sun
      const near = 0.15 + 0.85 * Math.max(0, Math.cos(sun.rel * RAD));
      const sx = w.x + w.w / 2 + (clamp(sun.rel, -150, 150) / 60) * (w.w / 2);
      const rg = c.createRadialGradient(sx, hy, 0, sx, hy, w.w * 0.9);
      rg.addColorStop(0, hexAlpha(L.horizonSun, 0.9 * near)); rg.addColorStop(1, hexAlpha(L.horizonSun, 0));
      c.fillStyle = rg;
      c.fillRect(w.x, w.y, w.w, hy - w.y + 20);
      // stars
      if (L.stars > 0.01) {
        c.fillStyle = '#ffffff';
        for (const s of stars) { c.globalAlpha = L.stars * s.a; c.fillRect(s.x, s.y, s.s, s.s); }
        c.globalAlpha = 1;
      }
      // moon and sun
      if (moon && moon.visible && sun.h < -4) drawMoon(c, moon, L);
      if (sun.disc.visible && L.sunTransmit === undefined) {          // (under any cloud the disc is gone)
        const d = sun.disc;
        const sg = c.createRadialGradient(d.x, d.y, 0, d.x, d.y, SUN_GLOW);
        sg.addColorStop(0, hexAlpha(L.sunColor, 0.35)); sg.addColorStop(1, hexAlpha(L.sunColor, 0));
        c.fillStyle = sg; c.fillRect(d.x - SUN_GLOW, d.y - SUN_GLOW, SUN_GLOW * 2, SUN_GLOW * 2);
        c.fillStyle = L.sunColor;
        c.beginPath(); c.arc(d.x, d.y, SUN_RADIUS, 0, 6.2832); c.fill();
      }
      // clouds
      const cc = Lighting.mix(L.horizonAway, '#ffffff', 0.6);
      c.fillStyle = hexAlpha(cc, 0.32 + 0.3 * L.dayness);
      for (const cl of clouds) {
        const x = w.x + ((cl.x + t * cl.speed) % (w.w + 400)) - 200;
        for (const [dx, dy, rx, ry] of [[0, 0, cl.w * 0.5, 18], [cl.w * 0.28, -9, cl.w * 0.3, 16], [-cl.w * 0.3, 4, cl.w * 0.28, 12]]) {
          c.beginPath(); c.ellipse(x + dx, cl.y + dy, rx, ry, 0, 0, 6.2832); c.fill();
        }
      }
    }

    function drawMoon(c, moon, L) {
      const key = Math.round(moon.phase * 100) + (moon.southern ? 's' : 'n');
      if (key !== moonKey) {
        const size = MOON_RADIUS * 2 + 4;
        moonSprite = make(size, size);
        const m = moonSprite.getContext('2d');
        m.fillStyle = '#f2efe0';
        m.beginPath(); m.arc(size / 2, size / 2, MOON_RADIUS, 0, 6.2832); m.fill();
        m.globalCompositeOperation = 'destination-out';
        m.beginPath(); m.arc(size / 2 + moonShadowOffset(moon.phase, moon.southern, MOON_RADIUS), size / 2, MOON_RADIUS, 0, 6.2832); m.fill();
        moonKey = key;
      }
      c.globalAlpha = clamp((-4 - moon.h) / 6, 0, 1) * 0.95;
      c.drawImage(moonSprite, moon.x - moonSprite.width / 2, moon.y - moonSprite.height / 2);
      c.globalAlpha = 1;
    }

    // Seated characters stand on their seat's own line (seat.y) and are drawn at the seat's own size
    // (seat.scale, a touch of perspective: the sofas are farther back than the aisle); walkers use
    // baselineY and size 1. While turning toward or away from a seat both slide between the two, so
    // nobody jumps. Returns {y, s}.
    function place(e) {
      const idx = Number.isInteger(e.spot) ? e.spot : e.seat;
      const seat = idx >= 0 ? scene.seats[idx] : null;
      const seatY = seat && Number.isFinite(seat.y) ? seat.y : scene.baselineY;
      const seatS = seat && Number.isFinite(seat.scale) ? seat.scale : 1;
      if (e.state === 'ENTERING' || e.state === 'EXITING' || !seat) return { y: scene.baselineY, s: 1 };
      if (e.state === 'TURN_IN' || e.state === 'TURN_OUT') {
        const ch = chars.get(e.name), clip = ch && ch.manifest.clips[e.clip];
        const n = clip ? clip.frames.length : 1, t = n > 1 ? e.frame / (n - 1) : 1;
        const k = e.state === 'TURN_IN' ? t : 1 - t;
        return { y: scene.baselineY + (seatY - scene.baselineY) * k, s: 1 + (seatS - 1) * k };
      }
      return { y: seatY, s: seatS };
    }
    const charScale = Number.isFinite(scene.charScale) ? scene.charScale : 1;

    function atlasFrame(ch, clipId, frame) {
      const clip = ch.manifest.clips[clipId];
      if (!clip) return null;
      const idx = clip.frames[Math.min(frame, clip.frames.length - 1)];
      return { idx, f: ch.manifest.frames[idx] };
    }
    // What to draw for a frame with a face (docs/LOUNGE_SCENE_DESIGN.md 6.2): frame.v[face] names another
    // frame drawn instead. When that frame has "over": j it is a small patch (eyes, mouth) drawn on top
    // of frame j, both placed by their own anchors. Without the variant, the frame itself.
    function faceLayers(ch, af, face) {
      const frames = ch.manifest.frames;
      const vi = face && af.f.v ? af.f.v[face] : undefined;
      const vf = Number.isInteger(vi) ? frames[vi] : null;
      if (!vf) return [af];
      if (Number.isInteger(vf.over) && frames[vf.over]) return [{ idx: vf.over, f: frames[vf.over] }, { idx: vi, f: vf }];
      return [{ idx: vi, f: vf }];
    }
    const ROOM_GRADE = { base: 0.62, slope: 1.1, min: 0.72, wash: 0.14 };
    function tinted(ch, idx, f, L) {
      const key = ch.manifest.name + '|' + idx;
      let t = tintCache.get(key);
      if (!t) {
        t = make(f.w, f.h);
        const c = t.getContext('2d');
        c.drawImage(ch.atlas, f.x, f.y, f.w, f.h, 0, 0, f.w, f.h);
        const s = clamp(L.ambientStr, 0, 1);
        if (s > 0.001) {
          c.globalCompositeOperation = 'multiply';
          c.fillStyle = tintColor(L.ambient, s);
          c.fillRect(0, 0, f.w, f.h);
        }
        // room grade: a little darker in a dim room, and a touch of the room's own colour
        const dim = clamp(ROOM_GRADE.base + ROOM_GRADE.slope * room.lum, ROOM_GRADE.min, 1);
        if (dim < 0.999) {
          c.globalCompositeOperation = 'multiply';
          const v = Math.round(dim * 255).toString(16).padStart(2, '0');
          c.fillStyle = '#' + v + v + v;
          c.fillRect(0, 0, f.w, f.h);
        }
        c.globalCompositeOperation = 'source-atop';
        c.globalAlpha = ROOM_GRADE.wash;
        c.fillStyle = room.color;
        c.fillRect(0, 0, f.w, f.h);
        c.globalAlpha = 1;
        c.globalCompositeOperation = 'destination-in';
        c.drawImage(ch.atlas, f.x, f.y, f.w, f.h, 0, 0, f.w, f.h);
        tintCache.set(key, t);
      }
      return t;
    }
    function silhouette(ch, idx, f) {
      const key = ch.manifest.name + '|' + idx;
      let s = silhouettes.get(key);
      if (!s) {
        s = make(Math.max(1, Math.ceil(f.w / 2)), Math.max(1, Math.ceil(f.h / 2)));
        const c = s.getContext('2d');
        c.drawImage(ch.atlas, f.x, f.y, f.w, f.h, 0, 0, s.width, s.height);
        c.globalCompositeOperation = 'source-in';
        c.fillStyle = '#000000';
        c.fillRect(0, 0, s.width, s.height);
        silhouettes.set(key, s);
      }
      return s;
    }

    // Seated people over the sofa front (scene.seatedInFront): they rest on the cushion, so instead of a
    // floor shadow they get a short soft contact shadow on the cushion at the seat's contact point
    // (seats[].cx, cy), along the cushion's front edge (seats[].tilt), drawn after the sofa front and
    // before them.
    const seatedInFront = !!scene.seatedInFront;
    const seatOf = e => { const i = Number.isInteger(e.spot) ? e.spot : e.seat; return i >= 0 ? scene.seats[i] : null; };
    function drawSeatShadows(c, list) {
      for (const e of list) {
        const ch = chars.get(e.name), af = ch && atlasFrame(ch, e.clip, e.frame), seat = seatOf(e);
        if (!af || !seat) continue;
        const pl = place(e);
        const x = Number.isFinite(seat.cx) ? seat.cx : (e.drawX ?? e.x), y = Number.isFinite(seat.cy) ? seat.cy : pl.y - 100 * pl.s;
        const g = c.createRadialGradient(0, 0, 0, 0, 0, 1);
        g.addColorStop(0, 'rgba(0,0,0,0.32)'); g.addColorStop(1, 'rgba(0,0,0,0)');
        c.save();
        c.translate(x, y + 3);
        c.rotate((Number.isFinite(seat.tilt) ? seat.tilt : 0) * RAD);
        c.scale(95 * pl.s, 13 * pl.s);
        c.fillStyle = g;
        c.beginPath(); c.arc(0, 0, 1, 0, 6.2832); c.fill();
        c.restore();
      }
    }
    function drawShadows(c, list, L, sun, direct) {
      const sh = sunShadow(sun.rel, sun.h);
      for (const e of list) {
        if (seatedInFront && e.lane === 'seat') continue;      // up on the cushion: see drawSeatShadows
        const ch = chars.get(e.name), af = ch && atlasFrame(ch, e.clip, e.frame);
        if (!af) continue;
        const pl = place(e), f = af.f, sc = ch.manifest.scale * charScale * pl.s, fy = pl.y;
        // contact shadow
        c.save();
        c.globalAlpha = 0.30; c.fillStyle = '#000000';
        c.beginPath(); c.ellipse((e.drawX ?? e.x), fy, f.w * sc * 0.225, 9, 0, 0, 6.2832); c.fill();
        c.restore();
        const sil = silhouette(ch, af.idx, f);
        const draw = (skew, len, alpha) => {
          c.save();
          c.globalAlpha = alpha;
          c.translate((e.drawX ?? e.x), fy);
          c.transform(1, 0, skew, -len, 0, 0);
          c.drawImage(sil, -f.ax * sc, -f.ay * sc, f.w * sc, f.h * sc);
          c.restore();
        };
        if (direct > 0) draw(sh.skew, sh.len, 0.35 * direct);
        const ls = lampShadow(scene.lamps || [], L, direct, (e.drawX ?? e.x), fy);
        if (ls) draw(ls.skew, ls.len, ls.alpha);
      }
    }

    function drawChar(c, e, L) {
      const ch = chars.get(e.name), af = ch && atlasFrame(ch, e.clip, e.frame);
      if (!af) return;
      const pl = place(e), sc = ch.manifest.scale * charScale * pl.s, fy = pl.y, x = e.drawX ?? e.x;
      for (const { idx, f } of faceLayers(ch, af, e.face)) c.drawImage(tinted(ch, idx, f, L), x - f.ax * sc, fy - f.ay * sc, f.w * sc, f.h * sc);
    }

    let floorTint = null, floorTintKey = '';
    function drawFloorLight(c, L, rel, h, direct) {
      if (direct <= 0.01 || !assets.floorLight || !scene.floorLight) return;
      const key = L.sunColor;
      if (key !== floorTintKey) {
        const img = assets.floorLight;
        floorTint = make(img.width, img.height);
        const t = floorTint.getContext('2d');
        t.drawImage(img, 0, 0);
        t.globalCompositeOperation = 'multiply'; t.fillStyle = L.sunColor; t.fillRect(0, 0, img.width, img.height);
        t.globalCompositeOperation = 'destination-in'; t.drawImage(img, 0, 0);
        floorTintKey = key;
      }
      const fp = floorPatch(rel, h), a = scene.floorLight.anchor;
      c.save();
      c.globalCompositeOperation = 'soft-light';
      c.globalAlpha = 0.45 * direct;
      c.translate(a[0], a[1]);
      c.transform(1, 0, Math.tan(fp.skewDeg * RAD), fp.scaleY, 0, 0);
      c.drawImage(floorTint, -floorTint.width / 2, 0);
      c.restore();
    }

    function drawOverlay(c, list, dbg) {
      c.save();
      c.lineWidth = 2;
      if (dbg.baseline) { c.strokeStyle = '#00ffd0'; c.beginPath(); c.moveTo(0, scene.baselineY); c.lineTo(W, scene.baselineY); c.stroke(); }
      if (dbg.seats) {
        c.strokeStyle = '#ffd000'; c.fillStyle = '#ffd000'; c.font = '20px monospace';
        scene.seats.forEach(s => { const y = Number.isFinite(s.y) ? s.y : scene.baselineY; c.beginPath(); c.moveTo(s.x, y - 30); c.lineTo(s.x, y + 30); c.stroke(); c.fillText(s.id, s.x - 10, y - 40); });
      }
      for (const e of list) {
        const ch = chars.get(e.name), af = ch && atlasFrame(ch, e.clip, e.frame);
        if (!af) continue;
        const pl = place(e), f = af.f, sc = ch.manifest.scale * charScale * pl.s, fy = pl.y;
        if (dbg.feet) { c.strokeStyle = '#ff3060'; c.beginPath(); c.arc((e.drawX ?? e.x), fy, 7, 0, 6.2832); c.stroke(); }
        if (dbg.frames) { c.strokeStyle = '#60a0ff'; c.strokeRect((e.drawX ?? (e.drawX ?? e.x)) - f.ax * sc, fy - f.ay * sc, f.w * sc, f.h * sc); }
        if (dbg.labels) {
          c.fillStyle = '#ffffff'; c.strokeStyle = '#000000'; c.font = '22px monospace';
          const txt = e.name + ' ' + e.clip + ' #' + e.frame + (e.lane === 'seat' ? ' [seat]' : '');
          c.strokeText(txt, (e.drawX ?? e.x) - 90, fy - f.ay * sc - 8); c.fillText(txt, (e.drawX ?? e.x) - 90, fy - f.ay * sc - 8);
        }
      }
      c.restore();
    }

    // state: { lighting, sunAzimuth, windowFacing?, moon?: {elevation, azimuth, phase, southern}, boardRows, boardKey,
    //          chars: [{name, clip, frame, x, lane}], plane?: {u, right} | null, t: seconds, debug?: {...} }
    function draw(state) {
      if (!pw) return;
      // the weather's cloud factor (eased, so a change fades in) dims and cools the room; quantized, so a
      // fade is a few staged rebuilds rather than one per frame
      const dtw = updateWx(state.weather || CLEAR_WX, state.t, !wxSeen || !!state.still);
      wxSeen = true;
      const cq = Math.round(WX.cloud * 10) / 10;
      const L = Lighting.withWeather(state.lighting, cq);
      const lk = L.zenith + L.ambient + Math.round(L.h * 20) + '|' + Math.round(L.lamp * 50) + '|' + Math.round(L.city * 50) + '|c' + cq;
      lightKey = lk;
      // A light change redraws one layer group per frame into a spare canvas and swaps it in, so the
      // cost never lands on a single frame (a full rebuild is ~10 ms, more on a phone). A round in
      // progress finishes with the newest light before the next one starts.
      if (cacheDirty) { rebuild(L, state.boardRows); pending = []; builtKey = lk; tintCache = new Map(); }
      else {
        if (!pending.length && builtKey !== lk) { pending = ['far', 'back', 'mid', 'arms', 'front']; builtKey = lk; }
        if (pending.length) { pendingL = L; stepRebuild(); }
      }
      if (state.boardKey !== boardKey) {
        boardKey = state.boardKey;
        const rows = (state.boardRows || []).map(r => ({ ...r }));
        flip = { from: shownRows, to: rows, t0: state.t, t: state.t };
        shownRows = rows;
      }
      if (flip) {
        flip.t = state.t;
        if (flipDone(flip, state.t)) { flip = null; paintBoard(shownRows); }
        else paintBoard(flapRows(flip, state.t));
      }

      const rel = sunRelative(state.sunAzimuth, scene.windowFacing);
      const sun = { rel, h: L.h, disc: discPosition(scene, rel, L.h) };
      let moon = null;
      if (state.moon) {
        const mrel = sunRelative(state.moon.azimuth, scene.windowFacing);
        const mp = discPosition(scene, mrel, state.moon.elevation);
        moon = { x: mp.x, y: mp.y, visible: mp.visible && state.moon.elevation > 0, h: state.moon.elevation, phase: state.moon.phase, southern: !!state.moon.southern };
      }
      const direct = directLight(rel, L.h, WX.cloud);

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, pw, ph);
      ctx.setTransform(k, 0, 0, k, 0, 0);
      drawSky(ctx, L, sun, moon, state.t);
      const blit = name => { ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(caches[name].canvas, 0, 0); ctx.restore(); };
      blit('far');
      drawWxPlates(ctx, L);
      drawBeacons(ctx, L, state.t);
      planeHaze = hazeNow();
      const flash = drawWindowLayer(ctx, L, state.t, dtw, state.plane, !!state.still) || 0;
      blit('back');
      { const bb = boardBounds(); ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.drawImage(caches.board.canvas, bb.x, bb.y, bb.w, bb.h, bb.x, bb.y, bb.w, bb.h); ctx.restore(); }
      drawFloorLight(ctx, L, rel, L.h, direct);
      const list = state.chars || [];
      drawShadows(ctx, list, L, sun, direct);
      const byX = (a, b) => a.x - b.x;
      // seated people: farther seats first (the seat's contact line, then x), so a nearer one overlaps
      const depth = e => { const s = seatOf(e); return s ? (Number.isFinite(s.cy) ? s.cy : s.y) : 0; };
      const seated = list.filter(e => e.lane === 'seat').sort((a, b) => depth(a) - depth(b) || a.x - b.x);
      if (seatedInFront) {          // on the cushion, legs over the sofa front; sofa arms over them; the aisle in front
        blit('mid');
        drawSeatShadows(ctx, seated);
        for (const e of seated) drawChar(ctx, e, L);
        blit('arms');
      } else {
        for (const e of seated) drawChar(ctx, e, L);
        blit('mid');
      }
      for (const e of list.filter(e => e.lane !== 'seat').sort(byX)) drawChar(ctx, e, L);
      blit('front');
      if (flash > 0.05) {                       // lightning lights the room a touch, too
        ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'lighter';
        ctx.fillStyle = 'rgba(120,140,190,' + (flash * 0.07).toFixed(3) + ')'; ctx.fillRect(0, 0, pw, ph); ctx.restore();
      }
      if (state.debug) drawOverlay(ctx, list, state.debug);
    }

    function dispose() { caches.far = caches.back = caches.mid = caches.arms = caches.front = caches.board = null; tintCache.clear(); silhouettes.clear(); }
    return { resize, draw, dispose, get size() { return { w: pw, h: ph }; } };
  }

  function hexAlpha(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + clamp(a, 0, 1).toFixed(3) + ')';
  }

  return { createRenderer, blendVariants, sunRelative, directLight, discPosition, sunShadow, floorPatch, nearestLamp,
    lampShadow, moonShadowOffset, tintColor, wrap180, windSlant, RAIN_AMT, SNOW_AMT, RAIN_PLATE, laneScale, laneRun, planePose, planeEase };
});
