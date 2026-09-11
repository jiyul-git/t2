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
};

const fmt = (n) => (n === null || n === undefined || isNaN(n))
  ? '-' : Number(n).toLocaleString('en-US');

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
    html += `<div class="${cls}" data-slot="${slot}" style="${style}">` +
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
  document.querySelectorAll('.bubble').forEach((b) => b.remove());
}
function actionText(e) {
  const t = ACT[e.action] || e.action;
  return (e.action === 'bet' || e.action === 'raise') && e.amount
    ? `${t} ${fmt(e.amount)}` : t;
}
function showBubbles(entries, v) {
  let i = 0;
  entries.forEach((e) => {
    if (e.seat === v.hero_seat) return;
    const delay = i * 380; i++;
    S.timers.push(setTimeout(() => {
      const pod = document.querySelector(`.pod[data-slot="${e.seat}"]`);
      if (!pod) return;
      const b = document.createElement('div');
      b.className = 'bubble' + (e.action === 'fold' ? ' fold' : '');
      b.textContent = actionText(e);
      pod.appendChild(b);
      setTimeout(() => b.remove(), 1700);
    }, delay));
  });
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

function renderResult(v) {
  clearBubbles();
  $('#mainrow').innerHTML = '<div class="wait">핸드 종료</div>';
  closeRaise();
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

  const st = v.stacks || {};
  const stacksHTML = '<div class="potline">스택</div><div class="grid">' +
    Object.keys(st).sort((a, b) => a - b).map((s) =>
      `<div class="row"><span class="who">${seatName(v, s)}</span>` +
      `<span class="amt">${fmt(st[s])}</span></div>`).join('') + '</div>';

  const how = { fold: '폴드로 종료', showdown: '쇼다운', void: '무효' }[v.how] || v.how;
  showOverlay(
    `<h2>HAND ${v.hand_no ?? ''} 결과</h2>` +
    `<div class="sub">${how} · 팟 ${fmt(v.pot)}</div>` +
    `<div class="boardrow">${(v.board || []).length ? cardsHTML(v.board) : '<span class="sub">보드 없음</span>'}</div>` +
    rows + potsHTML + stacksHTML +
    logBoxHTML(v.log, v) +
    (v.notes || []).map((n) => `<div class="potline">${n}</div>`).join('') +
    `<div class="actions"><button type="button" id="bDeal">다음 핸드</button></div>`);
  $('#bDeal').addEventListener('click', () => send(null, 0));
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
function showLog() {
  const v = S.view;
  if (!v) return;
  const all = (v.prior_log || []).concat(
    (v.log || []).map((e) => ({ street: v.stage, seat: e.seat,
                                action: e.action, amount: e.amount })));
  showOverlay(`<h2>HAND ${v.hand_no ?? ''} 기록</h2>` +
    `<div class="boardrow">${(v.board || []).length ? cardsHTML(v.board) : '<span class="sub">보드 없음</span>'}</div>` +
    (all.length ? logBoxHTML(all, v) : '<div class="sub">아직 액션이 없습니다.</div>') +
    `<div class="actions"><button type="button" id="bClose">닫기</button></div>`);
  $('#bClose').addEventListener('click', hideOverlay);
}

/* ---------------- 토스트 ---------------- */
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.hidden = false;
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
  if (resp.no_game) { showNewGame(); return; }
  if (resp.game_over) { showGameOver(resp); return; }
  const v = resp.view;
  if (!v) { showNewGame('상태를 읽지 못했습니다.'); return; }
  S.view = v;

  if (v.type === 'result') {
    renderResult(v);
    S.handNo = null; S.stage = null; S.logLen = 0; S.boardLen = 0;
    return;
  }

  const freshHand = S.handNo !== v.hand_no;
  const streetChanged = !freshHand && S.stage !== v.stage;
  const newLog = (freshHand || streetChanged) ? (v.log || [])
                                              : (v.log || []).slice(S.logLen);
  if (freshHand) { clearBubbles(); S.boardLen = 0; }

  hideOverlay();
  renderTop(v);
  renderSeats(v);
  renderChips(v, streetChanged);
  renderBoard(v);
  renderPot(v);
  renderHero(v);
  renderActions(v);
  renderLogLine(v);
  showBubbles(newLog, v);

  S.handNo = v.hand_no; S.stage = v.stage; S.logLen = (v.log || []).length;
  if (v.error) toast(v.error);
}

/* ---------------- 시작 ---------------- */
$('#bLog').addEventListener('click', showLog);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideOverlay();
});
sync();
