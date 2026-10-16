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
  const directLight = (rel, h) => clamp(Math.cos(rel * RAD), 0, 1) * Lighting.smoothstep(0, 6, h);
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
      const scale = Math.min(dpr || 1, 1.5);
      const w = Math.max(1, Math.round(cssWidth * scale)), h = Math.max(1, Math.round(w * H / W));
      if (w === pw && h === ph) return false;
      pw = w; ph = h; k = w / W; boardBox = null;
      canvas.width = w; canvas.height = h;
      scratch = make(w, h);
      for (const g of ['far', 'back', 'mid', 'front', 'board']) ensureCache(g);
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

    // Aircraft taxiing past the window now and then. Deterministic in scene time, so a reload shows
    // the same plane at the same moment.
    const planeTint = new Map();
    let hazeColor = '#808080';
    // Average colour of the apron behind the plane in the current window view; the plane is graded
    // toward it so a crisp white sprite sits inside the softer painting.
    function sampleHaze() {
      const p = scene.planes;
      if (!p || !caches.far) return hazeColor;
      try {
        const x = Math.round(Math.max(scene.window.x, p.from) * k), y = Math.round((p.y - p.height) * k);
        const w = Math.round(Math.min(scene.window.w, 500) * k), h = Math.round(p.height * k);
        const d = caches.far.ctx.getImageData(x, y, Math.max(1, w), Math.max(1, h)).data;
        let r = 0, g = 0, b = 0, n = 0;
        for (let i = 0; i < d.length; i += 16) { if (d[i + 3] > 200) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; } }
        if (!n) return hazeColor;
        const hx = v => Math.round(v / n).toString(16).padStart(2, '0');
        return '#' + hx(r) + hx(g) + hx(b);
      } catch (e) { return hazeColor; }
    }
    // Average colour and brightness of the room where people walk (sofas and floor). Characters are
    // graded toward it so a bright, clean sprite sits inside the painted light instead of on top of it.
    let room = { color: '#808080', lum: 0.5 };
    function sampleRoom() {
      try {
        const y0 = Math.round(ph * 0.6), h = Math.max(1, Math.round(ph * 0.35));
        const d = caches.back.ctx.getImageData(0, y0, pw, h).data;
        let r = 0, g = 0, b = 0, n = 0;
        for (let i = 0; i < d.length; i += 64) { if (d[i + 3] > 200) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; } }
        if (!n) return room;
        r /= n; g /= n; b /= n;
        const hx = v => Math.round(v).toString(16).padStart(2, '0');
        return { color: '#' + hx(r) + hx(g) + hx(b), lum: (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 };
      } catch (e) { return room; }
    }
    function planeState(t) {
      const p = scene.planes;
      if (!p || !assets.planes) return null;
      const k = Math.floor(t / p.period), phase = t - k * p.period;
      if (phase > p.duration) return null;
      const u = phase / p.duration, ease = u * u * (3 - 2 * u) * 0.3 + u * 0.7;
      const right = k % 2 === 0;
      const x = right ? p.from + (p.to - p.from) * ease : p.to - (p.to - p.from) * ease;
      return { x, img: right ? assets.planes.right : assets.planes.left };
    }
    function drawPlane(c, L, t) {
      const st = planeState(t);
      if (!st) return;
      const img = st.img, p = scene.planes;
      const key = (img === assets.planes.right ? 'r' : 'l') + L.ambient + Math.round(L.ambientStr * 50) + hazeColor;
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
        g.globalAlpha = Number.isFinite(p.haze) ? p.haze : 0.3;
        g.fillStyle = hazeColor; g.fillRect(0, 0, img.width, img.height);
        g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
        const soft = make(Math.max(1, Math.round(img.width * 0.55)), Math.max(1, Math.round(img.height * 0.55)));
        soft.getContext('2d').drawImage(tinted, 0, 0, soft.width, soft.height);
        tinted = soft;
        if (planeTint.size > 8) planeTint.clear();
        planeTint.set(key, tinted);
      }
      const h = p.height, w = h * img.width / img.height;
      c.drawImage(tinted, st.x - w / 2, p.y - h, w, h);
    }

    function rebuild(L, rows) {
      for (const g of ['far', 'back', 'mid', 'front']) {
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
      if (sun.disc.visible) {
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

    // Seated characters stand on their seat's own line (seat.y); walkers use baselineY. While turning
    // toward or away from a seat the line slides between the two so nobody jumps.
    function footY(e) {
      const idx = Number.isInteger(e.spot) ? e.spot : e.seat;
      const seat = idx >= 0 ? scene.seats[idx] : null;
      const seatY = seat && Number.isFinite(seat.y) ? seat.y : scene.baselineY;
      if (e.state === 'ENTERING' || e.state === 'EXITING' || !seat) return scene.baselineY;
      if (e.state === 'TURN_IN' || e.state === 'TURN_OUT') {
        const ch = chars.get(e.name), clip = ch && ch.manifest.clips[e.clip];
        const n = clip ? clip.frames.length : 1, t = n > 1 ? e.frame / (n - 1) : 1;
        const k = e.state === 'TURN_IN' ? t : 1 - t;
        return scene.baselineY + (seatY - scene.baselineY) * k;
      }
      return seatY;
    }
    const charScale = Number.isFinite(scene.charScale) ? scene.charScale : 1;

    function atlasFrame(ch, clipId, frame) {
      const clip = ch.manifest.clips[clipId];
      if (!clip) return null;
      const idx = clip.frames[Math.min(frame, clip.frames.length - 1)];
      return { idx, f: ch.manifest.frames[idx] };
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

    function drawShadows(c, list, L, sun, direct) {
      const sh = sunShadow(sun.rel, sun.h);
      for (const e of list) {
        const ch = chars.get(e.name), af = ch && atlasFrame(ch, e.clip, e.frame);
        if (!af) continue;
        const f = af.f, sc = ch.manifest.scale * charScale, fy = footY(e);
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
      const f = af.f, sc = ch.manifest.scale * charScale, fy = footY(e);
      c.drawImage(tinted(ch, af.idx, f, L), (e.drawX ?? (e.drawX ?? e.x)) - f.ax * sc, fy - f.ay * sc, f.w * sc, f.h * sc);
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
        const f = af.f, sc = ch.manifest.scale * charScale, fy = footY(e);
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
    //          chars: [{name, clip, frame, x, lane}], t: seconds, debug?: {...} }
    function draw(state) {
      if (!pw) return;
      const L = state.lighting;
      const lk = L.zenith + L.ambient + Math.round(L.h * 20) + '|' + Math.round(L.lamp * 50) + '|' + Math.round(L.city * 50);
      if (lk !== lightKey) { lightKey = lk; cacheDirty = true; tintCache = new Map(); }
      if (cacheDirty) rebuild(L, state.boardRows);
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
      const direct = directLight(rel, L.h);

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, pw, ph);
      ctx.setTransform(k, 0, 0, k, 0, 0);
      drawSky(ctx, L, sun, moon, state.t);
      const blit = name => { ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(caches[name].canvas, 0, 0); ctx.restore(); };
      blit('far');
      drawPlane(ctx, L, state.t);
      blit('back');
      { const bb = boardBounds(); ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.drawImage(caches.board.canvas, bb.x, bb.y, bb.w, bb.h, bb.x, bb.y, bb.w, bb.h); ctx.restore(); }
      drawFloorLight(ctx, L, rel, L.h, direct);
      const list = state.chars || [];
      drawShadows(ctx, list, L, sun, direct);
      const byX = (a, b) => a.x - b.x;
      for (const e of list.filter(e => e.lane === 'seat').sort(byX)) drawChar(ctx, e, L);
      blit('mid');
      for (const e of list.filter(e => e.lane !== 'seat').sort(byX)) drawChar(ctx, e, L);
      blit('front');
      if (state.debug) drawOverlay(ctx, list, state.debug);
    }

    function dispose() { caches.far = caches.back = caches.mid = caches.front = caches.board = null; tintCache.clear(); silhouettes.clear(); }
    return { resize, draw, dispose, get size() { return { w: pw, h: ph }; } };
  }

  function hexAlpha(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + clamp(a, 0, 1).toFixed(3) + ')';
  }

  return { createRenderer, blendVariants, sunRelative, directLight, discPosition, sunShadow, floorPatch, nearestLamp,
    lampShadow, moonShadowOffset, tintColor, wrap180 };
});
