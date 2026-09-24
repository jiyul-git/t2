/* Presentation only: stable portraits and bounded gaze, independent of game RNG. */
(function (root) {
  'use strict';
  // Atlas crops and eye centers in source pixels. Eyes remain separate from the art.
  const portraits = [
    {crop:[0,0,432,440], eyes:[[151,283],[293,283]]},
    {crop:[439,0,396,440], eyes:[[557,282],[694,282]]},
    {crop:[855,0,390,440], eyes:[[976,282],[1112,282]]},
    {crop:[15,440,405,390], eyes:[[145,651],[296,651]]},
    {crop:[444,440,370,390], eyes:[[553,667],[696,667]]},
    {crop:[867,440,358,390], eyes:[[975,676],[1111,676]]},
    {crop:[15,828,405,382], eyes:[[137,1012],[305,1012]]},
    {crop:[431,828,395,382], eyes:[[550,1038],[702,1038]]},
    {crop:[855,828,382,382], eyes:[[957,1024],[1126,1024]]}
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
  function avatarHTML(pid) {
    const index = portraitIndex(pid), p = portraits[index];
    const [x,y,w,h] = p.crop;
    const eyes = p.eyes.map(([ex,ey]) =>
      '<i class="portrait-pupil" style="left:'+((ex-x)/w*100)+'%;top:'+((ey-y)/h*100)+'%;width:'+(28/w*100)+'%;height:'+(32/h*100)+'%"></i>'
    ).join('');
    return '<span class="portrait" data-portrait="'+index+'" aria-hidden="true" style="aspect-ratio:'+w+'/'+h+'">'+
      '<img draggable="false" alt="" src="assets/portraits.png" style="width:'+(1254/w*100)+'%;left:'+(-x/w*100)+'%;top:'+(-y/h*100)+'%">'+eyes+'</span>';
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
  const api = {avatarHTML, portraitIndex, gazeOffset, scheduleGaze};
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

