#!/usr/bin/env python3
"""병렬 테이블 round의 소유권/merge 불변식 검증.

HERO 테이블과 나머지 테이블이 같은 round-start snapshot에서 갈라졌다가
끝에서 합쳐질 때 서로의 상태를 덮어쓰지 않는지 본다.
"""
import copy
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# import 전에 로그를 끈다. 검증은 사용자 sidecar를 쓰면 안 된다.
os.environ.setdefault('T2_BOT_LOG', '0')
_tmp = tempfile.mkdtemp(prefix='t2_parallel_round_')
os.environ['T2_LIVE_STATE'] = os.path.join(_tmp, 'state.json')

import fieldsim as FS
import live2 as L


def _chips(d):
    return sum(int(v['stack']) for v in d['players'].values())


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _make_base(entries=27, seed=20260927):
    f = FS.Field(entries=entries, start_stack=30000, hero_pid=0, seed=seed,
                 hands_per_level=12, itm_frac=0.15)
    f.hand_no += 1
    f.advance_level()
    f.notes = []
    return L._dump(f)


def check_overlay(seed):
    base = _make_base(seed=seed)
    hero_tid, other_tids, other_pids = L._round_owners(base)
    hero_pids = set(base['tables'][str(hero_tid)]['pids'])

    # HERO branch를 눈에 띄게 바꾼다. 실제 HandRun이 아니라 ownership 검증용.
    main = L._load_field(copy.deepcopy(base))
    ht = main.tables[hero_tid]
    alive = ht.ordered_alive()
    _assert(len(alive) >= 2, 'hero table needs >=2 players')
    a, b = alive[0], alive[1]
    move = min(137, int(b['stack']))
    a['stack'] += move
    b['stack'] -= move
    ht.advance_button()
    ht.hands += 1
    main.tilt._s(a['pid'])['level'] = 0.731
    main_dump = L._dump(main)

    worker1 = L.compute_others_parallel(base)
    worker2 = L.compute_others_parallel(base)

    # 같은 snapshot은 같은 other-table 결과를 내야 한다.
    for k in ('players', 'tables', 'tilt', 'notes', 'hero_table', 'base_key'):
        _assert(worker1.get(k) == worker2.get(k),
                'worker nondeterminism at %s' % k)

    _assert(str(hero_tid) not in worker1['tables'],
            'worker returned HERO table')
    _assert(not (hero_pids & {int(x) for x in worker1['players']}),
            'worker returned HERO player')

    over = L._overlay_parallel_dump(main_dump, base, worker1)

    # HERO-owned rows survive exactly.
    _assert(over['tables'][str(hero_tid)] == main_dump['tables'][str(hero_tid)],
            'HERO table overwritten')
    for pid in hero_pids:
        _assert(over['players'][str(pid)] == main_dump['players'][str(pid)],
                'HERO player %s overwritten' % pid)

    # Worker-owned rows come exactly from worker.
    for tid in other_tids:
        _assert(over['tables'][str(tid)] == worker1['tables'][str(tid)],
                'other table %s not merged' % tid)
    for pid in other_pids:
        _assert(over['players'][str(pid)] == worker1['players'][str(pid)],
                'other player %s not merged' % pid)

    # HERO tilt는 main, other tilt는 worker 소유.
    mt = main_dump.get('tilt') or {}
    ot = over.get('tilt') or {}
    wt = worker1.get('tilt') or {}
    for pid in hero_pids:
        k = str(pid)
        _assert(ot.get(k) == mt.get(k), 'HERO tilt %s overwritten' % pid)
    for pid in other_pids:
        k = str(pid)
        _assert(ot.get(k) == wt.get(k), 'other tilt %s not worker-owned' % pid)

    _assert(_chips(over) == _chips(base), 'chip total changed at overlay')

    settled, _notes = L._merge_parallel_field(main, base, worker1)
    final = L._dump(settled)
    _assert(_chips(final) == _chips(base), 'chip total changed after settle')

    sizes = [tb.n() for tb in settled.tables.values() if tb.n() > 0]
    if len(sizes) > 1:
        _assert(max(sizes) - min(sizes) <= 1,
                'tables not balanced after merged round: %r' % sizes)

    bad = copy.deepcopy(worker1)
    bad['base_key'] ^= 1
    try:
        L._overlay_parallel_dump(main_dump, base, bad)
    except ValueError:
        pass
    else:
        raise AssertionError('mismatched base_key was accepted')

    return {
        'seed': seed,
        'hero_table': hero_tid,
        'other_tables': len(other_tids),
        'other_players': len(other_pids),
        'remaining': settled.remaining(),
    }


def check_live_finish(seed=20260928):
    """live2.finish가 준비된 worker 결과를 즉시 merge하는 통합 경로."""
    L.new_game(entries=18, start_stack=30000, seed=seed)
    holder = {}

    def start_worker(field_dump):
        holder['base'] = copy.deepcopy(field_dump)
        holder['result'] = L.compute_others_parallel(field_dump)

    r = L.step(defer_others=True, on_round_start=start_worker)
    _assert('result' in holder, 'round-start callback did not run')

    guard = 0
    while not r.get('done'):
        guard += 1
        _assert(guard < 20, 'HERO hand did not finish')
        raw = r.get('raw') or {}
        # 가능한 한 빨리 끝내되 check 가능하면 규칙상 check를 쓴다.
        a = 'check' if float(raw.get('tocall') or 0) <= 0 else 'fold'
        r = L.step(a, 0, defer_others=True, others=holder['result'])

    st = L.load()
    _assert(not st.get('others_pending'), 'ready parallel result left pending')
    _assert('others_base' not in st, 'ready parallel result left others_base')
    _assert(st.get('hand_seed') is None, 'finished hand_seed not cleared')
    f = L._load_field(st['field'])
    _assert(f.total_chips() == f.entries * f.start_stack,
            'live finish chip total changed')
    return {'live_remaining': f.remaining(), 'live_hand_no': f.hand_no}


def main():
    rows = [check_overlay(20260927), check_overlay(20260931)]
    live = check_live_finish()
    print('parallel table round: OK')
    for row in rows:
        print('  seed %(seed)s hero_table=%(hero_table)s other_tables=%(other_tables)s '
              'other_players=%(other_players)s remaining=%(remaining)s' % row)
    print('  live hand=%(live_hand_no)s remaining=%(live_remaining)s' % live)


if __name__ == '__main__':
    main()
