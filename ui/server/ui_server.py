#!/usr/bin/env python3
"""그래픽 UI용 HTTP 래퍼. 판단 로직은 건드리지 않고 live2.step() 만 호출한다.

  python ui_server.py [--port 8765]

반드시 엔진을 **별도 폴더에 복사**해서 그 폴더에서 실행한다.
live2 는 아카이브·리딩 장부를 모듈 폴더에 쓴다. sidecar 이름은 이제 상태
파일 경로에서 나오므로(`storage_paths`) 상태가 다르면 파일도 갈리지만,
같은 폴더에서 같은 상태로 돌리면 여전히 겹친다.
그래서 이 폴더에 UI_SERVER_DIR 표시 파일이 없으면 시작하지 않는다.

엔드포인트
  GET  /                      web/index.html (없으면 404)
  GET  /<경로>                web/ 아래 정적 파일. 같은 출처라 CORS 가 필요 없다.
  GET  /api/state             마지막 응답 (없으면 현재 상태를 재생해서 만든다)
  POST /api/new   {entries?, seed?, fmt?, start_stack?}
  GET  /api/stats             정산 지연 카운터 (attempt/hit/mismatch/fallback…)
  GET  /api/tournament        대회 정보 / 전체 스택 순위
  GET  /api/memos             플레이어 전용 봇 메모 조회
  POST /api/memo  {pid, memo}  플레이어 전용 봇 메모 저장
  POST /api/step  {action, amount, token}
       action: fold/check/call/bet/raise/allin, 또는 null(다음 핸드 딜)
       amount: 이번 스트리트 총 투입 목표(raise-to)
       token : 직전 응답의 token. 다르면 409 — 재전송으로 액션이 두 번 들어가는 것을 막는다.
"""
import math, hmac, secrets, json, mimetypes, os, posixpath, sys, threading, time, traceback, urllib.parse, socket, copy
from concurrent.futures import ProcessPoolExecutor
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler

D = os.path.dirname(os.path.abspath(__file__))
if D not in sys.path:
    sys.path.insert(0, D)
if not os.path.exists(os.path.join(D, 'UI_SERVER_DIR')):
    sys.exit('중단: 이 폴더에 UI_SERVER_DIR 파일이 없습니다. 엔진을 별도 폴더에 복사한 뒤 '
             '그 폴더에 빈 UI_SERVER_DIR 파일을 만들고 실행하세요.')

import ui_view
sys.modules['view'] = ui_view          # live2 가 import 하기 전에 주입
import live2 as L
import timing as TMG
import formats as FM
import context as CTX
from table import BLINDS
import storage_paths as _SP   # 아카이브 경로는 엔진과 같은 resolver 를 쓴다
import telemetry_sync as _TM
import tournament_store as _TS
import scheduled_runtime as _SR

LOCK = threading.Lock()
_last = None
ECONOMY = _TS.Store()
SCHEDULE_FUTURE = None
SCHEDULE_POOL = None
SCHEDULE_CURSOR = 0
LAST_PLAY_PRESENCE = 0.0
if ECONOMY.active_id():
    L.STATE_STORE = ECONOMY
    _saved_game = ECONOMY.load_active()
    if _saved_game:
        L.save(_saved_game)


def _economy_receipt(st):
    if not st or not st.get('tournament_id'):
        return {}
    ev = ECONOMY.event(st['tournament_id'])
    return {'wallet': ECONOMY.wallet(), 'tournament_id': ev['id'],
            'my_entry': ev['entries'][-1] if ev['entries'] else None,
            'registration_closes_at': ev['closes_at'],
            'prize_pool': st.get('prize_pool', 0),
            'can_reenter': _TS.can_reenter(ev)}


def _managed_play_state():
    """Take over only a completed off-screen hand; no action/clock reset on reload."""
    global _last, LAST_PLAY_PRESENCE
    LAST_PLAY_PRESENCE = time.time()
    tid = ECONOMY.active_id()
    if not tid:
        return None
    ev = ECONOMY.event(tid)
    st = ev['state']
    entry = ev['entries'][-1] if ev['entries'] else None
    if st and entry and entry['status'] in ('busted', 'finished'):
        L.STATE_STORE = ECONOMY
        _last = _game_over()
        return None
    if time.time() < ev['starts_at']:
        if not ev['enter_requested']:
            ECONOMY.request_enter(tid)
        return {'waiting': True, 'message': '예약한 대회의 시작을 기다리고 있습니다.',
                'starts_at': ev['starts_at'], **_economy_receipt(st)}
    if (not st or not entry or entry['pid'] is None or entry['status'] in ('reserved', 'waiting')
            or st.get('offscreen') and (not st.get('hero_ready') or
                st.get('background_seconds', 0) + 2 < _TS.active_seconds(time.time() - ev['starts_at']))):
        if not ev['enter_requested']:
            ECONOMY.request_enter(tid)
        return {'waiting': True, 'message': '대회 진행을 동기화하고 다음 핸드에 입장합니다.'}
    L.STATE_STORE = ECONOMY
    if st.get('offscreen'):
        _clear_worker()
        _vclock_reset()
        st['offscreen'] = False
        st.pop('background_pending', None)
        st['field']['sitout_pids'] = []
        st['field']['virtual_play_seconds'] = _TS.active_seconds(time.time() - ev['starts_at'])
        st['ui_clock_started_at'] = ev['starts_at']
        _sync_clock(st)
        L.save(st)
        _last = None
    return None


def _schedule_tick():
    """One publisher under LOCK; process workers never write wallet/live state."""
    global SCHEDULE_FUTURE, SCHEDULE_POOL, SCHEDULE_CURSOR, _last
    now = time.time()
    ECONOMY.ensure_schedule(now)
    if SCHEDULE_FUTURE is not None and SCHEDULE_FUTURE.done():
        try:
            result = SCHEDULE_FUTURE.result()
            ok = ECONOMY.save_state(result['id'], result['state'],
                                    expected_revision=result['revision'],
                                    assignments=result['assignments'])
            if ok and result['id'] == ECONOMY.active_id():
                L.STATE_STORE = ECONOMY
                L.save(ECONOMY.load_active())
                _last = None
        except Exception:
            traceback.print_exc()
        SCHEDULE_FUTURE = None
    tid = ECONOMY.active_id()
    st = ECONOMY.load_active() if tid else None
    if tid and now - LAST_PLAY_PRESENCE > 20 and ECONOMY.event(tid)['enter_requested']:
        # A player may leave the waiting room before the tournament starts.
        # An abandoned entry request must never pause that player's future blinds.
        ECONOMY.request_enter(tid, False)
        st = ECONOMY.load_active()
    if st and not st.get('offscreen'):
        # The deadline is authoritative even if the browser never posts again.
        if not st.get('busted') and _last is None and st.get('hand_seed') is not None:
            _last = _wrap(_step_sched())
            st = L.load()
        decision = ((_last or {}).get('view') or {}).get('type') == 'decision'
        if decision and st.get('ui_action_deadline') is None:
            ready_at = float(st.get('ui_decision_ready_at') or now)
            idle = now - LAST_PLAY_PRESENCE > 20
            # Connected players retain the existing full clock beginning when
            # their action bar is presented. Absence / failed presentation gets
            # a bounded server fallback, without buying extra time on reload.
            grace = 0.0 if idle else max(30.0, STREAM_ACK_TIMEOUT * 2)
            if idle or now >= ready_at + grace:
                _arm_action_clock(_token(), now=ready_at + grace)
                st = L.load()
        if (decision and st.get('ui_action_deadline') is not None
                and now >= float(st['ui_action_deadline'])):
            if TIMING_ON:
                _settle_hero_bank(st, now, timed_out=True)
                L.save(st)
            _last = _wrap(_step_sched(_timeout_action()))
            _last['auto_folded'] = True
            st = L.load()
        if ((st.get('busted') or now - LAST_PLAY_PRESENCE > 20)
                and st.get('hand_seed') is None):
            # Finalize legacy/vclock pending work before handing the whole field
            # to the off-screen scheduler.
            if st.get('vclock_settle_pending'):
                _vclock_refresh_settle_target(st)
                L.save(st)
                _vclock_settle(st, wait=False)
                st = L.load()
            if st.get('others_pending'):
                _kick_pending_worker()
                ready = _peek_others()
                if ready is not None:
                    L.resume_others(st, ready)
                    _clear_worker()
                    st = L.load()
            if not st.get('others_pending') and not st.get('vclock_settle_pending'):
                _clear_worker()
                _vclock_reset()
                st['offscreen'] = True
                st['field']['sitout_pids'] = [st['field']['hero_pid']]
                st['background_pending'] = {}
                st['background_seconds'] = min(
                    (float(t.get('vclock_seconds', 0)) for t in st['field']['tables'].values()),
                    default=0.0)
                st['hero_ready'] = False
                L.save(st)
                ECONOMY.request_enter(tid, False)
                _last = None
    if SCHEDULE_FUTURE is not None:
        return
    jobs = []
    for ev in ECONOMY.jobs(now):
        es = ev['state'] or {}
        if (ev['id'] == tid and es and not es.get('offscreen')
                and not es.get('busted')):
            continue
        if es.get('hand_seed') is not None or es.get('others_pending') or es.get('vclock_settle_pending'):
            continue
        target = _TS.active_seconds(now - ev['starts_at'])
        if es and es.get('background_seconds', -1) >= target - 0.25 and not any(
                e['status'] in ('reserved', 'waiting') for e in ev['entries']):
            continue
        jobs.append((ev, target))
    if jobs:
        ev, target = jobs[SCHEDULE_CURSOR % len(jobs)]
        SCHEDULE_CURSOR += 1
        if SCHEDULE_POOL is None:
            SCHEDULE_POOL = ProcessPoolExecutor(max_workers=1)
        SCHEDULE_FUTURE = SCHEDULE_POOL.submit(_SR.advance, ev, target)


def _schedule_loop():
    stop = threading.Event()
    while not stop.wait(1):
        if LOCK.acquire(timeout=0.05):
            try:
                _schedule_tick()
            except Exception:
                traceback.print_exc()
            finally:
                LOCK.release()

# HERO는 실제 wall-clock, 봇 전용 테이블은 독립 가상시계다.
# 55분 플레이 + 5분 브레이크가 기본이며 테스트에서는 env로만 축소할 수 있다.
PLAY_WINDOW_SECONDS = max(
    60, int(float(os.environ.get('T2_PLAY_WINDOW_SECONDS', '3300'))))
BREAK_SECONDS = max(
    0, int(float(os.environ.get('T2_BREAK_SECONDS', '300'))))
VCLOCK_CHUNK_SECONDS = max(
    15, int(float(os.environ.get('T2_VCLOCK_CHUNK_SECONDS', '120'))))

def _clock_values(st, now):
    fd = st.get('field') or {}
    if st.get('tournament_id'):
        elapsed = max(0.0, now - st['tournament_started_at'])
        return _TS.active_seconds(elapsed), elapsed
    if 'ui_clock_started_at' not in st:
        seconds = fd.get('virtual_play_seconds')
        return seconds, None if seconds is None else seconds + st.get('ui_break_seconds', 0)
    elapsed = max(0.0, now - st['ui_clock_started_at'])
    paused = st.get('ui_clock_paused_seconds', 0.0)
    if st.get('ui_break_pending'):
        # 5분이 끝났어도 봇 동기화가 늦으면 추가 대기까지 전부 브레이크다.
        paused += max(0.0, now - st.get('ui_break_started_at', now))
    return max(0.0, elapsed - paused), elapsed


def _sync_clock(st, now=None):
    now = time.time() if now is None else now
    fd = st.get('field') or {}
    if fd.get('virtual_play_seconds') is None:
        return
    if st.get('tournament_id'):
        active, elapsed = _clock_values(st, now)
        fd['virtual_play_seconds'] = active
        cycles, phase = divmod(elapsed, 3600.0)
        st['ui_next_break'] = (cycles + 1) * 3300.0
        if phase >= 3300 and st.get('hand_seed') is None:
            st['ui_break_pending'] = True
            st['ui_break_until'] = st['tournament_started_at'] + (cycles + 1) * 3600
            st['ui_break_started_at'] = st['ui_break_until'] - 300
            st['ui_break_at'] = active
        elif phase < 3300:
            st['ui_break_pending'] = False
            st.pop('ui_break_at', None)
        return
    # Upgrade an existing minute-based game without resetting its elapsed time.
    if 'ui_clock_started_at' not in st:
        st['ui_clock_started_at'] = now - fd['virtual_play_seconds'] - st.get('ui_break_seconds', 0)
        st['ui_clock_paused_seconds'] = st.get('ui_break_seconds', 0)
        if st.get('ui_break_pending'):
            st['ui_break_started_at'] = now
    fd['virtual_play_seconds'] = _clock_values(st, now)[0]


def _ui_timing(st, now=None):
    now = time.time() if now is None else now
    active, elapsed = _clock_values(st, now)
    fd = st.get('field') or {}
    minutes = fd.get('level_minutes')
    deadline = st.get('ui_action_deadline')
    next_break = (
        st.get('ui_break_at')
        if st.get('ui_break_pending') and st.get('ui_break_at') is not None
        else st.get('ui_next_break', PLAY_WINDOW_SECONDS)
    )
    level_remaining = None
    if active is not None and minutes:
        period = float(minutes) * 60.0
        fallback_level = 1 + int(max(0.0, float(active)) // period)
        level_no = max(1, int(fd.get('level') or fallback_level))
        used = max(0.0, float(active) - (level_no - 1) * period)
        level_remaining = int(math.ceil(max(0.0, period - used)))
    return {'scheduled_tournament': bool(st.get('tournament_id')),
            'elapsed_seconds': None if elapsed is None else int(elapsed),
            'active_seconds': None if active is None else int(active),
            'level_minutes': minutes,
            'level_remaining_seconds': level_remaining,
            'session_remaining_seconds': None if active is None else max(0, int(math.ceil(float(next_break) - active))),
            'break_remaining': max(0, int(math.ceil(st.get('ui_break_until', 0) - now))),
            'action_deadline_ms': None if deadline is None else int(float(deadline) * 1000),
            'action_remaining': None if deadline is None else max(0, int(math.ceil(float(deadline) - now))),
            'action_token': st.get('ui_action_token'),
            # 시간 규칙 필드. 이 함수만 떼어 실행하는 검증(verify_clock_ui)에서도 동작하도록
            # 전역이 없으면 꺼진 것으로 본다.
            'timing_on': globals().get('TIMING_ON', False),
            'server_now_ms': int(now * 1000),
            'action_started_ms': (None if st.get('ui_action_started_at') is None
                                  else int(float(st['ui_action_started_at']) * 1000)),
            'action_base_deadline_ms': (None if st.get('ui_action_base_deadline') is None
                                        else int(float(st['ui_action_base_deadline']) * 1000)),
            'hero_time_bank': (_hero_clock_params(st)[1]
                               if globals().get('TIMING_ON', False) and st.get('field') else None),
            'bot_ready_at_ms': (None if st.get('ui_bot_ready_at') is None
                                else int(float(st['ui_bot_ready_at']) * 1000)),
            'bot_schedule': [e for e in (st.get('ui_bot_schedule') or [])
                             if (e.get('act_at_ms') or e.get('at_ms') or 0) > int(now * 1000)]}

ACTIONS = {'fold', 'check', 'call', 'bet', 'raise', 'allin'}
HERO_ACTION_SECONDS = min(120.0, max(1.0, float(os.environ.get('T2_HERO_ACTION_SECONDS', '15'))))

# ---------- 시간 규칙(timing.py, TIME_SYSTEM_IMPLEMENTATION_DESIGN T5·T6) ----------
# T7: 기본 ON(timing.mode()). T2_TIMING_V1=off 일 때만 예전 고정 경로(HERO 15초, 봇 1.5초 템포,
# 액션별 고정비용 가상시간)로 돌아간다 — 호환/fallback 경로로만 남긴다.
TIMING_ON = TMG.mode() != 'off'
STREET_GAP_SECONDS = TMG.STREET_SECONDS   # 사람 테이블 보드 공개 기계 시간(봇 테이블과 같은 값)


def _hero_clock_params(st):
    """HERO 시계: 포맷 기본 초 + 누적 타임뱅크(pid 를 따라감)."""
    fd = st.get('field') or {}
    base = TMG.action_seconds(fd.get('fmt', 'standard'))
    # 검증 전용 덮어쓰기(시간 규칙이 켜져 있을 때만 여기까지 온다).
    if os.environ.get('T2_TIMING_TEST_BASE'):
        base = float(os.environ['T2_TIMING_TEST_BASE'])
    hero = str(fd.get('hero_pid'))
    banks = fd.get('time_banks') or {}
    if hero not in banks and os.environ.get('T2_TIMING_TEST_BANK'):
        bank = float(os.environ['T2_TIMING_TEST_BANK'])
    else:
        bank = TMG.bank_get(banks, hero, fd.get('virtual_play_seconds'))
    return base, bank, hero


def _settle_hero_bank(st, now, timed_out=False):
    """HERO 결정 하나의 타임뱅크 정산. 사람도 봇과 같은 timing.settle 규칙."""
    if not TIMING_ON or st.get('ui_action_started_at') is None:
        return
    base, bank, hero = _hero_clock_params(st)
    elapsed = max(0.0, float(now) - float(st['ui_action_started_at']))
    res = TMG.settle(base + bank + 1.0 if timed_out else elapsed, base, bank)
    TMG.bank_put(st['field'].setdefault('time_banks', {}), hero, res['bank_left'],
                 st['field'].get('virtual_play_seconds'))
    st.pop('ui_action_started_at', None)
    st.pop('ui_action_base_deadline', None)


class _BotSchedule:
    """사람 테이블 봇 액션의 절대 예정 시각. 엔진은 즉시 계산하고 화면 재생만 이 시각을 따른다.

    봇 결정의 시계는 직전 이벤트가 끝난 시각에 시작하고, 사람과 같은 규칙으로 흐른 시간(elapsed)
    뒤에 행동한다. 보드 공개는 STREET_GAP_SECONDS. 다음 HERO 결정은 마지막 예정 시각 뒤에만 시작한다.
    """
    def __init__(self, start):
        self.cursor = float(start)
        self.events = []

    def stamp(self, event):
        if event.get('kind') == 'street':
            self.cursor += STREET_GAP_SECONDS
            event['at_ms'] = int(self.cursor * 1000)
        elif event.get('timing'):
            t = event['timing']
            started = self.cursor
            act = started + float(t['elapsed'])
            event['clock_started_ms'] = int(started * 1000)
            event['act_at_ms'] = int(act * 1000)
            event['base_deadline_ms'] = int((started + float(t['base'])) * 1000)
            event['bank_deadline_ms'] = int((started + float(t['base'])
                                             + float(t['bank_before'])) * 1000)
            self.cursor = act
        self.events.append({k: event.get(k) for k in (
            'kind', 'seat', 'street', 'action', 'amount', 'at_ms', 'clock_started_ms',
            'act_at_ms', 'base_deadline_ms', 'bank_deadline_ms') if event.get(k) is not None})
        return event

    def save(self):
        st = L.load()
        st['ui_bot_ready_at'] = self.cursor
        st['ui_bot_schedule'] = self.events
        L.save(st)


# 새 핸드의 봇 시계는 딜·블라인드 기계 시간(timing.DEAL_SECONDS 7.5초) 뒤에 시작한다.
# 봇 테이블 mechanical 의 딜 값과 같고, 브라우저 실측 화면 딜+블라인드 애니메이션(7.0~7.5초)에 맞춘 값이다.
HAND_START_SECONDS = TMG.DEAL_SECONDS


def _step_sched(action=None, amount=0, on_bot_action=None):
    """_step 과 같지만, 시간 규칙이 켜져 있으면 이번 호출의 봇 액션에 예정 시각을 붙여 저장한다.

    새 핸드를 딜하는 경로(/api/new, /api/state, 스트림의 '다음 핸드', 서버 tick)도 모두 여기를 탄다 —
    첫 핸드만 예정표 없이 고정 템포로 재생되는 예외를 두지 않는다.
    """
    if not TIMING_ON:
        return _step(action, amount, on_bot_action=on_bot_action)
    try:
        new_hand = L.load().get('hand_seed') is None
    except Exception:
        new_hand = False
    sched = _BotSchedule(time.time() + (HAND_START_SECONDS if new_hand else 0.0))

    def _cb(event):
        sched.stamp(event)
        if on_bot_action is not None:
            on_bot_action(event)
    r = _step(action, amount, on_bot_action=_cb)
    sched.save()
    return r


def _arm_action_clock(token, now=None):
    """Start one server-authoritative clock when the HERO action bar is actually shown.

    Re-arming the same token never extends the deadline, so reload/re-render cannot
    buy extra time. A new engine token gets a fresh clock only when its action bar opens.
    """
    global _last
    now = time.time() if now is None else now
    current = _token()
    view = ((_last or {}).get('view') or {})
    if token != current or view.get('type') != 'decision':
        raise ValueError('현재 히어로 액션 차례가 아닙니다.')

    st = L.load()
    if st.get('ui_action_token') != current or st.get('ui_action_deadline') is None:
        st['ui_action_token'] = current
        if TIMING_ON:
            # 봇 예정표가 끝나기 전에는 HERO 시계가 시작하지 않는다(서버 권위).
            started = max(float(now), float(st.get('ui_bot_ready_at') or 0.0))
            base, bank, _ = _hero_clock_params(st)
            st['ui_action_started_at'] = started
            st['ui_action_base_deadline'] = started + base
            st['ui_action_deadline'] = started + base + bank
        else:
            st['ui_action_deadline'] = now + HERO_ACTION_SECONDS
        L.save(st)
    return _ui_timing(st, now)


def _timeout_action():
    """Prefer literal fold; only free-check when this decision exposes no fold action."""
    legal = (((_last or {}).get('view') or {}).get('legal') or {})
    if legal.get('fold'):
        return 'fold'
    if legal.get('check'):
        return 'check'
    return 'fold'

# UI motion acknowledgement gate.
# The gameplay request holds LOCK while the engine is in a hand. ACK must bypass
# that LOCK, otherwise the stream waits for an ACK that is queued behind itself.
STREAM_LOCK = threading.Lock()
STREAMS = {}
STREAM_ACK_TIMEOUT = float(os.environ.get('T2_UI_ACK_TIMEOUT', '15'))


def _stream_gate_open():
    sid = secrets.token_hex(12)
    state = {'cond': threading.Condition(), 'acked': 0, 'closed': False}
    with STREAM_LOCK:
        STREAMS[sid] = state
    return sid


def _stream_gate_ack(sid, seq):
    with STREAM_LOCK:
        state = STREAMS.get(str(sid))
    if state is None:
        return False
    with state['cond']:
        if int(seq) > int(state['acked']):
            state['acked'] = int(seq)
        state['cond'].notify_all()
    return True


def _stream_gate_wait(sid, seq):
    with STREAM_LOCK:
        state = STREAMS.get(str(sid))
    if state is None:
        return False
    with state['cond']:
        ok = state['cond'].wait_for(
            lambda: state['closed'] or int(state['acked']) >= int(seq),
            timeout=max(1.0, STREAM_ACK_TIMEOUT))
    COUNT['motion_ack' if ok else 'motion_ack_timeout'] += 1
    return ok


def _stream_gate_close(sid):
    with STREAM_LOCK:
        state = STREAMS.pop(str(sid), None)
    if state is None:
        return
    with state['cond']:
        state['closed'] = True
        state['cond'].notify_all()

def _lobby_payload():
    """UI-only tournament catalog; formats.py remains the rules source."""
    bb0 = int(BLINDS[0][2]) if BLINDS else 200
    tournaments = []
    for key in FM.names():
        f = FM.get(key)
        tournaments.append({
            'key': key,
            'name': f['name'],
            'start_bb': int(f['start_bb']),
            'start_stack': int(f['start_bb']) * bb0,
            'hands_per_level': int(f['hpl']),
            'level_minutes': FM.level_minutes(key),
            'seats': int(f['seats']),
            'itm_frac': float(f['itm_frac']),
            'reentry': bool(f['reentry']),
            'buyin_level': float(f['buyin_level']),
            'payout_flat': float(f['payout_flat']),
        })

    current = None
    if os.path.exists(L.ST):
        try:
            st = L.load()
            f = L._load_field(st['field'])
            hero = f.players.get(f.hero_pid)
            fmt = getattr(f, 'fmt', {}) or {}
            current = {
                'fmt': fmt.get('key', FM.DEFAULT),
                'name': fmt.get('name', FM.get().get('name')),
                'entries': int(f.entries),
                'remaining': int(f.remaining()),
                'hand_no': int(f.hand_no),
                'level': int(f.level),
        'level_minutes': getattr(f, 'level_minutes', None),
        'virtual_clock': getattr(f, 'virtual_play_seconds', None) is not None,
                'stack': int((hero or {}).get('stack', 0)),
                'busted': bool(st.get('busted')),
                'rank': st.get('rank'),
            }
        except Exception:
            current = {'error': 'current_state_unreadable'}
    payload = ECONOMY.catalog()
    payload['current'] = current
    return payload


def _tournament_payload():
    """현재 대회 공개 정보 + 전체 스택 순위.

    전략용 hidden persona/read/hand 정보는 절대 내보내지 않는다.
    """
    if not os.path.exists(L.ST):
        return {'no_game': True}

    st = L.load()
    f = L._load_field(st['field'])
    status = f.status()
    sb, bb = f.blinds()
    fmt = getattr(f, 'fmt', {}) or {}
    hero = f.players.get(f.hero_pid) or {}
    mj = CTX.money_jump_context(f.remaining(), f.itm, f.payouts)

    # 다음 실제 상금 변화들. 같은 상금 구간은 context 함수가 건너뛴다.
    jumps = []
    probe = int(f.remaining())
    seen = set()
    for _ in range(8):
        row = CTX.money_jump_context(probe, f.itm, f.payouts)
        nr = row.get('next_rank')
        if nr is None or nr in seen:
            break
        seen.add(nr)
        jumps.append({
            'rank': int(nr),
            'prize_pct': float(row.get('next_prize') or 0.0),
            'jump_pct': float(row.get('next_jump') or 0.0),
            'players_to_jump': int(row.get('players_to_jump') or 0),
        })
        probe = int(nr)

    # 각 테이블의 '다음 핸드 기준' 포지션. dead BTN/SB도 같은 엔진에서 나온다.
    pos_by_pid = {}
    for tb in f.tables.values():
        if tb.n() < 2:
            continue
        try:
            lay = tb.hand_layout()
        except Exception:
            continue
        for seat, pos in (lay.get('pos') or {}).items():
            p = tb.player_at(seat)
            if p is not None:
                pos_by_pid[p['pid']] = pos

    alive = sorted(
        (p for p in f.players.values() if p.get('stack', 0) > 0),
        key=lambda p: (-int(p.get('stack', 0)), int(p['pid'])))
    alive_rank = {p['pid']: i + 1 for i, p in enumerate(alive)}

    rows = []
    for p in f.players.values():
        pid = int(p['pid'])
        stack = int(p.get('stack', 0) or 0)
        live = stack > 0
        finish_rank = None
        if not live and pid in f.busted_order:
            finish_rank = int(f.rank_of(pid))
        table_id = p.get('table')
        seat = None
        if table_id is not None and table_id in f.tables:
            seat = f.tables[table_id].seat_of(pid)
        rows.append({
            'pid': pid,
            'hero': pid == f.hero_pid,
            'alive': live,
            'chip_rank': alive_rank.get(pid),
            'finish_rank': finish_rank,
            'stack': stack,
            'bb': round(stack / max(1.0, float(bb)), 1),
            'table': table_id,
            'seat': seat,
            'pos': pos_by_pid.get(pid),
        })

    rows.sort(key=lambda x: (
        0 if x['alive'] else 1,
        x['chip_rank'] if x['chip_rank'] is not None else 10**9,
        x['finish_rank'] if x['finish_rank'] is not None else 10**9,
        x['pid']))

    ante = bb if int(f.level) >= int(fmt.get('ante_from', 10**9)) else 0

    return {
        'format': fmt.get('name') or fmt.get('key') or '대회',
        'format_key': fmt.get('key'),
        'entries': int(f.entries),
        'remaining': int(f.remaining()),
        'itm': int(f.itm),
        'to_itm': int(status.get('to_itm') or 0),
        'bubble': bool(status.get('bubble')),
        'hand_no': int(f.hand_no),
        'level': int(f.level),
        'sb': int(sb),
        'bb': int(bb),
        'ante': int(ante),
        'tables': int(len(f.tables)),
        'avg_stack': int(round(float(status.get('avg') or 0))),
        'avg_bb': round(float(status.get('avg') or 0) / max(1.0, float(bb)), 1),
        'leader': int(status.get('leader') or 0),
        'hero_pid': int(f.hero_pid),
        'hero_rank': status.get('rank'),
        'hero_stack': int(hero.get('stack', 0) or 0),
        'hero_bb': round(float(hero.get('stack', 0) or 0) / max(1.0, float(bb)), 1),
        'in_money': bool(mj.get('in_money')),
        'current_prize_pct': float(mj.get('current_prize') or 0.0),
        'next_rank': mj.get('next_rank'),
        'next_prize_pct': float(mj.get('next_prize') or 0.0),
        'next_jump_pct': float(mj.get('next_jump') or 0.0),
        'players_to_jump': int(mj.get('players_to_jump') or 0),
        'money_jumps': jumps,
        'standings': rows,
        **_economy_receipt(st),
    }


# ---------- 다른 테이블 정산을 결과 반환 뒤로 미룬다 ----------
# 비-HERO 테이블은 HERO 핸드가 끝난 뒤가 아니라 **같은 라운드 시작 시점**에
# 별도 프로세스에서 시작한다. 워커는 비-HERO 테이블만 진행하고
# bust 수거/밸런싱은 하지 않는다. 두 쪽 결과가 합쳐진 뒤 메인에서 한 번만 한다.
#
# 다른 테이블들끼리는 기존 step_others 순서를 그대로 유지한다. 병렬화 경계는
# HERO table vs all other tables 두 갈래뿐이다.
DEFER = os.environ.get('T2_UI_DEFER', '1') != '0'
POOL = None
PENDING = {'future': None, 'base_key': None}

# v2: 55분 세션을 여러 짧은 계산 chunk로 계속 앞서 계산한다.
# events는 확정 전 메모리 버퍼이며 상태 파일에는 쓰지 않는다.
VCLOCK_LOCK = threading.Lock()
VCLOCK = {
    'future': None,
    'events': {},
    'cursors': {},
    'coverage': 0.0,
    'barrier_time': None,
    'barrier_kind': None,
    'spec_field': None,
    'segment_target': None,
    'session_end': None,
    'started_at': None,
}

COUNT = {'attempt': 0, 'hit': 0, 'mismatch': 0, 'fallback': 0,
         'single_table_skip': 0, 'worker_exception': 0, 'worker_join': 0, 'pool_unavailable': 0,
         'round_start': 0, 'round_restart': 0,
         'round_ready_before_finish': 0, 'round_ready_after_finish': 0,
         'vclock_chunk_start': 0, 'vclock_chunk_done': 0,
         'vclock_barrier': 0,
         'motion_ack': 0, 'motion_ack_timeout': 0,
         # 다음 라운드 직전까지도 worker가 안 끝나 실제로 기다린 시간.
         'worker_wait_ms': 0, 'worker_wait_max_ms': 0}


def _count_resume():
    """live2.resume_others 의 판정을 센다. 엔진은 고치지 않는다."""
    _orig = L.resume_others
    def wrapped(st, others=None):
        how = _orig(st, others)
        if how:
            COUNT[how] = COUNT.get(how, 0) + 1
        return how
    L.resume_others = wrapped


_count_resume()


def _pool():
    global POOL
    if not DEFER:
        return None
    if POOL is None:
        try:
            POOL = ProcessPoolExecutor(max_workers=1)
        except Exception:
            COUNT['pool_unavailable'] += 1
            return None
    return POOL


def _clear_worker():
    PENDING['future'] = None
    PENDING['base_key'] = None


def _vclock_enabled(st):
    return bool(st and st.get('vclock_session_v2')
                and (st.get('field') or {}).get('virtual_play_seconds') is not None)


def _vclock_session_end(st):
    if st.get('ui_break_pending') and st.get('ui_break_at') is not None:
        return float(st['ui_break_at'])
    return float(st.get('ui_next_break', PLAY_WINDOW_SECONDS))


def _vclock_refresh_settle_target(st, now=None):
    """대기 중 settlement의 HERO 확정선을 현재 실제 초까지 전진시킨다."""
    if not st or not st.get('vclock_settle_pending'):
        return
    _sync_clock(st, now)
    active = float((st.get('field') or {}).get('virtual_play_seconds', 0.0) or 0.0)
    if st.get('ui_break_pending') and st.get('ui_break_at') is not None:
        active = min(active, float(st['ui_break_at']))
    st['vclock_settle_target'] = active


def _vclock_other_clock_floor(field_dump):
    try:
        hero_tid, other_tids, _ = L._round_owners(field_dump)
    except Exception:
        return 0.0
    if not other_tids:
        return float((field_dump or {}).get('virtual_play_seconds') or 0.0)
    vals = []
    for tid in other_tids:
        row = (field_dump.get('tables') or {}).get(str(tid)) or {}
        vals.append(float(row.get('vclock_seconds',
                                  field_dump.get('virtual_play_seconds', 0.0)) or 0.0))
    return min(vals) if vals else 0.0


def _vclock_reset_locked():
    fut = VCLOCK.get('future')
    if fut is not None and not fut.done():
        try:
            fut.cancel()
        except Exception:
            pass
    VCLOCK.update({
        'future': None,
        'events': {},
        'cursors': {},
        'coverage': 0.0,
        'barrier_time': None,
        'barrier_kind': None,
        'spec_field': None,
        'segment_target': None,
        'session_end': None,
        'started_at': None,
    })


def _vclock_reset():
    with VCLOCK_LOCK:
        _vclock_reset_locked()


def _vclock_init_locked(st):
    session_end = _vclock_session_end(st)
    if (VCLOCK.get('spec_field') is not None
            and VCLOCK.get('session_end') == session_end):
        return
    _vclock_reset_locked()
    field = L._copy_field(st['field'])
    VCLOCK['spec_field'] = field
    VCLOCK['session_end'] = session_end
    VCLOCK['coverage'] = _vclock_other_clock_floor(field)


def _vclock_submit_next_locked():
    if VCLOCK.get('future') is not None:
        return
    if VCLOCK.get('barrier_time') is not None:
        return
    field = VCLOCK.get('spec_field')
    session_end = VCLOCK.get('session_end')
    if field is None or session_end is None:
        return
    coverage = float(VCLOCK.get('coverage') or 0.0)
    if coverage >= float(session_end) - 1e-9:
        return
    p = _pool()
    if p is None:
        return
    target = min(float(session_end), coverage + VCLOCK_CHUNK_SECONDS)
    VCLOCK['segment_target'] = target
    VCLOCK['started_at'] = time.monotonic()
    COUNT['attempt'] += 1
    COUNT['vclock_chunk_start'] += 1
    try:
        VCLOCK['future'] = p.submit(
            L.compute_vclock_ahead, field, target, session_end)
    except Exception:
        COUNT['worker_exception'] += 1
        VCLOCK['future'] = None


def _vclock_accept_locked(wait=False):
    fut = VCLOCK.get('future')
    if fut is None:
        _vclock_submit_next_locked()
        fut = VCLOCK.get('future')
        if fut is None:
            return False
    if not wait and not fut.done():
        return False
    try:
        out = fut.result()
    except Exception:
        COUNT['worker_exception'] += 1
        traceback.print_exc()
        VCLOCK['future'] = None
        return False
    VCLOCK['future'] = None
    COUNT['vclock_chunk_done'] += 1
    if not isinstance(out, dict) or out.get('mode') != L.VCLOCK_AHEAD_MODE:
        COUNT['mismatch'] += 1
        return False

    for tid, row in (out.get('tables') or {}).items():
        dst = VCLOCK['events'].setdefault(str(tid), [])
        dst.extend(copy.deepcopy(row.get('events') or []))
        VCLOCK['cursors'].setdefault(str(tid), 0)

    b = out.get('barrier_time')
    if b is not None:
        b = float(b)
        old = VCLOCK.get('barrier_time')
        if old is None or b < float(old):
            VCLOCK['barrier_time'] = b
            VCLOCK['barrier_kind'] = out.get('barrier_kind')
        COUNT['vclock_barrier'] += 1

    VCLOCK['coverage'] = max(
        float(VCLOCK.get('coverage') or 0.0),
        float(out.get('coverage') or 0.0))

    if VCLOCK.get('barrier_time') is None and out.get('end_field') is not None:
        VCLOCK['spec_field'] = L._copy_field(out['end_field'])
        _vclock_submit_next_locked()
    return True


def _vclock_ready_locked(target):
    target = float(target)
    b = VCLOCK.get('barrier_time')
    if b is not None and VCLOCK.get('barrier_kind') == 'hand_for_hand':
        return float(b) <= target + 1e-9
    if b is not None and float(b) <= target + 1e-9:
        return True
    return float(VCLOCK.get('coverage') or 0.0) >= target - 1e-9


def _vclock_pump(st, wait=False, target=None):
    """완료 chunk를 버퍼에 붙이고 다음 chunk를 즉시 시작한다.

    현재 HERO 시각을 이미 따라잡았더라도 speculative worker는 멈추지 않는다.
    완료된 chunk는 수확해 다음 chunk를 잇고, 세션 끝/barrier까지 계속 앞서 간다.
    """
    if not _vclock_enabled(st):
        return True
    with VCLOCK_LOCK:
        _vclock_init_locked(st)
        if target is None:
            target = float(
                st.get('vclock_settle_target',
                       (st.get('field') or {}).get('virtual_play_seconds', 0.0))
                or 0.0)

        while True:
            # 목표가 이미 충족돼도 다음 speculative chunk는 항상 걸어 둔다.
            _vclock_submit_next_locked()
            fut = VCLOCK.get('future')

            # 지난 호출 사이 끝난 chunk가 있으면 즉시 수확하고 다음 chunk를 잇는다.
            if fut is not None and fut.done():
                _vclock_accept_locked(wait=False)
                continue

            if _vclock_ready_locked(target):
                return True

            # HERO가 앞서 버렸을 때만 필요한 coverage까지 기다린다.
            changed = _vclock_accept_locked(wait=wait)
            if _vclock_ready_locked(target):
                return True
            if not wait:
                return False
            if not changed and VCLOCK.get('future') is None:
                _vclock_submit_next_locked()
                if VCLOCK.get('future') is None:
                    return False


def _vclock_prepare_refill(st):
    """Read-only candidate search; the current hand's field is never changed."""
    with VCLOCK_LOCK:
        L.vclock_find_refill(
            st, VCLOCK.get('events') or {}, VCLOCK.get('cursors') or {},
            _clock_values(st, time.time())[0], VCLOCK.get('barrier_time'))


def _vclock_settle(st, wait=False):
    """Normal hands never await bot coverage or a replenishment candidate."""
    global _last
    if st.get('hand_seed') is not None:
        _vclock_pump(st, wait=False)
        _vclock_prepare_refill(st)
        L.save(st)
        return True, None

    pending = bool(st.get('vclock_settle_pending'))
    sync = L.vclock_needs_sync(st)
    if sync and not pending:
        # A completed H4H round is already settled. Start its next HERO hand;
        # the new round's bots must not be consumed before that hand finishes.
        _vclock_pump(st, wait=False)
        return True, None

    target = float((st.get('field') or {}).get('virtual_play_seconds') or 0.0)
    if st.get('ui_break_pending'):
        target = min(target, _vclock_session_end(st))
    fin = None
    if not sync and pending:
        # Close the HERO archive now. One slow bot chunk must not hold it open
        # across multiple HERO hands (nor overwrite pending_archive).
        fin = L.finalize_vclock_settle(st, independent_hero=True)

    ready = _vclock_pump(st, wait=bool(wait and sync), target=target)
    if not ready:
        return (False, None) if sync else (True, fin)

    _vclock_prepare_refill(st)
    with VCLOCK_LOCK:
        applied = L.apply_vclock_events(
            st, VCLOCK.get('events') or {}, VCLOCK.get('cursors') or {},
            target, VCLOCK.get('barrier_time'), independent_hero=not sync)
        VCLOCK['cursors'] = applied.get('cursors') or {}
        invalidated = bool(applied.get('invalidated'))

    fin = L.finalize_vclock_settle(
        st, notes=applied.get('notes') or [],
        bot_log=applied.get('bot_log') or '', independent_hero=not sync)
    if sync:
        st.pop('vclock_refill', None)
        L.save(st)

    if invalidated:
        _vclock_reset()
        _vclock_pump(L.load(), wait=False)

    if _last is not None:
        _last['busted'] = fin.get('busted')
        _last['rank'] = fin.get('rank')
        _last['remaining'] = fin.get('remaining')
        _last['status'] = fin.get('status')
    return True, fin


def _submit_parallel(field_dump, restart=False):
    """라운드 시작 스냅샷으로 비-HERO worker를 한 번만 시작한다."""
    if not DEFER:
        return
    try:
        _hero_tid, _other_tids, _other_pids = L._round_owners(field_dump)
    except Exception:
        _other_tids = None
    if _other_tids == []:
        # 파이널테이블은 HERO table 자체가 전체 필드다.
        COUNT['single_table_skip'] += 1
        _clear_worker()
        return
    key = L._others_key(field_dump)
    fut = PENDING.get('future')
    if fut is not None and PENDING.get('base_key') == key:
        return
    if fut is not None:
        # 서로 다른 라운드 worker가 겹치면 상태를 섞지 않는다.
        if not fut.done():
            return
        _clear_worker()

    p = _pool()
    if p is None:
        return
    COUNT['attempt'] += 1
    COUNT['round_restart' if restart else 'round_start'] += 1
    try:
        PENDING['future'] = p.submit(L.compute_others_parallel, field_dump)
        PENDING['base_key'] = key
        PENDING['started_at'] = time.monotonic()
    except Exception:
        COUNT['worker_exception'] += 1
        _clear_worker()


def _peek_others():
    """완료됐을 때만 결과를 본다. 아직 진행 중이면 절대 기다리지 않는다."""
    fut = PENDING.get('future')
    if fut is None or not fut.done():
        return None
    try:
        return fut.result()
    except Exception:
        COUNT['worker_exception'] += 1
        traceback.print_exc()
        _clear_worker()
        return None


def _take_others(wait):
    """다음 라운드 직전에는 필요하면 join하고, 그 외에는 non-blocking."""
    fut = PENDING.get('future')
    if fut is None:
        return None
    if not wait and not fut.done():
        return None
    COUNT['worker_join'] += 1
    _t = time.time()
    try:
        r = fut.result()
        _ms = int((time.time() - _t) * 1000)
        COUNT['worker_wait_ms'] += _ms
        COUNT['worker_wait_max_ms'] = max(COUNT['worker_wait_max_ms'], _ms)
        return r
    except Exception:
        COUNT['worker_exception'] += 1
        traceback.print_exc()
        return None
    finally:
        _clear_worker()


def _ensure_round_worker(st):
    """서버가 핸드 중간에 재시작됐어도 현재 round worker를 복구한다."""
    if not DEFER or not st or st.get('others_pending'):
        return
    if st.get('hand_seed') is None:
        return
    if PENDING.get('future') is None:
        _submit_parallel(st['field'], restart=True)


def _kick_pending_worker():
    """HERO 결과가 먼저 끝났는데 worker가 없을 때의 crash/fallback 안전망."""
    if not DEFER or PENDING.get('future') is not None:
        return
    try:
        st = L.load()
    except Exception:
        return
    if not st.get('others_pending'):
        return
    base = st.get('others_base')
    if st.get('others_mode') == L.PARALLEL_TABLES_MODE and base:
        _submit_parallel(base, restart=True)
        return
    p = _pool()
    if p is None:
        return
    COUNT['attempt'] += 1
    try:
        PENDING['future'] = p.submit(L.compute_others, st['field'])
        PENDING['base_key'] = L._others_key(st['field'])
        PENDING['started_at'] = time.monotonic()
    except Exception:
        COUNT['worker_exception'] += 1
        _clear_worker()


def _step(action=None, amount=0, on_bot_action=None):
    """HERO 진행과 비-HERO round worker를 병렬로 조정한다."""
    st0 = None
    try:
        if os.path.exists(L.ST):
            st0 = L.load()
    except Exception:
        st0 = None

    if st0 is not None:
        _sync_clock(st0)
    vclock = _vclock_enabled(st0)

    if st0 and vclock and st0.get('vclock_settle_pending'):
        _vclock_refresh_settle_target(st0)

    if st0 is not None:
        L.save(st0)

    if st0 and st0.get('ui_break_pending'):
        if _ui_timing(st0)['break_remaining']:
            raise ValueError('브레이크가 끝난 뒤 다음 핸드를 시작할 수 있습니다.')

        if vclock and st0.get('vclock_settle_pending'):
            ok, _ = _vclock_settle(st0, wait=True)
            if not ok:
                raise ValueError('다른 테이블 가상시계 동기화가 아직 끝나지 않았습니다.')
            st0 = L.load()

        resume_now = time.time()
        paused = max(0.0, resume_now - st0.get('ui_break_started_at', resume_now))
        st0['ui_clock_paused_seconds'] = (
            st0.get('ui_clock_paused_seconds', 0) + paused)
        st0['ui_break_seconds'] = st0.get('ui_break_seconds', 0) + paused
        st0['ui_break_pending'] = False
        st0.pop('ui_break_at', None)
        L.save(st0)

    vclock = _vclock_enabled(st0)
    others = None

    if vclock and st0 is not None:
        if st0.get('vclock_settle_pending') or st0.get('hand_seed') is None:
            _vclock_refresh_settle_target(st0)
            L.save(st0)
            ok, _ = _vclock_settle(st0, wait=True)
            if not ok:
                raise ValueError('다른 테이블 가상시계 동기화가 아직 끝나지 않았습니다.')
            st0 = L.load()
        _vclock_pump(st0, wait=False)
        kw = {'vclock_others': True}
    else:
        if DEFER and st0 is not None:
            if st0.get('others_pending'):
                # legacy round worker: 다음 라운드 전에는 settlement를 끝낸다.
                others = _take_others(wait=True)
            else:
                _ensure_round_worker(st0)
                others = _peek_others()
        kw = {'defer_others': True, 'others': others} if DEFER else {}
        if DEFER:
            kw['on_round_start'] = _submit_parallel

    if on_bot_action is not None:
        kw['on_bot_action'] = on_bot_action

    r = L.step(action, amount, **kw) if action is not None else L.step(**kw)

    if DEFER and not vclock:
        try:
            st1 = L.load()
        except Exception:
            st1 = None

        if r.get('done') and st1 is not None:
            if st1.get('others_pending'):
                # final action 계산 중 worker가 끝났다면 결과 화면을 막지 않고
                # 지금 즉시 merge한다. 아직이면 worker는 그대로 계속 돈다.
                ready = _peek_others()
                if ready is not None:
                    L.resume_others(st1, ready)
                    COUNT['round_ready_after_finish'] += 1
                    _clear_worker()
                else:
                    _kick_pending_worker()
            else:
                if others is not None:
                    COUNT['round_ready_before_finish'] += 1
                _clear_worker()

    st = L.load()
    _sync_clock(st)
    now = time.time()

    if r.get('done'):
        active = (st.get('field') or {}).get('virtual_play_seconds')
        remaining = sum(
            p.get('stack', 0) > 0
            for p in st['field']['players'].values())
        threshold = float(st.get('ui_next_break', PLAY_WINDOW_SECONDS))
        if (not st.get('tournament_id') and active is not None and float(active) >= threshold
                and not st.get('busted') and remaining > 1):
            # HERO 핸드가 55:00을 넘겨 끝나도 다음 세션으로 초과분을 넘기지 않는다.
            overshoot = max(0.0, float(active) - threshold)
            st['ui_clock_paused_seconds'] = (
                st.get('ui_clock_paused_seconds', 0.0) + overshoot)
            st['field']['virtual_play_seconds'] = threshold
            st['ui_break_started_at'] = now
            st['ui_break_until'] = now + BREAK_SECONDS
            st['ui_break_pending'] = True
            st['ui_break_at'] = threshold
            st['ui_next_break'] = threshold + PLAY_WINDOW_SECONDS

        if vclock:
            # Fix elimination time at the HERO result, not at a later worker
            # completion/readiness poll (the clock keeps flowing while waiting).
            L._vclock_record_busts(st, st['field']['players'],
                                   st['field'].get('virtual_play_seconds') or 0)
            st['vclock_settle_target'] = float(
                st.get('ui_break_at')
                if st.get('ui_break_pending') and st.get('ui_break_at') is not None
                else (st.get('field') or {}).get('virtual_play_seconds', 0.0))
        if st.get('tournament_id'):
            _sync_clock(st, now)
    L.save(st)

    if vclock and r.get('done'):
        ok, fin = _vclock_settle(st, wait=False)
        if ok and fin:
            r['busted'] = fin.get('busted')
            r['rank'] = fin.get('rank')
            r['status'] = fin.get('status')
    return r

WEB = os.path.join(D, 'web')          # setup_run_dir.sh 가 ui/web 을 여기로 복사한다
# 확장자별 타입. mimetypes 에 없거나 OS 마다 다른 것만 직접 못박는다.
MIME = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
        '.webmanifest': 'application/manifest+json; charset=utf-8',
        '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon'}


def _resolve(path):
    """URL 경로를 web/ 아래 실제 파일로. 밖으로 나가면 None."""
    rel = posixpath.normpath(urllib.parse.unquote(path))
    if rel in ('/', '', '.'):
        rel = '/index.html'
    rel = rel.lstrip('/')
    full = os.path.realpath(os.path.join(WEB, rel))
    root = os.path.realpath(WEB)
    if full != root and not full.startswith(root + os.sep):
        return None                    # ../ 로 폴더를 빠져나가려는 요청
    return full if os.path.isfile(full) else None



def _archive_status():
    """아카이브 출처 metadata. **'없음'과 '모호'를 가른다.**

    빈 목록 하나로 접으면 사용자가 "기록이 없다"와 "옛 공유 기록이 있는데
    이 세션 것인지 증명할 수 없어 안 쓴다"를 구분할 수 없다. 두 번째는
    데이터가 어딘가에 있다는 뜻이라 대응이 완전히 다르다.
    """
    r = _SP.resolve_read('archive')
    out = {'archive_source': r['source'], 'archive_warning': None,
           'legacy_archive': None}
    if r['source'] == _SP.SRC_LEGACY_AMBIGUOUS:
        out['legacy_archive'] = os.path.basename(r['legacy_path'] or '')
        out['archive_warning'] = (
            '옛 공유 아카이브(%s)가 있으나 이 상태의 기록인지 증명할 수 없어 '
            '사용하지 않았습니다. 과거에는 모든 custom state 가 이 한 파일에 '
            '썼습니다.' % out['legacy_archive'])
    return out


def _public_history():
    """현재 토너먼트의 완료 핸드를 UI용으로 안전하게 반환한다.

    중요:
    - hero 홀카드는 항상 허용
    - 상대 카드는 실제 shown_hole 만 허용
    - archive 의 top-level/result hole 전체는 절대 반환하지 않는다
    """
    # 엔진 상태의 namespace 를 그대로 따른다. UI 전용 아카이브를 만들지
    # 않는다. 예전에는 접미사 없는 이름을 고정으로 읽어서, T2_LIVE_STATE 를
    # 쓰는 세션을 띄우면 **다른 상태의 아카이브**를 보고 있었다.
    # 엔진 상태의 namespace 를 그대로 따른다. 옛 공유 `_alt` 는 **쓰지
    # 않는다** — 과거에는 모든 custom state 가 그 한 파일에 썼으므로 다른
    # 세션의 핸드가 섞여 있을 수 있다. 현재 핸드 기록에 섞어 보여주면
    # 화면상 구분이 불가능해진다.
    _r = _SP.resolve_read('archive')
    fn = _r['path']

    if not fn:
        return []

    out = []

    with open(fn, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                h = json.loads(line)
            except Exception:
                # 쓰는 순간의 마지막 불완전 행 등은 건너뛴다.
                continue

            r = h.get('result') or {}
            hand_no = h.get('hand_no')

            if hand_no is None or not isinstance(r, dict):
                continue

            hero = h.get('hero')

            # 실제 공개된 카드만 상대 카드로 전달한다.
            raw_shown = r.get('shown_hole') or {}
            shown = {}

            if isinstance(raw_shown, dict):
                for seat, cards in raw_shown.items():
                    if isinstance(cards, (list, tuple)):
                        shown[str(seat)] = list(cards)

            # hero_hole 이 결과에 없을 때만 내부 hole 에서
            # 'hero 자신의 카드만' 복구한다.
            hero_hole = r.get('hero_hole') or []

            if not hero_hole and hero is not None:
                raw_hole = h.get('hole') or {}

                if isinstance(raw_hole, dict):
                    hero_hole = (
                        raw_hole.get(str(hero))
                        or raw_hole.get(hero)
                        or []
                    )

            out.append({
                'type': 'result',
                'hand_no': hand_no,
                'hash': r.get('hash') or h.get('hash'),

                'hero_seat': hero,
                'hero_hole': list(hero_hole or []),

                'board': r.get('board') or h.get('board') or [],
                'pot': r.get('pot') or 0,
                'pots': r.get('pots') or [],

                'how': r.get('how'),
                'showdown': bool(r.get('showdown')),
                'allin_show': bool(r.get('allin_show')),

                'shown': shown,
                'show_order': r.get('show_order') or [],
                'mucked': r.get('mucked') or [],

                'winners': r.get('winners') or [],
                'main_winners': r.get('main_winners') or [],
                'best_five': r.get('best_five') or {},

                'pos': r.get('pos') or h.get('pos') or {},
                'stacks': r.get('stacks') or {},

                # UI 상세 기록에서 사용하는 필드
                'log': h.get('full_log') or [],
                'notes': h.get('notes') or []
            })

    def hand_key(x):
        try:
            return int(x.get('hand_no'))
        except Exception:
            return -1

    out.sort(key=hand_key, reverse=True)
    return out

def _hero_memos():
    """현재 대회의 사용자 봇 메모. 공개 관전 API에는 절대 섞지 않는다."""
    if not os.path.exists(L.ST):
        return {}

    st = L.load()
    raw = st.get('hero_memos') or {}
    out = {}

    if isinstance(raw, dict):
        for pid, memo in raw.items():
            txt = str(memo or '').strip()
            if txt:
                out[str(pid)] = txt

    return out


def _save_hero_memo(pid, memo):
    """pid 메모를 상태 파일에 저장하고, 아직 쓰기 전인 핸드 기록에도 반영한다."""
    if not os.path.exists(L.ST):
        raise RuntimeError('진행 중인 게임 없음')

    st = L.load()
    players = ((st.get('field') or {}).get('players') or {})
    key = str(pid)

    if key not in players:
        raise ValueError('현재 대회에 없는 플레이어 pid: %s' % key)

    memos = dict(st.get('hero_memos') or {})

    if memo:
        memos[key] = memo
    else:
        memos.pop(key, None)

    st['hero_memos'] = memos

    # 핸드 종료 직후 worker 정산을 기다리는 동안 메모를 고쳤다면,
    # pending_archive도 같은 값으로 맞춰야 방금 끝난 핸드에 최신 메모가 남는다.
    rec = st.get('pending_archive')
    if isinstance(rec, dict):
        seated = {
            str(v)
            for v in (rec.get('seat_pid') or {}).values()
        }

        if key in seated:
            hm = dict(rec.get('hero_memos') or {})
            if memo:
                hm[key] = memo
            else:
                hm.pop(key, None)
            rec['hero_memos'] = hm

    L.save(st)
    return dict(memos)


def _token():
    try:
        st = L.load()
    except Exception:
        return None
    return '%s:%d' % (st.get('hand_seed'), len(st.get('actions') or []))


def _wrap(r):
    """step()/finish() 반환값 중 UI에 필요한 값만 내보낸다."""
    out = {
        'done': bool(r.get('done')),
        'view': r.get('view')
    }

    if r.get('opening_view') is not None:
        out['opening_view'] = r.get('opening_view')

    if r.get('done'):
        out['busted'] = bool(r.get('busted'))
        out['rank'] = r.get('rank')
        out['bust_pending'] = bool(
            r.get('bust_pending')
        )

        try:
            fd = L.load().get('field') or {}

            out['remaining'] = sum(
                1
                for p in (fd.get('players') or {}).values()
                if (p.get('stack') or 0) > 0
            )

            out['entries'] = len(
                fd.get('players') or {}
            )

        except Exception:
            pass

    if r.get('game_over'):
        out['game_over'] = True
        out['won'] = bool(r.get('won'))
        out['busted'] = bool(r.get('busted'))
        out['rank'] = r.get('rank')

        if r.get('remaining') is not None:
            out['remaining'] = r.get('remaining')

        if r.get('entries') is not None:
            out['entries'] = r.get('entries')

    out['token'] = _token()
    if globals().get('TIMING_ON', False):
        try:
            _sst = L.load()
            out['bot_schedule'] = list(_sst.get('ui_bot_schedule') or [])
            out['bot_ready_at_ms'] = (None if _sst.get('ui_bot_ready_at') is None
                                      else int(float(_sst['ui_bot_ready_at']) * 1000))
            out['server_now_ms'] = int(time.time() * 1000)
        except Exception:
            pass

    # A decision deadline belongs to exactly one engine token. Once an action
    # changes the token (or the hand ends), remove it. The next decision is armed
    # only when the UI actually presents its action bar.
    try:
        st = L.load()
        if st.get('ui_action_token') is not None and st.get('ui_action_token') != out['token']:
            st.pop('ui_action_token', None)
            st.pop('ui_action_deadline', None)
            st.pop('ui_action_started_at', None)
            st.pop('ui_action_base_deadline', None)
            L.save(st)
        if st.get('tournament_id') and (out.get('view') or {}).get('type') == 'decision':
            if st.get('ui_decision_token') != out['token']:
                st['ui_decision_token'] = out['token']
                st['ui_decision_ready_at'] = time.time()
                L.save(st)
        out.update(_economy_receipt(st))
    except Exception:
        pass
    return out


def _game_over():
    st = L.load()
    f = L._load_field(st['field'])
    remaining = f.remaining()
    hero = f.players.get(f.hero_pid)
    busted = bool(st.get('busted')) or not hero or hero.get('stack', 0) <= 0
    won = bool(not busted and remaining <= 1)
    rank = 1 if won else st.get('rank')
    return {
        'done': True,
        'game_over': True,
        'won': won,
        'busted': busted,
        'rank': rank,
        'remaining': remaining,
        'entries': f.entries,
        'view': None,
        'token': _token(),
        **_economy_receipt(st),
    }


class H(BaseHTTPRequestHandler):
    def handle(self):
        # 브라우저가 응답 도중 탭을 닫거나 새로고침하면 BrokenPipe 가 난다.
        # 정상적인 잡음이라 트레이스백을 찍지 않는다.
        try:
            BaseHTTPRequestHandler.handle(self)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers(); self.wfile.write(b)

    def _send_bytes(self, code, body, ctype, extra_headers=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        # 개발 중에 고친 파일이 바로 반영되게 한다.
        # no-cache 는 '검증 후 재사용'이라 검증자(ETag 등)가 없으면 브라우저가
        # 옛 파일을 계속 쓰는 경우가 있었다. no-store 는 저장 자체를 막는다.
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, path, extra_headers=None):
        full = _resolve(path)
        if full is None:
            return self._send(404, {'error': 'not found'})
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext) or mimetypes.guess_type(full)[0] or 'application/octet-stream'
        try:
            with open(full, 'rb') as fp:
                body = fp.read()
        except OSError as e:
            return self._send(500, {'error': str(e)})
        return self._send_bytes(200, body, ctype, extra_headers)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def _stream_start(self):
        """봇 진행 이벤트를 계산 즉시 NDJSON으로 흘려보낸다."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

    def _stream_line(self, obj):
        try:
            b = (json.dumps(obj, ensure_ascii=False, default=str) + '\n').encode()
            self.wfile.write(b)
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError):
            # 클라이언트가 사라져도 엔진 계산/저장은 중단하지 않는다.
            return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header(
            'Access-Control-Allow-Headers',
            'Content-Type'
        )
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.end_headers()

    def do_GET(self):
        global _last, LAST_PLAY_PRESENCE
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == '/api/ready':
            LAST_PLAY_PRESENCE = time.time()
            # 워커가 아직 다른 테이블을 돌리는 중인가. 결과 화면이 이걸 보고
            # 정산이 끝난 뒤에 다음 핸드로 넘어간다 — 빈 로딩 화면을 없앤다.
            # LOCK 을 잡지 않는다. 잡으면 진행 중인 요청 뒤에 줄을 서게 된다.
            st = L.load() if os.path.exists(L.ST) else {}
            if _vclock_enabled(st):
                # 결정/애니메이션 중에도 완료 chunk를 이어 붙여 계속 선계산한다.
                _vclock_pump(st, wait=False)
                if LOCK.acquire(blocking=False):
                    try:
                        st = L.load()
                        _vclock_refresh_settle_target(st)
                        L.save(st)
                        _vclock_settle(st, wait=False)
                        st = L.load()
                    finally:
                        LOCK.release()
                working = bool(st.get('vclock_settle_pending'))
                timing = _ui_timing(st)
                timing['working'] = working
                timing['vclock_coverage_seconds'] = int(
                    float(VCLOCK.get('coverage') or 0.0))
                timing['vclock_session_end_seconds'] = int(
                    float(VCLOCK.get('session_end') or _vclock_session_end(st)))
                timing['worker_elapsed_seconds'] = (
                    int(time.monotonic() - VCLOCK.get('started_at', time.monotonic()))
                    if working and VCLOCK.get('started_at') else 0)
            else:
                fut = PENDING.get('future')
                working = bool(fut and not fut.done())
                timing = _ui_timing(st)
                timing['working'] = working
                timing['worker_elapsed_seconds'] = int(
                    time.monotonic() - PENDING.get('started_at', time.monotonic())
                ) if working else 0
            return self._send(200, timing)
        if path == '/api/stats':
            return self._send(200, {'defer': DEFER, 'counters': dict(COUNT)})
        if path == '/api/telemetry':
            return self._send(200, _TM.status())
        if path == '/api/lobby':
            return self._send(200, _lobby_payload())
        if path == '/api/wallet':
            return self._send(200, ECONOMY.wallet())

        if path == '/api/tournament':
            # Read-only UI requests should not queue behind a long bot calculation.
            # live2.save() replaces the state file atomically, so readers see the last
            # completed snapshot while a hand is being computed.
            try:
                return self._send(200, _tournament_payload())
            except Exception as e:
                traceback.print_exc()
                return self._send(
                    500, {'error': '%s: %s' % (type(e).__name__, e)})

        if path == '/api/memos':
            try:
                return self._send(200, {'memos': _hero_memos()})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {'error': '%s: %s' % (type(e).__name__, e)})

        if path == '/api/history':
            # 공개 관전 화면에서도 읽을 수 있는 sanitized 완료 핸드 기록.
            # 숨은 상대 hole / profiles / reads / intents 는 포함하지 않는다.
            # 목록과 **출처 metadata** 를 함께 준다. 'hands' 키는 그대로라
            # 기존 클라이언트가 깨지지 않는다.
            _h = {'hands': _public_history()}
            _h.update(_archive_status())
            return self._send(200, _h)
        if path == '/play/':
            self.send_response(302)
            self.send_header('Location', '/play')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return

        if path == '/watch' or path.startswith('/watch/'):
            return self._send(404, {'error': '관전 모드는 제거되었습니다'})

        if path in ('/', '/lobby'):
            return self._serve_static('/lobby.html')
        if path == '/play':
            return self._serve_static('/index.html')

        if path != '/api/state':
            return self._serve_static(path)
        with LOCK:
            try:
                waiting = _managed_play_state()
                if waiting:
                    return self._send(200, waiting)
                if not ECONOMY.active_id() and os.path.exists(L.ST) and L.load().get('tournament_id'):
                    return self._send(200, {'no_game': True})
                if _last is None:
                    if not os.path.exists(L.ST):
                        return self._send(200, {'no_game': True})
                    _st = L.load()
                    _f = L._load_field(_st['field'])
                    if _st.get('busted') or _f.remaining() <= 1:
                        _last = _game_over()
                    else:
                        _last = _wrap(_step_sched())
                return self._send(200, _last)
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {'error': '%s: %s' % (type(e).__name__, e)})

    def do_POST(self):
        global _last
        try:
            body = self._body()
            if not isinstance(body, dict):
                raise ValueError('JSON object required')
        except ValueError:
            return self._send(400, {'error': 'JSON 파싱 실패'})
        if self.path == '/api/step-ack':
            sid = body.get('stream_id')
            try:
                seq = int(body.get('seq'))
            except (TypeError, ValueError):
                return self._send(400, {'error': 'seq가 올바르지 않습니다'})
            if not sid:
                return self._send(400, {'error': 'stream_id가 없습니다'})
            ok = _stream_gate_ack(sid, seq)
            return self._send(200 if ok else 410, {
                'ok': bool(ok), 'stream_id': sid, 'seq': seq})

        with LOCK:
            try:
                if self.path in ('/api/register', '/api/reenter', '/api/enter', '/api/unregister'):
                    tid = str(body.get('tournament_id') or '')
                    if self.path == '/api/unregister':
                        ECONOMY.cancel(tid, body.get('entry_no'))
                        return self._send(200, {'ok': True, 'wallet': ECONOMY.wallet()})
                    receipt = None
                    target = ECONOMY.event(tid)
                    wants_enter = self.path == '/api/enter' or time.time() >= target['starts_at']
                    old = ECONOMY.active_id()
                    old_st = ECONOMY.load_active() if old and old != tid else None
                    if self.path == '/api/enter' and (not target['entries'] or
                            target['entries'][-1]['status'] == 'cancelled'):
                        raise _TS.TournamentError('먼저 바이인해 주세요.')
                    if wants_enter and old_st and (
                            old_st.get('hand_seed') is not None or old_st.get('others_pending')
                            or old_st.get('vclock_settle_pending')):
                        raise _TS.TournamentError('현재 핸드와 정산이 끝난 뒤 다른 대회에 입장해 주세요.')
                    if self.path != '/api/enter':
                        receipt = ECONOMY.reserve(tid, reentry=self.path == '/api/reenter',
                                                  expected_entry=body.get('entry_no'))
                    # Paid reservations can coexist. The UI controls one HERO
                    # table at a time; every other registered seat sits out.
                    if wants_enter:
                        old = ECONOMY.active_id()
                        if old and old != tid:
                            old_st = ECONOMY.load_active()
                            if old_st and not old_st.get('offscreen') and old_st.get('hand_seed') is not None:
                                raise _TS.TournamentError('진행 중인 핸드가 끝난 뒤 다른 대회에 입장해 주세요.')
                            if old_st:
                                old_st['offscreen'] = True
                                old_st['field']['sitout_pids'] = [old_st['field']['hero_pid']]
                                old_st['hero_ready'] = False
                                old_st['background_pending'] = {}
                                ECONOMY.save_state(old, old_st)
                            ECONOMY.request_enter(old, False)
                        ECONOMY.set_active(tid)
                        ECONOMY.request_enter(tid)
                        L.STATE_STORE = ECONOMY
                        _clear_worker()
                        _vclock_reset()
                        _last = None
                    return self._send(200, {'ok': True, 'receipt': receipt,
                                            'wallet': ECONOMY.wallet(),
                                            'scheduled': time.time() < ECONOMY.event(tid)['starts_at']})
                if self.path == '/api/memo':
                    if not os.path.exists(L.ST):
                        return self._send(409, {'error': '진행 중인 게임 없음'})

                    try:
                        pid = int(body.get('pid'))
                    except (TypeError, ValueError):
                        return self._send(400, {'error': 'pid가 올바르지 않습니다'})

                    memo = body.get('memo', '')
                    if memo is None:
                        memo = ''
                    if not isinstance(memo, str):
                        return self._send(400, {'error': 'memo는 문자열이어야 합니다'})

                    memo = memo.strip()
                    if len(memo) > 2000:
                        return self._send(400, {'error': '메모는 2000자 이하만 저장할 수 있습니다'})

                    try:
                        memos = _save_hero_memo(pid, memo)
                    except ValueError as e:
                        return self._send(400, {'error': str(e)})

                    return self._send(200, {
                        'ok': True,
                        'pid': pid,
                        'memo': memo,
                        'memos': memos
                    })

                if self.path == '/api/break':
                    st = L.load()
                    if st.get('tournament_id') and body.get('skip'):
                        return self._send(409, {'error': '예약 대회의 공통 브레이크는 건너뛸 수 없습니다.'})
                    if body.get('skip'):
                        if _vclock_enabled(st) and st.get('vclock_settle_pending'):
                            _vclock_refresh_settle_target(st)
                            L.save(st)
                            ok, _ = _vclock_settle(st, wait=False)
                            st = L.load()
                            if not ok or st.get('vclock_settle_pending'):
                                out = _ui_timing(st)
                                out['error'] = '다른 테이블 동기화가 끝나야 휴식을 건너뛸 수 있습니다.'
                                return self._send(409, out)
                        st['ui_break_until'] = min(
                            time.time(), st.get('ui_break_until', time.time()))
                        L.save(st)
                    return self._send(200, _ui_timing(st))
                if self.path == '/api/action-clock':
                    if not os.path.exists(L.ST):
                        return self._send(409, {'error': '진행 중인 게임 없음'})
                    try:
                        timing = _arm_action_clock(body.get('token'))
                    except ValueError as e:
                        return self._send(409, {'error': str(e), 'current': _last})
                    return self._send(200, timing)
                if self.path == '/api/new':
                    if ECONOMY.active_id() or os.environ.get('T2_ALLOW_PRACTICE_NEW') != '1':
                        return self._send(409, {'error': '로비에서 예약 토너먼트에 바이인해 주세요.'})
                    kw = {k: body[k] for k in ('entries', 'seed', 'fmt', 'start_stack')
                          if body.get(k) is not None}
                    raw_minutes = body.get('level_minutes', FM.level_minutes(kw.get('fmt')))
                    try:
                        minutes = int(raw_minutes)
                        valid_minutes = not isinstance(raw_minutes, bool) and float(raw_minutes) == minutes and 1 <= minutes <= 120
                    except (ValueError, TypeError, OverflowError):
                        valid_minutes = False
                    if not valid_minutes:
                        return self._send(400, {'error': '레벨 길이는 1~120분이어야 합니다.'})
                    _clear_worker()             # 새 게임이면 legacy 밀린 것도 버린다
                    _vclock_reset()
                    L.new_game(**kw)
                    st = L.load()
                    st['field']['virtual_play_seconds'] = 0.0
                    st['field']['level_minutes'] = minutes
                    st['vclock_session_v2'] = True
                    st['ui_clock_started_at'] = time.time()
                    st['ui_clock_paused_seconds'] = 0.0
                    st['ui_next_break'] = PLAY_WINDOW_SECONDS
                    st['ui_break_seconds'] = 0
                    st.pop('ui_break_at', None)
                    L.save(st)
                    _last = _wrap(_step_sched())
                    return self._send(200, _last)
                if self.path in ('/api/step', '/api/step-stream'):
                    waiting = _managed_play_state()
                    if waiting:
                        return self._send(409, {'error': waiting['message'], 'current': waiting})
                    if not ECONOMY.active_id() and os.path.exists(L.ST) and L.load().get('tournament_id'):
                        return self._send(409, {'error': '로비에서 참가한 대회에 입장해 주세요.'})
                    stream = self.path == '/api/step-stream'
                    if not os.path.exists(L.ST):
                        return self._send(409, {'error': '진행 중인 게임 없음'})
                    if body.get('token') != _token():
                        # 결과 화면에서 '다음 핸드'(action=null)가 중복 도착한 경우:
                        # 첫 요청이 이미 새 핸드를 만들었다면 두 번째 요청으로
                        # 또 한 핸드를 넘기지 않는다. 현재 화면만 다시 돌려준다.
                        if body.get('action') is None and _last is not None:
                            return self._send(200, _last)
                        return self._send(409, {'error': 'token 불일치 (중복 또는 오래된 요청)',
                                                'current': _last})
                    _st = L.load()
                    _f = L._load_field(_st['field'])
                    if _st.get('busted') or _f.remaining() <= 1:
                        _last = _game_over(); return self._send(200, _last)
                    if _st.get('ui_break_pending') and _ui_timing(_st)['break_remaining']:
                        return self._send(409, {'error': '브레이크가 끝난 뒤 재개됩니다.', 'current': _last})
                    a = body.get('action')
                    timed_out = False
                    deadline = _st.get('ui_action_deadline')
                    if (a is not None and _st.get('ui_action_token') == body.get('token')
                            and deadline is not None and time.time() >= float(deadline)):
                        a = _timeout_action()
                        timed_out = True
                    if a is not None and a not in ACTIONS:
                        return self._send(400, {'error': '알 수 없는 액션: %s' % a})
                    amt = 0 if timed_out else int(body.get('amount') or 0)
                    if TIMING_ON and a is not None and not timed_out and \
                            time.time() < float(_st.get('ui_bot_ready_at') or 0.0) - 0.25:
                        # 봇 예정표가 끝나기 전(아직 HERO 차례 전)의 액션은 받지 않는다.
                        return self._send(409, {'error': '아직 차례가 아닙니다.', 'current': _last})
                    if TIMING_ON and a is not None and _st.get('ui_action_token') == body.get('token'):
                        _settle_hero_bank(_st, time.time(), timed_out=timed_out)
                        L.save(_st)
                    _sched = _BotSchedule(time.time()) if TIMING_ON else None

                    # 일반 /api/step 은 기존 호환 경로. 실제 플레이 액션만
                    # 스트림 경로를 쓰며, 1.5초 모션 템포는 프론트가 그대로 유지한다.
                    if stream:
                        self._stream_start()
                        alive = [True]
                        stream_id = _stream_gate_open()
                        seq = [0]
                        alive[0] = self._stream_line({
                            'type': 'stream_start',
                            'stream_id': stream_id,
                            'server_now_ms': int(time.time() * 1000),
                        })

                        def _emit_bot(event):
                            if _sched is not None:
                                _sched.stamp(event)
                            if not alive[0]:
                                return
                            seq[0] += 1
                            cur = seq[0]
                            alive[0] = self._stream_line({
                                'type': 'bot_action',
                                'stream_id': stream_id,
                                'seq': cur,
                                'event': event,
                            })
                            # UI는 이벤트를 기존 템포로 재생하지만,
                            # 다음 봇 계산은 화면 애니메이션 완료를 기다리지 않는다.

                        try:
                            # 새 핸드(a=None)는 봇 이벤트를 스트림으로 보내지 않는다(화면이 로그로 재생).
                            # 그래도 예정표는 같은 규칙으로 만든다.
                            r = (_step(a, amt, on_bot_action=_emit_bot)
                                 if a is not None else _step_sched())
                        except Exception as e:
                            traceback.print_exc()
                            if alive[0]:
                                self._stream_line({
                                    'type': 'error',
                                    'error': '%s: %s' % (type(e).__name__, e),
                                })
                            return
                        finally:
                            _stream_gate_close(stream_id)
                        if _sched is not None and a is not None:
                            _sched.save()
                        v = r.get('view') or {}
                        if (not r.get('done') and v.get('error') and _last
                                and (_last.get('view') or {}).get('type') == 'decision'):
                            out = dict(_last)
                            out['view'] = dict(_last['view'], error=v['error'])
                            out['token'] = _token()
                            _last = out
                        else:
                            _last = _wrap(r)
                        if timed_out:
                            _last['auto_folded'] = True
                        if alive[0]:
                            self._stream_line({
                                'type': 'final',
                                'payload': _last,
                            })
                        return

                    r = _step_sched(a, amt) if a is not None else _step_sched()
                    v = r.get('view') or {}
                    if (not r.get('done') and v.get('error') and _last
                            and (_last.get('view') or {}).get('type') == 'decision'):
                        # 엔진의 오류 응답에는 stacks/contrib 가 빠져 있어 좌석 값이 틀린다.
                        # 상태는 바뀌지 않았으므로(token 동일) 직전 정상 화면에 오류만 붙인다.
                        out = dict(_last); out['view'] = dict(_last['view'], error=v['error'])
                        out['token'] = _token()
                        return self._send(200, out)
                    _last = _wrap(r)
                    if timed_out:
                        _last['auto_folded'] = True
                    return self._send(200, _last)
                return self._send(404, {'error': 'not found'})
            except _TS.TournamentError as e:
                return self._send(409, {'error': str(e), 'code': e.code})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {'error': '%s: %s' % (type(e).__name__, e)})

    def log_message(self, fmt, *args):
        sys.stderr.write('[ui] ' + fmt % args + '\n')


if __name__ == '__main__':
    host = os.environ.get('IP', '0.0.0.0')
    port = int(os.environ.get('PORT', '8765'))
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    # 워커는 **소켓을 열기 전에** 미리 띄운다. 서버가 돈 뒤에 fork 하면
    # 자식이 듣기 소켓을 물려받는다.
    if DEFER and _pool() is None:
        print('경고: 워커 프로세스를 못 만들었습니다. 정산 지연이 꺼진 것과 같게 동작합니다.')
    _tm = _TM.start()
    if os.environ.get('T2_SCHEDULE_ENABLED', '1') != '0':
        # Start the process before the listening socket exists (fork-safe).
        SCHEDULE_POOL = ProcessPoolExecutor(max_workers=1)
        SCHEDULE_POOL.submit(_SR.worker_ready).result()
        SCHEDULE_FUTURE = None
        ECONOMY.ensure_schedule()
        threading.Thread(target=_schedule_loop, name='t2-schedule', daemon=True).start()
    print('정산 지연: %s  (끄려면 T2_UI_DEFER=0)' % ('켬' if DEFER else '끔'))
    print('텔레메트리: %s%s' % (
        '켬' if _tm.get('enabled') else '끔',
        (' -> ' + str(_tm.get('branch'))) if _tm.get('enabled') else ''))
    print('상태 파일: %s' % L.ST)
    print('정적 파일: %s%s' % (WEB, '' if os.path.isdir(WEB) else '  (없음 — API 만 동작)'))
    print('로비 주소: http://127.0.0.1:%d' % port)
    print('테이블 주소: http://127.0.0.1:%d/play' % port)
    print('다른 기기: http://<이 기기의 LAN IP>:%d' % port)
    # The gameplay stream can be waiting for a motion ACK while settings/history
    # are requested. A single-threaded HTTPServer would serialize those requests.
    class _T2ThreadingHTTPServer(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    if ':' in host:
        class _HTTPServer6(_T2ThreadingHTTPServer):
            address_family = socket.AF_INET6
        srv = _HTTPServer6((host, port), H)
    else:
        srv = _T2ThreadingHTTPServer((host, port), H)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n종료 중…')
    finally:
        # 워커가 계산 중이어도 기다리지 않는다. 기다리면 Ctrl+C 후에도
        # 30초쯤 포트를 붙들고 있어 바로 다시 켤 수 없다.
        srv.server_close()
        if POOL is not None:
            try: POOL.shutdown(wait=False, cancel_futures=True)
            except TypeError: POOL.shutdown(wait=False)   # 파이썬 3.8 이하
        if SCHEDULE_POOL is not None:
            SCHEDULE_POOL.shutdown(wait=False, cancel_futures=True)
        os._exit(0)
