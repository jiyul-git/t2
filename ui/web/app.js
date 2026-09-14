'use strict';
/* t2 포커 테이블 UI.
 *
 * 원칙: **마지막 JSON 응답이 유일한 진실이다.**
 * 프론트엔드는 규칙을 다시 계산하지 않는다. 버튼 노출은 legal 만 보고 정하고,
 * 레이즈 범위는 legal.raise.min_to / max_to 를 그대로 쓴다. 최소 레이즈를
 * 여기서 다시 구현하면 엔진과 어긋나는 순간 화면과 서버가 따로 논다.
 * 상태를 추정하지 않으므로, 409 를 받으면 GET /api/state 로 다시 맞춘다.
 */

const $ = (s) => document.querySelector(s);
const SUIT = { s: '♠', h: '♥', d: '♦', c: '♣' };
const RED = { h: 1, d: 1 };
const ACT = { fold: '폴드', check: '체크', call: '콜', bet: '벳',
              raise: '레이즈', allin: '올인' };
const STREET = { preflop: '프리플랍', flop: '플랍', turn: '턴', river: '리버' };

const S = {
  last: null, view: null, token: null, busy: false,
  handNo: null, stage: null, logLen: 0, boardLen: 0,
  timers: [], busyTimer: null, toastTimer: null,
  prevBets: null,          // 직전에 그린 좌석별 이번 스트리트 투입액
  replayDone: null,        // 재생 중이면 마지막 프레임을 그리는 함수
  view0: null,             // 마지막 decision 뷰. 관전 재생의 출발점
  folding: {},             // 방금 폴드해서 카드가 사라지는 중인 좌석
  autoTimer: null,         // 결과 화면 자동 진행
  spectating: false,       // 히어로가 접어서 남은 진행을 구경하는 중인가
  dealt: null,             // 딜링 모션 중이면 카드를 받은 좌석 집합. null = 전부
  foldTimers: [],          // 폴드 모션 정리 타이머. 재생 타이머와 수명이 다르다
  heroSig: null,           // 히어로 카드가 지금 무엇을 그리고 있는지
  queuedNew: null,         // 요청 처리 중에 눌러둔 새 게임
  queuedAction: null,      // 재생 중에 눌러둔 히어로 액션
  won: false,              // 히어로가 대회를 우승했나
  entries: null,           // 총 엔트리 (우승 화면 표시용)
};

// 표시 속도. **계산과 무관하다.** 엔진과 워커에는 sleep 을 넣지 않는다 —
// 다른 테이블은 계속 최고 속도로 돈다.
//
// 주의: 핸드 '진행 중'의 텀은 다음 핸드 대기를 줄이지 못한다. 서버 워커는
// 핸드가 끝나야 시작하므로, 겹칠 수 있는 건 관전 재생과 결과 화면뿐이다.
const STEP_CHOICES = [1000, 1500, 2000, 2600];
function numPref(key, def, allowed) {
  try {
    const v = Number(localStorage.getItem(key));
    return allowed.indexOf(v) >= 0 ? v : def;
  } catch (e) { return def; }
}
const stepMs = () => numPref('t2step', 1500, STEP_CHOICES);
// 폴드는 정보가 거의 없다. 프리플랍에서 3~5명이 연달아 접는 것이 핸드당 봇 액션
// 수의 대부분이고(실측 중앙 9개 중 58%), 그걸 벳과 같은 간격으로 띄우면 연출만
// 핸드당 13.5초가 된다. 다만 1/3 은 너무 빨랐다 — 접는 것도 보여야 한다.
// 독립된 상수를 새로 두지 않고 stepMs 하나에서 파생시킨다.
const FOLD_DIV = 2;
const paceMs = (e) => (e && e.action === 'fold'
  ? Math.round(stepMs() / FOLD_DIV) : stepMs());
function setPref(key, v) { try { localStorage.setItem(key, String(v)); } catch (e) {} }

const fmt = (n) => (n === null || n === undefined || isNaN(n))
  ? '-' : Number(n).toLocaleString('en-US');

/* ---------------- 봇 메모 ----------------
 * 좌석 번호(1~8 슬롯)는 테이블 밸런싱으로 사람이 바뀌므로 쓰지 않는다.
 * 엔진의 pid 를 쓴다 — live2.build_hand 가 h.seat_pid 로 들고 있고
 * ui_view 가 좌석마다 실어 보낸다. pid 가 없는 응답이면 메모 버튼을 감춘다.
 *
 * 저장은 브라우저 localStorage 다. 서버·엔진·상태 파일에 닿지 않으므로
 * 봇 판단에 영향을 줄 수 없다. 순수한 사용자 메모다.
 */
const memoKey = (pid) => 't2memo:' + pid;
function memoGet(pid) {
  try { return localStorage.getItem(memoKey(pid)) || ''; } catch (e) { return ''; }
}
function memoSet(pid, txt) {
  try {
    if (txt) localStorage.setItem(memoKey(pid), txt);
    else localStorage.removeItem(memoKey(pid));
  } catch (e) { toast('메모를 저장하지 못했습니다'); }
}
const esc = (t) => String(t).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function openMemo(pid, label) {
  clearTimeout(S.autoTimer); S.autoTimer = null;
  showOverlay(`<h2>${esc(label)} 메모</h2>` +
    `<div class="sub">플레이어 #${esc(pid)} — 자리를 옮겨도 따라갑니다. ` +
    `이 메모는 이 브라우저에만 저장되고 봇 판단에는 쓰이지 않습니다.</div>` +
    `<textarea id="memoText" rows="7" placeholder="예: 플랍 체크레이즈 자주, 리버 오버벳은 거의 밸류"` +
    `>${esc(memoGet(pid))}</textarea>` +
    `<div class="actions"><button type="button" id="memoSave">저장</button>` +
    `<button type="button" id="memoClose">닫기</button></div>`);
  const ta = $('#memoText');
  ta.focus();
  $('#memoSave').addEventListener('click', () => {
    memoSet(pid, ta.value.trim());
    hideOverlay();
    if (S.view && S.view.type === 'decision') renderSeats(S.view);
    toast(ta.value.trim() ? '메모를 저장했습니다' : '메모를 지웠습니다', true);
  });
  $('#memoClose').addEventListener('click', hideOverlay);
}

/* ---------------- 카드 ---------------- */
function cardHTML(code, cls) {
  if (!code) return `<div class="card slot ${cls || ''}"></div>`;
  const c = String(code);
  const r = c.slice(0, c.length - 1);
  const s = c.slice(-1).toLowerCase();
  const red = RED[s] ? ' red' : '';
  return `<div class="card${red} ${cls || ''}"><span class="r">${r}</span>` +
         `<span class="s">${SUIT[s] || s}</span></div>`;
}
const backHTML = (cls) => `<div class="card back ${cls || ''}"></div>`;
const cardsHTML = (arr, cls) => (arr || []).map((c) => cardHTML(c, cls)).join('');

/* ---------------- 좌석 좌표 ----------------
 * 히어로 슬롯이 항상 하단 중앙이 되도록 회전한다. 히어로 자신은 타원 위가
 * 아니라 하단 바(#hero)에 그리므로, 타원에는 나머지 슬롯만 놓인다.
 * 화면 좌표는 y 가 아래로 커진다. 하단(+90도)에서 각도를 줄이면
 * 오른쪽 → 위 → 왼쪽 순서가 되어 포커의 시계방향과 맞는다. */
function slotPos(slot, heroSlot, n, rfx, rfy) {
  const off = (((slot - heroSlot) % n) + n) % n;
  const th = (90 - off * (360 / n)) * Math.PI / 180;
  return { x: 50 + 39 * rfx * Math.cos(th), y: 44 + 36 * rfy * Math.sin(th) };
}

/* ---------------- 상단 바 ---------------- */
function renderTop(v) {
  const lv = v.level;
  $('#lvl').innerHTML = lv
    ? `레벨 ${lv.n} &nbsp;${fmt(lv.sb)}/${fmt(lv.bb)}` +
      (lv.ante ? ` <span class="ante">ante ${fmt(lv.ante)}</span>` : '')
    : '—';
  $('#handno').textContent = v.hand_no ? `HAND ${v.hand_no}` : '';
  const f = v.field || {};
  const bits = [];
  if (f.entries !== undefined) bits.push(`${f.entries}명 중 ${f.remaining}명`);
  if (f.itm !== undefined) bits.push(`ITM ${f.itm}위`);
  if (f.rank) bits.push(`내 순위 ${f.rank}위`);
  $('#fieldline').innerHTML = bits.join(' · ') +
    (f.bubble ? ' <span class="bubblewarn">버블</span>' : '');
  $('#notes').textContent = (v.notes || []).join('  ');
}

/* ---------------- 좌석 ---------------- */
function renderSeats(v) {
  const n = v.n_slots || 8;
  const box = $('#seats');
  // 카드가 가운데 덱에서 날아오게 하려면 '가운데 → 이 자리' 를 픽셀로 알아야
  // 한다. 좌석은 %로 배치되는데 CSS transform 의 %는 자기 박스 기준이라
  // 그대로 못 쓴다. 테이블 크기를 한 번 재서 환산한다.
  const wrap = $('#tablewrap');
  const W = wrap ? wrap.clientWidth : 0, H = wrap ? wrap.clientHeight : 0;
  const by = {};
  (v.seats || []).forEach((s) => { by[s.seat] = s; });
  let html = '';
  for (let slot = 1; slot <= n; slot++) {
    if (slot === v.hero_seat) continue;           // 히어로는 하단 바에 그린다
    const p = slotPos(slot, v.hero_seat, n, 1, 1);
    const d = by[slot];
    const style = `left:${p.x}%;top:${p.y}%`;
    if (!d) {
      html += `<div class="pod empty" data-slot="${slot}" style="${style}">` +
              `<div class="avatar">·</div><div class="meta">` +
              `<span class="pos">빈자리</span><span class="stack">&nbsp;</span>` +
              `</div></div>`;
      continue;
    }
    const cls = 'pod' + (d.in_hand || S.folding[slot] ? '' : ' folded');
    // 방금 폴드한 좌석은 카드를 한 번 더 그려서 사라지는 모션을 보여준다
    const dx = Math.round((50 - p.x) / 100 * W);
    const dy = Math.round((44 - p.y) / 100 * H);   // 44 = slotPos 의 세로 중심
    const nc = dealtCount(slot);
    // 카드마다 자기 시각으로 지연을 계산한다. 한 장씩 들어오므로 두 장의
    // 비행 시점이 다르고, 프레임을 다시 그려도 각자 이어서 난다.
    const cards = [];
    for (let ci = 0; ci < nc; ci++) {
      const st0 = S.dealt ? (S.dealt[slot] || [])[ci] : null;
      cards.push(`<div class="card back mini${S.dealt ? ' fly' : ''}"` +
        (st0 ? ` style="--dx:${dx}px;--dy:${dy}px;animation-delay:${dealDelay(st0)}"` : '') +
        '></div>');
    }
    const backs = (d.in_hand && nc)
      ? `<div class="backs">${cards.join('')}</div>`
      : (S.folding[slot]
         ? `<div class="backs out" style="animation-delay:${foldDelay(S.folding[slot])}">` +
           `${backHTML('mini')}${backHTML('mini')}</div>` : '');
    const memo = (d.pid === undefined || d.pid === null) ? ''
      : `<button type="button" class="memo${memoGet(d.pid) ? ' has' : ''}" ` +
        `data-pid="${d.pid}" data-label="${slot}번(${d.pos || ''})">✎</button>`;
    html += `<div class="${cls}" data-slot="${slot}" style="${style}">` + memo +
            backs +
            `<div class="avatar">${slot}</div>` +
            (d.allin ? `<div class="tag">ALL-IN</div>` : '') +
            (v.button_seat === slot ? `<div class="dealer">D</div>` : '') +
            `<div class="meta"><span class="pos">${d.pos || ''}</span>` +
            `<span class="stack">${fmt(d.stack)}</span></div></div>`;
  }
  box.innerHTML = html;
}

/* ---------------- 좌석 앞 칩 ---------------- */
function renderChips(v, streetChanged) {
  const box = $('#chips');
  const old = Array.from(box.children);
  if (streetChanged && old.length) {
    // 스트리트가 끝났다 — 칩을 중앙으로 보내고 지운다
    old.forEach((el) => {
      el.style.left = '50%'; el.style.top = '50%';
      el.classList.add('toPot');
    });
    setTimeout(() => old.forEach((el) => el.remove()), 420);
  } else {
    box.innerHTML = '';
  }
  const n = v.n_slots || 8;
  (v.seats || []).forEach((s) => {
    if (!s.bet) return;
    const p = slotPos(s.seat, v.hero_seat, n, 0.62, 0.62);
    const el = document.createElement('div');
    el.className = 'chips';
    el.style.left = p.x + '%'; el.style.top = p.y + '%';
    el.innerHTML = `<span class="disc"></span>${fmt(s.bet)}`;
    box.appendChild(el);
  });
}

/* ---------------- 보드 / 팟 ---------------- */
function renderBoard(v) {
  const b = v.board || [];
  const fresh = S.handNo !== v.hand_no;
  const known = fresh ? 0 : S.boardLen;
  let html = '';
  for (let i = 0; i < 5; i++) {
    // 새로 깔린 카드에만 딜 애니메이션을 준다 (지연은 아래에서 스타일로)
    html += (i < b.length) ? cardHTML(b[i], i >= known ? 'deal' : '')
                           : cardHTML(null);
  }
  const box = $('#board');
  box.innerHTML = html;
  Array.from(box.querySelectorAll('.card.deal')).forEach((el, i) => {
    el.style.animationDelay = (i * 90) + 'ms';
  });
  S.boardLen = b.length;
}

function renderPot(v) {
  $('#pot').textContent = '팟 ' + fmt(v.pot_total);
  $('#potsub').textContent = (v.pot_center && v.pot_center !== v.pot_total)
    ? '중앙 ' + fmt(v.pot_center) : '';
}

/* ---------------- 히어로 ---------------- */
function renderHero(v) {
  const me = (v.seats || []).find((s) => s.hero);
  const box = $('#hero');
  box.hidden = false;
  box.classList.toggle('folded', !!me && !me.in_hand);
  const d = v.button_seat === v.hero_seat ? ' · D' : '';
  $('#heroinfo .pos').textContent = (me ? (me.pos || '') : '') + d +
    (me && me.allin ? ' · ALL-IN' : '');
  $('#heroinfo .stack').textContent = me ? fmt(me.stack) : '';
  // **내용이 같으면 다시 그리지 않는다.**
  // renderHero 는 프레임마다 불린다. innerHTML 을 매번 새로 넣으면 카드
  // 엘리먼트가 매번 새로 만들어지고 deal 애니메이션이 그때마다 다시 시작한다.
  // 딜링 한 바퀴 동안 여러 번 되감기고, 끝나면서 클래스가 빠져 툭 하고
  // 자리잡는다 — '두 번쯤 버벅이다 나오는' 증상이 이것이었다.
  const nc = dealtCount(v.hero_seat);
  const sig = nc ? (v.hand_no + '|' + nc + '|' + (v.hero_hole || []).join(',')) : '';
  if (S.heroSig !== sig) {
    S.heroSig = sig;
    $('#herocards').innerHTML = nc
      ? cardsHTML((v.hero_hole || []).slice(0, nc), 'deal') : '';
  }
}

/* ---------------- 딜링 모션 ----------------
 * 핸드가 시작되면 SB 부터 딜러까지 한 바퀴 카드를 돌린 뒤에 액션을 재생한다.
 * 예전에는 핸드가 바뀌는 순간 이미 UTG 가 액션한 화면이 떠 있었다.
 *
 * **순전히 표시다.** 서버에 아무것도 묻지 않고, 이미 받은 뷰의 좌석 목록을
 * 순서대로 공개하는 것뿐이다. 엔진은 이 동안에도 계속 돌고 있다.
 *
 * 속도는 stepMs 하나에서 파생시킨다. 슬롯이 8개라 8로 나눠 한 바퀴가
 * 액션 하나 간격 정도에 끝나게 둔다.
 */
// 카드 돌리는 데 걸리는 총 시간. 좌석 수로 나눠 한 장씩 뿌린다.
// 8명이든 3명이든 한 바퀴가 같은 시간에 끝나 리듬이 일정하다.
const SHUFFLE_MS = 700;       // 가운데 덱이 섞이는 구간
// 실제 딜처럼 **한 장씩 두 바퀴** 돌린다. 한 장 간격은 폴드 연출과 같은
// 빠르기로 맞추되, 8인 테이블이면 카드가 16장이라 그대로 쓰면 12초가 된다.
// 그래서 간격은 그 1/3 로 두고, 대신 카드 한 장의 **비행 시간**을 폴드
// 모션만큼 길게 잡아 서로 겹쳐 날아가게 한다 — 딜러가 빠르게 튕겨도
// 카드 하나하나는 천천히 도는 것과 같은 그림이다.
const dealMs = () => Math.round(paceMs({ action: 'fold' }) / 3);

const DEAL_ANIM = 240;           // style.css 의 dealin 길이와 같아야 한다
function dealtCount(slot) {
  if (!S.dealt) return 2;                 // 딜링이 끝났으면 두 장 다
  return (S.dealt[slot] || []).length;
}
function dealtYet(slot) {
  return dealtCount(slot) > 0;
}
/* 폴드 모션과 같은 이유로 경과분을 건너뛴다. renderSeats 가 프레임마다
 * #seats 를 통째로 다시 그리므로, 이미 카드를 받은 좌석은 딜링이 한 바퀴
 * 도는 동안 애니메이션을 계속 처음부터 다시 시작하고 있었다. */
function dealDelay(t0) {
  const el = Math.min(DEAL_ANIM, Math.max(0, performance.now() - t0));
  return (-el).toFixed(0) + 'ms';
}

function dealOrder(v) {
  // 버튼 다음 자리부터 시계방향 = SB, BB, ... , 마지막이 버튼이다.
  //
  // **앉아 있는 사람 전원**에게 돌린다. in_hand 로 거르면 안 된다 — 화면에
  // 온 뷰는 이미 프리플랍 액션이 끝난 시점이라 접은 사람이 빠져 있고,
  // 그러면 그 자리만 카드를 못 받다가 재생이 시작되는 순간 불쑥 생긴다.
  // 실제로도 카드는 전원에게 돌리고 그 다음에 접는다.
  const n = v.n_slots || 8;
  const have = {};
  (v.seats || []).forEach((s) => { have[s.seat] = 1; });
  const btn = v.button_seat || n;
  const out = [];
  for (let k = 1; k <= n; k++) {
    const slot = ((btn - 1 + k) % n) + 1;
    if (have[slot]) out.push(slot);
  }
  return out;
}

function dealThen(v, done) {
  const order = dealOrder(v);
  if (!order.length) { S.dealt = null; deckHide(); done(); return; }
  // 딜링 중에는 아직 아무 액션도 없었다. 뷰는 재생이 끝난 뒤의 상태라
  // 그대로 그리면 **프리플랍 액션이 전부 이미 벌어진 화면**이 된다 —
  // 접은 자리가 회색이고, 칩과 올인 표시까지 미리 나와 있었다.
  // 액션 전 상태(블라인드만 들어간 상태)로 그린다. drawFrame 이 칩·스택·
  // 올인을 그 프레임 기준으로 다시 계산하고, folded 가 비었으니 전원 참가다.
  const bets0 = baseBets(v, false);
  const draw0 = () => drawFrame(v, bets0, {});
  // 한 장씩 두 바퀴. S.dealt[좌석] 은 '받은 카드들의 시각' 배열이다.
  const seq = order.concat(order);
  S.dealt = {};
  draw0();
  deckShow();
  let i = 0, ended = false;
  // **딜링 중에도 재생 중이다.** 여기에 replayDone 을 안 걸어둬서, 카드를
  // 돌리는 동안 폴드를 누르면 예약되지 않고 바로 전송됐다 — 그러면 응답이
  // 와서 stopReplay 가 딜링과 뒤이을 봇 액션 재생을 통째로 끊는다.
  // 딜링을 3초로 늘리면서 이 구멍이 더 잘 드러났다.
  const finish = () => {
    if (ended) return;
    ended = true;
    S.timers.forEach(clearTimeout); S.timers = [];
    S.dealt = null; S.replayDone = null;
    deckHide();
    renderSeats(v); renderHero(v);
    done();
  };
  S.replayDone = finish;
  const next = () => {
    if (i >= seq.length) { finish(); return; }
    const slot = seq[i++];
    (S.dealt[slot] = S.dealt[slot] || []).push(Math.max(1, performance.now()));
    draw0();
    S.timers.push(setTimeout(next, dealMs()));
  };
  S.timers.push(setTimeout(next, SHUFFLE_MS));   // 섞고 나서 돌린다
}

/* ---------------- 가운데 덱 ----------------
 * 카드가 허공에서 생기는 대신, 가운데 덱에서 한 장씩 날아가게 한다.
 * 덱은 표시 전용 엘리먼트다 — 상태도 엔진도 건드리지 않는다.
 */
function deckShow() {
  const d = $('#deck');
  if (!d) return;
  d.innerHTML = backHTML('mini') + backHTML('mini') + backHTML('mini');
  d.hidden = false;
  d.classList.remove('shuffle');
  void d.offsetWidth;              // 애니메이션 재시작
  d.classList.add('shuffle');
}
function deckHide() {
  const d = $('#deck');
  if (!d) return;
  d.hidden = true; d.classList.remove('shuffle');
}

/* ---------------- 말풍선 ---------------- */
/* 진행 중인 연출을 끊는다. **응답이 올 때마다 반드시 먼저 불러야 한다.**
 *
 * 예전에는 핸드 번호가 바뀔 때만(clearBubbles) 타이머를 정리했다. 그래서
 * 봇 액션 재생이 끝나기 전에 히어로가 액션을 누르면 새 응답의 재생 체인과
 * 예전 체인이 **동시에** 돌았다. 둘이 각자의 bets/folded 를 들고 drawFrame 을
 * 불러서 칩과 말풍선이 뒤섞였다. 화면이 깨지는 원인이 이것이었다.
 *
 * folding 도 같이 비운다. 폴드 모션을 지우는 타이머가 S.timers 에 있어서
 * 그것까지 취소되면 그 좌석이 영구히 '사라지는 중' 상태로 남는다.
 */
function stopReplay() {
  S.timers.forEach(clearTimeout); S.timers = [];
  S.replayDone = null;
  S.queuedAction = null;   // 응답이 왔으면 그 예약은 이미 의미가 없다
  S.dealt = null;          // 딜링 중에 끊겼으면 카드를 전부 보이는 상태로 되돌린다
  // folding 은 건드리지 않는다. 진행 중인 폴드 모션은 응답이 와도 끝까지 간다
  // (정리 타이머가 S.foldTimers 에 따로 있어서 취소되지 않는다).
}

function clearBubbles() {
  stopReplay();
  document.querySelectorAll('.bubble').forEach((b) => b.remove());
}
function actionText(e) {
  const t = ACT[e.action] || e.action;
  return (e.action === 'bet' || e.action === 'raise') && e.amount
    ? `${t} ${fmt(e.amount)}` : t;
}
/* 폴드 모션.
 *
 * renderSeats 는 프레임마다 #seats 를 통째로 다시 그린다. 그래서 .backs.out
 * 엘리먼트가 매번 새로 만들어지고, **CSS 애니메이션이 그때마다 처음부터
 * 다시 시작한다.** 그게 '버벅이다 사라지는' 증상이었다. 액션 간격이 짧아질수록
 * 다시 그리는 횟수가 늘어 더 눈에 띈다.
 *
 * 시작 시각을 들고 있다가 음수 animation-delay 로 경과분만큼 건너뛴다.
 * 엘리먼트가 새로 만들어져도 모션은 이어진 자리에서 계속된다.
 *
 * 정리 타이머는 S.timers 가 아니라 따로 둔다. stopReplay 가 재생 타이머를
 * 취소할 때 같이 취소되면 그 좌석이 영구히 '사라지는 중' 으로 남는다.
 */
const FOLD_ANIM = 550;          // style.css 의 foldout 길이와 같아야 한다
function foldDelay(t0) {
  const el = Math.min(FOLD_ANIM, Math.max(0, performance.now() - t0));
  return (-el).toFixed(0) + 'ms';
}
function markFold(seat) {
  if (S.folding[seat]) return;            // 이미 도는 모션을 되감지 않는다
  S.folding[seat] = performance.now();
  S.foldTimers.push(setTimeout(() => { delete S.folding[seat]; }, FOLD_ANIM + 150));
}
function resetFolding() {
  S.foldTimers.forEach(clearTimeout); S.foldTimers = [];
  S.folding = {};
}

function bubbleAt(seat, e) {
  const pod = document.querySelector(`.pod[data-slot="${seat}"]`);
  if (!pod) return;
  const b = document.createElement('div');
  b.className = 'bubble' + (e.action === 'fold' ? ' fold' : '');
  b.textContent = actionText(e);
  pod.appendChild(b);
}

/* ---------------- 봇 액션 순차 재생 ----------------
 * 규칙을 다시 계산하지 않는다. 중간 프레임은 서버가 준 숫자들의 산술일 뿐이다.
 *   로그의 amount = 그 액션 뒤 그 좌석의 '이번 스트리트 총 투입액' (runner.py:122-126)
 *   한 스트리트 안에서 stack + bet 는 보존되므로  stack_i = 최종stack + 최종bet - bet_i
 *   pot_i = pot_center + Σ bet_i        (pot_center 는 스트리트 안에서 불변)
 * 마지막에는 반드시 서버 응답 그대로 다시 그린다. 중간은 연출, 최종은 진실.
 */
function baseBets(v, hasPrev) {
  const b = {};
  (v.seats || []).forEach((s) => { b[s.seat] = s.bet || 0; });
  if (hasPrev && S.prevBets) {
    Object.keys(S.prevBets).forEach((k) => { b[k] = S.prevBets[k]; });
    return b;
  }
  // 새 핸드/새 스트리트: 이번에 액션한 좌석만 액션 전 값으로 되돌린다.
  // 프리플랍은 블라인드가 로그보다 먼저 들어가 있으므로 그 값, 그 외는 0.
  const lv = v.level || {};
  (v.log || []).forEach((e) => {
    const st = (v.seats || []).find((x) => x.seat === e.seat);
    const pos = st ? st.pos : null;
    b[e.seat] = (v.stage === 'preflop')
      ? (pos === 'SB' ? (lv.sb || 0) : pos === 'BB' ? (lv.bb || 0) : 0)
      : 0;
  });
  return b;
}

function drawFrame(v, bets, folded) {
  // allin 도 그 프레임 기준으로 다시 판정한다. v.seats 의 allin 은 **재생이 다
  // 끝난 뒤**의 상태라, 그대로 쓰면 아직 올인하지 않은 좌석에 ALL-IN 배지가
  // 미리 떴다 (칩과 폴드는 이미 프레임 기준으로 다시 계산하고 있었다).
  const seats = (v.seats || []).map((s) => {
    const st = s.stack + (s.bet || 0) - (bets[s.seat] || 0);
    return Object.assign({}, s, {
      bet: bets[s.seat] || 0,
      in_hand: !folded[s.seat],
      stack: st,
      allin: st <= 0 && !folded[s.seat] && (bets[s.seat] || 0) > 0,
    });
  });
  const sum = seats.reduce((a, s) => a + (s.bet || 0), 0);
  const fv = Object.assign({}, v, { seats: seats,
                                    pot_total: (v.pot_center || 0) + sum });
  renderSeats(fv); renderChips(fv, false); renderPot(fv); renderHero(fv);
}

function finalFrame(v) {
  // clearBubbles -> stopReplay 가 예약을 지우므로 먼저 챙겨둔다.
  // stopReplay 가 지우는 이유는 '응답이 왔을 때' 를 위한 것이고,
  // 여기는 '재생이 끝났을 때' 라 의미가 반대다.
  const q = S.queuedAction;
  clearBubbles();
  renderSeats(v); renderPot(v); renderHero(v);
  const bets = {};
  (v.seats || []).forEach((s) => { bets[s.seat] = s.bet || 0; });
  S.prevBets = bets;
  renderLogLine(v);              // 재생이 끝났으니 이제 글로도 보여준다
  S.queuedAction = q;
  flushQueued();                 // 재생 중에 눌러둔 히어로 액션
}

function playSequence(v, entries, streetChanged) {
  const bets = baseBets(v, !streetChanged && S.handNo === v.hand_no);
  const folded = {};
  (v.seats || []).forEach((s) => { if (!s.in_hand) folded[s.seat] = 1; });
  entries.forEach((e) => { if (e.action === 'fold') delete folded[e.seat]; });

  // 히어로 자신의 액션은 이미 본 것이다. 거기까지는 즉시 반영하고 그 뒤부터 재생한다.
  let from = 0;
  entries.forEach((e, i) => { if (e.seat === v.hero_seat) from = i + 1; });
  for (let i = 0; i < from; i++) {
    const e = entries[i];
    if (e.action === 'fold') folded[e.seat] = 1;
    else if (e.action !== 'check') bets[e.seat] = e.amount || bets[e.seat] || 0;
  }

  const rest = entries.slice(from).filter((e) => e.seat !== v.hero_seat);
  if (!rest.length) { finalFrame(v); return; }

  drawFrame(v, bets, folded);
  S.replayDone = () => finalFrame(v);
  let i = 0;
  (function next() {
    if (i >= rest.length) { finalFrame(v); return; }
    const e = rest[i++];
    if (e.action === 'fold') { folded[e.seat] = 1; markFold(e.seat); }
    else if (e.action !== 'check') bets[e.seat] = e.amount || bets[e.seat] || 0;
    drawFrame(v, bets, folded);
    bubbleAt(e.seat, e);
    S.timers.push(setTimeout(next, paceMs(e)));
  })();
}

/* ---------------- 관전 재생 ----------------
 * 히어로가 폴드하면 서버는 남은 진행을 한 번에 끝내고 결과만 돌려준다.
 * 그 결과의 log 가 핸드 전체 기록(full_log: street/seat/action/amount)이므로,
 * 아직 화면에 안 나온 뒷부분을 여기서 순서대로 재생한다.
 * **엔진을 다시 돌리지 않는다.** 서버가 준 숫자만 산술로 전개한다.
 *
 * 이미 보여준 개수 = 마지막 decision 뷰의 prior_log + log 길이.
 * prior_log 는 '완료된 스트리트'만 담고 현재 스트리트는 log 에 있어 겹치지 않는다
 * (session.py:234,325,669).
 */
const BOARD_AT = { preflop: 0, flop: 3, turn: 4, river: 5 };

function applyEntry(ss, e) {
  if (e.street && e.street !== ss.stage) {
    // 스트리트가 끝났다 — 칩을 팟으로 넣고 베팅을 접는다
    ss.potCenter += ss.seats.reduce((a, x) => a + (x.bet || 0), 0);
    ss.seats.forEach((x) => { x.bet = 0; });
    ss.stage = e.street;
    if (BOARD_AT[e.street] !== undefined) ss.boardShown = BOARD_AT[e.street];
  }
  const st = ss.seats.find((x) => x.seat === e.seat);
  if (!st) return;
  if (e.action === 'fold') { st.in_hand = false; return; }
  if (e.action === 'check') return;
  // 로그의 amount = 그 액션 뒤 그 좌석의 '이번 스트리트 총 투입액' (runner.py:122-126)
  const add = Math.max(0, (e.amount || 0) - (st.bet || 0));
  st.stack = Math.max(0, (st.stack || 0) - add);
  st.bet = e.amount || 0;
  if (st.stack === 0) st.allin = true;
}

function renderSpectate(base, res, ss) {
  const bets = ss.seats.reduce((a, x) => a + (x.bet || 0), 0);
  const fv = Object.assign({}, base, {
    seats: ss.seats, stage: ss.stage,
    board: (res.board || []).slice(0, ss.boardShown),
    pot_center: ss.potCenter, pot_total: ss.potCenter + bets,
  });
  renderSeats(fv); renderChips(fv, false); renderBoard(fv);
  renderPot(fv); renderHero(fv);
  // '관전 중' 은 히어로가 접었을 때만 쓴다. 히어로가 아직 핸드에 남아 있는데
  // 이 표기가 뜨면 재생이 시작되기도 전에 '봇들이 다 접어서 끝났다'가 드러난다.
  $('#logline').innerHTML = '<span class="cur">' +
    (STREET[ss.stage] || ss.stage) + '</span>' + (S.spectating ? ' 관전 중' : '');
}

function spectateTail(res) {
  const base = S.view0;
  if (!base || base.type !== 'decision' || base.hand_no !== res.hand_no) return false;
  const shown = (base.prior_log || []).length + (base.log || []).length;
  const tail = (res.log || []).slice(shown);
  if (!tail.length) return false;

  const ss = {
    seats: (base.seats || []).map((x) => Object.assign({}, x)),
    potCenter: base.pot_center || 0,
    stage: base.stage,
    boardShown: (base.board || []).length,
  };
  // 히어로가 접어서 남은 진행을 구경하는 것인지, 아니면 히어로가 아직 핸드에
  // 남아 있는데 상대가 접어서 끝난 것인지 구분한다. 뒤쪽에서 '관전' 이라고
  // 쓰면 연출 전에 결과가 노출된다.
  const mine = (res.log || []).filter((e) => e.seat === res.hero_seat);
  S.spectating = mine.length > 0 && mine[mine.length - 1].action === 'fold';
  $('#mainrow').innerHTML = '<div class="wait">' +
    (S.spectating ? '관전 중 — 화면을 누르면 건너뜁니다'
                  : '진행 중 — 화면을 누르면 건너뜁니다') + '</div>';
  closeRaise();
  clearBubbles();

  let i = 0;
  S.replayDone = () => { finishResult(res); };
  (function next() {
    if (i >= tail.length) { finishResult(res); return; }
    const e = tail[i++];
    if (e.action === 'fold') markFold(e.seat);
    applyEntry(ss, e);
    renderSpectate(base, res, ss);
    if (e.seat !== res.hero_seat) bubbleAt(e.seat, e);
    // 스트리트 전환에 간격을 더 주던 것을 뺐다. 보드 카드 애니메이션은 CSS 가
    // 이미 하고 있어서, 그 500ms 는 다음 액션을 더 미루기만 했다.
    S.timers.push(setTimeout(next, paceMs(e)));
  })();
  return true;
}

/* ---------------- 액션 로그 한 줄 ---------------- */
function renderLogLine(v) {
  const txt = (v.log || []).map((e) => {
    const who = e.seat === v.hero_seat ? '나' : (e.seat + '번');
    return who + ' ' + actionText(e);
  }).join(' → ');
  $('#logline').innerHTML = `<span class="cur">${STREET[v.stage] || v.stage}</span> ` +
    (txt || '—');
}

/* ---------------- 액션 바 ---------------- */
function btn(id, label, sub, fn) {
  const b = document.createElement('button');
  b.type = 'button'; b.id = id;
  b.innerHTML = label + (sub ? `<span class="sub">${sub}</span>` : '');
  b.addEventListener('click', fn);
  return b;
}

function renderActions(v) {
  closeRaise();
  const row = $('#mainrow');
  row.innerHTML = '';
  const lg = v.legal || {};
  if (lg.fold) row.appendChild(btn('bFold', '폴드', '', () => send('fold', 0)));
  if (lg.check) row.appendChild(btn('bCheck', '체크', '', () => send('check', 0)));
  if (lg.call !== null && lg.call !== undefined) {
    row.appendChild(btn('bCall', lg.call_is_allin ? 'ALL-IN' : '콜',
      fmt(lg.call), () => send('call', 0)));
  }
  const rz = lg.raise;
  if (rz) {
    if (rz.allin_only) {
      row.appendChild(btn('bRaise', 'ALL-IN', fmt(rz.max_to), () => send('allin', 0)));
    } else {
      row.appendChild(btn('bRaise', rz.kind === 'bet' ? '벳' : '레이즈',
        `${fmt(rz.min_to)} ~ ${fmt(rz.max_to)}`, () => openRaise(v)));
    }
  }
  row.hidden = false;
  if (!row.children.length) {
    row.innerHTML = '<div class="wait">액션 없음</div>';
  }
}

/* --- 레이즈 패널. 금액은 전부 raise-to(이번 스트리트 총 투입 목표) --- */
function openRaise(v) {
  const rz = v.legal.raise;
  const me = (v.seats || []).find((s) => s.hero) || { bet: 0 };
  const P = v.pot_total, C = v.to_call, L = me.bet + C;
  const clamp = (x) => Math.max(rz.min_to, Math.min(rz.max_to, Math.round(x)));
  // 팟 비율 레이즈: 콜한 뒤의 팟(P+C)의 f 배를 얹는다
  const byPot = (f) => clamp(Math.round((L + f * (P + C)) / 100) * 100);

  const panel = $('#raisepanel');
  panel.hidden = false;
  $('#mainrow').hidden = true;
  $('#rrange').textContent = `${fmt(rz.min_to)} ~ ${fmt(rz.max_to)} raise-to`;

  const sl = $('#rslider');
  sl.min = 0; sl.max = 1000; sl.step = 1;
  const toVal = (p) => clamp(Math.round((rz.min_to + (rz.max_to - rz.min_to) * p / 1000) / 100) * 100);
  const toPos = (x) => rz.max_to === rz.min_to ? 1000
    : Math.round((x - rz.min_to) / (rz.max_to - rz.min_to) * 1000);

  let cur = rz.min_to;
  function set(x, movePos) {
    cur = clamp(x);
    $('#ramtval').textContent = fmt(cur);
    $('#rnum').value = cur;
    if (movePos !== false) sl.value = toPos(cur);
  }
  sl.oninput = () => set(toVal(Number(sl.value)), false);
  $('#rnum').oninput = () => {
    const x = Number($('#rnum').value);
    if (!isNaN(x)) { cur = clamp(x); $('#ramtval').textContent = fmt(cur); sl.value = toPos(cur); }
  };
  $('#rnum').onblur = () => set(Number($('#rnum').value) || rz.min_to);

  const pres = $('#rpresets');
  pres.innerHTML = '';
  const items = [['최소', rz.min_to], ['½팟', byPot(0.5)], ['팟', byPot(1)],
                 ['올인', rz.max_to]];
  const seen = {};
  items.forEach(([label, val]) => {
    if (seen[val] && label !== '올인') return;
    seen[val] = 1;
    pres.appendChild(btn('', label, fmt(val), () => set(val)));
  });

  $('#rok').onclick = () => {
    closeRaise();
    // 상한이면 'allin' 으로 보낸다. 엔진이 스스로 올인 목표를 계산하므로
    // 반올림 때문에 1칩이 어긋날 일이 없다.
    if (cur >= rz.max_to) send('allin', 0);
    else send(rz.kind, cur);
  };
  $('#rcancel').onclick = closeRaise;
  set(rz.min_to);
}
function closeRaise() { $('#raisepanel').hidden = true; $('#mainrow').hidden = false; }

/* ---------------- 결과 / 종료 화면 ---------------- */
function seatName(v, s) {
  const p = (v.pos || {})[String(s)];
  const me = String(s) === String(v.hero_seat);
  return (me ? '나' : s + '번') + (p ? `(${p})` : '');
}

function finishResult(v) {
  clearBubbles();
  histPush(v);
  if (S.won) { showWin(v); return; }
  renderResult(v);
  S.handNo = null; S.stage = null; S.logLen = 0; S.boardLen = 0;
  S.prevBets = null; S.view0 = null;
  // 결과를 잠깐 보여주고 자동으로 다음 핸드로 간다. 이 시간 동안 서버 워커가
  // 다른 테이블 정산을 마저 돌린다 — 기다림이 여기에 겹친다.
  // 서버 워커가 다른 테이블을 다 돌릴 때까지는 넘어가지 않는다.
  // 넘어가 봐야 서버가 거기서 기다리게 되고, 사용자는 빈 로딩 화면만 본다.
  // 같은 시간이라면 결과를 보면서 기다리는 편이 낫다.
  const STEP = 500;
  let waited = 0;
  const auto = autoOn();
  const tick = async () => {
    const b = $('#bDeal');
    if (!b) { S.autoTimer = null; return; }
    let working = false;
    try {
      const r = await fetch('/api/ready');
      working = !!(await r.json()).working;
    } catch (e) { /* 못 물어봤으면 그냥 시간만 센다 */ }
    waited += STEP;
    if (working) {
      b.innerHTML = '다음 핸드 <span class="sub">다른 테이블 정산 중… ' +
        Math.round(waited / 1000) + '초</span>';
    } else if (!auto) {
      b.innerHTML = '다음 핸드';
      S.autoTimer = null; return;          // 자동이 꺼져 있으면 여기서 멈춘다
    } else {
      // 정산이 끝났으면 **기다리지 않는다.** 예전에는 여기서 결과 화면을
      // 몇 초 더 띄웠는데, 그 시간은 워커를 가리려고 둔 것이었다.
      // 정산이 빨라진 지금은 그냥 지연일 뿐이다.
      S.autoTimer = null; send(null, 0); return;
    }
    S.autoTimer = setTimeout(tick, STEP);
  };
  tick();
}

/* 사이드팟은 **올인한 사람 때문에 자격이 갈릴 때만** 생기는 개념이다.
 * 엔진은 기여액이 다른 구간마다 팟을 쪼개는데(session.award_pots), 프리플랍에
 * 블라인드·안테만 넣고 접은 사람들 때문에 구간이 생긴다. 돈 계산은 그게 맞지만
 * 화면에 '사이드1' 이라고 쓰면 아무도 올인하지 않은 핸드에 사이드팟이 뜬다.
 *
 * 자격자(살아서 다툰 사람)가 같은 구간은 하나로 합쳐서 보여준다. 올인이 없으면
 * 자격자가 내내 같으므로 팟이 하나가 되고, 올인이 있으면 자격자가 달라져 그대로
 * 갈린다. **표시만 합친다** — 금액과 분배는 엔진이 준 그대로다.
 */
function mergePots(pots) {
  const out = [];
  (pots || []).forEach((p) => {
    const key = (p.eligible || []).slice().sort().join(',');
    const last = out.length ? out[out.length - 1] : null;
    if (last && last._key === key) {
      last.amount = (last.amount || 0) + (p.amount || 0);
      return;
    }
    out.push({ _key: key, amount: p.amount, eligible: p.eligible, winners: p.winners });
  });
  return out;
}

/* withLog — 라인 기록을 붙일지. 방금 끝난 핸드의 결과 화면에는 붙이지 않는다.
 * 그 화면은 방금 눈으로 본 것을 다시 글로 읽게 하고 5초 안에 지나간다.
 * 지난 핸드 상세('기록')에서는 그게 유일한 내용이라 붙인다. */
function resultBodyHTML(v, withLog) {
  const win = (v.main_winners && v.main_winners.length ? v.main_winners : v.winners) || [];
  const winSet = {};
  win.forEach((w) => { winSet[String(w)] = 1; });

  let rows = '';
  if (v.showdown) {
    Object.keys(v.shown || {}).forEach((s) => {
      rows += `<div class="row${winSet[s] ? ' win' : ''}">` +
        `<span class="who">${seatName(v, s)}</span>` +
        `<span class="cards">${cardsHTML(v.shown[s], 'mini')}</span>` +
        `${winSet[s] ? '<span class="amt">승</span>' : ''}</div>`;
    });
  } else {
    const w = win.length ? win[0] : null;
    rows += `<div class="row win"><span class="who">` +
      (w === null ? '?' : seatName(v, w)) +
      `</span><span class="amt">팟 획득 · 쇼다운 없음</span></div>`;
  }

  let potsHTML = '';
  const pots = mergePots(v.pots);
  if (pots.length > 1) {
    potsHTML = '<div class="potline">팟 분배</div>' + pots.map((p, i) =>
      `<div class="row"><span class="who">${i === 0 ? '메인' : '사이드' + i}</span>` +
      `<span>${(p.winners || []).map((w) => seatName(v, w)).join(', ') || '-'}</span>` +
      `<span class="amt">${fmt(p.amount)}</span></div>`).join('');
  }

  const how = { fold: '폴드로 종료', showdown: '쇼다운', void: '무효' }[v.how] || v.how;
  return `<h2>HAND ${v.hand_no ?? ''} 결과</h2>` +
    `<div class="sub">${how} · 팟 ${fmt(v.pot)}</div>` +
    `<div class="boardrow">${(v.board || []).length ? cardsHTML(v.board) : '<span class="sub">보드 없음</span>'}</div>` +
    rows + potsHTML +
    (withLog ? logBoxHTML(v.log, v) : '') +
    (v.notes || []).map((n) => `<div class="potline">${n}</div>`).join('');
}

function renderResult(v) {
  $('#mainrow').innerHTML = '<div class="wait">핸드 종료</div>';
  closeRaise();
  showOverlay(resultBodyHTML(v) +
    `<div class="actions"><button type="button" id="bDeal">다음 핸드</button></div>`);
  $('#bDeal').addEventListener('click', () => {
    clearTimeout(S.autoTimer); S.autoTimer = null;
    send(null, 0);
  });
}

/* ---------------- 지난 핸드 기록 ----------------
 * 진행 중인 핸드는 화면으로 직접 본다(관전 재생). 그래서 '기록'은 **지난 핸드**를
 * 보여준다. 서버 아카이브(hand_archive2.jsonl)를 읽지 않는다 — 거기에는
 * 쇼다운하지 않은 좌석의 홀카드가 들어 있다. 이미 화면에 나왔던 결과 뷰만
 * 그대로 쌓는다. 쇼다운 좌석 외의 카드는 애초에 들어 있지 않다.
 */
const AUTO_KEY = 't2auto';
function autoOn() {
  try { return localStorage.getItem(AUTO_KEY) !== '0'; } catch (e) { return true; }
}
function autoSet(on) {
  try { localStorage.setItem(AUTO_KEY, on ? '1' : '0'); } catch (e) {}
}

const HIST_KEY = 't2hands';
const HIST_MAX = 40;

function histLoad() {
  try { return JSON.parse(localStorage.getItem(HIST_KEY) || '[]') || []; }
  catch (e) { return []; }
}
function histSave(list) {
  try { localStorage.setItem(HIST_KEY, JSON.stringify(list)); }
  catch (e) {
    // 용량이 차면 오래된 것부터 버린다
    try { localStorage.setItem(HIST_KEY, JSON.stringify(list.slice(0, 10))); }
    catch (e2) { /* 저장 못 해도 게임은 계속된다 */ }
  }
}
function histPush(v) {
  if (!v || v.type !== 'result') return;
  const list = histLoad().filter((x) => x.hand_no !== v.hand_no);
  list.unshift(v);
  histSave(list.slice(0, HIST_MAX));
}
function histClear() { try { localStorage.removeItem(HIST_KEY); } catch (e) {} }

function showHistory() {
  const list = histLoad();
  if (!list.length) {
    showOverlay('<h2>지난 핸드</h2><div class="sub">아직 끝난 핸드가 없습니다.</div>' +
      '<div class="actions"><button type="button" id="bClose">닫기</button></div>');
    $('#bClose').addEventListener('click', hideOverlay);
    return;
  }
  const rows = list.map((v, i) => {
    const win = (v.main_winners && v.main_winners.length ? v.main_winners : v.winners) || [];
    const mine = win.some((w) => String(w) === String(v.hero_seat));
    const how = { fold: '폴드로 종료', showdown: '쇼다운', void: '무효' }[v.how] || v.how;
    return `<div class="row hist${mine ? ' win' : ''}" data-i="${i}">` +
      `<span class="who">HAND ${v.hand_no ?? '?'}</span>` +
      `<span class="cards">${cardsHTML((v.board || []).slice(0, 5), 'mini')}</span>` +
      `<span class="amt">${mine ? '승 ' : ''}${fmt(v.pot)}</span>` +
      `<div class="histsub">${how}</div></div>`;
  }).join('');
  showOverlay(`<h2>지난 핸드</h2><div class="sub">${list.length}개 · 눌러서 자세히</div>` +
    rows +
    '<div class="actions"><button type="button" id="bClose">닫기</button></div>');
  $('#bClose').addEventListener('click', hideOverlay);
  document.querySelectorAll('#overlay .row.hist').forEach((el) => {
    el.addEventListener('click', () => showHandDetail(list[Number(el.dataset.i)]));
  });
}

/* index.html 이 app.js 를 ?v=N 으로 불러온다. 그 N 을 그대로 보여준다.
 * 브라우저가 옛 파일을 캐시하고 있으면 여기 숫자도 옛것이라 바로 드러난다. */
function buildTag() {
  const el = document.querySelector('script[src*="app.js"]');
  const m = el && /[?&]v=([^&]*)/.exec(el.getAttribute('src') || '');
  return m ? m[1] : '?';
}

function showMenu() {
  clearTimeout(S.autoTimer); S.autoTimer = null;
  const on = autoOn();
  const sm = stepMs();
  showOverlay('<h2>설정</h2>' +
    `<div class="row"><span class="who">봇 액션 간격</span>` +
    `<span class="amt">${(sm / 1000).toFixed(1)}초</span></div>` +
    `<button type="button" id="mStep">간격 바꾸기</button>` +
    '<div class="potline" style="margin-top:8px">딜링 속도도 이 값을 따라갑니다.</div>' +
    `<div class="row" style="margin-top:14px"><span class="who">결과 화면</span>` +
    `<span class="amt">${on ? '정산 끝나면 바로' : '자동 안 넘김'}</span></div>` +
    `<button type="button" id="mAuto">${on ? '자동 진행 끄기' : '자동 진행 켜기'}</button>` +
    '<div class="potline" style="margin-top:8px">자동 진행이면 다른 테이블 정산이' +
    ' 끝나는 즉시 다음 핸드로 갑니다. 카운트다운은 없앴습니다 — 그 대기는' +
    ' 정산을 가리려고 두었던 것인데, 정산이 빨라진 지금은 지연일 뿐입니다.</div>' +
    '<div class="potline" style="margin-top:14px">지금 대회를 접고 새로 시작합니다.' +
    ' 기존 기록은 bak_ 파일로 보관됩니다.</div>' +
    '<button type="button" id="mNew">새 게임</button>' +
    // 어느 빌드가 떠 있는지 확인할 수단이 없어서, 이미 고친 것을 두고
    // '아직도 그대로다' 를 서로 확인하는 데 시간을 썼다.
    `<div class="potline" style="margin-top:14px;opacity:.6">화면 버전 ${buildTag()}</div>` +
    '<div class="actions"><button type="button" id="mClose">닫기</button></div>');
  $('#mStep').addEventListener('click', () => {
    const i = STEP_CHOICES.indexOf(sm);
    setPref('t2step', STEP_CHOICES[(i + 1) % STEP_CHOICES.length]);
    showMenu();
  });
  $('#mAuto').addEventListener('click', () => { autoSet(!on); showMenu(); });
  $('#mNew').addEventListener('click', () => {
    showOverlay('<h2>새 게임을 시작할까요?</h2>' +
      '<div class="sub">진행 중인 대회는 끝납니다. 되돌릴 수 없습니다.</div>' +
      newGameFormHTML() +
      '<div class="actions"><button type="button" id="bNew">시작</button>' +
      '<button type="button" id="mBack">취소</button></div>');
    $('#bNew').addEventListener('click', startNew);
    $('#mBack').addEventListener('click', showMenu);
  });
  $('#mClose').addEventListener('click', hideOverlay);
}

function showHandDetail(v) {
  showOverlay(resultBodyHTML(v, true) +
    '<div class="actions"><button type="button" id="bBack">목록으로</button></div>');
  $('#bBack').addEventListener('click', showHistory);
}

function logBoxHTML(log, v) {
  if (!log || !log.length) return '';
  let out = '<div class="logbox">';
  let cur = null;
  log.forEach((e) => {
    if (e.street !== cur) {
      cur = e.street;
      out += `<div><span class="st">${STREET[cur] || cur}</span>`;
    } else out += ' · ';
    const who = String(e.seat) === String(v.hero_seat) ? '나' : e.seat + '번';
    out += `${who} ${actionText(e)}`;
  });
  return out + '</div></div>';
}

/* 우승 화면. 마지막 핸드 결과를 그대로 보여주고 그 위에 우승을 얹는다.
 * 여기서 멈춘다 — 다음 핸드를 부르지 않는다. 한 명 남은 대회에 딜을 걸면
 * 엔진이 테이블을 못 찾는다. */
function showWin(v) {
  clearTimeout(S.autoTimer); S.autoTimer = null;
  $('#mainrow').innerHTML = '<div class="wait">대회 종료</div>';
  closeRaise();
  showOverlay('<h2>🏆 우승</h2>' +
    `<div class="sub">${S.entries ? S.entries + '명 중 ' : ''}1위</div>` +
    resultBodyHTML(v, true) +
    newGameFormHTML() +
    '<div class="actions"><button type="button" id="bNew">새 게임</button>' +
    '<button type="button" id="bClose">닫기</button></div>');
  $('#bNew').addEventListener('click', startNew);
  $('#bClose').addEventListener('click', hideOverlay);
}

function showGameOver(resp) {
  clearBubbles();
  clearTimeout(S.autoTimer); S.autoTimer = null;
  $('#mainrow').innerHTML = '<div class="wait">토너먼트 종료</div>';
  closeRaise();
  showOverlay(
    `<h2>탈락</h2><div class="sub">최종 ${resp.rank ? resp.rank + '위' : '순위 미상'}</div>` +
    newGameFormHTML() +
    `<div class="actions"><button type="button" id="bNew">새 게임</button></div>`);
  $('#bNew').addEventListener('click', startNew);
}

function showNewGame(msg) {
  $('#mainrow').innerHTML = '<div class="wait">진행 중인 게임 없음</div>';
  closeRaise();
  $('#hero').hidden = true;
  showOverlay(`<h2>t2 포커</h2><div class="sub">${msg || '새 게임을 시작하세요.'}</div>` +
    newGameFormHTML() +
    `<div class="actions"><button type="button" id="bNew">시작</button></div>`);
  $('#bNew').addEventListener('click', startNew);
}

function newGameFormHTML() {
  return `<div class="field">
    <label>엔트리<input id="fEntries" type="number" inputmode="numeric" value="100"></label>
    <label>시드<input id="fSeed" type="number" inputmode="numeric" placeholder="자동"></label>
  </div>
  <div class="field">
    <label>시작 스택<input id="fStack" type="number" inputmode="numeric" value="30000"></label>
  </div>`;
}

function startNew() {
  clearTimeout(S.autoTimer); S.autoTimer = null;
  S.heroSig = null; S.won = false;
  histClear();                       // 핸드 번호가 1부터 다시 시작한다
  const body = {};
  const e = Number($('#fEntries') && $('#fEntries').value);
  const s = $('#fSeed') && $('#fSeed').value;
  const k = Number($('#fStack') && $('#fStack').value);
  if (e) body.entries = e;
  if (s !== '' && s !== null && s !== undefined && !isNaN(Number(s))) body.seed = Number(s);
  if (k) body.start_stack = k;
  S.handNo = null; S.boardLen = 0; S.logLen = 0; S.stage = null;
  call('/api/new', body, '새 게임을 만드는 중…');
}

function showOverlay(html) {
  const o = $('#overlay');
  o.innerHTML = `<div class="sheet">${html}</div>`;
  o.hidden = false;
}
function hideOverlay() { $('#overlay').hidden = true; }

/* ---------------- 기록 보기 ---------------- */
/* ---------------- 토스트 ---------------- */
function toast(msg, ok) {
  const t = $('#toast');
  t.textContent = msg; t.hidden = false;
  t.classList.toggle('ok', !!ok);
  clearTimeout(S.toastTimer);
  S.toastTimer = setTimeout(() => { t.hidden = true; }, 4200);
}

/* ---------------- 로딩 ----------------
 * 핸드를 끝내는 액션은 finish() 안에서 다른 테이블까지 진행한다.
 * 실측으로 엔트리 100 기준 중앙 8.9초, 최대 13.0초였다. 멈춘 것처럼
 * 보이면 안 되므로 경과 시간과 이유를 같이 보여준다. */
function setBusy(on, msg) {
  S.busy = on;
  const box = $('#status');
  document.querySelectorAll('#actionbar button').forEach((b) => { b.disabled = on; });
  clearInterval(S.busyTimer);
  if (!on) { box.hidden = true; return; }
  const t0 = Date.now();
  box.hidden = false;
  box.querySelector('.msg').textContent = msg || '진행 중…';
  box.querySelector('.el').textContent = '';
  box.querySelector('.hint').textContent = '';
  S.busyTimer = setInterval(() => {
    const s = (Date.now() - t0) / 1000;
    if (s >= 1.2) box.querySelector('.el').textContent = s.toFixed(1) + '초';
    if (s >= 4) {
      box.querySelector('.msg').textContent = '핸드 정산 중…';
      box.querySelector('.hint').textContent =
        '다른 테이블도 함께 진행됩니다. 15초 정도 걸릴 수 있습니다.';
    }
  }, 100);
}

/* ---------------- 통신 ---------------- */
async function req(path, body) {
  const init = body
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) }
    : {};
  const res = await fetch(path, init);
  let json = null;
  try { json = await res.json(); } catch (e) { json = null; }
  return { status: res.status, json };
}

async function call(path, body, msg) {
  if (S.busy) {
    // 조용히 무시하면 버튼이 고장난 것처럼 보인다. 실제로 '새 게임 시작이
    // 안 먹는다'는 신고가 여기서 나왔다 — 다른 테이블 정산이 30~50초 걸리는
    // 동안 눌러도 아무 일도 일어나지 않았고 아무 표시도 없었다.
    // (액션바 버튼은 setBusy 가 비활성화하지만 오버레이 시트의 버튼은 아니다.)
    if (path === '/api/new') {
      // 새 게임만 예약해 둔다. 게임 액션을 예약하면 안 된다 — 직전 응답을
      // 보지 못한 채로 다음 액션을 미리 잡아두는 셈이 된다.
      S.queuedNew = { body: body, msg: msg };
      toast('정산이 끝나면 새 게임을 시작합니다');
    } else {
      toast('앞선 요청을 처리하는 중입니다 — 끝나면 다시 눌러 주세요');
    }
    return null;
  }
  setBusy(true, msg);
  try {
    const r = await req(path, body);
    if (r.status === 409) {
      toast((r.json && r.json.error) || '요청이 충돌했습니다 — 화면을 다시 맞춥니다');
      const s = await req('/api/state', null);          // 추정하지 않고 다시 받는다
      if (s.status === 200 && s.json) apply(s.json);
      return null;
    }
    if (r.status !== 200 || !r.json) {
      toast((r.json && r.json.error) || ('서버 오류 ' + r.status));
      return null;
    }
    apply(r.json);
    return r.json;
  } catch (e) {
    toast('연결 실패: ' + e.message);
    return null;
  } finally {
    setBusy(false);
    if (S.queuedNew) {                 // 기다리는 동안 눌러둔 새 게임
      const q = S.queuedNew; S.queuedNew = null;
      clearTimeout(S.autoTimer); S.autoTimer = null;
      call('/api/new', q.body, q.msg);
    }
  }
}

/* 재생이 도는 중이면 히어로 액션을 **예약**한다.
 *
 * 예전에는 바로 보냈고, 그러면 응답이 와서 stopReplay 가 남은 봇 액션 재생을
 * 끊어버렸다 — 앞사람들이 뭘 했는지 못 보고 화면이 건너뛰었다.
 * 이제는 재생이 끝나는 순간(finalFrame)에 보낸다. 화면을 누르면 재생을
 * 건너뛸 수 있으므로, 급하면 두 번 누르면 바로 진행된다.
 *
 * '다음 핸드'(action === null)는 예약하지 않는다. 그건 결과 화면에서 누르는
 * 것이라 재생 중일 수가 없다.
 */
function send(action, amount) {
  if (S.token === null || S.token === undefined) { sync(); return; }
  if (action !== null && S.replayDone) {
    S.queuedAction = { action: action, amount: amount | 0 };
    markQueued(action);
    return;
  }
  call('/api/step', { action, amount: amount | 0, token: S.token },
       action === null ? '다음 핸드 준비 중…' : '진행 중…');
}

function markQueued(action) {
  const row = $('#mainrow');
  if (row) {
    row.innerHTML = '<div class="wait">' + (ACT[action] || action) +
      ' 예약됨 — 앞사람 액션이 끝나면 진행합니다 (화면을 누르면 바로)</div>';
  }
  closeRaise();
}

function flushQueued() {
  if (!S.queuedAction) return false;
  const q = S.queuedAction; S.queuedAction = null;
  call('/api/step', { action: q.action, amount: q.amount, token: S.token },
       '진행 중…');
  return true;
}

function sync() { call('/api/state', null, '상태를 받는 중…'); }

/* ---------------- 응답 반영 ---------------- */
function apply(resp) {
  S.last = resp;
  S.token = resp.token;
  clearTimeout(S.autoTimer); S.autoTimer = null;
  if (resp.no_game) { showNewGame(); return; }
  if (resp.game_over) { showGameOver(resp); return; }
  const v = resp.view;
  if (!v) { showNewGame('상태를 읽지 못했습니다.'); return; }
  S.view = v;
  // 새 응답은 이전 연출을 무효로 만든다. 말풍선은 남겨 둔다 — 그 스트리트에서
  // 누가 뭘 했는지 보여주는 기록이라, 히어로가 액션할 때마다 지울 것이 아니다.
  stopReplay();

  if (v.type === 'result') {
    // 우승 판정. 엔진은 탈락만 신호하므로 남은 인원으로 여기서 가른다.
    // (ui_server._wrap 이 remaining 을 실어 보낸다)
    S.won = (resp.remaining === 1 && !resp.busted);
    S.entries = resp.entries || S.entries;
    // 히어로가 폴드했어도 남은 액션이 있으면 먼저 보여준 뒤 결과를 띄운다
    if (!spectateTail(v)) finishResult(v);
    return;
  }
  S.view0 = v;

  const freshHand = S.handNo !== v.hand_no;
  const streetChanged = !freshHand && S.stage !== v.stage;
  const newLog = (freshHand || streetChanged) ? (v.log || [])
                                              : (v.log || []).slice(S.logLen);
  if (freshHand) { clearBubbles(); resetFolding(); S.boardLen = 0; S.prevBets = null; }

  hideOverlay();
  renderTop(v);
  renderChips(v, streetChanged);     // 스트리트가 끝났으면 칩을 팟으로 보낸다
  renderBoard(v);
  renderActions(v);                  // 버튼은 바로 쓸 수 있다. 재생을 기다리지 않는다
  // 액션 한 줄도 재생이 끝난 뒤에 채운다. 먼저 채우면 '누가 뭘 했는지' 가
  // 연출보다 먼저 글로 나와버린다.
  if (freshHand || streetChanged) {
    $('#logline').innerHTML = '<span class="cur">' +
      (STREET[v.stage] || v.stage) + '</span> —';
  } else renderLogLine(v);
  if (freshHand) {
    // 카드를 다 돌린 뒤에 액션을 재생한다. 액션 버튼은 이미 살아 있으므로
    // 기다리기 싫으면 바로 눌러도 된다 (stopReplay 가 정리한다).
    dealThen(v, () => playSequence(v, newLog, true));
  } else {
    playSequence(v, newLog, streetChanged);
  }

  S.handNo = v.hand_no; S.stage = v.stage; S.logLen = (v.log || []).length;
  if (v.error) toast(v.error);
}

/* ---------------- 시작 ---------------- */
$('#bLog').addEventListener('click', showHistory);
$('#bMenu').addEventListener('click', showMenu);
$('#seats').addEventListener('click', (e) => {
  const b = e.target.closest && e.target.closest('button.memo');
  if (!b) return;
  e.stopPropagation();
  openMemo(b.dataset.pid, b.dataset.label);
});
$('#seats').addEventListener('pointerdown', (e) => {
  if (e.target.closest && e.target.closest('button.memo')) e.stopPropagation();
}, true);
// 기다리기 싫으면 빈 곳을 한 번 누르면 재생을 건너뛴다
$('#tablewrap').addEventListener('pointerdown', () => {
  if (S.replayDone) S.replayDone();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideOverlay();
});
sync();
