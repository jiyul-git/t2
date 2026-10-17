/* Debug panel for the lounge scene (docs/LOUNGE_SCENE_DESIGN.md 10). Loaded only when the page is
   opened with ?lounge_debug=1 or localStorage.t2_lounge_debug = '1'. Nothing here is saved. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.T2LoungeDebug = api;
})(typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  const PLACES = [['서울', 37.5665, 126.978], ['레이캬비크', 64.15, -21.94], ['시드니', -33.87, 151.21]];
  const ACTIVITIES = [['idle', '가만히'], ['phone', '폰'], ['call', '전화'], ['eat', '식사'], ['sunglasses', '선글라스'],
    ['fix_clothes', '옷매무새'], ['doze', '졸기'], ['chat', '대화']];
  const OVERLAYS = [['seats', '좌석'], ['baseline', '기준선'], ['feet', '발 기준점'], ['frames', '프레임 경계'], ['labels', '클립·프레임']];
  const pad2 = n => String(n).padStart(2, '0');

  const CSS = '.lounge-debug{margin:6px 0 10px;border:1px solid #cdaa69;border-radius:12px;background:#0d242a;color:#e8f0ec;font-size:12px}'
    + '.lounge-debug summary{padding:9px 12px;font-weight:800;color:#ffe0a1;cursor:pointer}'
    + '.lounge-debug .body{padding:2px 12px 12px;display:grid;gap:10px}'
    + '.lounge-debug fieldset{border:1px solid #31534b;border-radius:9px;margin:0;padding:8px 10px}'
    + '.lounge-debug legend{padding:0 6px;color:#c5d6d0;font-size:11px}'
    + '.lounge-debug .row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:3px 0}'
    + '.lounge-debug button,.lounge-debug select,.lounge-debug input{font:inherit;color:#fff3d8;background:#173b36;border:1px solid #4f7a6f;border-radius:7px;padding:5px 8px;min-height:30px}'
    + '.lounge-debug button.on{background:#7a5a1a;border-color:#ffd27a}'
    + '.lounge-debug input[type=range]{width:100%;padding:0}.lounge-debug input[type=number]{width:96px}'
    + '.lounge-debug output,.lounge-debug pre{font-family:ui-monospace,monospace;font-size:11px;white-space:pre-wrap;margin:0}';

  function el(doc, tag, props, children) {
    const e = doc.createElement(tag);
    Object.assign(e, props || {});
    for (const c of children || []) e.appendChild(typeof c === 'string' ? doc.createTextNode(c) : c);
    return e;
  }

  function attach(h, doc) {
    doc = doc || root.document;
    const scene = doc.getElementById('lounge');
    if (!scene || doc.getElementById('loungeDebug')) return null;
    h.debug.enabled = true;
    const style = el(doc, 'style', { textContent: CSS });
    const panel = el(doc, 'details', { id: 'loungeDebug', className: 'lounge-debug', open: true });
    panel.appendChild(el(doc, 'summary', { textContent: '라운지 디버그' }));
    const body = el(doc, 'div', { className: 'body' });
    panel.appendChild(body);
    const group = (title, ...rows) => { const f = el(doc, 'fieldset'); f.appendChild(el(doc, 'legend', { textContent: title })); rows.forEach(r => f.appendChild(r)); body.appendChild(f); return f; };
    const row = (...kids) => el(doc, 'div', { className: 'row' }, kids);
    const btn = (text, fn) => el(doc, 'button', { type: 'button', textContent: text, onclick: fn });

    // time
    const date = el(doc, 'input', { type: 'date' });
    const slider = el(doc, 'input', { type: 'range', min: 0, max: 1439, step: 1, value: 720 });
    const clockOut = el(doc, 'output', { textContent: '--:--' });
    let dragging = false;
    const apply = () => {
      const [y, m, d] = (date.value || '').split('-').map(Number);
      if (!y) return;
      const mins = Number(slider.value);
      h.setClock(new Date(y, m - 1, d, Math.floor(mins / 60), mins % 60).getTime());
    };
    date.onchange = apply;
    slider.oninput = () => { dragging = true; clockOut.textContent = pad2(Math.floor(slider.value / 60)) + ':' + pad2(slider.value % 60); apply(); };
    slider.onchange = () => { dragging = false; };
    const scales = [1, 60, 600].map(n => { const b = btn(n + '×', () => { h.setScale(n); scales.forEach(x => x.classList.toggle('on', x === b)); }); if (n === 1) b.className = 'on'; return b; });
    group('시간 (이 기기의 현지 시각)', row(date, clockOut, btn('현재 시각', () => { h.reset(); scales.forEach((x, i) => x.classList.toggle('on', i === 0)); })), slider, row(...scales));

    // place
    const lat = el(doc, 'input', { type: 'number', step: 'any', placeholder: '위도', min: -90, max: 90 });
    const lon = el(doc, 'input', { type: 'number', step: 'any', placeholder: '경도', min: -180, max: 180 });
    const placeOut = el(doc, 'output');
    group('위치', row(...PLACES.map(p => btn(p[0], () => h.setPlace(p[1], p[2]))), btn('기기 위치로', () => h.setPlace(null))),
      row(lat, lon, btn('적용', () => { const a = parseFloat(lat.value), b = parseFloat(lon.value); if (Number.isFinite(a) && Number.isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180) h.setPlace(a, b); })), placeOut);

    // seed
    const seed = el(doc, 'input', { type: 'number', value: 1, step: 1 });
    group('난수 시드', row(seed, btn('다시 시작', () => h.reseed(Number(seed.value) || 0))));

    // overlays
    group('겹쳐 보기', row(...OVERLAYS.map(([k, label]) => { const b = btn(label, () => { h.debug.overlay[k] = !h.debug.overlay[k]; b.classList.toggle('on', !!h.debug.overlay[k]); h.redraw(); }); return b; })));

    // forced activities
    const forceRows = h.characters().map(name => {
      const sel = el(doc, 'select', {}, ACTIVITIES.map(([v, t]) => el(doc, 'option', { value: v, textContent: t })));
      const msg = el(doc, 'output');
      return row(el(doc, 'span', { textContent: name, style: 'min-width:62px' }), sel, btn('실행', () => { msg.textContent = h.force(name, sel.value) ? '다음 차례에 실행' : '지금은 할 수 없음'; }), msg);
    });
    group('활동 강제', ...forceRows);

    // readout
    const info = el(doc, 'pre');
    group('현재 값', info);
    const fmtDate = ms => { const d = new Date(ms); return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); };
    let last = 0;
    h.debug.onInfo = i => {
      const now = Date.now();
      if (now - last < 250 || !i.sun) return;
      last = now;
      const d = new Date(i.ms);
      if (!dragging) {
        clockOut.textContent = pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
        slider.value = d.getHours() * 60 + d.getMinutes();
        if (doc.activeElement !== date) date.value = fmtDate(i.ms);
      }
      placeOut.textContent = '(' + i.place.lat.toFixed(2) + ', ' + i.place.lon.toFixed(2) + ') 출처: ' + i.place.source;
      info.textContent = '태양 고도 ' + i.sun.elevation.toFixed(1) + '°  방위 ' + i.sun.azimuth.toFixed(0) + '°\n직사광 ' + i.direct.toFixed(2)
        + '  램프 ' + i.light.lamp.toFixed(2) + '  도시불빛 ' + i.light.city.toFixed(2) + '  별 ' + i.light.stars.toFixed(2)
        + '\n지금 화면 속 인원 ' + i.people + '명  프레임 비용 평균 ' + h.stats().avg.toFixed(2) + 'ms';
    };

    scene.parentNode.insertBefore(style, scene.nextSibling);
    scene.parentNode.insertBefore(panel, style.nextSibling);
    return panel;
  }

  return { attach, PLACES, ACTIVITIES, OVERLAYS };
});
