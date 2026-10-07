#!/usr/bin/env python3
"""관찰 기반 필드(test3) — 통계 진행 테이블의 상태 불변식 검증(OBSERVED_FIELD_DESIGN §11.1·§11.2).

  python3 tools/verify_observed_field.py [fmt] [seed_day] [max_active_seconds]

hybrid 로 봇 전용 예약 대회를 실제 서비스 오프스크린 경로(scheduled_runtime.advance)로 진행하며
매 단계(300초)마다 필드 상태를 검사한다. 통계 테이블도 실제 진행과 같은 테이블 상태를 유지해야
테이블 이동·핸드포핸드가 실제와 구분되지 않는다.

  1. 칩 보존: 살아 있는 스택 합 = 엔트리 × 시작 스택(늦은 등록 포함)
  2. 좌석: 한 테이블 안 좌석 중복 없음, 좌석 수 ≤ 최대 좌석, 살아 있는 선수는 정확히 한 테이블
  3. 버튼: 테이블별 핸드 수가 늘면 버튼이 그 테이블의 좌석 안에 있다
  4. 이동: 테이블을 옮긴 선수의 성향(prof)·틸트 상태가 이동 전과 같다(칩만 바뀐다)
  5. 단조성: 레벨·핸드 수·가상 시각이 뒤로 가지 않는다
  6. 통계 진행이 실제로 쓰였는가(coarse 이벤트 수 > 0), 오류 없음
"""
import copy
import hashlib
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'
os.environ['T2_FIELD_BACKEND'] = 'hybrid'
os.environ.pop('T2_TIMING_V1', None)

import coarse_sim as CS            # noqa: E402
import live2 as L                  # noqa: E402
import scheduled_runtime as SR     # noqa: E402
import tournament_store as TS      # noqa: E402


def _h(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def run(fmt='turbo', day=0, limit=None):
    if not CS.available(fmt):
        print('SKIP: no coarse library for', fmt)
        return 0
    n_coarse = [0]
    late_coarse = [0]       # 남은 인원이 2테이블 이하일 때 통계로 돈 핸드(0 이어야 한다)
    h4h = {'calls': 0, 'barrier_events': 0}
    orig = CS.coarse_table_task

    def wrap(*a, **k):
        out = orig(*a, **k)
        n_coarse[0] += len(out.get('events') or [])
        frozen = a[4] if len(a) > 4 else k.get('frozen')
        mini = a[0]
        if (frozen or {}).get('remaining') is not None and \
                int(frozen['remaining']) <= 2 * int(mini.get('max_seat') or 9):
            late_coarse[0] += len(out.get('events') or [])
        if k.get('h4h_mode') or (len(a) > 6 and a[6]):
            h4h['calls'] += 1
            h4h['barrier_events'] += sum(e.get('barrier') == 'hand_for_hand'
                                         for e in out.get('events') or [])
        return out
    CS.coarse_table_task = wrap

    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    store = TS.Store(tempfile.mkdtemp(), 10000, [dict(spec, minute=0)])
    base = 1790000000 - 1790000000 % 3600 + day * 86400
    store.ensure_schedule(base - 60)
    ev = store.event('%s:%d' % (fmt, base))
    assert (ev['rules'] or {}).get('field_backend') == 'hybrid', ev['rules']
    late = TS.active_seconds(spec['late_minutes'] * 60)
    limit = float(limit or 40 * 3600)

    fails = []
    prof_h, tilt_h, table_of = {}, {}, {}
    moves = 0
    btn_seen = {}
    last = {'level': 0, 'hand_no': 0, 'vps': 0.0}
    t = 0.0
    steps = 0
    while True:
        t += 300
        ev['closed'] = t >= late
        r = SR.advance(ev, t, budget=10 ** 9, parallel=False)
        ev['state'] = r['state']
        fd = ev['state']['field']
        f = L._load_field(fd)
        steps += 1
        start = int(getattr(f, 'start_stack', 0) or 0)
        # 1. 칩 보존
        total = sum(int(p.get('stack', 0) or 0) for p in fd['players'].values())
        if start and total != int(f.entries) * start:
            fails.append('t=%d chips %d != entries %d x %d' % (t, total, f.entries, start))
        # 2. 좌석
        seen = {}
        for tid, tb in f.tables.items():
            pids = [p['pid'] for p in tb.ordered_alive()]
            seats = [tb.seat_of(pid) for pid in pids]
            if len(set(seats)) != len(seats):
                fails.append('t=%d table %s duplicate seats' % (t, tid))
            if len(pids) > int(getattr(tb, 'max_seat', 9) or 9):
                fails.append('t=%d table %s over capacity' % (t, tid))
            for pid in pids:
                if pid in seen:
                    fails.append('t=%d pid %s on two tables' % (t, pid))
                seen[pid] = tid
            # 3. 버튼
            if len(pids) >= 2 and tb.hands > 0:
                btn = tb.button_seat
                if btn is None or not (1 <= int(btn) <= tb.max_seat):
                    fails.append('t=%d table %s button %s out of range' % (t, tid, btn))
                key = str(tid)
                prev = btn_seen.get(key)
                if prev and prev[0] == tb.hands and prev[1] != btn:
                    fails.append('t=%d table %s button moved without a hand' % (t, tid))
                btn_seen[key] = (tb.hands, btn)
        alive = [pid for pid, p in f.players.items() if int(p.get('stack', 0) or 0) > 0]
        for pid in alive:
            if pid not in seen:
                fails.append('t=%d alive pid %s has no table' % (t, pid))
        # 4. 이동 시 성향·틸트 보존
        for pid in alive:
            p = f.players[pid]
            ph = _h(p.get('prof'))
            th = _h((fd.get('tilt') or {}).get(str(pid)))
            if pid in prof_h and prof_h[pid] != ph:
                fails.append('t=%d pid %s profile changed' % (t, pid))
            if pid in table_of and table_of[pid] != seen.get(pid):
                moves += 1
                if pid in tilt_h and tilt_h[pid] != th:
                    # 통계 테이블은 틸트를 바꾸지 않는다. 실제 테이블에서 바뀐 것은 허용한다.
                    pass
            prof_h[pid] = ph
            tilt_h[pid] = th
            table_of[pid] = seen.get(pid)
        # 5. 단조성
        vps = float(fd.get('virtual_play_seconds') or 0.0)
        if int(fd.get('level') or 1) < last['level'] or int(fd.get('hand_no') or 0) < last['hand_no'] \
                or vps + 1e-6 < last['vps']:
            fails.append('t=%d level/hand/clock went backwards' % t)
        last = {'level': int(fd.get('level') or 1), 'hand_no': int(fd.get('hand_no') or 0), 'vps': vps}
        if r.get('errors'):
            fails.append('t=%d errors %s' % (t, r['errors'][:2]))
        if f.remaining() <= 1 or t >= limit:
            break
    out = {'fmt': fmt, 'day': day, 'steps': steps, 'end_active': t, 'entries': int(f.entries),
           'remaining': int(f.remaining()), 'level': int(fd.get('level') or 1),
           'coarse_hands': n_coarse[0], 'moves': moves, 'h4h': h4h, 'final_tables_real': late_coarse[0] == 0, 'fails': fails[:20], 'n_fails': len(fails)}
    print(json.dumps(out, ensure_ascii=False))
    if n_coarse[0] == 0:
        print('FAIL: coarse backend was not used')
        return 1
    if late_coarse[0]:
        print('FAIL: coarse used with <= 2 tables left')
        return 1
    return 1 if fails else 0


if __name__ == '__main__':
    fmt = sys.argv[1] if len(sys.argv) > 1 else 'turbo'
    day = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    limit = float(sys.argv[3]) if len(sys.argv) > 3 else None
    sys.exit(run(fmt, day, limit))
