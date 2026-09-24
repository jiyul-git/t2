'use strict';
const CLEAN_PATH =
  location.pathname.replace(/\/+$/, '');

const PLAY_PATH =
  CLEAN_PATH === '/play' ||
  CLEAN_PATH.startsWith('/play/');

let URL_PLAY_KEY =
  new URLSearchParams(location.search).get('k') ||
  new URLSearchParams(location.hash.slice(1)).get('k') ||
  '';

if (PLAY_PATH && URL_PLAY_KEY) {
  try {
    localStorage.setItem('t2_play_key', URL_PLAY_KEY);
  } catch (e) {}
}

let SAVED_PLAY_KEY = '';
try {
  SAVED_PLAY_KEY = localStorage.getItem('t2_play_key') || '';
} catch (e) {}

const WATCH_PATH =
  location.pathname.replace(/\/+$/, '') === '/watch';

const WATCH_MODE =
  WATCH_PATH ||
  (!PLAY_PATH && !URL_PLAY_KEY);

const PLAY_KEY =
  WATCH_MODE
    ? ''
    : (URL_PLAY_KEY || SAVED_PLAY_KEY);

/* t2 포커 테이블 UI.
 *
 * 원칙: **마지막 JSON 응답이 유일한 진실이다.**
 * 프론트엔드는 규칙을 다시 계산하지 않는다. 버튼 노출은 legal 만 보고 정하고,
 * 레이즈 범위는 legal.raise.min_to / max_to 를 그대로 쓴다. 최소 레이즈를
 * 여기서 다시 구현하면 엔진과 어긋나는 순간 화면과 서버가 따로 논다.
 * 상태를 추정하지 않으므로, 409 를 받으면 GET /api/state 로 다시 맞춘다.
 */

const $ = (s) => document.querySelector(s);

function profileStorage(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v;
  } catch (e) { return fallback; }
}
function heroProfileAvatar() {
  const n = Number(profileStorage('t2profile_avatar', '0'));
  return Math.max(0, Math.min(8, Number.isFinite(n) ? Math.trunc(n) : 0));
}
function heroProfileNickname() {
  return String(profileStorage('t2profile_nickname', '플레이어') || '플레이어')
    .trim().slice(0, 16) || '플레이어';
}
function applyProfileDeck() {
  const allowed = ['jade', 'navy', 'burgundy', 'ivory'];
  const deck = profileStorage('t2profile_deck', 'jade');
  document.documentElement.dataset.deck =
    allowed.indexOf(deck) >= 0 ? deck : 'jade';
}
applyProfileDeck();

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
  reveal: null,            // 쇼다운 공개 중이면 {좌석: 카드들}
  winners: null,           // 실제 팟 수령 좌석 집합
  awards: null,            // {seat:[{label,split,pot}]} 메인/사이드/스플릿
  bestFive: null,            // 승자의 실제 5장 조합
  won: false,              // 히어로가 대회를 우승했나
  entries: null,           // 총 엔트리 (우승 화면 표시용)
  overlayPinned: false,     // 기록/설정은 사용자가 닫기 전까지 유지
  pendingMoveNote: null,   // 엔진이 알려준 HERO 테이블 이동
  memos: {},                 // pid → 사용자 메모. 서버가 원본, localStorage는 캐시
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
 * 좌석 번호는 테이블 밸런싱으로 사람이 바뀌므로 pid 기준으로 저장한다.
 * 서버 live2_state.json의 hero_memos가 원본이고, 완료 핸드에는 그 핸드에
 * 앉아 있던 pid의 메모 스냅샷이 hand_archive2.jsonl에 함께 들어간다.
 *
 * localStorage는 화면 반응/연결 실패용 캐시일 뿐 원본이 아니다.
 * 메모는 봇 판단 로직에서 읽지 않는다.
 */
const memoKey = (pid) => 't2memo:' + pid;

function memoLocalGet(pid) {
  try { return localStorage.getItem(memoKey(pid)) || ''; }
  catch (e) { return ''; }
}

function memoGet(pid) {
  const k = String(pid);

  if (
    S.memos &&
    Object.prototype.hasOwnProperty.call(S.memos, k)
  ) {
    return S.memos[k] || '';
  }

  return memoLocalGet(pid);
}

function memoLocalSet(pid, txt) {
  try {
    if (txt) localStorage.setItem(memoKey(pid), txt);
    else localStorage.removeItem(memoKey(pid));
  } catch (e) {}
}

async function memoLoad() {
  if (WATCH_MODE) return;

  try {
    const headers = PLAY_KEY
      ? { 'X-T2-Play-Key': PLAY_KEY }
      : {};

    const res = await fetch('/api/memos', {
      cache: 'no-store',
      headers: headers
    });

    if (!res.ok) throw new Error('HTTP ' + res.status);

    const data = await res.json();
    const raw = data && data.memos && typeof data.memos === 'object'
      ? data.memos
      : {};

    S.memos = {};

    Object.keys(raw).forEach((pid) => {
      const txt = String(raw[pid] || '');
      if (!txt) return;
      S.memos[String(pid)] = txt;
      memoLocalSet(pid, txt);
    });

    if (S.view && S.view.type === 'decision') {
      renderSeats(S.view);
    }

  } catch (e) {
    // 서버를 못 읽었을 때만 기존 브라우저 캐시를 그대로 사용한다.
  }
}

function memoSet(pid, txt) {
  if (WATCH_MODE) return;

  const k = String(pid);
  const val = String(txt || '').trim();

  if (val) S.memos[k] = val;
  else delete S.memos[k];

  memoLocalSet(k, val);

  const headers = {
    'Content-Type': 'application/json',
    'X-T2-Client-Mode': WATCH_MODE ? 'watch' : 'play'
  };
  if (PLAY_KEY) headers['X-T2-Play-Key'] = PLAY_KEY;

  fetch('/api/memo', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({
      pid: Number(pid),
      memo: val
    })
  }).then(async (res) => {
    let data = null;
    try { data = await res.json(); } catch (e) {}

    if (!res.ok) {
      throw new Error(
        (data && data.error) || ('HTTP ' + res.status)
      );
    }

    if (data && data.memos && typeof data.memos === 'object') {
      S.memos = Object.assign({}, data.memos);
    }
  }).catch((e) => {
    toast('서버 메모 저장 실패: ' + e.message);
  });
}

function memoClearAll() {
  S.memos = {};

  try {
    const keys = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith('t2memo:')) keys.push(k);
    }
    keys.forEach((k) => localStorage.removeItem(k));
  } catch (e) {}
}
const esc = (t) => String(t).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function openMemo(pid, label) {
  clearTimeout(S.autoTimer); S.autoTimer = null;
  showOverlay(`<h2>${esc(label)} 메모</h2>` +
    `<div class="sub">플레이어 #${esc(pid)} — 자리를 옮겨도 따라갑니다. ` +
    `서버와 핸드 기록에 함께 저장되며 봇 판단에는 쓰이지 않습니다.</div>` +
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

function winFive(seat) {
  return (S.bestFive && S.bestFive[String(seat)]) || [];
}
function isWinCard(seat, code) {
  if (!S.winners || !S.winners[String(seat)]) return false;
  return winFive(seat).indexOf(code) >= 0;
}
function boardWinCard(code) {
  if (!S.winners || !S.bestFive) return false;
  return Object.keys(S.winners).some((s) =>
    S.winners[s] && ((S.bestFive[String(s)] || []).indexOf(code) >= 0));
}

/* ---------------- 좌석 좌표 ----------------
 * 히어로 슬롯이 항상 하단 중앙이 되도록 회전한다. 히어로 자신은 타원 위가
 * 아니라 하단 바(#hero)에 그리므로, 타원에는 나머지 슬롯만 놓인다.
 * 화면 좌표는 y 가 아래로 커진다. 하단(+90도)에서 각도를 줄이면
 * 오른쪽 → 위 → 왼쪽 순서가 되어 포커의 시계방향과 맞는다. */
function slotPos(slot, heroSlot, n, rfx, rfy) {
  const off = (((slot - heroSlot) % n) + n) % n;
  const th = (90 - off * (360 / n)) * Math.PI / 180;
  // Seat centers ride just outside the table rail rather than inside the felt.
  // Chips still pass rfx/rfy < 1, so betting markers remain inside the table.
  return { x: 50 + 42 * rfx * Math.cos(th), y: 44 + 39 * rfy * Math.sin(th) };
}

function sideSeatClass(p) {
  // 8/9-handed layouts have one seat almost exactly at 3 and 9 o'clock.
  // Tag only those near-horizontal seats; diagonals keep the normal layout.
  if (!p || p.y < 34 || p.y > 58) return '';
  if (p.x >= 84) return ' side-right';
  if (p.x <= 16) return ' side-left';
  return '';
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

// First integrated portrait set. Identity follows pid when a player changes seats.
function botAvatarHTML(pid) {
  return PokerVisuals.avatarHTML(pid);
}

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
    // '가운데 → 이 자리' 를 좌석 자신에 심는다. 커스텀 속성은 상속되므로
    // 카드가 var(--dx)/var(--dy) 를 그대로 받는다. 카드마다 style 을 따로
    // 찍지 않아야 딜링 중에 카드 한 장만 DOM 에 끼워 넣을 수 있다.
    const dp = deckAnchor(W, H);
    const dx = Math.round(dp.x - (p.x / 100 * W));
    const dy = Math.round(dp.y - (p.y / 100 * H));   // 44 = slotPos 의 세로 중심
    const style = `left:${p.x}%;top:${p.y}%;--dx:${dx}px;--dy:${dy}px`;
    if (!d) {
      html += `<div class="pod empty" data-slot="${slot}" style="${style}">` +
              `<div class="avatar">·</div><div class="meta">` +
              `<span class="pos">빈자리</span><span class="stack">&nbsp;</span>` +
              `</div></div>`;
      continue;
    }
    const award = awardLabel(slot);
    const cls = 'pod' + sideSeatClass(p) +
                (d.in_hand || S.folding[slot] ? '' : ' folded') +
                (award && !awardSplitOnly(slot) ? ' won' : '');
    // 방금 폴드한 좌석은 카드를 한 번 더 그려서 사라지는 모션을 보여준다
    const nc = dealtCount(slot);
    // 카드마다 자기 시각으로 지연을 계산한다. 한 장씩 들어오므로 두 장의
    // 비행 시점이 다르고, 프레임을 다시 그려도 각자 이어서 난다.
    // (딜링 중 정상 경로는 dealAppend 다. 여기는 딜링 도중 다른 이유로
    //  좌석을 통째로 다시 그리게 됐을 때의 복구용이다.)
    const cards = [];
    for (let ci = 0; ci < nc; ci++) {
      const st0 = S.dealt ? (S.dealt[slot] || [])[ci] : null;
      cards.push(`<div class="card back mini${S.dealt ? ' fly' : ''}"` +
        (st0 ? ` style="animation-delay:${dealDelay(st0)}"` : '') +
        '></div>');
    }
    // 쇼다운 공개 — 뒷면을 앞면으로 뒤집는다. 카드마다 순서대로 지연을 준다.
    const rv = S.reveal ? S.reveal[slot] : null;
    const backs = (rv && rv.length)
      ? `<div class="backs reveal">${rv.map((c, ci) =>
           `<div class="flip" style="animation-delay:${revealDelay(slot, ci)}">` +
           cardHTML(c, 'mini' + (isWinCard(slot, c) ? ' win5' : '')) +
           backHTML('mini') + '</div>').join('')}</div>`
      : (d.in_hand && nc)
      ? `<div class="backs">${cards.join('')}</div>`
      : (S.folding[slot]
         ? `<div class="backs out" style="animation-delay:${foldDelay(S.folding[slot])}">` +
           `${backHTML('mini')}${backHTML('mini')}</div>` : '');
    const memo = (WATCH_MODE || d.pid === undefined || d.pid === null) ? ''
      : `<button type="button" class="memo${memoGet(d.pid) ? ' has' : ''}" ` +
        `data-pid="${d.pid}" data-label="${slot}번(${d.pos || ''})">✎</button>`;
    const botNo =
      (d.pid === undefined || d.pid === null)
        ? '?'
        : d.pid;

    html += `<div class="${cls}" data-slot="${slot}" style="${style}">` + memo +
            backs +
            `<div class="avatar botavatar">${botAvatarHTML(botNo)}</div>` +
            `<div class="seatno">B${esc(botNo)} · S${slot}</div>` +
            (award ? `<div class="winlabel">${esc(award)}</div>` : '') +
            (d.allin ? `<div class="tag">ALL-IN</div>` : '') +
            (v.button_seat === slot ? `<div class="dealer">D</div>` : '') +
            `<div class="meta"><span class="pos">${d.pos || ''}</span>` +
            `<span class="stack">${fmt(d.stack)}</span></div></div>`;
  }
  box.innerHTML = html;
  PokerVisuals.scheduleGaze();
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
    const seatP = slotPos(s.seat, v.hero_seat, n, 1, 1);
    const p = slotPos(s.seat, v.hero_seat, n, 0.43, 0.62);
    const side = sideSeatClass(seatP);
    // 3/9 o'clock chips need to clear the outer board cards, but pushing them
    // down to 59% collides with the lower-diagonal seat's chips. Keep them just
    // below the board lane instead.
    if (side) p.y = Math.max(p.y, 51);
    const el = document.createElement('div');
    el.className = 'chips' + side;
    el.dataset.seat = String(s.seat);
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
    if (i < b.length) {
      const cls = [];
      if (i >= known) cls.push('deal');
      if (boardWinCard(b[i])) cls.push('win5');
      html += cardHTML(b[i], cls.join(' '));
    } else {
      html += cardHTML(null);
    }
  }
  const box = $('#board');
  box.innerHTML = html;
  Array.from(box.querySelectorAll('.card.deal')).forEach((el, i) => {
    el.style.animationDelay = (i * 90) + 'ms';
  });
  S.boardLen = b.length;
}

/* 가운데 팟을 메인/사이드로 나눈다.
 *
 * **완료된 스트리트만 센다.** 실제 딜러도 베팅 라운드가 끝나야 사이드팟을
 * 만든다. 이번 스트리트 투입분은 아직 좌석 앞 칩으로 보이고 있다 —
 * 그게 곧 v.pot_center 의 정의라 숫자가 저절로 맞는다.
 *
 * 서버에 묻지 않는다. 로그의 amount 는 '그 액션 뒤 그 좌석의 이번 스트리트
 * 총 투입액'이라(runner.py:122-126), 스트리트마다 최댓값을 더하면 총 기여가
 * 나온다. 폴드·체크는 amount 0 이라 최댓값을 쓰면 알아서 무시된다.
 *
 * 쪼개는 방식은 session.award_pots 와 같다. 기여액 단계마다 한 칸씩 만들고,
 * 안테 같은 데드머니는 메인에만 얹는다. 그래야 합이 pot_center 와 같다.
 */
function potParts(v) {
  const pc = v.pot_center || 0;
  const live = {};
  (v.seats || []).forEach((x) => { if (x.in_hand) live[x.seat] = 1; });
  const per = {};                       // {스트리트: {좌석: 그 스트리트 투입}}
  (v.prior_log || []).forEach((e) => {
    const k = e.street || '?';
    const m = per[k] || (per[k] = {});
    m[e.seat] = Math.max(m[e.seat] || 0, e.amount || 0);
  });
  const total = {};
  Object.keys(per).forEach((k) => {
    const m = per[k];
    Object.keys(m).forEach((sd) => { total[sd] = (total[sd] || 0) + m[sd]; });
  });
  const vals = Object.keys(total).map((k) => total[k]).filter((x) => x > 0);
  if (!vals.length) return [{ amount: pc, eligible: Object.keys(live).map(Number) }];

  const levels = Array.from(new Set(vals)).sort((a, b) => a - b);
  const parts = [];
  let prev = 0;
  levels.forEach((lv) => {
    const at = Object.keys(total).filter((k) => total[k] >= lv);
    parts.push({ amount: (lv - prev) * at.length,
                 eligible: at.map(Number).filter((x) => live[x]) });
    prev = lv;
  });
  // 안테·데드머니는 재구성에 안 잡힌다. 차액을 메인에 얹어 합을 맞춘다.
  const sum = parts.reduce((a, p) => a + p.amount, 0);
  if (parts.length) parts[0].amount += pc - sum;

  // 자격자가 같은 칸은 한 팟이다. 자격자가 1명 이하인 칸은 겨룰 상대가 없어
  // 따로 세울 이유가 없으므로 앞 칸에 합친다 (합계는 그대로 유지된다).
  const out = [];
  parts.forEach((p) => {
    const key = p.eligible.slice().sort((a, b) => a - b).join(',');
    const last = out.length ? out[out.length - 1] : null;
    if (last && (last._key === key || p.eligible.length <= 1)) {
      last.amount += p.amount;
      return;
    }
    out.push({ _key: key, amount: p.amount, eligible: p.eligible });
  });
  return out;
}

function renderPot(v) {
  $('#pot').textContent = '팟 ' + fmt(v.pot_total);
  const parts = potParts(v);
  if (parts.length > 1) {
    // 올인 때문에 자격이 갈렸다 — 나눠서 보여준다
    $('#potsub').textContent = parts.map((p, i) =>
      (i === 0 ? '메인 ' : '사이드' + i + ' ') + fmt(p.amount)).join(' · ');
    return;
  }
  $('#potsub').textContent = (v.pot_center && v.pot_center !== v.pot_total)
    ? '중앙 ' + fmt(v.pot_center) : '';
}

/* ---------------- 히어로 ---------------- */
const CARD_RANK = {
  '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
  'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
};

function heroCardOrder(cards) {
  return (cards || []).slice(0, 2).sort((a, b) =>
    (CARD_RANK[(b || '')[0]] || 0) -
    (CARD_RANK[(a || '')[0]] || 0));
}

function ensureHeroSlots() {
  const root = $('#herocards');
  if (root.querySelector('.hero-slot')) return;

  root.innerHTML =
    '<div class="hero-slot left"></div>' +
    '<div class="hero-slot right"></div>';
}

function renderHeroSlot(side, code, seat) {
  ensureHeroSlots();

  const slot = $(`#herocards .hero-slot.${side}`);
  if (!slot) return;

  const oldCode = slot.dataset.card || '';
  const win = !!(code && isWinCard(seat, code));
  const oldWin = slot.dataset.win === '1';

  if (!code) {
    if (oldCode) slot.innerHTML = '';
    slot.dataset.card = '';
    slot.dataset.win = '0';
    return;
  }

  // 같은 카드면 DOM을 다시 만들지 않는다.
  if (oldCode === code && oldWin === win) return;

  const isNew = oldCode !== code;
  const cls =
    (isNew ? 'deal' : '') +
    (win ? ' win5' : '');

  slot.innerHTML = cardHTML(code, cls.trim());
  slot.dataset.card = code;
  slot.dataset.win = win ? '1' : '0';
}

function renderHero(v) {
  const me = (v.seats || []).find((x) => x.hero);
  const box = $('#hero');

  box.hidden = false;
  const portrait = $('#heroavatar');
  const portraitId = WATCH_MODE
    ? PokerVisuals.portraitIndex(me ? me.pid : 0)
    : heroProfileAvatar();
  if (portrait.dataset.portraitId !== String(portraitId)) {
    portrait.innerHTML = PokerVisuals.avatarHTML(portraitId);
    portrait.dataset.portraitId = String(portraitId);
  }
  PokerVisuals.scheduleGaze();
  box.classList.toggle('folded', !!me && !me.in_hand);

  const d = v.button_seat === v.hero_seat ? ' · D' : '';
  const award = awardLabel(v.hero_seat);

  const heroName = WATCH_MODE ? '' : heroProfileNickname();
  $('#heroinfo .pos').textContent =
    (heroName ? heroName + (me && me.pos ? ' · ' : '') : '') +
    (me ? (me.pos || '') : '') +
    d +
    (me && me.allin ? ' · ALL-IN' : '') +
    (award ? ' · ' + award : '');

  $('#heroinfo .stack').textContent = me ? fmt(me.stack) : '';

  ensureHeroSlots();

  const nc = dealtCount(v.hero_seat);
  const h = heroCardOrder(v.hero_hole || []);

  const high = h.length >= 2 ? h[0] : null;
  const low  = h.length >= 2 ? h[1] : (h[0] || null);

  // 첫 장: 낮은 카드가 오른쪽 최종 자리로.
  renderHeroSlot('right', nc >= 1 ? low : null, v.hero_seat);

  // 두 번째 장: 높은 카드가 왼쪽으로.
  // 오른쪽 기존 카드는 절대 재생성하지 않는다.
  renderHeroSlot('left', nc >= 2 ? high : null, v.hero_seat);

  S.heroSig = [
    v.hand_no,
    nc,
    high || '',
    low || '',
    award || '-',
    winFive(v.hero_seat).join(',')
  ].join('|');
}

/* ---------------- 쇼다운 공개 ----------------
 * 결과 창을 읽어야 누가 이겼는지 알 수 있던 것을, 테이블에서 바로 보이게 한다.
 * 카드를 한 장씩 뒤집고 이긴 자리를 강조한 뒤에 결과 창을 띄운다.
 *
 * **표시 전용이다.** 서버에 아무것도 묻지 않고, 결과 뷰가 이미 준 shown
 * (쇼다운에 깐 패)만 쓴다. 접은 사람의 패는 애초에 거기 없다.
 */
const REVEAL_STEP = 170;      // 카드 한 장 간격
const REVEAL_ANIM = animMs('--flip-anim', 520);
const REVEAL_HOLD = 900;      // 다 뒤집고 나서 결과 창까지의 여유

function revealDelay(slot, ci) {
  const t0 = S.reveal && S.reveal._t0;
  const n = (S.reveal && S.reveal._order ? S.reveal._order.indexOf(slot) : 0);
  const start = (n < 0 ? 0 : n) * 2 * REVEAL_STEP + ci * REVEAL_STEP;
  // 프레임마다 다시 그려도 이어서 뒤집히게 한다 (딜링·폴드와 같은 이유).
  const el = t0 ? Math.min(start + REVEAL_ANIM, Math.max(0, performance.now() - t0)) : 0;
  return (start - el).toFixed(0) + 'ms';
}

/* 결과 뷰에는 seats 가 없다 (render_result 가 stacks/pos 만 준다).
 * 마지막 decision 뷰를 바탕으로 공개용 프레임을 만든다. */
function revealView(res, finalState) {
  const base =
    S.showdownFrame ||
    S.view0 ||
    S.view;

  if (!base || !base.seats || !base.seats.length) {
    return null;
  }

  const folded = {};
  (res.log || []).forEach((e) => {
    if (e.action === 'fold') {
      folded[e.seat] = 1;
    }
  });

  const st = res.stacks || {};

  const seats = base.seats.map((x) =>
    Object.assign({}, x, {
      // 쇼다운 중에는 이미 베팅이 끝났으므로 칩은 팟으로 들어간 상태.
      bet: 0,
      in_hand: !folded[x.seat],

      // 공개/런아웃 도중에는 지급 후 스택을 쓰지 않는다.
      // 승패가 끝난 최종 화면에서만 서버의 최종 스택을 적용한다.
      stack:
        finalState &&
        st[String(x.seat)] !== undefined
          ? Number(st[String(x.seat)])
          : x.stack,

      allin: false
    })
  );

  const beforeRunout =
    !!res.allin_show && !finalState;

  return Object.assign({}, base, {
    seats: seats,

    stage:
      beforeRunout
        ? base.stage
        : 'river',

    board:
      beforeRunout
        ? (base.board || [])
        : (res.board || []),

    log: res.log || base.log || [],

    pot_center: res.pot || 0,
    pot_total: res.pot || 0
  });
}

/* 쇼다운이면 공개 연출을 하고 done() 을 부른다. 아니면 바로 done(). */
function revealShowdown(res, done) {
  const epoch = S.epoch || 0;
  const shown = res.shown || {};

  const serverOrder = (res.show_order || []).map(Number);

  let order = serverOrder.filter((s) =>
    (shown[String(s)] || []).length &&
    String(s) !== String(res.hero_seat)
  );

  // 구버전 결과에 show_order가 없을 때만 fallback.
  if (!order.length) {
    order = Object.keys(shown)
      .map(Number)
      .filter((s) =>
        (shown[String(s)] || []).length &&
        String(s) !== String(res.hero_seat)
      );
  }

  const fv =
    res.showdown && order.length
      ? revealView(res, false)
      : null;

  /*
   * 상대 공개 카드가 하나도 없어도 올인 쇼다운에서는
   * HERO 카드는 이미 하단에 보이고 있으므로 곧바로 다음 단계로 간다.
   */
  if (!fv) {
    done();
    return;
  }

  S.reveal = {
    _t0: performance.now(),
    _order: order
  };

  order.forEach((s) => {
    S.reveal[s] = shown[String(s)];
  });

  // 중요: 아직 승자를 표시하지 않는다.
  S.winners = null;
  S.awards = null;
  S.bestFive = null;

  $('#mainrow').innerHTML =
    '<div class="wait">쇼다운</div>';

  closeRaise();

  renderSeats(fv);
  renderChips(fv, false);
  renderBoard(fv);
  renderPot(fv);
  renderHero(fv);

  // revealView의 임의 stage가 아니라 실제 마지막 액션 street.
  renderLogLine(res);

  let ended = false;

  const finish = () => {
    if (ended || !epochAlive(epoch)) return;

    ended = true;
    S.replayDone = null;
    done();
  };

  S.replayDone = finish;

  const total =
    (order.length * 2 - 1) * REVEAL_STEP +
    REVEAL_ANIM +
    REVEAL_HOLD;

  epochTimer(finish, Math.max(0, total), epoch);
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
const dealMs = () => Math.round(paceMs({ action:'fold' }) / 3);
const FORCED_POST_MS = 500;  // SB/BB/ante 표시 간격

/* 모션 길이는 style.css 의 :root 에서 읽는다. 같은 숫자를 두 곳에 적어두면
 * 한쪽만 고쳐진다 — 실제로 CSS 를 .24s 에서 .5s 로 늘리면서 여기 240 을
 * 그대로 둬서, 이미 받은 카드가 매 프레임 '남은 52%' 를 다시 날았다.
 * (renderSeats 가 프레임마다 카드를 새로 만들기 때문에, 음수 지연이
 *  애니메이션 길이보다 짧으면 그만큼 다시 재생된다.) */
function animMs(name, fallback) {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name);
    const n = parseFloat(v);
    if (!isNaN(n)) return /\ds\s*$/.test(v.trim()) ? n * 1000 : n;
  } catch (e) { /* 못 읽으면 기본값 */ }
  return fallback;
}
const DEAL_ANIM = animMs('--deal-anim', 500);
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

/* 딜링 중에는 좌석을 통째로 다시 그리지 않는다.
 *
 * #seats 를 innerHTML 로 다시 만들면 날고 있는 카드가 전부 지워졌다 새로
 * 생긴다. 음수 지연으로 진행률은 맞출 수 있어도, 250ms 마다 좌석 7개분
 * 레이아웃이 다시 잡히는 것까지는 못 없앤다 — 그게 '살짝 끊기는' 느낌이다.
 * 새로 받은 카드 한 장만 끼워 넣으면 나머지 카드는 건드려지지 않는다.
 *
 * 붙이는 위치는 화면에 영향이 없다. .backs 는 z-index 0, .avatar 는 1,
 * .memo 는 3 으로 전부 정해져 있어서 DOM 순서로 겹침이 정해지지 않는다.
 */
function dealAppend(slot) {
  const pod = $(`#seats .pod[data-slot="${slot}"]`);
  if (!pod || pod.classList.contains('empty')) return false;
  let backs = pod.querySelector('.backs');
  if (!backs) {
    backs = document.createElement('div');
    backs.className = 'backs';
    pod.appendChild(backs);
  }
  const c = document.createElement('div');
  // 지금 만들어졌으니 지연이 필요 없다. 처음부터 날면 된다.
  c.className = 'card back mini fly';
  backs.appendChild(c);
  return true;
}

function blindSeat(v, kind) {
  const seats = v.seats || [];
  let s = seats.find((x) =>
    String(x.pos || '').split('/').indexOf(kind) >= 0 ||
    String(x.pos || '').indexOf(kind) >= 0
  );

  // 헤즈업에서 BTN/SB 표기가 따로인 경우의 안전망.
  if (!s && kind === 'SB' && seats.length === 2) {
    s = seats.find((x) =>
      String(x.seat) === String(v.button_seat)
    );
  }

  if (!s && kind === 'BB' && seats.length === 2) {
    s = seats.find((x) =>
      String(x.seat) !== String(v.button_seat)
    );
  }

  return s || null;
}

function blindAmount(v, seatObj, kind) {
  if (!seatObj) return 0;

  const nominal = Number(
    ((v.level || {})[kind === 'SB' ? 'sb' : 'bb']) || 0
  );

  // 현재 street 시작 시 사용 가능했던 칩.
  // short-stack 자동 올인이면 nominal보다 작을 수 있다.
  const available =
    Number(seatObj.stack || 0) +
    Number(seatObj.bet || 0);

  return Math.max(0, Math.min(nominal, available));
}

function forcedStartState(v) {
  /*
   * 서버의 decision 화면은 이미 블라인드/안테와
   * 앞선 봇 액션이 적용된 상태다.
   *
   * frameView(... bet=0)으로 이번 스트리트의
   * 모든 일반 투입분을 스택으로 되돌린다.
   */
  const zero = {};
  (v.seats || []).forEach((s) => {
    zero[s.seat] = 0;
  });

  const fv0 = frameView(v, zero, {});
  const bb = blindSeat(v, 'BB');

  /*
   * BB ante는 seat.bet이 아니라 dead money라
   * frameView가 되돌려주지 못한다.
   */
  const ante =
    Math.max(
      0,
      Math.min(
        Number((v.level || {}).ante || 0),
        Number(v.pot_center || 0)
      )
    );

  const seats = (fv0.seats || []).map((s) => {
    let stack = Number(s.stack || 0);

    if (
      bb &&
      String(s.seat) === String(bb.seat) &&
      ante > 0
    ) {
      stack += ante;
    }

    return Object.assign({}, s, {
      stack: stack,
      bet: 0,
      in_hand: true,
      allin: false
    });
  });

  return {
    base: Object.assign({}, fv0, {
      seats: seats,
      pot_center: 0,
      pot_total: 0
    }),

    state: {
      seats: seats.map((x) => Object.assign({}, x)),
      potCenter: 0,
      stage: 'preflop',
      boardShown: 0
    },

    ante: ante
  };
}


function renderForced(base, ss) {
  const bets =
    ss.seats.reduce(
      (a, x) => a + Number(x.bet || 0),
      0
    );

  const fv = Object.assign({}, base, {
    seats: ss.seats,
    stage: 'preflop',
    board: [],
    pot_center: ss.potCenter,
    pot_total: ss.potCenter + bets
  });

  renderSeats(fv);
  renderChips(fv, false);
  renderPot(fv);
  renderHero(fv);

  return fv;
}


function makeAnteChip(v, seat, amount) {
  const box = $('#chips');
  if (!box || !amount) return null;

  const n = v.n_slots || 8;
  const p =
    slotPos(
      seat,
      v.hero_seat,
      n,
      0.43,
      0.62
    );

  const el =
    document.createElement('div');

  /*
   * 일반 벳과 완전히 같은 .chips / .disc를 쓴다.
   * 별도 scale/translate 애니메이션 없음.
   */
  el.className = 'chips forced-ante';
  el.style.left = p.x + '%';
  el.style.top = p.y + '%';

  el.innerHTML =
    `<span class="disc"></span>${fmt(amount)}`;

  box.appendChild(el);

  return el;
}


function postBlindsThen(v, done, epoch) {
  if (!epochAlive(epoch)) return;

  const sb = blindSeat(v, 'SB');
  const bb = blindSeat(v, 'BB');

  const fs = forcedStartState(v);
  const base = fs.base;
  const ss = fs.state;
  const anteAmt = fs.ante;

  const sbAmt =
    blindAmount(v, sb, 'SB');

  const bbAmt =
    blindAmount(v, bb, 'BB');


  const finish = () => {
    if (!epochAlive(epoch)) return;
    done();
  };


  const postAnte = () => {
    if (!epochAlive(epoch)) return;

    if (!bb || anteAmt <= 0) {
      finish();
      return;
    }

    const st =
      ss.seats.find(
        (x) =>
          String(x.seat) ===
          String(bb.seat)
      );

    if (!st) {
      finish();
      return;
    }

    /*
     * 일반 bet처럼:
     *   스택 감소
     *   -> 좌석 앞 칩 표시
     *
     * ante는 callable bet이 아니므로
     * st.bet에는 넣지 않는다.
     */
    const paid =
      Math.min(
        anteAmt,
        Number(st.stack || 0)
      );

    st.stack =
      Math.max(
        0,
        Number(st.stack || 0) - paid
      );

    if (st.stack <= 0) {
      st.allin = true;
    }

    const fv = renderForced(base, ss);

    const chip =
      makeAnteChip(
        fv,
        bb.seat,
        paid
      );

    if (!chip) {
      ss.potCenter += paid;
      renderForced(base, ss);
      finish();
      return;
    }

    /*
     * 평소 BET과 동일하게 좌석 앞 칩을 유지한다.
     * 별도의 70ms -> 중앙 이동 모션은 사용하지 않는다.
     */
    epochTimer(() => {
      if (!epochAlive(epoch)) return;

      ss.potCenter += paid;

      try {
        chip.remove();
      } catch (e) {}

      renderForced(base, ss);
      finish();

    }, FORCED_POST_MS, epoch);
  };


  const postBB = () => {
    if (!epochAlive(epoch)) return;

    if (!bb || bbAmt <= 0) {
      postAnte();
      return;
    }

    /*
     * 일반 액션 재생과 같은 applyEntry를 실제로 재사용한다.
     */
    applyEntry(ss, {
      street: 'preflop',
      seat: bb.seat,
      action: 'bet',
      amount: bbAmt
    });

    renderForced(base, ss);

    epochTimer(
      postAnte,
      FORCED_POST_MS,
      epoch
    );
  };


  const postSB = () => {
    if (!epochAlive(epoch)) return;

    if (!sb || sbAmt <= 0) {
      postBB();
      return;
    }

    applyEntry(ss, {
      street: 'preflop',
      seat: sb.seat,
      action: 'bet',
      amount: sbAmt
    });

    renderForced(base, ss);

    epochTimer(
      postBB,
      FORCED_POST_MS,
      epoch
    );
  };


  /*
   * 카드 딜
   * -> 덱 제거
   * -> SB
   * -> BB
   * -> BB ante
   * -> 실제 프리플랍 액션
   */
  renderForced(base, ss);
  postSB();
}

function dealThen(v, done) {
  const epoch = S.epoch || 0;
  const order = dealOrder(v);
  const gap = dealMs();

  if (!order.length) {
    S.dealt = null;
    deckHide(true);
    postBlindsThen(v, done, epoch);
    return;
  }

  /*
   * 카드 딜링 동안은 아직 SB/BB가 칩을 내기 전 화면으로 보인다.
   * 서버 값에는 블라인드가 이미 들어가 있지만 frameView를 bet=0으로
   * 되감아 시각적으로만 게시 전 상태를 만든다.
   */
  const noBets = {};
  (v.seats || []).forEach((s) => {
    noBets[s.seat] = 0;
  });

  const fv0 = frameView(v, noBets, {});

  const draw0 = () => {
    if (!epochAlive(epoch)) return;
    renderSeats(fv0);
    renderChips(fv0, false);
    renderPot(fv0);
    renderHero(fv0);
  };

  const seq = order.concat(order);

  S.dealt = {};
  draw0();
  deckShow();

  let i = 0;
  let ended = false;

  const afterBlinds = () => {
    if (!epochAlive(epoch) || ended) return;

    ended = true;
    S.replayDone = null;

    // 프리플랍 실제 액션 재생은 SB/BB 게시가 끝난 뒤에만 시작.
    done();
  };

  const finishCards = () => {
    if (!epochAlive(epoch) || ended) return;

    S.dealt = null;

    // 마지막 카드 비행이 끝난 뒤 중앙 덱을 먼저 치운다.
    deckHide(true);

    // 그 다음 SB -> BB 순서로 각각 1.3초.
    postBlindsThen(v, afterBlinds, epoch);
  };

  S.replayDone = afterBlinds;

  const next = () => {
    if (!epochAlive(epoch) || ended) return;

    if (i >= seq.length) {
      // 마지막 카드도 비행 애니메이션을 끝까지 보여준다.
      const remain = Math.max(
        0,
        DEAL_ANIM - gap
      ) + 40;

      epochTimer(finishCards, remain, epoch);
      return;
    }

    const slot = seq[i++];

    (S.dealt[slot] = S.dealt[slot] || []).push(
      Math.max(1, performance.now())
    );

    if (slot === fv0.hero_seat) {
      renderHero(fv0);
    } else if (!dealAppend(slot)) {
      draw0();
    }

    epochTimer(next, gap, epoch);
  };

  epochTimer(next, SHUFFLE_MS, epoch);
}

/* ---------------- 가운데 덱 ----------------
 * 카드가 허공에서 생기는 대신, 가운데 덱에서 한 장씩 날아가게 한다.
 * 덱은 표시 전용 엘리먼트다 — 상태도 엔진도 건드리지 않는다.
 */
function deckAnchor(fallbackW, fallbackH) {
  const table = $('#tablewrap');
  const potline = $('#potline');

  if (table && potline) {
    const tr = table.getBoundingClientRect();
    const pr = potline.getBoundingClientRect();

    if (tr.width > 0 && tr.height > 0 &&
        pr.width > 0 && pr.height > 0) {
      return {
        x: (pr.left + pr.right) / 2 - tr.left,

        // POT + 보조문구 전체의 하단에서 충분히 떨어뜨린다.
        // 덱 높이 31px의 중심 좌표.
        y: pr.bottom - tr.top + 40
      };
    }
  }

  return {
    x: (fallbackW || 0) / 2,
    y: (fallbackH || 0) * 0.62
  };
}

function positionDeck() {
  const d = $('#deck');
  const table = $('#tablewrap');

  if (!d || !table) return;

  const tr = table.getBoundingClientRect();
  const p = deckAnchor(tr.width, tr.height);

  d.style.left = p.x + 'px';
  d.style.top = p.y + 'px';
}

function deckShow() {
  const d = $('#deck');
  if (!d) return;

  // 고정 %가 아니라 현재 POT 표시의 실제 화면 위치를 기준으로 잡는다.
  positionDeck();

  // 새 핸드 셔플이 실제로 시작됐으므로 이제 일반 deckHide를 허용한다.
  S.keepDeck = false;

  d.innerHTML = backHTML('mini') + backHTML('mini') + backHTML('mini');
  d.hidden = false;
  d.classList.remove('shuffle');
  void d.offsetWidth;              // 애니메이션 재시작
  d.classList.add('shuffle');
}
function deckHide(force) {
  const d = $('#deck');
  if (!d) return;

  // 결과 카드 수거가 끝난 뒤 다음 핸드 셔플 전까지는
  // 중앙 덱을 화면에서 유지한다.
  if (S.keepDeck && !force) return;

  d.hidden = true;
  d.classList.remove('shuffle');
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
function epochAlive(epoch) {
  return (S.epoch || 0) === epoch;
}

function epochTimer(fn, ms, epoch) {
  const id = setTimeout(() => {
    if (!epochAlive(epoch)) return;
    fn();
  }, ms);
  S.timers.push(id);
  return id;
}

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
  return (
    e.action === 'bet' ||
    e.action === 'raise' ||
    e.action === 'allin'
  ) && e.amount
    ? `${t} ${fmt(e.amount)}`
    : t;
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
const FOLD_ANIM = animMs('--fold-anim', 550);
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

/* 이 프레임 시점의 뷰를 만든다. 그리지는 않는다 —
 * 딜링은 프레임이 내내 같아서 한 번만 만들어 재사용한다. */
function frameView(v, bets, folded) {
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
  return Object.assign({}, v, { seats: seats,
                                pot_total: (v.pot_center || 0) + sum });
}

function drawFrame(v, bets, folded) {
  const fv = frameView(v, bets, folded);
  renderSeats(fv); renderChips(fv, false); renderPot(fv); renderHero(fv);
}

function finalFrame(v) {
  renderActions(v);
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

function fullActionLog(v) {
  if (!v) return [];

  // result.log는 핸드 전체 로그.
  if (v.type === 'result') {
    return (v.log || []).slice();
  }

  // decision은 완료된 street + 현재 street를 연결.
  const prior = (v.prior_log || []).slice();

  const current = (v.log || []).map((e) =>
    Object.assign({}, e, {
      street: e.street || v.stage
    })
  );

  return prior.concat(current);
}

function actualLastStreet(v) {
  const log = fullActionLog(v);

  // result의 v.stage를 믿지 않고 실제 마지막 액션의 street를 사용.
  for (let i = log.length - 1; i >= 0; i--) {
    if (log[i] && log[i].street) {
      return log[i].street;
    }
  }

  return v && v.stage ? v.stage : 'preflop';
}

function actionIdentity(e) {
  if (!e) return '';

  return [
    String(e.street || ''),
    String(e.seat === undefined ? '' : e.seat),
    String(e.action || ''),
    String(Number(e.amount || 0))
  ].join('|');
}

function unseenActionTail(prev, next) {
  const before = fullActionLog(prev);
  const after = fullActionLog(next);

  /*
   * 서버가 street 전환 때 log -> prior_log로 옮기거나
   * 배열 구성을 다시 만들어도 길이 자체는 믿지 않는다.
   *
   * 이전 화면 로그의 suffix와 새 로그의 prefix가
   * 실제 액션 내용으로 일치하는 가장 긴 구간을 찾는다.
   */
  const max = Math.min(before.length, after.length);
  let overlap = 0;

  outer:
  for (let k = max; k >= 0; k--) {
    for (let i = 0; i < k; i++) {
      const a = before[before.length - k + i];
      const b = after[i];

      if (actionIdentity(a) !== actionIdentity(b)) {
        continue outer;
      }
    }

    overlap = k;
    break;
  }

  return after.slice(overlap);
}

function playDecisionTail(prev, v) {
  if (!prev ||
      prev.type !== 'decision' ||
      prev.hand_no !== v.hand_no) {
    return false;
  }

  const tail = unseenActionTail(prev, v);

  const ss = {
    seats: (prev.seats || []).map((x) => Object.assign({}, x)),
    potCenter: prev.pot_center || 0,
    stage: prev.stage,
    boardShown: (prev.board || []).length
  };

  function currentView() {
    const bets = ss.seats.reduce(
      (a, x) => a + (x.bet || 0),
      0
    );

    return Object.assign({}, v, {
      seats: ss.seats,
      stage: ss.stage,
      board: (v.board || []).slice(0, ss.boardShown),
      pot_center: ss.potCenter,
      pot_total: ss.potCenter + bets
    });
  }

  function renderCurrent(streetChanged) {
    const fv = currentView();

    renderSeats(fv);
    renderChips(fv, !!streetChanged);
    renderBoard(fv);
    renderPot(fv);
    renderHero(fv);
  }

  function enterStreet(street) {
    if (!street || street === ss.stage) return;

    /*
     * 반드시 이전 street 액션을 전부 본 뒤:
     * 1. 테이블 위 칩을 pot으로 넣고
     * 2. bet을 0으로 만들고
     * 3. 새 board를 공개한다.
     */
    ss.potCenter += ss.seats.reduce(
      (a, x) => a + (x.bet || 0),
      0
    );

    ss.seats.forEach((x) => {
      x.bet = 0;
    });

    ss.stage = street;

    if (BOARD_AT[street] !== undefined) {
      ss.boardShown = BOARD_AT[street];
    }

    renderCurrent(true);

    $('#logline').innerHTML =
      '<span class="cur">' +
      (STREET[ss.stage] || ss.stage) +
      '</span> —';
  }

  let i = 0;
  let finished = false;

  const finish = () => {
    if (finished) return;
    finished = true;
    finalFrame(v);
  };

  S.replayDone = finish;

  const playEntry = (e) => {
    const mine = e.seat === v.hero_seat;

    if (e.action === 'fold' && !mine) {
      markFold(e.seat);
    }

    applyEntry(ss, e);

    /*
     * 히어로 액션은 클릭 순간 previewHeroAction()에서 이미 보여줬다.
     * 서버가 확정한 값만 내부 상태에 적용하고 기다리지 않는다.
     */
    if (mine) {
      S.timers.push(setTimeout(next, 0));
      return;
    }

    // 봇 액션은 하나도 생략하지 않고 화면에 그린다.
    renderCurrent(false);
    bubbleAt(e.seat, e);

    S.timers.push(
      setTimeout(next, paceMs(e))
    );
  };

  const next = () => {
    if (i >= tail.length) {
      /*
       * 새 street의 첫 액션이 HERO라 로그에 새 액션이 없어도
       * 여기서만 board를 연다.
       */
      if (ss.stage !== v.stage) {
        enterStreet(v.stage);
        S.timers.push(setTimeout(finish, 360));
      } else {
        finish();
      }

      return;
    }

    const e = tail[i++];
    const targetStreet = e.street || ss.stage;

    if (targetStreet !== ss.stage) {
      enterStreet(targetStreet);

      // 보드를 먼저 확인한 뒤 해당 street 첫 액션.
      S.timers.push(
        setTimeout(() => playEntry(e), 360)
      );

      return;
    }

    playEntry(e);
  };

  next();
  return true;
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

  if (!base ||
      base.type !== 'decision' ||
      base.hand_no !== res.hand_no) {
    return false;
  }

  const tail = unseenActionTail(base, res);

  if (!tail.length) {
    return false;
  }

  const ss = {
    seats: (base.seats || []).map((x) => Object.assign({}, x)),
    potCenter: base.pot_center || 0,
    stage: base.stage,
    boardShown: (base.board || []).length
  };

  const full = fullActionLog(res);

  const mine = full.filter(
    (e) => e.seat === res.hero_seat
  );

  S.spectating =
    mine.length > 0 &&
    mine[mine.length - 1].action === 'fold';

  /*
   * 내가 폴드한 뒤라면 관전 중이라는 정보만 남긴다.
   * 내가 살아 있는데 상대 폴드로 끝나는 경우에는
   * '진행 중…'으로 액션바를 덮지 않는다.
   */
  if (S.spectating) {
    $('#mainrow').innerHTML =
      '<div class="wait">관전 중…</div>';
  }

  closeRaise();
  clearBubbles();

  function currentView() {
    const bets = ss.seats.reduce(
      (a, x) => a + (x.bet || 0),
      0
    );

    return Object.assign({}, base, {
      seats: ss.seats,
      stage: ss.stage,
      board: (res.board || []).slice(0, ss.boardShown),
      pot_center: ss.potCenter,
      pot_total: ss.potCenter + bets
    });
  }

  function renderCurrent(streetChanged) {
    const fv = currentView();

    renderSeats(fv);
    renderChips(fv, !!streetChanged);
    renderBoard(fv);
    renderPot(fv);
    renderHero(fv);

    $('#logline').innerHTML =
      '<span class="cur">' +
      (STREET[ss.stage] || ss.stage) +
      '</span>' +
      (S.spectating ? ' 관전 중' : '');
  }

  function enterStreet(street) {
    if (!street || street === ss.stage) return;

    ss.potCenter += ss.seats.reduce(
      (a, x) => a + (x.bet || 0),
      0
    );

    ss.seats.forEach((x) => {
      x.bet = 0;
    });

    ss.stage = street;

    if (BOARD_AT[street] !== undefined) {
      ss.boardShown = BOARD_AT[street];
    }

    renderCurrent(true);
  }

  let i = 0;
  let finished = false;

  const finish = () => {
    if (finished) return;
    finished = true;

    // 쇼다운 공개 때 서버의 '팟 지급 후 스택'을 먼저 보여주면
    // 보드가 나오기도 전에 승자를 스택으로 알 수 있다.
    // 마지막 액션 직후, 팟 지급 전 프레임을 따로 보관한다.
    S.showdownFrame = currentView();

    finishResult(res);
  };

  S.replayDone = finish;

  const playEntry = (e) => {
    const mine = e.seat === res.hero_seat;

    if (e.action === 'fold' && !mine) {
      markFold(e.seat);
    }

    applyEntry(ss, e);

    if (mine) {
      S.timers.push(setTimeout(next, 0));
      return;
    }

    renderCurrent(false);
    bubbleAt(e.seat, e);

    S.timers.push(
      setTimeout(next, paceMs(e))
    );
  };

  const next = () => {
    if (i >= tail.length) {
      finish();
      return;
    }

    const e = tail[i++];
    const targetStreet = e.street || ss.stage;

    if (targetStreet !== ss.stage) {
      enterStreet(targetStreet);

      S.timers.push(
        setTimeout(() => playEntry(e), 360)
      );

      return;
    }

    playEntry(e);
  };

  next();
  return true;
}

/* ---------------- 액션 로그 한 줄 ---------------- */
function renderLogLine(v) {
  const all = fullActionLog(v);
  const stage = actualLastStreet(v);

  const hasStreet =
    all.some((e) => e && e.street);

  const rows = hasStreet
    ? all.filter((e) =>
        !e.street || e.street === stage)
    : (v.log || []);

  const txt = rows.map((e) => {
    const who =
      e.seat === v.hero_seat
        ? '나'
        : (e.seat + '번');

    return who + ' ' + actionText(e);
  }).join(' → ');

  $('#logline').innerHTML =
    '<span class="cur">' +
    (STREET[stage] || stage) +
    '</span> ' +
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

  if (WATCH_MODE) {
    const row = $('#mainrow');
    row.hidden = false;
    row.innerHTML = '<div class="wait">관전 중…</div>';
    return;
  }
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

  const confirm = () => {
    closeRaise();
    // 상한이면 'allin' 으로 보낸다. 엔진이 스스로 올인 목표를 계산하므로
    // 반올림 때문에 1칩이 어긋날 일이 없다.
    if (cur >= rz.max_to) send('allin', 0);
    else send(rz.kind, cur);
  };
  $('#rok').onclick = confirm;
  // 금액 칸에서 엔터 = 확인. onblur 를 기다리면 값이 확정되기 전에 나가므로
  // 여기서 먼저 확정한다. 패널은 confirm 이 닫는다.
  $('#rnum').onkeydown = (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    set(Number($('#rnum').value) || rz.min_to);
    confirm();
  };
  $('#rcancel').onclick = closeRaise;
  set(rz.min_to);
}
function closeRaise() { $('#raisepanel').hidden = true; $('#mainrow').hidden = false; }

function tableMoveNote(v) {
  return ((v && v.notes) || []).find((n) =>
    String(n || '').indexOf('자리 이동') >= 0
  ) || null;
}

function showTableMove(note, seat, done) {
  clearTimeout(S.autoTimer);
  S.autoTimer = null;

  const clean =
    String(note || '테이블이 변경되었습니다.')
      .replace(/^🔄\s*/, '');

  const seatText =
    (seat !== null && seat !== undefined)
      ? `<div class="sub" style="margin-top:8px">새 좌석 S${seat}</div>`
      : '';

  showOverlay(
    `<h2>테이블 이동</h2>` +
    `<div class="sub">${esc(clean)}</div>` +
    seatText +
    `<div class="actions">` +
    `<button type="button" id="bMoveOk">확인</button>` +
    `</div>`
  );

  $('#bMoveOk').addEventListener('click', () => {
    hideOverlay();
    if (done) done();
  });
}

/* ---------------- 결과 / 종료 화면 ---------------- */
function seatName(v, s) {
  const p = (v.pos || {})[String(s)];
  const me = String(s) === String(v.hero_seat);
  return (me ? '나' : s + '번') + (p ? `(${p})` : '');
}

const RUNOUT_HOLD = 2000;
const RESULT_HOLD = 2000;

const COLLECT_MS = 430;

function collectCards(done) {
  const epoch = S.epoch || 0;
  const deck = $('#deck');

  const safeDone = () => {
    if (!epochAlive(epoch)) return;
    done();
  };

  if (!deck) {
    safeDone();
    return;
  }

  S.keepDeck = true;

  deck.innerHTML =
    backHTML('mini') +
    backHTML('mini') +
    backHTML('mini');

  positionDeck();

  deck.hidden = false;
  deck.classList.remove('shuffle');

  const dr = deck.getBoundingClientRect();
  const targetX = dr.left + dr.width / 2;
  const targetY = dr.top + dr.height / 2;

  const cards = Array.from(
    document.querySelectorAll(
      '#herocards .card, #seats .backs .card, #board .card:not(.slot)'
    )
  ).filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });

  if (!cards.length) {
    epochTimer(safeDone, 70, epoch);
    return;
  }

  cards.forEach((el, i) => {
    const r = el.getBoundingClientRect();

    const dx =
      targetX - (r.left + r.width / 2);

    const dy =
      targetY - (r.top + r.height / 2);

    el.animate([
      {
        translate: '0px 0px',
        scale: '1',
        opacity: 1
      },
      {
        translate: `${dx}px ${dy}px`,
        scale: '.25',
        opacity: 0
      }
    ], {
      duration: COLLECT_MS,
      delay: Math.min(i * 10, 80),
      easing: 'cubic-bezier(.45,.05,.75,.25)',
      fill: 'forwards'
    });
  });

  epochTimer(
    safeDone,
    COLLECT_MS + 110,
    epoch
  );
}

function runoutThen(res, done) {
  const epoch = S.epoch || 0;

  if (!res.showdown || !(res.board || []).length) {
    done();
    return;
  }

  const fv = revealView(res, false);

  if (!fv) {
    done();
    return;
  }

  const target =
    Math.min(5, (res.board || []).length);

  let shown = Math.min(
    target,
    S.boardLen ||
      ((S.showdownFrame && S.showdownFrame.board) || []).length ||
      ((S.view0 && S.view0.board) || []).length
  );

  const seq = [];

  if (shown < 3 && target >= 3) seq.push(3);
  if (shown < 4 && target >= 4) seq.push(4);
  if (shown < 5 && target >= 5) seq.push(5);

  if (!seq.length) {
    done();
    return;
  }

  let i = 0;

  const showNext = () => {
    if (!epochAlive(epoch)) return;

    const n = seq[i++];

    const v2 = Object.assign({}, fv, {
      board: (res.board || []).slice(0, n)
    });

    renderSeats(v2);
    renderChips(v2, false);
    renderBoard(v2);
    renderPot(v2);
    renderHero(v2);

    // 홀카드는 S.reveal에 남아 있으므로 열린 채로 보드가 진행된다.
    $('#mainrow').innerHTML =
      '<div class="wait">쇼다운</div>';

    if (i >= seq.length) {
      epochTimer(done, RUNOUT_HOLD, epoch);
    } else {
      epochTimer(showNext, RUNOUT_HOLD, epoch);
    }
  };

  if (shown === 0) {
    showNext();
  } else {
    epochTimer(showNext, RUNOUT_HOLD, epoch);
  }
}

function finishResult(v) {
  clearBubbles();
  histPush(v);

  // 보드/홀카드 공개 완료 전에는 결과를 스포일러하지 않는다.
  S.winners = null;
  S.awards = null;
  S.bestFive = null;

  const showWinner = () => {
    S.awards = potAwards(v);
    S.winners = {};

    Object.keys(S.awards || {}).forEach((s) => {
      S.winners[String(s)] = 1;
    });

    S.bestFive = v.best_five || {};

    finishResult2(v);
  };

  if (v.allin_show) {
    // 올인콜 -> 홀카드 공개 -> 보드 런아웃 -> 팟별 결과 표시
    revealShowdown(
      v,
      () => runoutThen(v, showWinner)
    );
  } else {
    runoutThen(
      v,
      () => revealShowdown(v, showWinner)
    );
  }
}

function finishResult2(v) {
  const epoch = S.epoch || 0;

  renderResult(v);

  const amap = potAwards(v);
  const heroAward =
    awardLabelFor(amap, v.hero_seat);

  const afterHold = () => {
    if (!epochAlive(epoch)) return;

    if (WATCH_MODE) {
      $('#mainrow').innerHTML =
        '<div class="wait">다음 핸드 대기 중…</div>';
      return;
    }

    if (S.pendingMoveNote) {
      const note = S.pendingMoveNote;
      S.pendingMoveNote = null;

      showTableMove(
        note,
        null,
        afterHold
      );
      return;
    }

    if (S.won) {
      showWin(v);
      return;
    }

    if (!autoOn()) {
      $('#mainrow').innerHTML =
        '<button type="button" id="bDeal">다음 핸드</button>';

      $('#bDeal').addEventListener('click', () => {
        if (!epochAlive(epoch)) return;

        clearTimeout(S.autoTimer);
        S.autoTimer = null;

        collectCards(() => send(null, 0));
      });

      return;
    }

    const waitReady = async () => {
      if (!epochAlive(epoch)) return;

      let working = false;

      try {
        const r = await fetch('/api/ready');
        working = !!(await r.json()).working;
      } catch (e) {}

      if (!epochAlive(epoch)) return;

      if (working) {
        $('#mainrow').innerHTML =
          '<div class="wait">다른 테이블 정산 중…</div>';

        S.autoTimer =
          setTimeout(waitReady, 500);

        return;
      }

      S.autoTimer = null;

      collectCards(() => {
        if (!epochAlive(epoch)) return;
        send(null, 0);
      });
    };

    waitReady();
  };

  S.handNo = null;
  S.stage = null;
  S.logLen = 0;
  S.prevBets = null;

  $('#mainrow').innerHTML =
    '<div class="wait resultmsg">' +
    (heroAward || '핸드 종료') +
    ' · 팟 ' + fmt(v.pot) +
    '</div>';

  S.autoTimer =
    setTimeout(afterHold, RESULT_HOLD);
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
/* 엔진의 pots 는 '투입 단계'별로 쪼갠 것이지 사이드팟이 아니다.
 *
 *  - 자격자가 같은 칸이 연달아 나오면 한 팟이다. 단계가 나뉜 것은
 *    누가 언제 얼마를 넣었냐일 뿐 나눠 줄 대상이 같다.
 *  - **자격자가 한 명인 칸은 팟이 아니다.** 상대가 다 콜하지 못한
 *    초과분이 그대로 돌아가는 것이다. 헤즈업 올인에서 항상 생긴다 —
 *    이걸 '사이드1' 로 찍어서, 둘이 치는 판에 사이드팟이 있는 것처럼
 *    보였다. view.py 도 이미 이걸 '반환' 으로 부른다.
 *
 * 사이드팟은 올인한 사람을 두고 **나머지가 계속 칠 때** 생긴다.
 * 그래서 자격자 2명 이상인 칸이 둘 이상일 때만 팟이 나뉜 것이다.
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

/* 실제로 겨룬 팟과, 콜되지 않아 돌아간 몫을 가른다. */
function splitPots(pots) {
  const all = mergePots(pots);
  const real = all.filter((p) => (p.eligible || []).length > 1);
  const back = all.filter((p) => (p.eligible || []).length <= 1);
  return { real: real, back: back,
           backAmt: back.reduce((a, p) => a + (p.amount || 0), 0) };
}


function potAwards(v) {
  const out = {};
  const sp = splitPots((v && v.pots) || []);
  const real = sp.real || [];

  const add = (seat, label, split, potIndex) => {
    const k = String(seat);
    if (!out[k]) out[k] = [];

    if (!out[k].some((x) =>
      x.label === label &&
      x.split === split &&
      x.pot === potIndex)) {
      out[k].push({
        label: label,
        split: !!split,
        pot: potIndex
      });
    }
  };

  if (real.length) {
    real.forEach((p, i) => {
      const ws = (p.winners || []).map(Number);
      if (!ws.length) return;

      const split = ws.length > 1;
      const base = i === 0 ? 'MAIN' : `SIDE ${i}`;

      ws.forEach((w) =>
        add(
          w,
          split ? `${base} SPLIT` : base,
          split,
          i
        )
      );
    });

    return out;
  }

  // 폴드 종료 등 실제 contested pots가 없는 결과의 fallback.
  const ws = ((v && v.winners) || []).map(Number);

  if (ws.length) {
    const split = ws.length > 1;

    ws.forEach((w) =>
      add(
        w,
        split ? 'SPLIT' : 'MAIN',
        split,
        0
      )
    );
  }

  return out;
}

function awardLabelFor(map, seat) {
  const xs = (map && map[String(seat)]) || [];
  return xs.map((x) => x.label).join(' · ');
}

function awardLabel(seat) {
  return awardLabelFor(S.awards, seat);
}

function awardMapSplitOnly(map, seat) {
  const xs = (map && map[String(seat)]) || [];
  return !!xs.length && xs.every((x) => x.split);
}

function awardSplitOnly(seat) {
  return awardMapSplitOnly(S.awards, seat);
}

function awardHasSolo(map, seat) {
  const xs = (map && map[String(seat)]) || [];
  return xs.some((x) => !x.split);
}

/* withLog — 라인 기록을 붙일지. 방금 끝난 핸드의 결과 화면에는 붙이지 않는다.
 * 그 화면은 방금 눈으로 본 것을 다시 글로 읽게 하고 5초 안에 지나간다.
 * 지난 핸드 상세('기록')에서는 그게 유일한 내용이라 붙인다. */
function resultBodyHTML(v, withLog) {
  const awards = potAwards(v);
  const winSet = {};

  Object.keys(awards).forEach((s) => {
    winSet[String(s)] = 1;
  });

  const label = (s) =>
    awardLabelFor(awards, s);

  let rows = '';

  if (v.showdown) {
    const order = (v.show_order || [])
      .map(String);

    const shownKeys =
      Object.keys(v.shown || {});

    const seen = {};

    order.concat(shownKeys).forEach((s) => {
      s = String(s);
      if (seen[s]) return;
      if (!(v.shown || {})[s]) return;

      seen[s] = 1;

      const lab = label(s);

      rows +=
        `<div class="row${lab && !awardMapSplitOnly(awards, s) ? ' win' : ''}">` +
        `<span class="who">${seatName(v, s)}</span>` +
        `<span class="cards">${cardsHTML(v.shown[s], 'mini')}</span>` +
        `${lab ? `<span class="amt">${esc(lab)}</span>` : ''}` +
        `</div>`;
    });

    const hk = String(v.hero_seat);

    if ((v.hero_hole || []).length &&
        !(v.shown || {})[hk]) {
      const lab = label(hk);

      rows +=
        `<div class="row${lab && !awardMapSplitOnly(awards, hk) ? ' win' : ''}">` +
        `<span class="who">나</span>` +
        `<span class="cards">${cardsHTML(v.hero_hole, 'mini')}</span>` +
        `${lab ? `<span class="amt">${esc(lab)}</span>` : ''}` +
        `</div>`;
    }

  } else if ((v.hero_hole || []).length) {
    const hk = String(v.hero_seat);
    const myLab = label(hk);

    rows +=
      `<div class="row${myLab && !awardMapSplitOnly(awards, hk) ? ' win' : ''}">` +
      `<span class="who">나</span>` +
      `<span class="cards">${cardsHTML(v.hero_hole, 'mini')}</span>` +
      `${myLab ? `<span class="amt">${esc(myLab)} · 쇼다운 없음</span>` : ''}` +
      `</div>`;

    Object.keys(awards).forEach((s) => {
      if (String(s) === hk) return;

      const lab = label(s);

      rows +=
        `<div class="row${lab && !awardMapSplitOnly(awards, s) ? ' win' : ''}">` +
        `<span class="who">${seatName(v, s)}</span>` +
        `<span class="amt">${esc(lab)} · 쇼다운 없음</span>` +
        `</div>`;
    });

  } else {
    Object.keys(awards).forEach((s) => {
      const lab = label(s);

      rows +=
        `<div class="row${lab && !awardMapSplitOnly(awards, s) ? ' win' : ''}">` +
        `<span class="who">${seatName(v, s)}</span>` +
        `<span class="amt">${esc(lab)} · 쇼다운 없음</span>` +
        `</div>`;
    });
  }

  let potsHTML = '';
  const sp = splitPots(v.pots);

  if (sp.real.length > 1 || sp.back.length) {
    potsHTML =
      '<div class="potline">팟 분배</div>' +

      sp.real.map((p, i) => {
        const ws = p.winners || [];
        const split =
          ws.length > 1 ? ' SPLIT' : '';

        return (
          `<div class="row">` +
          `<span class="who">${i === 0 ? 'MAIN' : 'SIDE ' + i}${split}</span>` +
          `<span>${ws.map((w) => seatName(v, w)).join(', ') || '-'}</span>` +
          `<span class="amt">${fmt(p.amount)}</span>` +
          `</div>`
        );
      }).join('') +

      sp.back.map((p) =>
        `<div class="row">` +
        `<span class="who">반환</span>` +
        `<span>${(p.eligible || []).map((w) => seatName(v, w)).join(', ') || '-'}</span>` +
        `<span class="amt">${fmt(p.amount)}</span>` +
        `</div>`
      ).join('');
  }

  const how = {
    fold: '폴드로 종료',
    showdown: '쇼다운',
    void: '무효'
  }[v.how] || v.how;

  return (
    `<h2>HAND ${v.hand_no ?? ''} 결과</h2>` +
    `<div class="sub">${how} · 팟 ${fmt(v.pot)}</div>` +
    `<div class="boardrow">${
      (v.board || []).length
        ? cardsHTML(v.board)
        : '<span class="sub">보드 없음</span>'
    }</div>` +
    rows +
    potsHTML +
    (withLog ? logBoxHTML(v.log, v) : '') +
    (v.notes || [])
      .map((n) => `<div class="potline">${n}</div>`)
      .join('')
  );
}

function renderResult(v) {
  closeRaise();

  const fv = revealView(v, true);
  if (fv) {
    renderSeats(fv);
    renderChips(fv, false);
    renderBoard(fv);
    renderPot(fv);
    renderHero(fv);

    // 결과의 street 이름은 revealView가 아니라 실제 full_log에서 결정한다.
    renderLogLine(v);
  }
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

function renderHistoryList(list, fallbackNote) {
  list = Array.isArray(list) ? list : [];

  list.sort((a, b) =>
    Number(b && b.hand_no || 0) -
    Number(a && a.hand_no || 0)
  );

  if (!list.length) {
    showOverlayPersistent(
      '<h2>지난 핸드</h2>' +
      '<div class="sub">아직 끝난 핸드가 없습니다.</div>' +
      '<div class="actions">' +
      '<button type="button" id="bClose">닫기</button>' +
      '</div>'
    );

    $('#bClose').addEventListener('click', hideOverlay);
    return;
  }

  const rows = list.map((v, i) => {
    const amap = potAwards(v);
    const mineLabel = awardLabelFor(amap, v.hero_seat);
    const mine = !!mineLabel;
    const mineSolo = awardHasSolo(amap, v.hero_seat);

    const how = {
      fold: '폴드로 종료',
      showdown: '쇼다운',
      void: '무효'
    }[v.how] || v.how;

    return (
      `<div class="row hist${mineSolo ? ' win' : ''}" data-i="${i}">` +
      `<span class="who">HAND ${v.hand_no ?? '?'}</span>` +
      `<span class="cards">${
        cardsHTML((v.board || []).slice(0, 5), 'mini')
      }</span>` +
      `<span class="amt">${
        mine ? esc(mineLabel) + ' ' : ''
      }${fmt(v.pot)}</span>` +
      `<div class="histsub">${how || ''}</div>` +
      `</div>`
    );
  }).join('');

  const note = fallbackNote
    ? `<div class="potline">${esc(fallbackNote)}</div>`
    : '';

  showOverlayPersistent(
    `<h2>지난 핸드</h2>` +
    `<div class="sub">${list.length}개 · 눌러서 자세히</div>` +
    note +
    rows +
    '<div class="actions">' +
    '<button type="button" id="bClose">닫기</button>' +
    '</div>'
  );

  $('#bClose').addEventListener('click', hideOverlay);

  document
    .querySelectorAll('#overlay .row.hist')
    .forEach((el) => {
      el.addEventListener('click', () =>
        showHandDetail(list[Number(el.dataset.i)])
      );
    });
}

async function showHistory() {
  showOverlayPersistent(
    '<h2>지난 핸드</h2>' +
    '<div class="sub">서버 기록 불러오는 중…</div>'
  );

  try {
    const res = await fetch('/api/history', {
      cache: 'no-store'
    });

    if (!res.ok) {
      throw new Error('HTTP ' + res.status);
    }

    const data = await res.json();
    const hands = Array.isArray(data.hands)
      ? data.hands
      : [];

    renderHistoryList(hands, '');
    return;

  } catch (e) {
    // 서버 기록을 못 읽을 때만 기존 브라우저 기록을 비상용으로 사용한다.
    renderHistoryList(
      histLoad(),
      '서버 기록을 불러오지 못해 이 기기의 임시 기록을 표시합니다.'
    );
  }
}

/* index.html 이 app.js 를 ?v=N 으로 불러온다. 그 N 을 그대로 보여준다.
 * 브라우저가 옛 파일을 캐시하고 있으면 여기 숫자도 옛것이라 바로 드러난다. */
function buildTag() {
  const el = document.querySelector('script[src*="app.js"]');
  const m = el && /[?&]v=([^&]*)/.exec(el.getAttribute('src') || '');
  return m ? m[1] : '?';
}

function fullscreenActive() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement);
}

async function toggleFullscreen() {
  if (fullscreenActive()) {
    const exit = document.exitFullscreen || document.webkitExitFullscreen;
    if (exit) {
      try { await exit.call(document); } catch (e) {}
    }
    return;
  }

  const el = document.documentElement;
  const enter = el.requestFullscreen || el.webkitRequestFullscreen;
  if (!enter) {
    toast('이 브라우저는 웹 전체화면을 지원하지 않습니다');
    return;
  }

  try {
    // Android Chromium 계열은 navigationUI:'hide'를 지원하면 주소/탭 UI까지 숨긴다.
    await enter.call(el, { navigationUI: 'hide' });
  } catch (e) {
    try { await enter.call(el); }
    catch (e2) { toast('전체화면 전환을 사용할 수 없습니다'); }
  }
}

function showMenu() {
  const on = autoOn();
  const sm = stepMs();
  showOverlayPersistent('<h2>설정</h2>' +
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
    '<button type="button" id="mFull">' +
    (fullscreenActive() ? '전체화면 끄기' : '전체화면 켜기') + '</button>' +
    '<div class="potline" style="margin-top:8px">브라우저 주소창 때문에 세로 공간이 부족하면 전체화면을 사용합니다.</div>' +
    '<button type="button" id="mNew">새 게임</button>' +
    '<button type="button" id="mLobby">로비로 나가기</button>' +
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
  $('#mFull').addEventListener('click', () => {
    hideOverlay();
    toggleFullscreen();
  });
  $('#mNew').addEventListener('click', () => {
    showOverlayPersistent('<h2>새 게임을 시작할까요?</h2>' +
      '<div class="sub">진행 중인 대회는 끝납니다. 되돌릴 수 없습니다.</div>' +
      newGameFormHTML() +
      '<div class="actions"><button type="button" id="bNew">시작</button>' +
      '<button type="button" id="mBack">취소</button></div>');
    $('#bNew').addEventListener('click', startNew);
    $('#mBack').addEventListener('click', showMenu);
  });
  $('#mLobby').addEventListener('click', () => { location.href = '/'; });
  $('#mClose').addEventListener('click', hideOverlay);
}

function showHandDetail(v) {
  showOverlayPersistent(resultBodyHTML(v, true) +
    '<div class="actions"><button type="button" id="bBack">목록으로</button></div>');
  $('#bBack').addEventListener('click', showHistory);
}

function logBoxHTML(log, v) {
  if (!log || !log.length) return '';
  let out = '<div class="logbox">';
  let cur = null;

  log.forEach((raw) => {
    // 실시간 UI 로그는 object,
    // hand_archive2.jsonl의 full_log는
    // [street, seat, action, amount] 배열이다.
    // 둘 다 같은 렌더러에서 처리한다.
    const e = Array.isArray(raw)
      ? {
          street: raw[0],
          seat: raw[1],
          action: raw[2],
          amount: raw[3]
        }
      : raw;

    if (!e) return;

    if (e.street !== cur) {
      cur = e.street;
      out += `<div><span class="st">${STREET[cur] || cur}</span>`;
    } else {
      out += ' · ';
    }

    const who =
      String(e.seat) === String(v.hero_seat)
        ? '나'
        : e.seat + '번';

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

  if (resp.won) {
    S.won = true;
    S.entries = resp.entries || S.entries;
    showOverlay(
      `<h2>🏆 우승</h2>` +
      `<div class="sub">${S.entries ? S.entries + '명 중 ' : ''}1위</div>` +
      newGameFormHTML() +
      `<div class="actions"><button type="button" id="bNew">새 게임</button></div>`);
  } else {
    showOverlay(
      `<h2>탈락</h2><div class="sub">최종 ${resp.rank ? resp.rank + '위' : '순위 미상'}</div>` +
      newGameFormHTML() +
      `<div class="actions"><button type="button" id="bNew">새 게임</button></div>`);
  }
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
  if (WATCH_MODE) {
    toast('관전 모드에서는 새 게임을 시작할 수 없습니다');
    return;
  }

  // 새 게임 시작을 확정하면 설정/확인 창부터 닫는다.
  hideOverlay();
  clearTimeout(S.autoTimer); S.autoTimer = null;
  S.heroSig = null; S.won = false; S.pendingMoveNote = null;
  memoClearAll();                    // 새 게임이면 봇 메모도 완전히 초기화
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

function showOverlay(html, pinned) {
  const o = $('#overlay');
  S.overlayPinned = !!pinned;
  const close = pinned
    ? '<button type="button" class="sheetClose" aria-label="닫기">×</button>'
    : '';
  o.innerHTML = `<div class="sheet">${close}${html}</div>`;
  o.hidden = false;
  const x = o.querySelector('.sheetClose');
  if (x) x.addEventListener('click', hideOverlay);
}
function showOverlayPersistent(html) { showOverlay(html, true); }
function hideOverlay() {
  $('#overlay').hidden = true;
  S.overlayPinned = false;
}

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
function setBusy(on, msg, quiet) {
  S.busy = on;
  const box = $('#status');

  document.querySelectorAll('#actionbar button').forEach((b) => {
    b.disabled = on;
  });

  clearInterval(S.busyTimer);
  S.busyTimer = null;

  if (!on) {
    box.hidden = true;
    return;
  }

  // 실제 플레이 액션은 테이블을 가리지 않는다.
  if (quiet) {
    box.hidden = true;
    return;
  }

  const t0 = Date.now();
  box.hidden = false;
  box.querySelector('.msg').textContent = msg || '진행 중…';
  box.querySelector('.el').textContent = '';
  box.querySelector('.hint').textContent = '';

  S.busyTimer = setInterval(() => {
    const s = (Date.now() - t0) / 1000;

    if (s >= 1.2) {
      box.querySelector('.el').textContent = s.toFixed(1) + '초';
    }

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
    ? { method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-T2-Play-Key': PLAY_KEY,
          'X-T2-Client-Mode': WATCH_MODE ? 'watch' : 'play'
        },
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
  setBusy(true, msg, path === '/api/step');
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
 * 이제는 재생이 끝나는 순간(finalFrame)에 보낸다. 테이블 터치로 재생을
 * 건너뛰는 동작은 두지 않는다.
 *
 * '다음 핸드'(action === null)는 예약하지 않는다. 그건 결과 화면에서 누르는
 * 것이라 재생 중일 수가 없다.
 */
function previewHeroAction(action, amount) {
  const v = S.view;
  if (!v || v.type !== 'decision' || action === null) return;

  const seats = (v.seats || []).map((x) => Object.assign({}, x));
  const me = seats.find((x) => x.seat === v.hero_seat);
  if (!me) return;

  if (action === 'fold') {
    me.in_hand = false;

  } else if (action !== 'check') {
    let target = me.bet || 0;

    if (action === 'call') {
      target += Number((v.legal || {}).call || 0);

    } else if (action === 'bet' || action === 'raise') {
      target = Number(amount || target);

    } else if (action === 'allin') {
      const rz = (v.legal || {}).raise;

      target = rz && rz.max_to !== undefined
        ? Number(rz.max_to)
        : (me.bet || 0) + (me.stack || 0);
    }

    target = Math.max(me.bet || 0, target);

    const add = Math.max(0, target - (me.bet || 0));

    me.stack = Math.max(0, (me.stack || 0) - add);
    me.bet = target;
    me.allin = me.stack <= 0;
  }

  const sum = seats.reduce((a, x) => a + (x.bet || 0), 0);

  const pv = Object.assign({}, v, {
    seats: seats,
    pot_total: (v.pot_center || 0) + sum
  });

  renderSeats(pv);
  renderChips(pv, false);
  renderPot(pv);
  renderHero(pv);

  const row = $('#mainrow');

  if (row) {
    let txt = ACT[action] || action;

    if ((action === 'bet' || action === 'raise') && amount) {
      txt += ' ' + fmt(amount);
    }

    row.innerHTML = '<div class="wait">나 ' + txt + '</div>';
  }

  closeRaise();
}

function send(action, amount) {
  if (WATCH_MODE) {
    toast('관전 모드입니다');
    return;
  }

  if (S.token === null || S.token === undefined) {
    sync();
    return;
  }

  if (action !== null && S.replayDone) {
    S.queuedAction = {
      action: action,
      amount: amount | 0
    };
    markQueued(action);
    return;
  }

  // 클릭 즉시 내 액션을 먼저 보여준다.
  previewHeroAction(action, amount);

  call(
    '/api/step',
    {
      action: action,
      amount: amount | 0,
      token: S.token
    },
    action === null ? '다음 핸드 준비 중…' : '진행 중…'
  );
}

function markQueued(action) {
  const row = $('#mainrow');
  if (row) {
    row.innerHTML = '<div class="wait">' + (ACT[action] || action) +
      ' 예약됨 — 앞사람 액션이 끝나면 진행합니다</div>';
  }
  closeRaise();
}

function flushQueued() {
  if (!S.queuedAction) return false;

  const q = S.queuedAction;
  S.queuedAction = null;

  previewHeroAction(q.action, q.amount);

  call(
    '/api/step',
    {
      action: q.action,
      amount: q.amount,
      token: S.token
    },
    '진행 중…'
  );

  return true;
}

function sync() { call('/api/state', null, '상태를 받는 중…'); }

/* ---------------- 응답 반영 ---------------- */
function apply(resp) {
  S.last = resp;
  S.token = resp.token;

  clearTimeout(S.autoTimer);
  S.autoTimer = null;

  if (resp.no_game) {
    showNewGame();
    return;
  }

  if (resp.game_over) {
    showGameOver(resp);
    return;
  }

  const v = resp.view;

  if (!v) {
    showNewGame('상태를 읽지 못했습니다.');
    return;
  }

  const moveNote = tableMoveNote(v);
  if (moveNote) {
    S.pendingMoveNote = moveNote;
  }

  // 새 서버 응답으로 덮기 전에 직전 decision을 보관.
  const prevView = S.view0;

  S.view = v;

  // 새 서버 응답은 새 렌더 세대다.
  // 이전 핸드에서 늦게 깨어난 timeout/fetch 콜백은 화면을 건드리지 못한다.
  S.epoch = (S.epoch || 0) + 1;

  stopReplay();

  if (v.type === 'result') {
    S.won = (resp.remaining === 1 && !resp.busted);
    S.entries = resp.entries || S.entries;

    const opening = resp.opening_view || null;
    const freshAutoResult =
      !!opening &&
      String(S.handNo) !== String(v.hand_no);

    if (freshAutoResult) {
      const resultEpoch = S.epoch || 0;

      clearBubbles();
      resetFolding();

      S.boardLen = 0;
      S.prevBets = null;
      S.reveal = null;
      S.winners = null;
      S.awards = null;
      S.bestFive = null;
      S.heroSig = null;
      S.showdownFrame = null;

      if (!S.overlayPinned) {
        hideOverlay();
      }

      renderTop(opening);
      closeRaise();

      $('#mainrow').hidden = false;
      $('#mainrow').innerHTML = '';

      renderBoard(opening);

      $('#logline').innerHTML =
        '<span class="cur">' +
        (STREET[opening.stage] || opening.stage) +
        '</span> —';

      S.view0 = opening;
      S.handNo = opening.hand_no;
      S.stage = opening.stage;
      S.logLen = 0;

      dealThen(opening, () => {
        if (!epochAlive(resultEpoch)) return;

        S.view0 = opening;

        if (!spectateTail(v)) {
          finishResult(v);
        }
      });

    } else {
      if (!spectateTail(v)) {
        finishResult(v);
      }
    }

    return;
  }

  const freshHand = S.handNo !== v.hand_no;
  const streetChanged =
    !freshHand &&
    S.stage !== v.stage;

  const newLog =
    (freshHand || streetChanged)
      ? (v.log || [])
      : (v.log || []).slice(S.logLen);

  if (freshHand) {
    clearBubbles();
    resetFolding();

    S.boardLen = 0;
    S.prevBets = null;
    S.reveal = null;
    S.winners = null;
    S.awards = null;
    S.bestFive = null;
    S.heroSig = null;
    S.showdownFrame = null;
  }

  if (!S.overlayPinned) {
    hideOverlay();
  }

  renderTop(v);
  closeRaise();

  $('#mainrow').hidden = false;

  /*
   * 일반 액션 응답에서는 previewHeroAction()이 만든 마지막 자연스러운
   * 프레임을 그대로 유지한다.
   *
   * 새 핸드만 이전 결과 버튼/문구를 비운다.
   */
  if (freshHand) {
    $('#mainrow').innerHTML = '';
  }

  if (freshHand) {
    const startFreshHand = () => {
      renderBoard(v);

      $('#logline').innerHTML =
        '<span class="cur">' +
        (STREET[v.stage] || v.stage) +
        '</span> —';

      dealThen(
        v,
        () => playSequence(v, newLog, true)
      );
    };

    if (S.pendingMoveNote) {
      const note = S.pendingMoveNote;
      S.pendingMoveNote = null;

      showTableMove(
        note,
        v.hero_seat,
        startFreshHand
      );
    } else {
      startFreshHand();
    }

  } else {
    /*
     * 최종 서버 화면을 먼저 띄우지 않는다.
     *
     * 현재 화면
     * -> 남은 봇 액션
     * -> 칩 수거
     * -> 새 보드
     * -> 다음 스트리트 액션
     */
    if (!playDecisionTail(prevView, v)) {
      if (streetChanged) {
        renderChips(v, true);
        renderBoard(v);
        playSequence(v, v.log || [], true);
      } else {
        playSequence(v, newLog, false);
      }
    }
  }

  // 다음 서버 응답의 출발점.
  S.view0 = v;

  S.handNo = v.hand_no;
  S.stage = v.stage;
  S.logLen = (v.log || []).length;

  if (v.error) {
    toast(v.error);
  }
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
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideOverlay();
});
if (WATCH_MODE) {
  sync();
} else {
  memoLoad().finally(sync);
}

if (location.hash === '#history') {
  setTimeout(showHistory, 250);
}

if (WATCH_MODE) {
  setInterval(async () => {
    if (S.busy) return;

    try {
      const r = await req('/api/state', null);

      if (r.status !== 200 || !r.json)
        return;

      if (r.json.no_game) {
        if (S.last && S.last.no_game) return;
        apply(r.json);
        return;
      }

      if (r.json.token !== S.token)
        apply(r.json);

    } catch (e) {}
  }, 1000);
}
