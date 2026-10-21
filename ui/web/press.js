// 터치하면 버튼이 눌린 게 보이게 한다. 손가락이 닿는 순간 .pressed 를 붙이고,
// 짧게 톡 쳐도 최소 120ms 는 눌린 모습이 남게 뗄 때 늦춰서 뺀다.
// 손가락이 움직이면(스크롤) 바로 뺀다. 게임 화면과 로비가 같이 쓴다.
(function () {
  const SEL = 'button:not([disabled]), .card, [data-press]';
  const MIN_MS = 120, MOVE_PX = 10;
  let cur = null, t0 = 0, x0 = 0, y0 = 0;
  function release(now) {
    if (!cur) return;
    const el = cur; cur = null;
    const wait = now ? 0 : Math.max(0, MIN_MS - (performance.now() - t0));
    setTimeout(() => el.classList.remove('pressed'), wait);
  }
  document.addEventListener('pointerdown', e => {
    if (e.button > 0) return;
    const el = e.target.closest && e.target.closest(SEL);
    if (!el) return;
    release(true);
    cur = el; t0 = performance.now(); x0 = e.clientX; y0 = e.clientY;
    el.classList.add('pressed');
    // 살짝 진동: 앱(T2App.tap → 안드로이드 키보드 터치 피드백)이 있으면 그것을, 없으면 무시.
    // 버튼에만 준다(카드·칩 같은 곳은 진동 없음).
    if (el.tagName === 'BUTTON') {
      try { if (window.T2App && window.T2App.tap) window.T2App.tap(); } catch (err) {}
    }
  }, { passive: true, capture: true });
  document.addEventListener('pointermove', e => {
    if (cur && Math.hypot(e.clientX - x0, e.clientY - y0) > MOVE_PX) release(true);
  }, { passive: true, capture: true });
  document.addEventListener('pointerup', () => release(false), { passive: true, capture: true });
  document.addEventListener('pointercancel', () => release(true), { passive: true, capture: true });
  // 길게 누를 때 뜨는 메뉴(복사·이미지 저장 등)를 막는다. 입력칸은 그대로 둔다.
  document.addEventListener('contextmenu', e => {
    if (!(e.target.closest && e.target.closest('input, textarea, [contenteditable]'))) e.preventDefault();
  }, { capture: true });
  document.addEventListener('selectstart', e => {
    if (!(e.target.closest && e.target.closest('input, textarea, [contenteditable]'))) e.preventDefault();
  }, { capture: true });
  window.addEventListener('scroll', () => release(true), { passive: true, capture: true });
})();
