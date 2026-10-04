"""히어로가 직접 치는 실전 진행기. 필드 전체가 실제로 돌아간다."""
import copy, json, os, random, math, time
import telemetry_sync as TM
import zlib as _zlib
import fieldsim as FS, play, session as SE, view, persona as PS, reads as RD
import formats as FM
import runner as RU
from table import BLINDS

D = os.path.dirname(os.path.abspath(__file__))
# 상태 파일 경로. 환경변수로 바꿀 수 있다 —
# 검사 도구가 new_game 을 부르면 **진행 중인 게임이 통째로 날아간다**
# (아카이브까지 지운다). 도구는 별도 경로를 쓰게 한다.
import storage_paths as SP
ST = os.environ.get('T2_LIVE_STATE') or os.path.join(D, 'live2_state.json')
# sidecar 이름은 **상태 파일 경로에서** 나온다. 예전에는 T2_LIVE_STATE 가
# 설정돼 있기만 하면 경로와 무관하게 '_alt' 하나였고, 그래서 서로 다른
# 상태를 쓰는 두 실행이 같은 아카이브에 섞여 썼다 (아래 new_game 주석).
_SUFFIX = SP.namespace()



# ---------- 상태 직렬화 ----------
def _copy_field(d):
    """copy.deepcopy(field_dump) 와 같은 결과. 장부는 전용 복사(RD.copy_book_d) —
    대회 장부가 커지면 범용 deepcopy 가 한 액션 시간의 대부분이었다."""
    if not isinstance(d, dict):
        return copy.deepcopy(d)
    out = {}
    for k, v in d.items():
        out[k] = RD.copy_book_d(v) if (k == 'book' and isinstance(v, dict)) else copy.deepcopy(v)
    return out


def _dump(f):
    result = {
        'entries': f.entries, 'start_stack': f.start_stack, 'hero_pid': f.hero_pid,
        'hand_no': f.hand_no, 'level': f.level, 'itm': f.itm,
        'hands_per_level': f.hands_per_level,
        'busted_order': f.busted_order, 'hero_moves': f.hero_moves,
        'notes': f.notes,
        'fmt': f.fmt.get('key', 'standard'),
        'max_seat': getattr(f, 'max_seat', FS.MAXSEAT),
        'seed': getattr(f, 'seed', None),
        'tilt': f.tilt.state,
        # 대회 하나의 관찰 장부(L161). 내 테이블과 다른 테이블이 같은 장부를 쓴다.
        # 저장 형태는 기본값(0) 칸을 뺀 것(RD.pack_book_d). 읽을 때 채운다.
        'book': (f.book_packed() if hasattr(f, 'book_packed')
                 else RD.pack_book_d(getattr(getattr(f, 'book', None), 'd', {}) or {})),
        # 틸트 키가 좌석에서 사람(pid)으로 바뀌었다. 이 표시가 없는 저장본은
        # 좌석 키('1'..'8')라서 pid 1..8 과 그대로 충돌한다 — 3번 자리의
        # 누적 틸트가 pid 3 인 사람에게 붙는다. 그런 상태는 버린다.
        'tilt_key': 'pid',
        'blind_state': 'tda_dead_button_v1',
        'players': {str(p['pid']): {'prof': p['prof'], 'stack': p['stack'],
                                    'table': p['table'], 'seat': p['seat']}
                    for p in f.players.values()},
        'tables': {str(t): {'button': tb.button,
                            'button_seat': tb.dealer_seat(),
                            'sb_seat': getattr(tb, 'sb_seat', None),
                            'bb_seat': getattr(tb, 'bb_seat', None),
                            'hands': tb.hands,
                            'vclock_seconds': float(getattr(tb, 'virtual_seconds', 0.0) or 0.0),
                            'pids': [p['pid'] for p in tb.players],
                            'seats': list(tb.seats)}
                   for t, tb in f.tables.items()},
    }

    if getattr(f, 'virtual_play_seconds', None) is not None:
        result['virtual_play_seconds'] = f.virtual_play_seconds
        result['level_minutes'] = f.level_minutes
    return result


def _load_field(d):
    f = FS.Field.__new__(FS.Field)
    # 시드 없이 새로 만들면 매 step 마다 필드 RNG 가 무작위로 초기화된다.
    # 기준 시드와 핸드 번호에서 파생해 복원 시점이 같으면 같은 상태가 되게 한다.
    f.rng = random.Random(_zlib.crc32(
        ('field|%s|%s' % (d.get('seed'), d.get('hand_no', 0))).encode()))
    # **시드를 객체에 되돌려 놓아야 한다.** 예전에는 d 에서 읽어 RNG 파생에만
    # 쓰고 f.seed 를 복원하지 않았다. 그러면 다음 save() 에서 _dump 의
    # getattr(f,'seed',None) 이 None 을 저장하고, 그 뒤로 영구히 None 이 된다.
    # 결과: (1) 실험 재현 불가 (2) crc32('field|None|n') 로 파생되어
    # **어떤 시드로 시작하든 두 번째 핸드부터 같은 필드 RNG 를 쓴다.**
    f.seed = d.get('seed')
    # 장부는 깊은 복사로 복원한다 — 핸드 도중 관측이 입력 덤프(=저장 상태)로
    # 새면 재생 때 이미 이번 핸드를 품은 장부로 판단하게 된다(build_hand 주석).
    # 장부는 저장 형태 그대로 받아 두고 처음 쓸 때 푼다(Field.book).
    f.set_book_packed(d.get('book') or {})
    f.entries = d['entries']; f.start_stack = d['start_stack']
    f.hero_pid = d['hero_pid']; f.hand_no = d['hand_no']; f.level = d['level']
    f.itm = d['itm']; f.hands_per_level = d['hands_per_level']
    f.virtual_play_seconds = d.get('virtual_play_seconds')
    f.level_minutes = d.get('level_minutes') or FM.level_minutes(d.get('fmt'))
    f.busted_order = d['busted_order']; f.hero_moves = d['hero_moves']
    f.notes = d.get('notes', []); f.errors = []
    f.players = {}
    # tilt 내부 pid 상태도 중첩 dict다. 얕은 복사면 HandRun이 f.tilt를
    # 갱신할 때 입력 field_dump 자체가 변해 round-start fingerprint가 흔들린다.
    _tilt_in = (copy.deepcopy(d.get('tilt'))
                if d.get('tilt_key') == 'pid' else None)
    f._init_runtime(d.get('fmt'), _tilt_in)
    # 새 저장본은 max_seat 를 명시한다. 구 저장본은 저장된 좌석 슬롯 길이로
    # 추론해 진행 중인 8-max 세션이 standard=9 변경 때문에 중간에 변하지 않게 한다.
    _saved_max = d.get('max_seat')
    if _saved_max is None:
        _lens = [len(v.get('seats') or []) for v in (d.get('tables') or {}).values()
                 if v.get('seats')]
        _saved_max = max(_lens) if _lens else None
    if _saved_max is not None:
        _saved_max = int(_saved_max)
        if not (2 <= _saved_max <= FM.MAX_SEATS):
            raise ValueError('저장본 좌석 수가 범위를 벗어남: %s' % _saved_max)
        f.max_seat = _saved_max
    for k, v in d['players'].items():
        f.players[int(k)] = {'pid': int(k), 'prof': v['prof'], 'stack': v['stack'],
                             'table': v['table'], 'seat': v['seat']}
    f.set_book_caps()
    f.tables = {}
    for k, v in d['tables'].items():
        f.tables[int(k)] = _restore_table(f, k, v, d.get('blind_state'))
    return f


def _restore_table(f, k, v, blind_state):
    """저장된 테이블 하나를 f 의 플레이어 객체로 복원한다."""
    tb = FS.Table(
        int(k), [f.players[p] for p in v['pids']], button=v['button'],
        max_seat=f.max_seat, button_seat=v.get('button_seat'),
        sb_seat=v.get('sb_seat'), bb_seat=v.get('bb_seat'))
    tb.hands = v['hands']
    # 기존 저장본은 독립 테이블 시계가 없으므로 현재 대회 시각에서 이어간다.
    tb.virtual_seconds = float(
        v.get('vclock_seconds',
              getattr(f, 'virtual_play_seconds', 0.0) or 0.0) or 0.0)
    if v.get('seats'):
        tb.seats = list(v['seats'])
        if len(tb.seats) < tb.max_seat:
            tb.seats.extend([None] * (tb.max_seat - len(tb.seats)))
        elif len(tb.seats) > tb.max_seat:
            raise ValueError('저장본 테이블 슬롯이 max_seat보다 큼: %d > %d'
                             % (len(tb.seats), tb.max_seat))
    tb.restore_positions(
        v.get('button', 0), v.get('button_seat'),
        v.get('sb_seat'), v.get('bb_seat'),
        legacy_dead_hint=(blind_state != 'tda_dead_button_v1'))
    return tb


# ---------- 다른 테이블 동시 계산(테이블별 프로세스) ----------
_TABLE_POOL = None


def _table_workers():
    try:
        n = int(os.environ.get('T2_TABLE_WORKERS', '0') or 0)
    except ValueError:
        n = 0
    return n if n > 0 else max(1, min(8, os.cpu_count() or 1))


def _table_pool():
    """테이블별 계산 풀. fork 가 없거나 코어가 1개면 None(순차)."""
    global _TABLE_POOL
    if _table_workers() <= 1:
        return None
    if _TABLE_POOL is None:
        try:
            import multiprocessing as _mp
            from concurrent.futures import ProcessPoolExecutor as _PPE
            _TABLE_POOL = _PPE(max_workers=_table_workers(),
                               mp_context=_mp.get_context('fork'))
        except Exception:
            return None
    return _TABLE_POOL


def _table_task(mini, tid, seeds, frozen, base_suffix):
    """한 테이블의 이번 라운드를 계획된 시드로 진행하고 그 테이블 몫만 돌려준다."""
    f = _load_field(mini)
    f.notes = []
    f._frozen_field = frozen
    _suf = FS.BOT_SUFFIX
    _tmp = SP.pending_suffix('%s_t%s' % (base_suffix, tid), os.getpid())
    FS.BOT_SUFFIX = _tmp
    try:
        f.play_planned(tid, seeds)
    finally:
        FS.BOT_SUFFIX = _suf
        f._frozen_field = None
    out = _dump(f)
    pids = [str(p) for p in mini['tables'][str(tid)]['pids']]
    _p = SP.path_for('bot_log', _tmp, D)
    log = ''
    if os.path.exists(_p):
        with open(_p, encoding='utf-8') as fp:
            log = fp.read()
        try: os.remove(_p)
        except OSError: pass
    ps = set(pids)
    return {'tid': tid,
            'players': {p: out['players'][p] for p in pids if p in out['players']},
            'table': out['tables'][str(tid)],
            'tilt': {p: out['tilt'][p] for p in pids if p in (out.get('tilt') or {})},
            'book': {k: v for k, v in (out.get('book') or {}).items()
                     if str(k).partition('>')[0] in ps},
            'notes': list(f.notes), 'errors': list(f.errors), 'bot_log': log}


def _parallel_tables_runner(f, plan):
    """step_others(simultaneous=True) 의 runner: 테이블마다 다른 프로세스에서 진행.

    결과는 순차 동시 진행(runner=None)과 같다 — 각 테이블은 계획된 시드와
    라운드 시작 문맥만 쓰고, 장부·틸트·스택은 테이블끼리 겹치지 않는다.
    봇 로그·알림·오류는 계획 순서(=순차 순서)대로 붙인다.
    """
    pool = _table_pool() if len(plan) > 1 else None
    if pool is None:
        for tid, seeds in plan:
            f.play_planned(tid, seeds)
        return
    base = _dump(f)
    futs = []
    for tid, seeds in plan:
        ps = {str(p) for p in base['tables'][str(tid)]['pids']}
        mini = dict(base)
        mini['book'] = {k: v for k, v in base['book'].items()
                        if str(k).partition('>')[0] in ps}
        futs.append(pool.submit(_table_task, mini, tid, seeds,
                                f._frozen_field, FS.BOT_SUFFIX))
    results = [fu.result() for fu in futs]
    book_upd = {}
    for r in results:
        for pid, row in r['players'].items():
            p = f.players[int(pid)]
            p['stack'] = row['stack']; p['table'] = row['table']; p['seat'] = row['seat']
        f.tables[int(r['tid'])] = _restore_table(
            f, r['tid'], r['table'], base.get('blind_state'))
        for pid, t in r['tilt'].items():
            f.tilt.state[pid] = t
        book_upd.update(r['book'])
        f.notes.extend(r['notes'])
        f.errors.extend(r['errors'])
        if r['bot_log']:
            with open(SP.path_for('bot_log', FS.BOT_SUFFIX, D), 'a',
                      encoding='utf-8') as fp:
                fp.write(r['bot_log'])
    f.book_update_packed(book_upd)


# ---------- 독립 가상시계 선계산 ----------
# HERO 테이블은 UI wall-clock이 원본이다. 비-HERO 테이블은 각자 virtual_seconds
# 를 갖고 계산 가능한 만큼 앞서 간다. 선계산은 임시이며, 탈락/핸드포핸드처럼
# 전역 상태가 갈리는 지점에서는 barrier를 세워 그 뒤 결과를 확정하지 않는다.
VCLOCK_AHEAD_MODE = 'vclock_ahead_v1'
try:
    VCLOCK_DURATION_SCALE = max(
        0.1, float(os.environ.get('T2_VCLOCK_SCALE', '1.0')))
except ValueError:
    VCLOCK_DURATION_SCALE = 1.0


def _vclock_hand_seconds(res):
    """Claude 설계 초안과 같은 action-shape 시간 모델을 초 단위로 반환한다."""
    log = (res or {}).get('full_log') or []
    costs = {
        'fold': 1.5, 'check': 3.0, 'call': 3.5,
        'bet': 5.0, 'raise': 5.5, 'allin': 5.5,
    }
    streets = {a[0] for a in log if isinstance(a, (list, tuple)) and len(a) >= 3}
    raw = 8.0 + 2.0 * max(0, len(streets) - 1)
    raw += sum(
        costs.get(a[2], 3.5)
        for a in log
        if isinstance(a, (list, tuple)) and len(a) >= 3
    )
    raw += 3.0 if (res or {}).get('showdown') else 0.0
    return max(1.0, raw * VCLOCK_DURATION_SCALE)


def _vclock_book_subset(packed, pids):
    owners = {str(x) for x in pids}
    return RD.copy_book_d({
        k: v for k, v in (packed or {}).items()
        if str(k).partition('>')[0] in owners
    })


def _vclock_book_delta(before, after):
    set_rows = {
        k: copy.deepcopy(v) for k, v in (after or {}).items()
        if k not in (before or {}) or (before or {}).get(k) != v
    }
    deleted = [k for k in (before or {}) if k not in (after or {})]
    return set_rows, deleted


def _vclock_h4h(f):
    active_tables = sum(1 for tb in f.tables.values() if tb.n() >= 2)
    # 머니/새틀라이트 좌석 버블 + 마지막 두 테이블 -> FT 버블.
    return (f.remaining() <= f.itm + 1
            or (1 < active_tables <= 2))


def _vclock_table_task(mini, tid, target_seconds, session_end, frozen,
                       base_suffix):
    """한 봇 테이블을 target_seconds까지 독립적으로 선계산한다.

    첫 탈락 또는 hand-for-hand 지점에서 멈춘다. 그 지점 이후에는 테이블 이동/
    전역 remaining 문맥이 달라질 수 있으므로 임시 결과를 만들지 않는다.
    """
    f = _load_field(_copy_field(mini))
    f.notes = []
    tid = int(tid)
    tb = f.tables[tid]
    local = float(getattr(tb, 'virtual_seconds', 0.0) or 0.0)
    target_seconds = float(target_seconds)
    session_end = float(session_end)
    f._frozen_field = frozen

    _suf = FS.BOT_SUFFIX
    _tmp = SP.pending_suffix('%s_vc_t%s' % (base_suffix, tid), os.getpid())
    FS.BOT_SUFFIX = _tmp
    log_path = SP.path_for('bot_log', _tmp, D)
    log_seen = 0
    events = []
    errors = []
    try:
        pids = [str(p) for p in mini['tables'][str(tid)]['pids']]
        prev_book = _vclock_book_subset(mini.get('book') or {}, pids)

        while local + 1e-9 < target_seconds and tb.n() >= 2:
            f.virtual_play_seconds = local
            f.advance_level()
            seed = _zlib.crc32(
                ('%s|vclock|%s|%s' % (
                    getattr(f, 'seed', None), tid, tb.hands + 1
                )).encode()) % (10**9)

            note0 = len(f.notes)
            res = f._play_table(
                tb, seed=seed, return_result=True)
            if not isinstance(res, dict):
                errors.extend(list(getattr(f, 'errors', []) or []))
                break

            end = local + _vclock_hand_seconds(res)
            # 세션 경계에서는 진행 중이던 핸드까지 끝낸 뒤 정각에 동기화한다.
            if target_seconds >= session_end - 1e-9 and end >= session_end:
                end = session_end
            tb.virtual_seconds = end

            out = _dump(f)
            row = out['tables'][str(tid)]
            pids = [str(p) for p in row.get('pids') or []]
            cur_book = _vclock_book_subset(out.get('book') or {}, pids)
            book_set, book_del = _vclock_book_delta(prev_book, cur_book)
            prev_book = cur_book

            log_chunk = ''
            if os.path.exists(log_path):
                with open(log_path, encoding='utf-8') as fp:
                    txt = fp.read()
                log_chunk = txt[log_seen:]
                log_seen = len(txt)

            players = {
                p: copy.deepcopy(out['players'][p])
                for p in pids if p in out['players']
            }
            dead = any(int(r.get('stack', 0) or 0) <= 0
                       for r in players.values())
            barrier = 'bust' if dead else (
                'hand_for_hand' if _vclock_h4h(f) else None)

            events.append({
                'tid': tid,
                'end': float(end),
                'players': players,
                'table': copy.deepcopy(row),
                'tilt': {
                    p: copy.deepcopy((out.get('tilt') or {}).get(p))
                    for p in pids
                    if p in (out.get('tilt') or {})
                },
                'book_set': book_set,
                'book_del': book_del,
                'notes': list(f.notes[note0:]),
                'bot_log': log_chunk,
                'barrier': barrier,
            })
            local = float(end)
            if barrier:
                break
    finally:
        FS.BOT_SUFFIX = _suf
        f._frozen_field = None
        try:
            if os.path.exists(log_path):
                os.remove(log_path)
        except OSError:
            pass

    out = _dump(f)
    row = out['tables'].get(str(tid), {})
    pids = [str(p) for p in row.get('pids') or []]
    return {
        'tid': tid,
        'events': events,
        'covered_until': float(local),
        'barrier': next(
            (e['barrier'] for e in events if e.get('barrier')), None),
        'barrier_time': next(
            (float(e['end']) for e in events if e.get('barrier')), None),
        'players': {
            p: copy.deepcopy(out['players'][p])
            for p in pids if p in out.get('players', {})
        },
        'table': copy.deepcopy(row),
        'tilt': {
            p: copy.deepcopy((out.get('tilt') or {}).get(p))
            for p in pids if p in (out.get('tilt') or {})
        },
        'book': _vclock_book_subset(out.get('book') or {}, pids),
        'notes': list(f.notes),
        'errors': errors + list(getattr(f, 'errors', []) or []),
    }


def compute_vclock_ahead(field_dump, target_seconds, session_end=None):
    """비-HERO 테이블을 독립 가상시계로 target까지 선계산하는 순수 함수."""
    base = _copy_field(field_dump)
    f = _load_field(base)
    f.notes = []
    hero_tid, other_tids, _ = _round_owners(base)
    target_seconds = float(target_seconds)
    if session_end is None:
        session_end = target_seconds
    session_end = float(session_end)

    if not other_tids:
        return {
            'mode': VCLOCK_AHEAD_MODE,
            'base_key': _others_key(base),
            'hero_table': hero_tid,
            'target': target_seconds,
            'session_end': session_end,
            'coverage': session_end,
            'barrier_time': None,
            'tables': {},
            'end_field': base,
        }

    frozen = f.field_snapshot()
    pool = _table_pool() if len(other_tids) > 1 else None
    jobs = []
    for tid in other_tids:
        ps = {str(p) for p in base['tables'][str(tid)]['pids']}
        mini = dict(base)
        mini['book'] = {
            k: v for k, v in (base.get('book') or {}).items()
            if str(k).partition('>')[0] in ps
        }
        args = (mini, tid, target_seconds, session_end, frozen, FS.BOT_SUFFIX)
        if pool is None:
            jobs.append(_vclock_table_task(*args))
        else:
            jobs.append(pool.submit(_vclock_table_task, *args))
    results = [x.result() if hasattr(x, 'result') else x for x in jobs]
    results.sort(key=lambda x: int(x['tid']))

    barriers = [
        float(r['barrier_time']) for r in results
        if r.get('barrier_time') is not None
    ]
    barrier_time = min(barriers) if barriers else None
    coverage = min(float(r.get('covered_until', 0.0)) for r in results)
    if barrier_time is not None:
        coverage = min(coverage, barrier_time)

    end_field = None
    if barrier_time is None:
        end_field = _copy_field(base)
        for r in results:
            tid = str(r['tid'])
            for pid, row in (r.get('players') or {}).items():
                end_field['players'][str(pid)] = copy.deepcopy(row)
            end_field['tables'][tid] = copy.deepcopy(r['table'])
            et = end_field.setdefault('tilt', {})
            for pid, row in (r.get('tilt') or {}).items():
                et[str(pid)] = copy.deepcopy(row)
            owners = {
                str(p) for p in
                (end_field['tables'][tid].get('pids') or [])
            }
            eb = end_field.setdefault('book', {})
            for k in [
                k for k in eb
                if str(k).partition('>')[0] in owners
            ]:
                del eb[k]
            eb.update(RD.copy_book_d(r.get('book') or {}))

    return {
        'mode': VCLOCK_AHEAD_MODE,
        'base_key': _others_key(base),
        'hero_table': hero_tid,
        'target': target_seconds,
        'session_end': session_end,
        'coverage': float(coverage),
        'barrier_time': barrier_time,
        'tables': {str(r['tid']): r for r in results},
        'end_field': end_field,
    }


def apply_vclock_events(st, events_by_table, cursors, target_seconds,
                        barrier_time=None):
    """HERO 시각까지 확정된 봇 이벤트만 메인 상태에 반영한다.

    barrier가 HERO 시각 안에 들어오거나 HERO 테이블 자체에서 탈락이 생기면
    그 핸드 경계에서 전역 bust/balance를 한 번만 실행하고 선계산 이후분을
    무효화한다. 이동 후 모든 봇 테이블은 HERO 시각까지 대기한 것으로 맞춘다.
    """
    target_seconds = float(target_seconds)
    cutoff = target_seconds
    barrier_due = (
        barrier_time is not None
        and float(barrier_time) <= target_seconds + 1e-9
    )
    if barrier_due:
        cutoff = min(cutoff, float(barrier_time))

    fd = _copy_field(st['field'])
    cur = {str(k): int(v) for k, v in (cursors or {}).items()}
    due = []
    for tid, arr in (events_by_table or {}).items():
        tid = str(tid)
        i = cur.get(tid, 0)
        while i < len(arr) and float(arr[i]['end']) <= cutoff + 1e-9:
            due.append((float(arr[i]['end']), int(tid), i, arr[i]))
            i += 1
        cur[tid] = i
    due.sort(key=lambda x: (x[0], x[1], x[2]))

    notes = []
    bot_log = []
    for _end, tid_i, _idx, e in due:
        tid = str(tid_i)
        for pid, row in (e.get('players') or {}).items():
            fd['players'][str(pid)] = copy.deepcopy(row)
        fd['tables'][tid] = copy.deepcopy(e['table'])
        et = fd.setdefault('tilt', {})
        for pid, row in (e.get('tilt') or {}).items():
            et[str(pid)] = copy.deepcopy(row)
        eb = fd.setdefault('book', {})
        for k in e.get('book_del') or []:
            eb.pop(k, None)
        eb.update(RD.copy_book_d(e.get('book_set') or {}))
        notes.extend(e.get('notes') or [])
        if e.get('bot_log'):
            bot_log.append(e['bot_log'])

    f = _load_field(fd)
    dead = any(
        int(p.get('stack', 0) or 0) <= 0 and p.get('table') is not None
        for p in f.players.values()
    )
    invalidated = bool(barrier_due or dead)
    if invalidated:
        f._collect_busts()
        f._balance()
        # barrier 이후에는 테이블들이 HERO를 기다린다. 이동 확정 시점에서
        # 다음 선계산을 다시 시작하므로 각 봇 시계를 같은 HERO 시각으로 맞춘다.
        hero_tid = f.players.get(f.hero_pid, {}).get('table')
        for tid, tb in f.tables.items():
            if tid != hero_tid and tb.n() >= 2:
                tb.virtual_seconds = target_seconds
        notes.extend(list(f.notes))
        f.notes = []

    st['field'] = _dump(f)
    return {
        'cursors': cur,
        'invalidated': invalidated,
        'barrier_due': barrier_due,
        'applied': len(due),
        'notes': notes,
        'bot_log': ''.join(bot_log),
    }


def finalize_vclock_settle(st, notes=None, bot_log=''):
    """한 HERO 핸드 경계의 확정 작업(순위/아카이브/이동 알림)을 마친다."""
    f = _load_field(_copy_field(st['field']))
    # 버퍼가 없던 파이널테이블 등에서도 HERO 탈락 정리는 필요하다.
    dead = any(
        int(p.get('stack', 0) or 0) <= 0 and p.get('table') is not None
        for p in f.players.values()
    )
    if dead:
        f._collect_busts()
        f._balance()
        notes = list(notes or []) + list(f.notes)
        f.notes = []
        st['field'] = _dump(f)

    hero = f.players.get(f.hero_pid)
    busted = bool(hero and int(hero.get('stack', 0) or 0) <= 0)
    rank = None
    if busted:
        if f.hero_pid in f.busted_order:
            after = len(f.busted_order) - f.busted_order.index(f.hero_pid) - 1
            rank = f.remaining() + 1 + after
        else:
            rank = f.remaining() + 1
    st['busted'] = busted
    st['rank'] = rank

    extra = list(notes or [])
    if extra:
        st['pending_notes'] = list(st.get('pending_notes') or []) + extra

    if bot_log:
        _append_bot_log(bot_log)

    rec = st.pop('pending_archive', None)
    if rec is not None:
        rec['field'] = f.status()
        rec['notes'] = list(rec.get('notes') or []) + extra
        _archive_write(rec)

    st.pop('vclock_settle_pending', None)
    save(st)
    return {
        'busted': busted,
        'rank': rank,
        'remaining': f.remaining(),
        'status': f.status(),
    }


# 인코딩을 적지 않으면 파이썬이 OS 기본값을 쓴다. 리눅스·안드로이드는
# UTF-8 이라 문제가 없지만 한글 윈도우는 cp949 라, 알림에 이모지가
# 하나 들어가는 순간 기록이 통째로 터진다(실제로 그랬다).
def save(st):
    tmp = ST + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(st, fp)
        fp.flush(); os.fsync(fp.fileno())
    if os.path.exists(ST):
        try: os.replace(ST, ST + '.bak')
        except OSError: pass
    os.replace(tmp, ST)


def load():
    for p in (ST, ST + '.bak'):
        try:
            with open(p, encoding='utf-8') as fp:
                d = json.load(fp)
            if d: return d
        except (OSError, ValueError):
            continue
    raise RuntimeError('상태 파일 없음')


# ---------- 게임 생성 ----------
def new_game(entries=100, start_stack=30000, seed=None, itm_frac=0.15,
             hands_per_level=12, fmt=None):
    # 지우지 말고 옮긴다. 예전에는 os.remove 였는데, T2_LIVE_STATE 로 상태
    # 파일을 다른 경로에 두어도 **아카이브는 여전히 모듈 폴더(D)에 _SUFFIX
    # 이름으로 쓰인다.** 그래서 격리한 줄 알고 테스트를 돌렸다가 진행 중이던
    # 세션의 37핸드 기록을 통째로 날렸다. 되돌릴 방법이 없었다.
    _stamp = time.strftime('%Y%m%d_%H%M%S')
    # **이 상태의 namespace 파일만** 건드린다. 다른 상태나 legacy '_alt' 를
    # 백업 대상에 넣으면 남의 기록을 치우게 된다.
    for p in [SP.sidecar_path(k) for k in SP.BACKUP_KINDS]:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            try: os.rename(p, os.path.join(D, 'bak_%s_%s' % (_stamp, os.path.basename(p))))
            except OSError:
                try: os.remove(p)
                except OSError: pass
    f = FS.Field(entries=entries, start_stack=start_stack, hero_pid=0,
                 seed=seed, hands_per_level=hands_per_level, itm_frac=itm_frac,
                 fmt=fmt)
    st = {'field': _dump(f), 'actions': [], 'decisions': [], 'hand_seed': None,
          'seed': seed,
          'telemetry_session_id': '%s_%s_%s' % (
              time.strftime('%Y%m%d_%H%M%S'),
              seed if seed is not None else 'auto',
              os.urandom(4).hex()),
          # 히어로가 직접 적은 봇 메모. pid 기준이라 자리 이동 뒤에도 같은
          # 플레이어를 따라간다. 봇 판단에는 읽히지 않고 기록용으로만 쓴다.
          'hero_memos': {},
          'notes': [], 'busted': False, 'rank': None}
    save(st)
    return st


# ---------- 히어로 테이블 구성 ----------
def _hero_table_setup(f):
    """히어로 테이블을 TDA dead-button layout과 함께 구성한다."""
    tb = f.hero_table()
    alive = [p for p in tb.alive() if tb.seat_of(p['pid'])]
    alive.sort(key=lambda p: tb.seat_of(p['pid']))
    seats = [tb.seat_of(p['pid']) for p in alive]
    hero_seat = None
    profs = {}; stacks = {}
    for p in alive:
        s = tb.seat_of(p['pid'])
        profs[str(s)] = p['prof']; stacks[s] = p['stack']
        if p['pid'] == f.hero_pid:
            hero_seat = s
    layout = tb.hand_layout()
    return tb, alive, seats, profs, stacks, layout, hero_seat


def build_hand(st):
    f = _load_field(st['field'])
    tb, alive, seats, profs, stacks, layout, hero_seat = _hero_table_setup(f)
    sb, bb = f.blinds()
    # 리딩 장부는 이 대회 상태 안에 산다. 전역 book.json 을 쓰면
    # 대회끼리 관찰이 섞이고 같은 시드가 재현되지 않는다.
    # **깊은 복사여야 한다.** dict() 는 겉 매핑만 복사하고 Book.rec() 가
    # 돌려주는 안쪽 카운터 dict 는 st['book'] 과 그대로 공유된다.
    # 그러면 핸드를 진행하는 동안 쌓인 관측이 st 에 그대로 새고,
    # step() 의 save(st) 가 그걸 **핸드 도중에** 파일에 박는다.
    # 결과: (1) 다음 요청이 재생할 때 장부가 이미 이번 핸드 관측을 품고 있어
    # 봇의 프리플랍 판단이 라이브와 달라지고(= 기록된 히어로 액션이 불법이 됨),
    # (2) 요청마다 같은 관측이 다시 누적돼 리딩이 몇 배로 부풀려진다.
    # 장부는 field 덤프 안에 산다(L161) — _load_field 가 이미 깊은 복사했다.
    # 예전 저장본(st['book'] 만 있음)은 한 번 이어받는다.
    if not f.book.d and st.get('book'):
        f.book.d = RD.unpack_book_d(st['book'])
    _bk = f.book
    h = play.Hand(
        seats, profs, stacks, layout['button'], sb, bb, hero=hero_seat,
        seed=st['hand_seed'], book=_bk,
        position_map=layout['pos'],
        pre_seats=layout['pre_seats'],
        post_seats=layout['post_seats'],
        sb_seat=layout['sb'],
        bb_seat=layout['bb'])
    h.seat_pid = {tb.seat_of(p['pid']): p['pid'] for p in alive}
    h.table_id = tb.id
    h.table_max_seat = getattr(tb, 'max_seat', len(tb.seats))
    f.stamp(h)
    _pids = [str(p['pid']) for p in alive]
    h._telemetry_tilt_before = {
        pid: copy.deepcopy(f.tilt.state.get(pid, {})) for pid in _pids
    }
    # 아카이브에는 이 테이블 사람끼리의 기록만, 이력 제외(L161 — 장부가 대회 전체다).
    h._telemetry_book_before = FS.book_view(getattr(h.book, 'd', {}) or {}, _pids)
    h._telemetry_book_pids = list(_pids)
    return f, tb, alive, h, hero_seat


def level_of(f): return f.level


PARALLEL_TABLES_MODE = 'parallel_tables_v1'


def _round_owners(field_dump):
    """라운드 시작 스냅샷에서 HERO/기타 테이블의 소유 영역을 고정한다."""
    hero_pid = int(field_dump['hero_pid'])
    hp = field_dump['players'][str(hero_pid)]
    hero_tid = int(hp['table'])
    other_tids = []
    other_pids = set()
    for tid_s, td in (field_dump.get('tables') or {}).items():
        tid = int(tid_s)
        if tid == hero_tid:
            continue
        other_tids.append(tid)
        for pid in td.get('pids') or []:
            other_pids.add(int(pid))
    return hero_tid, sorted(other_tids), sorted(other_pids)


def compute_others_parallel(field_dump):
    """라운드 시작 스냅샷에서 비-HERO 테이블만 진행한다.

    탈락 수거/밸런싱은 하지 않는다. 반환값도 전체 field가 아니라
    비-HERO 테이블이 소유한 player/table/tilt 부분만 담는다.
    """
    base = _copy_field(field_dump)
    f = _load_field(base)
    f.notes = []
    hero_tid, other_tids, other_pids = _round_owners(base)

    _suf = FS.BOT_SUFFIX
    _tmp = SP.pending_suffix(_suf, os.getpid())
    FS.BOT_SUFFIX = _tmp
    try:
        f.step_others(settle=False, simultaneous=True,
                      runner=_parallel_tables_runner)
    finally:
        FS.BOT_SUFFIX = _suf

    out = _dump(f)
    _p = SP.path_for('bot_log', _tmp, D)
    _bot_log = ''
    if os.path.exists(_p):
        with open(_p, encoding='utf-8') as fp:
            _bot_log = fp.read()
        try: os.remove(_p)
        except OSError: pass

    players = {}
    for pid in other_pids:
        k = str(pid)
        if k in out['players']:
            players[k] = copy.deepcopy(out['players'][k])

    tables = {}
    for tid in other_tids:
        k = str(tid)
        if k in out['tables']:
            tables[k] = copy.deepcopy(out['tables'][k])

    tilt = {}
    for pid in other_pids:
        k = str(pid)
        if k in (out.get('tilt') or {}):
            tilt[k] = copy.deepcopy(out['tilt'][k])

    # 장부: 관찰자가 비-HERO 테이블 사람인 항목만 이 worker 소유다.
    _op = {str(x) for x in other_pids}
    _ob = out.get('book') or {}
    book = RD.copy_book_d({k: v for k, v in _ob.items() if str(k).partition('>')[0] in _op})

    return {
        'mode': PARALLEL_TABLES_MODE,
        'base_key': _others_key(base),
        'hero_table': hero_tid,
        'players': players,
        'tables': tables,
        'tilt': tilt,
        'book': book,
        'notes': list(f.notes),
        'bot_log': _bot_log,
    }


def _overlay_parallel_dump(main_dump, base_dump, others):
    """두 병렬 branch의 소유 영역만 합친다. 아직 bust/balance는 하지 않는다."""
    if not isinstance(others, dict) or others.get('mode') != PARALLEL_TABLES_MODE:
        raise ValueError('parallel worker result mode mismatch')
    want = _others_key(base_dump)
    if others.get('base_key') != want:
        raise ValueError('parallel worker base key mismatch')

    hero_tid, other_tids, other_pids = _round_owners(base_dump)
    if int(others.get('hero_table', -1)) != hero_tid:
        raise ValueError('parallel worker hero table mismatch')

    expected_tables = {str(x) for x in other_tids}
    expected_players = {str(x) for x in other_pids}
    if set((others.get('tables') or {}).keys()) != expected_tables:
        raise ValueError('parallel worker table ownership mismatch')
    if set((others.get('players') or {}).keys()) != expected_players:
        raise ValueError('parallel worker player ownership mismatch')

    merged = _copy_field(main_dump)
    for pid, row in (others.get('players') or {}).items():
        merged['players'][str(pid)] = copy.deepcopy(row)
    for tid, row in (others.get('tables') or {}).items():
        merged['tables'][str(tid)] = copy.deepcopy(row)

    # HERO branch의 decay_all 이 다른 테이블 pid까지 건드렸을 수 있다.
    # 비-HERO pid의 tilt는 worker 결과만 권위 있게 사용한다.
    mt = merged.setdefault('tilt', {})
    wt = others.get('tilt') or {}
    for pid in expected_players:
        mt.pop(pid, None)
        if pid in wt:
            mt[pid] = copy.deepcopy(wt[pid])

    # 장부: 관찰자가 비-HERO pid 인 항목은 worker 결과만 권위 있게 쓴다(L161).
    mb = merged.setdefault('book', {})
    for k in [k for k in mb if str(k).partition('>')[0] in expected_players]:
        del mb[k]
    _wb = others.get('book') or {}
    mb.update(RD.copy_book_d({k: v for k, v in _wb.items()
                              if str(k).partition('>')[0] in expected_players}))
    return merged


def _merge_parallel_field(main_field, base_dump, others):
    """HERO 결과 field에 비-HERO worker 소유 영역을 합치고 1회 settle 한다."""
    merged = _overlay_parallel_dump(_dump(main_field), base_dump, others)
    f2 = _load_field(merged)
    f2.notes = []
    f2._collect_busts()
    f2._balance()
    settle_notes = list(f2.notes)
    f2.notes = []
    return f2, list(others.get('notes') or []) + settle_notes


def _append_bot_log(text):
    if not text:
        return
    with open(SP.sidecar_path('bot_log'), 'a', encoding='utf-8') as fp:
        fp.write(text)


# ---------- 밀린 '다른 테이블 진행' ----------
# finish 가 defer_others=True 로 불리면 step_others 를 건너뛰고 상태에
# others_pending 표시만 남긴다. 실제 계산은 밖에서(워커 프로세스) 하고,
# 결과를 다음 step() 에 넘겨준다. 넘겨받지 못했으면 여기서 직접 돌린다.
#
# **워커는 상태 파일을 쓰지 않는다.** compute_others 는 필드 덤프를 받아
# 필드 덤프를 돌려줄 뿐이고, 파일 쓰기는 전부 기존 메인 경로(resume_others →
# save)가 한다. 그래야 쓰기가 한 곳으로 직렬화된다.
def compute_others(field_dump):
    """다른 테이블을 진행시킨다. 순수 함수 — 파일을 읽지도 쓰지도 않는다.

    finish 의 원래 순서를 그대로 재현한다. step_others() 가 끝에서
    _collect_busts/_balance 를 부르고, finish 가 그 뒤에 한 번 더 부른다.
    호출 횟수까지 같아야 결과가 같다(tools/verify_settle_split.py 로 확인함).

    _load_field 는 프로필 dict 를 넘겨받은 덤프와 그대로 공유하므로
    (live2.py 의 _load_field 참고) 반드시 깊은 복사로 넘긴다.
    """
    f = _load_field(_copy_field(field_dump))
    f.notes = []
    # 봇 핸드 기록은 fieldsim._log_bot_hand 가 모듈 폴더에 직접 append 한다.
    # 워커에서 그대로 두면 (1) 결과를 버리고 다시 계산할 때 줄이 중복되고
    # (2) 워커가 쓰기 도중 죽으면 줄이 잘린다. 실제로 둘 다 관측했다.
    # 그래서 워커에서는 임시 접미사로 빼두고, 파일에 붙이는 일은
    # resume_others(= 메인 경로) 가 한다. 쓰기는 한 곳으로 모은다.
    _suf = FS.BOT_SUFFIX
    _tmp = SP.pending_suffix(_suf, os.getpid())
    FS.BOT_SUFFIX = _tmp
    try:
        f.step_others(settle=False, simultaneous=True,
                      runner=_parallel_tables_runner)
        f._collect_busts(); f._balance()
    finally:
        FS.BOT_SUFFIX = _suf
    _p = SP.path_for('bot_log', _tmp, D)
    _bot_log = ''
    if os.path.exists(_p):
        with open(_p, encoding='utf-8') as fp:
            _bot_log = fp.read()
        try: os.remove(_p)
        except OSError: pass
    return {'field': _dump(f), 'notes': list(f.notes), 'bot_log': _bot_log,
            'key': _others_key(field_dump)}


def _others_key(field_dump):
    """어느 시점의 필드로 계산했는지 못박는 지문."""
    return _zlib.crc32(json.dumps(field_dump, sort_keys=True,
                                  separators=(',', ':')).encode())


def _resume_parallel_others(st, others=None):
    """병렬 라운드의 비-HERO 결과를 HERO 결과 field와 합친 뒤 settle 한다."""
    base = st.get('others_base')
    if not base:
        # 구/손상 상태의 안전망. HERO 결과를 보존한 채 예전 순차 경로로 끝낸다.
        legacy = compute_others(st['field'])
        st['field'] = legacy['field']
        _telemetry_bot_rows = TM.parse_bot_log(legacy.get('bot_log'))
        _append_bot_log(legacy.get('bot_log'))
        _new_notes = list(legacy.get('notes') or [])
        how = 'fallback'
        merged_f = _load_field(_copy_field(st['field']))
    else:
        want = _others_key(base)
        how = 'hit'
        if others is None:
            how = 'fallback'
        elif (others.get('mode') != PARALLEL_TABLES_MODE
              or others.get('base_key') != want):
            how = 'mismatch'
        if how != 'hit':
            others = compute_others_parallel(base)

        main_f = _load_field(_copy_field(st['field']))
        merged_f, _new_notes = _merge_parallel_field(
            main_f, base, others)
        st['field'] = _dump(merged_f)
        _telemetry_bot_rows = TM.parse_bot_log(others.get('bot_log'))
        _append_bot_log(others.get('bot_log'))

    if st.pop('bust_pending', False):
        _hero = merged_f.players.get(merged_f.hero_pid)
        if _hero and _hero.get('stack', 0) <= 0:
            if merged_f.hero_pid in merged_f.busted_order:
                after = (
                    len(merged_f.busted_order)
                    - merged_f.busted_order.index(merged_f.hero_pid)
                    - 1
                )
                rank = merged_f.remaining() + 1 + after
            else:
                rank = merged_f.remaining() + 1

            st['busted'] = True
            st['rank'] = rank
            itm = ' (ITM!)' if rank <= merged_f.itm else ''
            _new_notes.append(
                '💀 탈락 — %d명 중 %d위%s'
                % (merged_f.entries, rank, itm)
            )

    if _new_notes:
        st['pending_notes'] = list(st.get('pending_notes') or []) + _new_notes

    rec = st.pop('pending_archive', None)
    if rec is not None:
        rec['field'] = merged_f.status()
        rec['notes'] = list(rec.get('notes') or []) + _new_notes
        _archive_write(rec)
        try:
            TM.emit_round(
                st, merged_f, rec,
                locals().get('_telemetry_bot_rows', []),
                source='resume_parallel', round_before=base)
        except Exception:
            pass

    st.pop('others_pending', None)
    st.pop('others_mode', None)
    st.pop('others_base', None)
    save(st)
    return how


def resume_others(st, others=None):
    """밀린 다른 테이블 진행을 마무리하고 상태에 반영한다.

    others 가 주어지고 지문이 맞으면 그 결과를 쓰고(hit), 아니면 여기서
    직접 계산한다(fallback). 지문이 어긋나면 **버린다.** 성능 때문에
    상태의 정확성을 희생하지 않는다.
    """
    if not st.get('others_pending'):
        return None
    if st.get('others_mode') == PARALLEL_TABLES_MODE:
        return _resume_parallel_others(st, others)
    want = _others_key(st['field'])
    how = 'hit'
    if others is None:
        how = 'fallback'
    elif others.get('key') != want:
        how = 'mismatch'
    if how != 'hit':
        others = compute_others(st['field'])
    st['field'] = others['field']
    _telemetry_bot_rows = TM.parse_bot_log(others.get('bot_log'))
    if others.get('bot_log'):          # 워커가 모아둔 봇 핸드 기록을 여기서 붙인다
        with open(SP.sidecar_path('bot_log'), 'a', encoding='utf-8') as fp:
            fp.write(others['bot_log'])
    _new_notes = list(others.get('notes') or [])

    if st.pop('bust_pending', False):
        _f2 = _load_field(
            _copy_field(st['field'])
        )

        _hero = _f2.players.get(_f2.hero_pid)

        if _hero and _hero.get('stack', 0) <= 0:
            if _f2.hero_pid in _f2.busted_order:
                after = (
                    len(_f2.busted_order)
                    - _f2.busted_order.index(_f2.hero_pid)
                    - 1
                )
                rank = _f2.remaining() + 1 + after
            else:
                rank = _f2.remaining() + 1

            st['busted'] = True
            st['rank'] = rank

            itm = ' (ITM!)' if rank <= _f2.itm else ''

            _new_notes.append(
                '💀 탈락 — %d명 중 %d위%s'
                % (_f2.entries, rank, itm)
            )

    if _new_notes:
        st['pending_notes'] = list(st.get('pending_notes') or []) + _new_notes
    rec = st.pop('pending_archive', None)
    if rec is not None:
        # 정산이 끝났으니 비워둔 자리를 채운다. 키 순서는 그대로다.
        _final_f = _load_field(_copy_field(others['field']))
        rec['field'] = _final_f.status()
        rec['notes'] = list(rec.get('notes') or []) + _new_notes
        _archive_write(rec)
        try:
            TM.emit_round(
                st, _final_f, rec, _telemetry_bot_rows,
                source='resume_legacy')
        except Exception:
            pass
    st.pop('others_pending', None)
    save(st)
    return how


# ---------- 진행 ----------
def step(action=None, amount=0, defer_others=False, others=None,
         on_bot_action=None, on_round_start=None, vclock_others=False):
    st = load()
    TM.ensure_session(st)
    # 밀린 진행이 있으면 **다음 핸드를 딜하기 전에** 반드시 끝낸다.
    # 서버가 죽어도 상태 파일의 others_pending 이 남아 여기서 복구된다.
    if st.get('others_pending'):
        resume_others(st, others)
        others = None
    f = _load_field(st['field'])

    # worker 정산에서 히어로 탈락이 확정됐으면
    # 새 핸드를 만들지 않고 최종 순위만 돌려준다.
    if st.get('busted'):
        return {
            'done': True,
            'game_over': True,
            'won': False,
            'busted': True,
            'rank': st.get('rank'),
            'remaining': f.remaining(),
            'entries': f.entries,
            'view': None,
            'status': f.status(),
        }

    # 대회가 이미 끝났다면 새 핸드를 절대 만들지 않는다.
    # 정상 플레이에서는 서버가 먼저 막지만, live2.step() 자체도 안전해야 한다.
    # 특히 우승 후 브라우저 새로고침/직접 호출 때문에 1명 남은 필드에
    # 새 핸드를 딜하려던 경로를 여기서 최종 차단한다.
    if f.remaining() <= 1:
        hero = f.players.get(f.hero_pid)
        won = bool(hero and hero.get('stack', 0) > 0 and f.remaining() == 1)
        rank = 1 if won else st.get('rank')
        st['busted'] = not won
        st['rank'] = rank
        st['field'] = _dump(f)
        save(st)
        return {
            'done': True,
            'game_over': True,
            'won': won,
            'busted': not won,
            'rank': rank,
            'remaining': f.remaining(),
            'entries': f.entries,
            'view': None,
            'status': f.status(),
        }

    if st['hand_seed'] is None:
        # 미뤄둔 진행이 남긴 알림(테이블 브레이크·자리 이동)을 여기서 붙인다.
        # defer 를 안 쓰면 pending_notes 가 아예 없어 기존과 동일하다.
        _pending_notes = list(st.pop('pending_notes', None) or [])
        f.hand_no += 1
        prev_level = f.level
        f.advance_level()
        st['notes'] = _pending_notes + (list(f.notes[-3:]) if f.level != prev_level else [])
        f.notes = []
        # 전역 random 을 쓰면 OS 엔트로피로 시드되어 **같은 시드가 재현되지 않는다.**
        # 실제로 같은 seed 로 new_game 을 세 번 하면 매번 다른 핸드가 나왔다.
        # 기준 시드와 핸드 번호에서 결정론적으로 파생한다.
        _base = st.get('seed')
        if _base is None:
            _base = random.randrange(10**9); st['seed'] = _base
        st['hand_seed'] = _zlib.crc32(('%s|%d' % (_base, f.hand_no)).encode()) % (10**9)
        st['actions'] = []; st['decisions'] = []
        st['field'] = _dump(f)
        save(st)
        # UI 서버는 이 순간 비-HERO 테이블 worker를 띄운다.
        # 콜백 실패가 게임 진행을 막아서는 안 된다.
        if on_round_start is not None:
            try:
                on_round_start(_copy_field(st['field']))
            except Exception:
                pass

    # build_hand/HandRun이 내부 상태를 바꿔도 worker 기준점은
    # 반드시 라운드 시작 field 그대로여야 한다.
    _round_base = _copy_field(st['field'])
    f, tb, alive, h, hero_seat = build_hand(st)
    # 저장된 HERO 액션을 재생하는 동안은 UI 진행 콜백을 끈다.
    # 그렇지 않으면 과거 봇 액션을 현재 액션처럼 다시 스트리밍한다.
    run = SE.HandRun(h, decisions=st.get('decisions'))
    raw = run.start()
    for (a, amt) in st['actions']:
        if isinstance(raw, dict) and (raw.get('done') or raw.get('error')): break
        raw = run.send(a, amt)

    # 여기부터가 이번 요청에서 처음 계산되는 구간이다.
    run.on_bot_action = on_bot_action

    # 재생 중 기록된 액션이 불법이 됐으면 여기서 멈추고 정상 오류 응답으로 돌려준다.
    # 예전에는 오류 프레임에 **다음 기록 액션**을 그대로 먹였다. session 의
    # 히어로 재적용(프리플랍 157 · 포스트플랍 337)은 try 밖이라 ValueError 가
    # 서버까지 올라가 500 이 됐고, 상태가 저장되지 않아 다시 눌러도 같은 벽이었다
    # (= 그 핸드 영구 차단). 원인(재생 재지터)은 session 쪽에서 없앴지만
    # 안전망으로 남긴다.
    if isinstance(raw, dict) and raw.get('error'):
        return {'view': _render(raw, f, h, st), 'done': False, 'raw': raw}

    if action is not None and not (isinstance(raw, dict) and raw.get('done')):
        raw2 = run.send(action, amount)
        if isinstance(raw2, dict) and raw2.get('error'):
            return {'view': _render(raw2, f, h, st), 'done': False, 'raw': raw2}
        st['actions'].append([action, amount])
        st['decisions'] = [list(d) for d in run.recorded]
        save(st)
        raw = raw2

    if isinstance(raw, dict) and raw.get('done'):
        return finish(st, f, tb, alive, h, run, defer_others=defer_others,
                      parallel_others=others, round_base=_round_base,
                      vclock_others=vclock_others)
    return {'view': _render(raw, f, h, st), 'done': False, 'raw': raw}


def _render(raw, f, h, st):
    sb, bb = f.blinds()
    stt = f.status()

    class _F:
        def status(self_): return stt
        def avg_stack_bb(self_, ss, b): return stt['avg']/b
    v = view.build(raw, h, _F(), f.level, (sb, bb), f.hand_no, st.get('notes'),
                   f.start_stack)
    return view.render(v)



def _opening_raw(h, run):
    """히어로 액션 없이 끝난 핸드도 UI가 처음부터 재생할 수 있게
    '카드 배분 후, 액션 전' 상태를 복원한다."""

    stacks = dict(
        getattr(run, '_before', None)
        or getattr(h, '_start_stacks', None)
        or h.stacks
    )

    contrib = {}
    allin = set()

    sb_s = h.seat_of.get('SB')
    bb_s = h.seat_of.get('BB')

    # 강제 베팅은 session 과 같은 함수·같은 순서(안테 균등 분담 → SB → BB).
    _ante = getattr(h, 'ante', None)
    if _ante is None:
        _ante = h.bb
    _seats = [h.seat_of[p] for p in h.PRE if p in h.seat_of]
    _blinds, _ante_paid, ante_pot, _allin0 = RU.post_forced_bets(
        stacks, _seats, sb_s, bb_s, h.sb, h.bb, _ante)
    contrib.update(_blinds)
    allin.update(_allin0)

    hero = h.hero
    hero_contrib = contrib.get(hero, 0)
    tocall = max(0, h.bb - hero_contrib)

    return {
        'stage': 'preflop',
        'pos': h.pos.get(hero, ''),
        'hole': list(h.hole.get(hero, [])),
        'stacks': dict(stacks),
        'contrib': dict(contrib),
        'pot': sum(contrib.values()) + ante_pot,
        'ante_paid': dict(_ante_paid),
        'tocall': tocall,
        'stack': stacks.get(hero, 0),
        'min_raise': h.bb * 2,
        'can_raise': stacks.get(hero, 0) > tocall,
        'log': [],
        'live': list(h.seats),
        'allin': sorted(allin),
        'hash': h.hash,
    }


def finish(st, f, tb, alive, h, run, defer_others=False,
           parallel_others=None, round_base=None, vclock_others=False):
    res = run.result or {}

    try:
        opening_view = _render(
            _opening_raw(h, run),
            f, h, st
        )
    except Exception:
        opening_view = None

    # 히어로 테이블 스택 반영
    for p in alive:
        s = tb.seat_of(p['pid'])
        if s: p['stack'] = int(h.stacks.get(s, p['stack']))
    # 고정 좌석 기준으로 다음 딜러를 정한다.
    tb.advance_button()
    tb.hands += 1

    import dynamics as DY
    try: pass   # 틸트는 대회 객체가 들고 있다
    except Exception: pass

    # 다른 테이블 진행.
    #
    # 병렬 모드에서는 라운드 시작 스냅샷에서 worker가 이미 비-HERO 테이블을
    # 계산하고 있다. 준비된 결과가 있으면 HERO 결과와 합친 뒤 여기서만
    # bust 수거/밸런싱을 1회 수행한다.
    _hero_busted_now = (
        f.players[f.hero_pid]['stack'] <= 0
    )
    _hero_notes = list(f.notes)
    _parallel_notes = []
    _round_base = _copy_field(round_base if round_base is not None
                              else (st.get('field') or {}))

    _hero_tid, _other_tids, _other_pids = _round_owners(_round_base)
    _single_table_round = not _other_tids

    if vclock_others:
        # 비-HERO 테이블은 UI 서버의 독립 가상시계 선계산기가 소유한다.
        # 여기서는 HERO 핸드 결과만 저장하고, bust/balance는 같은 시간축의
        # 봇 이벤트가 확정되는 HERO 핸드 경계에서 한 번만 수행한다.
        st['vclock_settle_pending'] = True
        if _hero_busted_now:
            st['vclock_hero_bust_pending'] = True

    elif defer_others and parallel_others is not None:
        try:
            f, _parallel_notes = _merge_parallel_field(
                f, _round_base, parallel_others)
            _append_bot_log(parallel_others.get('bot_log'))
        except Exception:
            # 잘못된/다른 라운드 결과는 절대 합치지 않는다.
            parallel_others = None

    if defer_others and _single_table_round:
        # 파이널테이블: 다른 테이블이 없으므로 worker/pending을 만들 이유가 없다.
        # HERO 핸드 결과만으로 bust 정리/좌석 reconcile을 즉시 끝낸다.
        f._collect_busts()
        f._balance()

    elif defer_others and parallel_others is None:
        st['others_pending'] = True
        st['others_mode'] = PARALLEL_TABLES_MODE
        # 서버가 worker 완료 전에 죽어도 같은 라운드 스냅샷에서 재계산한다.
        st['others_base'] = _round_base

        if _hero_busted_now:
            st['bust_pending'] = True

    elif not defer_others:
        f.step_others(settle=False, simultaneous=True,
                      runner=_parallel_tables_runner)
        f._collect_busts()
        f._balance()

    notes = _hero_notes + _parallel_notes + list(f.notes)
    f.notes = []

    hero = f.players[f.hero_pid]
    busted_now = hero['stack'] <= 0
    pending = bool(
        st.get('others_pending') or st.get('vclock_settle_pending'))

    # worker 정산 전에는 정확한 탈락 순위가 아직 없다.
    # 그동안은 busted=False로 저장해 UI가 쇼다운/결과를 정상 재생하게 한다.
    busted = bool(busted_now and not pending)
    rank = None

    if busted:
        if f.hero_pid in f.busted_order:
            after = (
                len(f.busted_order)
                - f.busted_order.index(f.hero_pid)
                - 1
            )
            rank = f.remaining() + 1 + after
        else:
            rank = f.remaining() + 1

        itm = ' (ITM!)' if rank <= f.itm else ''

        notes.append(
            '💀 탈락 — %d명 중 %d위%s'
            % (f.entries, rank, itm)
        )

    if (getattr(f, 'virtual_play_seconds', None) is not None
            and not vclock_others):
        # Legacy virtual-time path only. UI vclock_others uses the real HERO wall-clock.
        f.virtual_play_seconds += _vclock_hand_seconds(res)
    st['field'] = _dump(f)                     # 리딩 누적(장부)은 field 안에 함께 저장된다
    st.pop('book', None)
    st['hand_seed'] = None; st['actions'] = []; st['decisions'] = []
    st['notes'] = notes
    st['busted'] = busted; st['rank'] = rank
    save(st)

    h._telemetry_tilt_after = {
        str(p['pid']): copy.deepcopy(f.tilt.state.get(str(p['pid']), {}))
        for p in alive
    }
    _hero_rec = _archive(
        st, f, h, res, notes,
        defer=bool(st.get('others_pending') or st.get('vclock_settle_pending')),
        run=run)
    if not st.get('others_pending'):
        if parallel_others is not None:
            _bot_rows = TM.parse_bot_log(parallel_others.get('bot_log'))
        elif _single_table_round:
            _bot_rows = []
        else:
            _bot_rows = TM.read_bot_round(
                SP.sidecar_path('bot_log'), f.hand_no)
        try:
            TM.emit_round(
                st, f, _hero_rec, _bot_rows,
                source='finish', round_before=_round_base)
        except Exception:
            pass
    if st.get('pending_archive'):
        # _archive 는 save() 뒤에 불린다. 미뤄둔 기록은 따로 한 번 더 저장해야
        # 다음 step() 이 디스크에서 읽을 수 있다.
        save(st)
    res['hero_seat'] = h.hero
    res.setdefault('pos', {str(k): v for k, v in h.pos.items()})
    # 결과도 화면으로 렌더한다. 예전에는 raw dict 만 돌려줘서
    # 무슨 일이 있었는지 읽을 수 없었다(다음 판이 바로 시작됐다).
    try:
        view_txt = view.render_result(res, hero=h.hero, hand_no=f.hand_no,
                                      notes=notes, bb=f.blinds()[1])
    except Exception as e:
        view_txt = '결과 렌더 실패: %s: %s' % (type(e).__name__, e)
    return {'done': True, 'view': view_txt, 'result': res, 'notes': notes,
            'hand_no': f.hand_no, 'busted': busted, 'rank': rank,
            'bust_pending': bool(st.get('bust_pending')),
            'opening_view': opening_view,
            'status': f.status()}


def _archive_json_safe(v):
    """JSON-safe telemetry copy; never used by strategy consumers.

    Weighted ranges use tuple(card, card) keys internally.  JSON forbids tuple
    object keys even with default=str, so serialize those keys only at the
    archive boundary instead of flattening probability weights in live logic.
    """
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if isinstance(k, tuple):
                if len(k) == 2 and all(isinstance(c, str) for c in k):
                    kk = '%s|%s' % (k[0], k[1])
                else:
                    kk = repr(k)
            else:
                kk = k
            out[kk] = _archive_json_safe(x)
        return out
    if isinstance(v, (list, tuple)):
        return [_archive_json_safe(x) for x in v]
    if isinstance(v, set):
        return [_archive_json_safe(x) for x in sorted(v, key=lambda z: str(z))]
    return v

def _archive_write(rec):
    path = SP.sidecar_path('archive')
    with open(path, 'a', encoding='utf-8') as fp:
        fp.write(json.dumps(
            _archive_json_safe(rec), ensure_ascii=False, default=str) + '\n')


def _archive(st, f, h, res, notes, defer=False, run=None):
    """핸드 기록. defer 면 파일에 쓰지 않고 상태에 넣어둔다.

    기록의 'field'(f.status())와 'notes' 는 다른 테이블까지 정산돼야 확정된다.
    그래서 지연 중에는 자리만 비워 두고, resume_others 가 채워서 쓴다.
    자리를 **미리 만들어 두는 것**이 중요하다 — 나중에 키를 새로 추가하면
    JSON 키 순서가 달라져 기존 파일과 바이트가 안 맞는다.
    """
    # 좌석은 테이블 밸런싱 때 사람이 바뀐다. 사용자 메모는 pid 기준으로
    # 저장하고, 이 핸드에서 seat↔pid 관계도 같이 남겨 나중 분석이 가능하게 한다.
    seat_pid = {
        str(seat): int(pid)
        for seat, pid in (getattr(h, 'seat_pid', {}) or {}).items()
    }
    all_memos = st.get('hero_memos') or {}
    hand_memos = {}
    for pid in seat_pid.values():
        memo = all_memos.get(str(pid), all_memos.get(pid, ''))
        if memo:
            hand_memos[str(pid)] = str(memo)

    rec = {'hand_no': f.hand_no, 'hash': getattr(h, 'hash', None),
           'level': f.level, 'blinds': list(f.blinds()),
           'button': h.button, 'hero': h.hero,
           'pos': {str(k): v for k, v in h.pos.items()},
           'seat_pid': seat_pid,
           'hero_memos': hand_memos,
           'hole': {str(k): v for k, v in h.hole.items()},
           'board': h.board,
           'stacks_before': {str(k): v for k, v in getattr(h, '_start_stacks', {}).items()},
           'full_log': res.get('full_log', []),
           'full_action_meta': copy.deepcopy(
               getattr(run, 'full_action_meta', []) or []) if run is not None else [],
           # Read-only provenance: preflop-only hands used to lose the complete
           # decision story because plans/intents are created postflop.  Keep the
           # seat-keyed preflop seeds so audit can prove which range/context path
           # actually produced each open/call/reraise/fold.
           'pf_seed': copy.deepcopy(getattr(h, 'pf_seed', {}) or {}),
           'intents': copy.deepcopy(getattr(h, 'intents', []) or []),
           'plans': copy.deepcopy(getattr(h, 'plans', {}) or {}),
           'decision_cache': copy.deepcopy(
               getattr(run, 'recorded', []) or []) if run is not None else [],
           'money_jump_obs': copy.deepcopy(
               getattr(h, 'money_jump_obs', []) or []),
           'reads': copy.deepcopy(getattr(h, 'reads_log', []) or []),
           'range_fallback_audit': copy.deepcopy(
               getattr(h, 'range_fallback_audit', []) or []),
           'book_before': copy.deepcopy(
               getattr(h, '_telemetry_book_before', {}) or {}),
           'book_after': FS.book_view(
               getattr(h.book, 'd', {}) or {},
               getattr(h, '_telemetry_book_pids', None)
               or [str(x) for x in (getattr(h, 'seat_pid', {}) or {}).values()]),
           'tilt_before': copy.deepcopy(
               getattr(h, '_telemetry_tilt_before', {}) or {}),
           'tilt_after': copy.deepcopy(
               getattr(h, '_telemetry_tilt_after', {}) or {}),
           'street_outcomes': copy.deepcopy(
               getattr(h, 'street_outcomes', {}) or {}),
           'uncalled_returns': copy.deepcopy(
               getattr(h, 'uncalled_returns', []) or []),
           'field_context': {
               'remaining': getattr(h, 'field_remaining', None),
               'itm': getattr(h, 'field_itm', None),
               'avg_stack': getattr(h, 'field_avg_stack', None),
               'field_q': getattr(h, 'field_q', None),
               'payouts': copy.deepcopy(getattr(h, 'payouts', None)),
               'payout_flat': getattr(h, 'payout_flat', None),
               'progress': getattr(h, 'progress', None),
               'erosion_per_hand': getattr(h, 'erosion_per_hand', None),
               'money_jump': copy.deepcopy(getattr(h, 'money_jump', None)),
               'ante': getattr(h, 'ante', None),
           },
           'result': {k: v for k, v in res.items() if k != 'full_log'},
           'field': (None if defer else f.status()), 'notes': list(notes),
           'profiles': {str(s): h.prof.get(str(s), {}) for s in h.seats}}
    if defer:
        # save() 는 default=str 를 안 쓰므로 여기서 미리 JSON 안전하게 만든다.
        st['pending_archive'] = _archive_json_safe(rec)
        return rec
    _archive_write(rec)
    return rec
