/* Presentation only: stable portraits and bounded gaze, independent of game RNG. */
(function (root) {
  'use strict';
  // Static portraits; eye centers use each extracted image's local pixels.
  const portraits = [
    {size:[433,410], eyes:[[142,246],[284,246]]},
    {size:[395,367], eyes:[[108,201],[246,200]]},
    {size:[375,408], eyes:[[106,243],[244,242]]},
    {size:[405,345], eyes:[[123,164],[281,163]]},
    {size:[365,394], eyes:[[108,227],[255,226]]},
    {size:[341,399], eyes:[[100,237],[240,237]]},
    {size:[398,367], eyes:[[111,172],[286,171]]},
    {size:[406,382], eyes:[[126,212],[280,212]]},
    {size:[385,329], eyes:[[110,141],[281,141]]}
  ];
  function portraitIndex(pid) {
    const n = Number(pid);
    return Number.isFinite(n) ? ((Math.trunc(n) % portraits.length) + portraits.length) % portraits.length : 0;
  }
  function gazeOffset(dx, dy, radius) {
    if (![dx, dy, radius].every(Number.isFinite) || radius <= 0) return {x:0, y:0};
    const distance = Math.hypot(dx, dy);
    const scale = distance ? Math.min(1, distance / 120) * radius / distance : 0;
    return {x: dx * scale, y: dy * scale};
  }
  // Keep continuing players' portraits and assign newcomers an unused portrait.
  // Hero participates in the same pool; missing pid falls back to the seat.
  function createTableAllocator() {
    let previous = new Map();
    const key = s => s.hero ? 'hero' : s.pid != null ? 'pid:'+s.pid : 'seat:'+s.seat;
    return function tablePortraits(seats) {
      const roster = [...seats].sort((a,b) => Number(b.hero)-Number(a.hero) || a.seat-b.seat);
      const next = new Map(), used = new Set(), result = new Map();
      for (const s of roster) {
        const id = previous.get(key(s));
        if (id !== undefined && !used.has(id)) {
          next.set(key(s), id); used.add(id); result.set(s.seat, id);
        }
      }
      for (const s of roster) {
        if (result.has(s.seat)) continue;
        let id = portraitIndex(s.pid);
        for (let count=0; count<portraits.length && used.has(id); count++) id=(id+1)%portraits.length;
        next.set(key(s), id); used.add(id); result.set(s.seat, id);
      }
      previous = next;
      return result;
    };
  }
  const tablePortraits = createTableAllocator();
  function avatarHTML(pid) {
    const index = portraitIndex(pid), p = portraits[index];
    const [w,h] = p.size;
    const eyes = p.eyes.map(([ex,ey]) =>
      '<i class="portrait-pupil" style="left:'+(ex/w*100)+'%;top:'+(ey/h*100)+'%;width:'+(28/w*100)+'%;height:'+(32/h*100)+'%"></i>'
    ).join('');
    return '<span class="portrait" data-portrait="'+index+'" aria-hidden="true" style="aspect-ratio:'+w+'/'+h+'">'+
      '<img draggable="false" alt="" src="assets/portraits/'+String(index+1).padStart(2,'0')+'.png" style="width:100%;left:0;top:0">'+eyes+'</span>';
  }
  function updateGaze() {
    const felt = document.getElementById('felt');
    if (!felt) return;
    const table = felt.getBoundingClientRect();
    if (!table.width || !table.height) return;
    const cx = table.left + table.width / 2, cy = table.top + table.height / 2;
    document.querySelectorAll('.portrait').forEach(el => {
      const r = el.getBoundingClientRect();
      const p = gazeOffset(cx-(r.left+r.width/2), cy-(r.top+r.height/2), r.width*.029);
      el.style.setProperty('--gaze-x', p.x.toFixed(3)+'px');
      el.style.setProperty('--gaze-y', p.y.toFixed(3)+'px');
    });
  }
  let queued = false;
  function scheduleGaze() {
    if (queued || typeof document === 'undefined') return;
    queued = true;
    requestAnimationFrame(() => { queued = false; updateGaze(); });
  }
  const api = {avatarHTML, portraitIndex, gazeOffset, scheduleGaze, tablePortraits, createTableAllocator};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.PokerVisuals = api;
  if (typeof document !== 'undefined') {
    const start = () => {
      const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(scheduleGaze);
      ['tablewrap','hero'].forEach(id => { const el = document.getElementById(id); if (el && observer) observer.observe(el); });
      window.addEventListener('resize', scheduleGaze);
      scheduleGaze();
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
    else start();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
