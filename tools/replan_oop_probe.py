#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blockbet 수정 후 oop_vs_aggr / oop_legacy_abs / initiative 가 replan 경로에서
실제로 행동에 닿는지 보는 **짧은** targeted fixture.

  python3 tools/replan_oop_probe.py
  python3 tools/replan_oop_probe.py --seeds 5150 --fmts standard

A6 full fixture(810 events, 12분)를 다시 돌리지 않는다. 같은 재생 방식만
빌려 쓰고 fixture 를 줄인다. **A6 결과와 수치를 비교하지 말 것** — 분모가
다르다.

왜 arm 에 짝을 넣는가
--------------------
블락벳 게이트는 `plan.py:450`:

    _oop_a = oop_vs_aggr if oop_vs_aggr is not None else bool(oop_legacy_abs)
    if _oop_a and not initiative and 0.25 <= rel <= 0.80:

production 의 replan 경로(runner.revise_plan)는 이 셋을 하나도 안 넘긴다.
그래서 make_plan 기본값이 쓰이고 `_oop_a = bool(None) = False`,
`initiative = True` 다 — **게이트는 항상 닫혀 있다.**

따라서 한 필드만 현재값으로 바꿔도 게이트는 안 열린다.
  oop_vs_aggr 만      → initiative 가 기본값 True 라 `not initiative` 거짓
  oop_legacy_abs 만   → 같은 이유로 거짓
  initiative 만       → `_oop_a` 가 여전히 False
열리려면 (oop_vs_aggr 또는 oop_legacy_abs) **그리고** initiative 가 같이
현재값이어야 한다. 그래서 단독 arm 과 짝 arm 을 나눠 잰다.

읽기 전용이다. production 을 수정하지 않는다.
"""
from __future__ import print_function

import argparse
import copy
import inspect
import json
import os
import sys
import time
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import plan as PL
import runner as RU

FIELDS = ('oop_vs_aggr', 'oop_legacy_abs', 'initiative')
ARMS = OrderedDict([
    ('oop_vs_aggr', ('oop_vs_aggr',)),
    ('oop_legacy_abs', ('oop_legacy_abs',)),
    ('initiative', ('initiative',)),
    ('oop_vs+initiative', ('oop_vs_aggr', 'initiative')),
    ('oop_legacy+initiative', ('oop_legacy_abs', 'initiative')),
    ('all3', FIELDS),
])
BASELINE_DEFAULT = {'oop_vs_aggr': None, 'oop_legacy_abs': None,
                    'initiative': True}
BLOCK_MSG = '블락벳으로 가격 통제'
MID_MSG = '중간강도'


def _intent_sig(st, street):
    it = PL.intent_of(st, street) or {}
    return {'plan': (st or {}).get('plan'), 'act': it.get('act'),
            'size': round(it.get('size', 0) or 0, 6)}


def _diff_kind(a, b):
    return tuple(k for k in ('plan', 'act', 'size') if a.get(k) != b.get(k))


def capture(seeds, fmts, hands, entries):
    orig = PL.update_plan
    sig = inspect.signature(orig)
    events, counts = [], Counter()

    def wrapped(*a, **k):
        b = sig.bind_partial(*a, **k)
        b.apply_defaults()
        state = b.arguments.get('state')
        counts['update_plan'] += 1
        if state is not None and not b.arguments.get('first'):
            counts['revise_path'] += 1
            if RU.board_changed(b.arguments.get('prev_board'),
                                b.arguments.get('board')):
                counts['board_changed'] += 1
                events.append({
                    'args': copy.deepcopy(a), 'kwargs': copy.deepcopy(k),
                    'current': {f: copy.deepcopy(b.arguments.get(f))
                                for f in FIELDS},
                    'street': b.arguments.get('street'),
                })
        return orig(*a, **k)

    PL.update_plan = wrapped
    old = getattr(FS.Field, 'BOT_LOG', None)
    errors = []
    try:
        FS.Field.BOT_LOG = 0
        for fmt in fmts:
            for seed in seeds:
                f = FS.Field(entries=entries, seed=seed, fmt=fmt)
                for _ in range(hands):
                    if f.remaining() <= 8:
                        break
                    f.hand_no += 1
                    f.advance_level()
                    for tb in list(f.tables.values()):
                        if tb.n() >= 2:
                            f._play_table(tb)
                    f._collect_busts()
                    f._balance()
                errors.extend(getattr(f, 'errors', ()) or ())
    finally:
        PL.update_plan = orig
        if old is not None:
            FS.Field.BOT_LOG = old
    counts['engine_errors'] = len(errors)
    return events, counts, errors


def _candidate(current, selected):
    def cand(state, hero, board, my_range, opp_range, profile, pot, stack,
             street, seed, n_opp, behind, prev_board):
        if not RU.board_changed(prev_board, board):
            return state
        kw = {'seed': seed, 'n_opp': n_opp, 'to_act_behind': behind,
              'opp_est': state.get('opp_est'),
              'opp_stack_bb': state.get('opp_stack_bb')}
        for f in FIELDS:
            if f in selected:
                kw[f] = current.get(f)
        new = PL.make_plan(hero, board, my_range, opp_range, profile, pot,
                           stack, street, **kw)
        new['revised'] = True
        for key in ('intents', 'deviations', 'streets', 'refreshed',
                    'bet_streets', 'plan_since', '_rsig'):
            if state.get(key) is not None:
                new[key] = state[key]
        return new
    return cand


def replay(event, selected=()):
    orig = RU.revise_plan
    try:
        if selected:
            RU.revise_plan = _candidate(event['current'], set(selected))
        return PL.update_plan(*copy.deepcopy(event['args']),
                              **copy.deepcopy(event['kwargs']))
    finally:
        RU.revise_plan = orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='5150,9001,4242')
    ap.add_argument('--fmts', default='standard')
    ap.add_argument('--hands', type=int, default=16)
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    seeds = tuple(int(x) for x in a.seeds.split(','))
    fmts = tuple(a.fmts.split(','))

    t0 = time.time()
    events, counts, errors = capture(seeds, fmts, a.hands, a.entries)
    t_cap = time.time() - t0
    fix_present = '_block_taken' in open(os.path.join(ROOT, 'plan.py'),
                                         encoding='utf-8').read()

    base = [_intent_sig(replay(ev, ()), ev['street']) for ev in events]

    out = OrderedDict()
    for name, sel in ARMS.items():
        # 값이 하나도 안 다르면 재생하지 않는다 (A6 과 같은 규칙).
        changed, kinds, ids, blocks = 0, Counter(), [], 0
        for i, ev in enumerate(events):
            if all(ev['current'][f] == BASELINE_DEFAULT[f] for f in sel):
                continue
            st = replay(ev, sel)
            s = _intent_sig(st, ev['street'])
            if s['plan'] == 'block':
                blocks += 1
            dk = _diff_kind(base[i], s)
            if dk:
                changed += 1
                kinds['+'.join(dk)] += 1
                ids.append(i)
        out[name] = {'fields': list(sel), 'changed': changed,
                     'plan_block': blocks, 'diff_kinds': dict(kinds),
                     'event_ids': ids}

    prov = {f: sum(1 for ev in events
                   if ev['current'][f] != BASELINE_DEFAULT[f])
            for f in FIELDS}
    base_blocks = sum(1 for s in base if s['plan'] == 'block')

    payload = {'fixture': {'seeds': list(seeds), 'fmts': list(fmts),
                           'hands': a.hands, 'entries': a.entries},
               'blockbet_fix_present': fix_present,
               'counts': dict(counts), 'events': len(events),
               'provenance_different': prov,
               'baseline_plan_block': base_blocks,
               'arms': out, 'capture_seconds': round(t_cap, 1)}
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if errors else 0

    print('fixture seeds=%s fmts=%s hands=%d entries=%d'
          % (','.join(map(str, seeds)), ','.join(fmts), a.hands, a.entries))
    print('blockbet 수정 적용됨: %s' % fix_present)
    print('update_plan %d  revise_path %d  board_changed %d  engine_errors %d'
          % (counts['update_plan'], counts['revise_path'],
             counts['board_changed'], counts['engine_errors']))
    print('replan events %d  (capture %.1fs)' % (len(events), t_cap))
    print()
    print('provenance different: %s' % prov)
    print('production replan 의 plan == block: %d' % base_blocks)
    print()
    print('  %-24s %8s %12s  %s' % ('arm', 'changed', 'plan=block', 'diff_kinds'))
    for name, r in out.items():
        print('  %-24s %8d %12d  %s'
              % (name, r['changed'], r['plan_block'], r['diff_kinds'] or ''))
        if r['event_ids']:
            print('      ids %s' % r['event_ids'][:20])
    if errors:
        print()
        print('ENGINE ERRORS %d — 해석 중단' % len(errors))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
