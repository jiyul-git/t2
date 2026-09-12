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
  autoTimer: null,         // 결과 화면 자동 진행
};

// 봇 액션 한 건을 보여주는 간격. **표시 속도일 뿐이고 계산과 무관하다.**
// 엔진과 워커에는 sleep 을 넣지 않는다 — 다른 테이블은 계속 최고 속도로 돈다.
const STEP_MS = 1200;
const RESULT_MS = 5000;    // 결과 화면을 보여주는 시간. 지나면 다음 핸드로

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
    const cls = 'pod' + (d.in_hand ? '' : ' folded');
    const memo = (d.pid === undefined || d.pid === null) ? ''
      : `<button type="button" class="memo${memoGet(d.pid) ? ' has' : ''}" ` +
        `data-pid="${d.pid}" data-label="${slot}번(${d.pos || ''})">✎</button>`;
    html += `<div class="${cls}" data-slot="${slot}" style="${style}">` + memo +
            (d.in_hand ? `<div class="backs">${backHTML('mini')}${backHTML('mini')}</div>` : '') +
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
  $('#herocards').innerHTML = cardsHTML(v.hero_hole);
}

/* ---------------- 말풍선 ---------------- */
function clearBubbles() {
  S.timers.forEach(clearTimeout); S.timers = [];
  S.replayDone = null;
  document.querySelectorAll('.bubble').forEach((b) => b.remove());
}
function actionText(e) {
  const t = ACT[e.action] || e.action;
  return (e.action === 'bet' || e.action === 'raise') && e.amount
    ? `${t} ${fmt(e.amount)}` : t;
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
  const seats = (v.seats || []).map((s) => Object.assign({}, s, {
    bet: bets[s.seat] || 0,
    in_hand: !folded[s.seat],
    stack: s.stack + (s.bet || 0) - (bets[s.seat] || 0),
  }));
  const sum = seats.reduce((a, s) => a + (s.bet || 0), 0);
  const fv = Object.assign({}, v, { seats: seats,
                                    pot_total: (v.pot_center || 0) + sum });
  renderSeats(fv); renderChips(fv, false); renderPot(fv); renderHero(fv);
}

function finalFrame(v) {
  S.timers.forEach(clearTimeout); S.timers = [];
  S.replayDone = null;
  document.querySelectorAll('.bubble').forEach((b) => b.remove());
  renderSeats(v); renderPot(v); renderHero(v);
  const bets = {};
  (v.seats || []).forEach((s) => { bets[s.seat] = s.bet || 0; });
  S.prevBets = bets;
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
    if (e.action === 'fold') folded[e.seat] = 1;
    else if (e.action !== 'check') bets[e.seat] = e.amount || bets[e.seat] || 0;
    drawFrame(v, bets, folded);
    bubbleAt(e.seat, e);
    S.timers.push(setTimeout(next, STEP_MS));
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
  $('#logline').innerHTML = '<span class="cur">' +
    (STREET[ss.stage] || ss.stage) + '</span> 관전 중';
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
  $('#mainrow').innerHTML = '<div class="wait">관전 중 — 화면을 누르면 건너뜁니다</div>';
  closeRaise();
  clearBubbles();

  let i = 0;
  S.replayDone = () => { finishResult(res); };
  (function next() {
    if (i >= tail.length) { finishResult(res); return; }
    const e = tail[i++];
    const streetChange = e.street && e.street !== ss.stage;
    applyEntry(ss, e);
    renderSpectate(base, res, ss);
    if (e.seat !== res.hero_seat) bubbleAt(e.seat, e);
    // 스트리트가 바뀐 직후에는 카드가 깔리는 걸 볼 시간을 조금 더 준다
    S.timers.push(setTimeout(next, streetChange ? STEP_MS + 500 : STEP_MS));
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
  renderResult(v);
  S.handNo = null; S.stage = null; S.logLen = 0; S.boardLen = 0;
  S.prevBets = null; S.view0 = null;
  // 결과를 잠깐 보여주고 자동으로 다음 핸드로 간다. 이 시간 동안 서버 워커가
  // 다른 테이블 정산을 마저 돌린다 — 기다림이 여기에 겹친다.
  if (!autoOn()) return;              // 자동 진행을 꺼두면 직접 누를 때까지 기다린다
  let left = Math.round(RESULT_MS / 1000);
  const tick = () => {
    const b = $('#bDeal');
    if (!b) return;
    if (left <= 0) { S.autoTimer = null; send(null, 0); return; }
    b.innerHTML = '다음 핸드 <span class="sub">' + left + '</span>';
    left -= 1;
    S.autoTimer = setTimeout(tick, 1000);
  };
  tick();
}

function resultBodyHTML(v) {
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
  const pots = v.pots || [];
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
    logBoxHTML(v.log, v) +
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

function showMenu() {
  clearTimeout(S.autoTimer); S.autoTimer = null;
  const on = autoOn();
  showOverlay('<h2>설정</h2>' +
    `<div class="row"><span class="who">자동 진행</span>` +
    `<span class="amt">${on ? '켬 · 결과 5초 뒤 다음 핸드' : '끔 · 직접 누르기'}</span></div>` +
    `<button type="button" id="mAuto">${on ? '자동 진행 끄기' : '자동 진행 켜기'}</button>` +
    '<div class="potline" style="margin-top:14px">지금 대회를 접고 새로 시작합니다.' +
    ' 기존 기록은 bak_ 파일로 보관됩니다.</div>' +
    '<button type="button" id="mNew">새 게임</button>' +
    '<div class="actions"><button type="button" id="mClose">닫기</button></div>');
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
  showOverlay(resultBodyHTML(v) +
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
  if (S.busy) return null;
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
  }
}

function send(action, amount) {
  if (S.token === null || S.token === undefined) { sync(); return; }
  call('/api/step', { action, amount: amount | 0, token: S.token },
       action === null ? '다음 핸드 준비 중…' : '진행 중…');
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

  if (v.type === 'result') {
    // 히어로가 폴드했어도 남은 액션이 있으면 먼저 보여준 뒤 결과를 띄운다
    if (!spectateTail(v)) finishResult(v);
    return;
  }
  S.view0 = v;

  const freshHand = S.handNo !== v.hand_no;
  const streetChanged = !freshHand && S.stage !== v.stage;
  const newLog = (freshHand || streetChanged) ? (v.log || [])
                                              : (v.log || []).slice(S.logLen);
  if (freshHand) { clearBubbles(); S.boardLen = 0; S.prevBets = null; }

  hideOverlay();
  renderTop(v);
  renderChips(v, streetChanged);     // 스트리트가 끝났으면 칩을 팟으로 보낸다
  renderBoard(v);
  renderActions(v);                  // 버튼은 바로 쓸 수 있다. 재생을 기다리지 않는다
  renderLogLine(v);
  playSequence(v, newLog, freshHand || streetChanged);

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
