/* Lounge scene entry point (docs/LOUNGE_SCENE_DESIGN.md 4). Wires location, sun, lighting,
   departure board, behaviour and renderer to the lobby page and keeps the animation loop polite
   (24 fps cap, stops when hidden or off screen, warm start after a long pause). */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2Lounge = api;
})(typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  const dep = (name, file) => root[name] || (typeof require === 'function' ? require(file) : null);
  const Sun = dep('T2LoungeSun', './sun.js');
  const Locate = dep('T2LoungeLocation', './location.js');
  const Light = dep('T2LoungeLighting', './lighting.js');
  const Board = dep('T2LoungeBoard', './board.js');
  const Behavior = dep('T2LoungeBehavior', './behavior.js');
  const Assets = dep('T2LoungeAssets', './assets.js');
  const Renderer = dep('T2LoungeRenderer', './renderer.js');

  const FRAME_MS = 1000 / 60;
  const LIGHT_EVERY_MS = 15000;
  const BOARD_EVERY_MS = 60000;
  const WARM_AFTER_MS = 60000;
  const DEBUG_FLAG_KEY = 't2_lounge_debug';

  // Sun, moon and lighting for a moment and a place. Pure; used by the loop and by tests.
  function computeSky(ms, loc) {
    const date = new Date(ms);
    const sun = Sun.sunPosition(date, loc.lat, loc.lon);
    const moonPos = Sun.moonPosition(date, loc.lat, loc.lon);
    return {
      sun,
      light: Light.lighting(sun.elevation),
      moon: { elevation: moonPos.elevation, azimuth: moonPos.azimuth, phase: Sun.moonPhase(ms), southern: loc.lat < 0 },
    };
  }

  function debugWanted(win) {
    try {
      if (/(^|[?&])lounge_debug=1(&|$)/.test(win.location.search)) return true;
      return win.localStorage.getItem(DEBUG_FLAG_KEY) === '1';
    } catch (e) { return false; }
  }

  function createLounge(env) {
    const win = env.window, doc = env.document;
    const assetBase = env.assetBase || 'lounge/assets/';
    let section = null, canvas = null, renderer = null, director = null, assets = null, location = null;
    let seed = null, sky = null, rows = [], boardKey = '', tournaments = [], serverOffsetMs = 0;
    let running = false, visible = true, failed = false, stopped = false, reduced = false;
    let raf = 0, lastTs = 0, lastLight = -1e9, lastBoard = -1e9, pausedAt = 0, t0 = 0, simT = 0;
    let frameMs = FRAME_MS, costEma = 0;
    const costs = [];                 // recent frame costs in ms (director step + draw), for the debug panel and perf checks
    const debug = { clockMs: null, clockSetAt: 0, scale: 1, overlay: {}, enabled: false, onInfo: null };

    // the moment the scene is showing: real time, or a debug time that keeps running from where it was set
    function clockMs() {
      if (debug.clockMs === null) return Date.now();
      return debug.clockMs + (Date.now() - debug.clockSetAt) * debug.scale;
    }
    const placeNow = () => location.get();

    // The last picture of the scene is kept (small JPEG) and shown while the next visit loads, so the
    // page never flashes the old still picture before the scene appears. Older than SNAP_MAX_MS = skipped.
    const SNAP_KEY = 't2.lounge.snap', SNAP_MAX_MS = 3 * 3600e3, SNAP_W = 480;
    function paintSnapshot(storage) {
      try {
        const raw = storage && storage.getItem(SNAP_KEY);
        const fb = section && section.querySelector('.lounge-fallback');
        if (!raw || !fb) return;
        const snap = JSON.parse(raw);
        if (Date.now() - snap.ts > SNAP_MAX_MS || typeof snap.url !== 'string') return;
        fb.style.backgroundImage = 'url("' + snap.url + '")';
      } catch (e) { /* no snapshot: the plain colour shows */ }
    }
    let snapTimer = 0, lastSnapAt = 0;
    function takeSnapshot(storage) {
      if (!storage || !canvas || failed || !renderer || !director) return;
      if (Date.now() - lastSnapAt < 60000) return;
      try {
        drawNow([]);                                   // the room without anybody in it
        const w = SNAP_W, h = Math.round(w * canvas.height / canvas.width);
        const c = doc.createElement('canvas'); c.width = w; c.height = h;
        c.getContext('2d').drawImage(canvas, 0, 0, w, h);
        const url = c.toDataURL('image/jpeg', 0.6);
        drawNow(director.step(0));
        storage.setItem(SNAP_KEY, JSON.stringify({ ts: Date.now(), url }));
        lastSnapAt = Date.now();
      } catch (e) { /* storage full or canvas tainted: skip */ }
    }
    function scheduleSnapshot(storage) {
      snapTimer = win.setTimeout(() => takeSnapshot(storage), 2500);
      doc.addEventListener('visibilitychange', () => { if (doc.hidden) takeSnapshot(storage); });
      win.addEventListener('pagehide', () => takeSnapshot(storage));
    }

    function fail(why) {
      if (failed) return;
      failed = true;
      if (win.console) console.warn('lounge: showing the still illustration instead:', why && why.message || why);
      stopLoop();
      if (section) { section.classList.remove('lounge-ready'); section.classList.add('lounge-failed'); }
    }

    function updateLighting(force) {
      const nowTs = win.performance.now();
      if (!force && nowTs - lastLight < LIGHT_EVERY_MS && debug.clockMs === null) return;
      lastLight = nowTs;
      sky = computeSky(clockMs(), placeNow());
      const vars = Light.cssVars(sky.light.h);
      const style = doc.documentElement.style;
      for (const k in vars) style.setProperty(k, vars[k]);
      floorDue = true;
    }

    // The page below the picture starts from the colour of the picture's bottom edge, so the two
    // meet without a seam. Read once after each lighting change (cheap: one row of pixels).
    let floorDue = true, floorAt = -1e9;
    function sampleFloor() {
      const nowTs = win.performance.now();
      if (nowTs - floorAt < 2000) return;          // the debug clock relights every frame; reading pixels is not free
      floorDue = false; floorAt = nowTs;
      try {
        const ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height;
        if (!w || !h) return;
        const row = ctx.getImageData(0, h - 2, w, 1).data;
        let r = 0, g = 0, b = 0, n = 0;
        for (let i = 0; i < row.length; i += 16) { r += row[i]; g += row[i + 1]; b += row[i + 2]; n++; }
        const hx = v => Math.round(v / n).toString(16).padStart(2, '0');
        doc.documentElement.style.setProperty('--lounge-floor', '#' + hx(r) + hx(g) + hx(b));
      } catch (e) { /* tainted or unavailable canvas: the CSS fallback colour stays */ }
    }

    function updateBoard(force) {
      const nowTs = win.performance.now();
      if (!force && nowTs - lastBoard < BOARD_EVERY_MS) return;
      lastBoard = nowTs;
      const ms = clockMs();
      const serverSec = debug.clockMs === null ? (Date.now() + serverOffsetMs) / 1000 : ms / 1000;
      rows = Board.boardRows(tournaments, serverSec, ms, assets && (assets.scene.board.textRows || assets.scene.board.rows));
      boardKey = rows.map(r => [r.flight, r.dest, r.time, r.status, r.mine].join('|')).join(';');
    }

    function newDirector() {
      const s = seed === null ? Date.now() : seed;
      director = Behavior.createDirector({
        seed: s, scene: assets.scene, characters: assets.chars.map(c => c.manifest),
        clock: clockMs, solar: () => (sky ? sky.sun : { elevation: 0 }),
      });
    }

    function drawNow(chars) {
      renderer.draw({
        lighting: sky.light, sunAzimuth: sky.sun.azimuth, moon: sky.moon, boardRows: rows, boardKey,
        chars, plane: director && !reduced ? director.plane() : null, t: simT, debug: debug.enabled ? debug.overlay : null,
      });
      if (floorDue) sampleFloor();
    }

    function frame(ts) {
      raf = win.requestAnimationFrame(frame);
      if (ts - lastTs < frameMs - 2) return;    // rAF jitters around the display rate
      const dt = lastTs ? Math.min(ts - lastTs, 250) : frameMs;
      lastTs = ts;
      try {
        updateLighting(false); updateBoard(false);
        simT += dt / 1000;
        const t0f = win.performance.now();
        drawNow(director.step(dt * debug.scale));
        const cost = win.performance.now() - t0f;
        costs.push(cost);
        // a phone that cannot keep up drops to 30 fps rather than stuttering, and comes back when it can
        costEma = costEma * 0.97 + cost * 0.03;
        if (frameMs < 20 && costEma > 9) frameMs = 1000 / 30;
        else if (frameMs > 20 && costEma < 4) frameMs = FRAME_MS;
        if (costs.length > 480) costs.shift();
        if (debug.onInfo) debug.onInfo(info());
      } catch (e) { fail(e); }
    }

    function startLoop() {
      if (running || failed || stopped || reduced || !renderer) return;
      if (pausedAt && win.performance.now() - pausedAt > WARM_AFTER_MS) { try { director.warmStart(); } catch (e) { fail(e); return; } }
      pausedAt = 0; running = true; lastTs = 0;
      raf = win.requestAnimationFrame(frame);
    }
    function stopLoop() {
      if (!running) return;
      running = false;
      win.cancelAnimationFrame(raf);
      pausedAt = win.performance.now();
    }
    const sync = () => { if (visible && !doc.hidden && !stopped) startLoop(); else stopLoop(); };

    // Reduced motion: two people sitting still, lighting refreshed once a minute.
    function startStatic() {
      const seats = assets.scene.seats;
      // up to two people, each on a seat whose facing it has, never two seats that block each other
      const taken = [], picks = [];
      for (const c of assets.chars.filter(c => Behavior.canSit(c.manifest))) {
        const fs = Behavior.sitFacings(c.manifest);
        const seat = seats.findIndex((s, i) => !taken.includes(i) && fs.includes(s.facing || 'f') &&
          !taken.some(j => (s.blocks || []).includes(seats[j].id) || (seats[j].blocks || []).includes(s.id)));
        if (seat < 0 || picks.length >= 2) continue;
        taken.push(seat);
        picks.push({ name: c.manifest.name, clip: Behavior.clipAt('sit_idle', seats[seat].facing), frame: 0, x: seats[seat].x, lane: 'seat', state: 'SEATED', seat, spot: seat, face: '' });
      }
      const redraw = () => {
        if (failed || stopped) return;
        try { updateLighting(true); updateBoard(true); drawNow(picks); } catch (e) { fail(e); return; }
        win.setTimeout(redraw, 60000);
      };
      redraw();
    }

    function resize() {
      if (!renderer || !section) return;
      const w = section.clientWidth;
      if (w > 0 && renderer.resize(w, win.devicePixelRatio || 1) && !running && sky && !failed) {
        try { drawNow(reduced ? [] : director.step(0)); } catch (e) { fail(e); }
      }
    }

    function info() {
      return {
        ms: clockMs(), place: placeNow(), sun: sky && sky.sun, light: sky && sky.light,
        direct: sky ? Renderer.directLight(Renderer.sunRelative(sky.sun.azimuth, assets.scene.windowFacing), sky.light.h) : 0,
        people: director ? director.step(0).length : 0,
      };
    }

    async function mount(sectionEl) {
      section = sectionEl;
      canvas = section.querySelector('.lounge-canvas');
      try {
        if (!canvas || !canvas.getContext || !canvas.getContext('2d')) throw new Error('canvas 2d unavailable');
        reduced = !!(win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches);
        let storage = null;
        try { storage = win.localStorage; } catch (e) { storage = null; }
        paintSnapshot(storage);
        location = Locate.createLocation({ navigator: win.navigator, storage, now: Date.now, intl: win.Intl, isSecureContext: win.isSecureContext });
        location.init();
        assets = await Assets.loadAssets(assetBase, Assets.browserIO(), Behavior.isActive);
        if (!assets.chars.length) throw new Error('no usable characters');
        renderer = Renderer.createRenderer({ canvas, assets });
        updateLighting(true); updateBoard(true);
        newDirector();
        renderer.resize(section.clientWidth || 360, win.devicePixelRatio || 1);
        section.classList.add('lounge-ready');
        scheduleSnapshot(storage);
        if (reduced) startStatic();
        else {
          drawNow(director.step(0));
          if (win.IntersectionObserver) {
            new win.IntersectionObserver(es => { visible = es[es.length - 1].isIntersecting; sync(); }).observe(section);
          }
          doc.addEventListener('visibilitychange', sync);
          win.addEventListener('pagehide', () => { stopped = true; stopLoop(); });
          win.addEventListener('pageshow', () => { stopped = false; sync(); });
          sync();
        }
        if (win.ResizeObserver) new win.ResizeObserver(resize).observe(section); else win.addEventListener('resize', resize);
        location.refreshIfStale().then(changed => { if (changed) updateLighting(true); }).then(askForLocation);
        if (debugWanted(win)) loadDebug();
      } catch (e) { fail(e); }
    }

    // Ask the browser for the real position once per visit; the browser shows its own permission prompt.
    // Without permission (or on a plain-http address) the time zone is used, so the scene never waits on it.
    function askForLocation() {
      location.canAsk().then(yes => (yes ? location.request() : null)).then(r => { if (r && r.ok) updateLighting(true); });
    }

    function loadDebug() {
      const s = doc.createElement('script');
      s.src = 'lounge/debug.js?v=2';
      s.onload = () => { if (root.T2LoungeDebug) root.T2LoungeDebug.attach(api.debugHandle()); };
      doc.head.appendChild(s);
    }

    const api = {
      mount,
      setTournaments(list, serverNowSec) {
        tournaments = Array.isArray(list) ? list : [];
        if (Number.isFinite(serverNowSec)) serverOffsetMs = serverNowSec * 1000 - Date.now();
        if (renderer && !failed) { try { updateBoard(true); } catch (e) { fail(e); } }
      },
      requestLocation() { return location ? location.request().then(r => { if (r.ok) updateLighting(true); return r; }) : Promise.resolve({ ok: false, reason: 'not mounted' }); },
      debugHandle() {
        return {
          debug, info, location: () => location, scene: () => assets.scene, characters: () => assets.chars.map(c => c.manifest.name),
          setClock(ms) { debug.clockMs = ms; debug.clockSetAt = Date.now(); updateLighting(true); updateBoard(true); },
          setSceneTime(sec) { simT = sec; },
          setScale(n) { debug.clockMs = clockMs(); debug.clockSetAt = Date.now(); debug.scale = n; },
          force(name, kind) { return director ? director.force(name, kind) : false; },
          // 'pass' | 'arrive' | 'leave' for a character, as the next event (behavior.js request)
          request(name, kind, seat) { return director ? director.request(name, kind, seat) : false; },
          mover() { return director ? director.mover() : null; },
          setFace(name, face) { return director && director.setFace ? director.setFace(name, face) : false; },
          reset() { debug.clockMs = null; debug.scale = 1; updateLighting(true); updateBoard(true); },
          setPlace(lat, lon) { location.setDebug(lat, lon); updateLighting(true); },
          reseed(s) { seed = s; newDirector(); },
          redraw() { if (renderer && sky) drawNow(director.step(0)); },
          stats() {
            const a = costs.slice().sort((x, y) => x - y);
            return { n: a.length, avg: a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0, p95: a.length ? a[Math.floor(a.length * 0.95)] : 0 };
          },
        };
      },
    };
    return api;
  }

  const api = { createLounge, computeSky, FRAME_MS };
  if (typeof window !== 'undefined' && root === window) {
    const lounge = createLounge({ window, document });
    api.mount = lounge.mount; api.setTournaments = lounge.setTournaments;
    api.requestLocation = lounge.requestLocation; api.debugHandle = lounge.debugHandle;
    const boot = () => { const el = document.getElementById('lounge'); if (el) lounge.mount(el); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
  }
  return api;
});
