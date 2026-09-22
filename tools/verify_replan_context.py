#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revise_plan current-context 전달 계약의 **동적** 검증.

  python3 tools/verify_replan_context.py
  python3 tools/verify_replan_context.py --seeds 5150 --hands 8

tools/verify_replan_contract.py 는 AST 로 "호출부에 키워드가 적혀 있는가"
만 본다. 여기서는 실제로 엔진을 돌려 **값이 그대로 도착하는가** 를 본다.

계약
----
A  전달        board_changed event 마다 update_plan 입력 7개 ==
               make_plan 이 받은 7개
B  명시 None   state 스냅샷에 값이 있어도, 현재값으로 None 을 명시하면
               make_plan 에는 None 이 가야 한다. 스냅샷으로 되돌아가면 FAIL
C  생략 호환   revise_plan 을 직접 부르며 7개를 생략하면 옛 semantics
               (opp_est/opp_stack_bb = state 스냅샷, 나머지 = make_plan 기본값)
D  음성 대조   필드마다 누락·기본값 치환·스냅샷 치환을 일부러 주입하면
               A 검사가 반드시 FAIL 해야 한다
E  blockbet 짝 oop_vs_aggr+initiative, oop_legacy_abs+initiative 가 함께
               현재값으로 전달되는가
F  core3       bb_chips, opp_est, opp_stack_bb 가 현재값으로 전달되는가
G  tilt        fixture 가 tilt=0 만 내더라도 0 이 아닌 값을 합성 주입해
               전달 자체를 확인한다

읽기 전용이다. production 을 수정하지 않는다.
"""
from __future__ import print_function

import argparse
import inspect
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import persona as PS
import plan as PL
import ranges as R
import runner as RU

FIELDS = ('oop_vs_aggr', 'oop_legacy_abs', 'initiative', 'tilt', 'bb_chips',
          'opp_est', 'opp_stack_bb')
SNAPSHOT_FIELDS = ('opp_est', 'opp_stack_bb')

RESULTS = []

# 합성 직접 호출용 고정 입력. prev -> board 가 board_changed 를 만족해야
# revise_plan 이 make_plan 까지 간다 (클럽 3장이 리버에 완성된다).
SYN_PREV = ['2c', '7c', '9s']
SYN_BOARD = ['2c', '7c', '9s', 'Qc']
SYN_STATE = {'opp_est': {'type': 'reg', 'n': 42, 'confidence': 0.5},
             'opp_stack_bb': 77.0, 'plan': 'showdown'}


def _syn_args():
    import random
    prof = PS.make_player(random.Random(20260915), 0.78, 0)
    rng_range = [tuple(c) for c in R._SORTED[:60]]
    return (dict(SYN_STATE), ['As', 'Kd'], list(SYN_BOARD), rng_range,
            rng_range, prof, 1000, 5000, 'turn', 7, 1, 0, list(SYN_PREV))


def _call_revise(**kw):
    """합성 revise_plan 호출. make_plan 이 받은 7필드를 돌려준다."""
    seen = {}
    real = PL.make_plan
    sig = inspect.signature(real)

    def spy(*x, **k):
        b = sig.bind_partial(*x, **k)
        b.apply_defaults()
        seen.update({f: b.arguments.get(f) for f in FIELDS})
        seen['_hit'] = True
        return real(*x, **k)
    PL.make_plan = spy
    try:
        RU.revise_plan(*_syn_args(), **kw)
    finally:
        PL.make_plan = real
    return seen


def ok(tag, cond, msg):
    RESULTS.append((tag, bool(cond), msg))
    print('  %-6s %s %s' % (tag, 'PASS' if cond else 'FAIL', msg))
    return cond


# ------------------------------------------------------------------ 계측
class Recorder(object):
    """update_plan 입력과 make_plan 수신값을 event 단위로 짝지어 기록한다."""

    def __init__(self, mutate=None):
        self.events = []
        self.counts = Counter()
        self._pending = None
        self.mutate = mutate          # 음성 대조용 주입기
        self._up = PL.update_plan
        self._rv = RU.revise_plan
        self._mk = PL.make_plan
        self._up_sig = inspect.signature(self._up)
        self._mk_sig = inspect.signature(self._mk)

    def __enter__(self):
        rec = self

        def update_plan(*a, **k):
            b = rec._up_sig.bind_partial(*a, **k)
            b.apply_defaults()
            rec.counts['update_plan'] += 1
            state = b.arguments.get('state')
            first = bool(b.arguments.get('first'))
            replan = (state is not None and not first
                      and RU.board_changed(b.arguments.get('prev_board'),
                                           b.arguments.get('board')))
            if replan:
                rec.counts['board_changed'] += 1
                rec._pending = {
                    'street': b.arguments.get('street'),
                    'given': {f: b.arguments.get(f) for f in FIELDS},
                    'snapshot': {f: (state or {}).get(f) for f in SNAPSHOT_FIELDS},
                    'seen': None,
                }
            else:
                rec._pending = None
            try:
                return rec._up(*a, **k)
            finally:
                if rec._pending is not None:
                    rec.events.append(rec._pending)
                    rec._pending = None

        def revise_plan(*a, **k):
            if rec.mutate is not None:
                a, k = rec.mutate(a, k, rec._pending)
            return rec._rv(*a, **k)

        def make_plan(*a, **k):
            if rec._pending is not None and rec._pending['seen'] is None:
                b = rec._mk_sig.bind_partial(*a, **k)
                b.apply_defaults()
                rec._pending['seen'] = {f: b.arguments.get(f) for f in FIELDS}
                rec.counts['make_plan_in_replan'] += 1
            return rec._mk(*a, **k)

        PL.update_plan = update_plan
        RU.revise_plan = revise_plan
        PL.make_plan = make_plan
        return self

    def __exit__(self, *e):
        PL.update_plan = self._up
        RU.revise_plan = self._rv
        PL.make_plan = self._mk
        return False


def run_field(seeds, fmts, hands, entries, mutate=None):
    old = getattr(FS.Field, 'BOT_LOG', None)
    errors = []
    with Recorder(mutate=mutate) as rec:
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
            if old is not None:
                FS.Field.BOT_LOG = old
    return rec.events, rec.counts, errors


def mismatches(events, fields=FIELDS):
    bad = Counter()
    first = None
    for i, ev in enumerate(events):
        if ev['seen'] is None:
            continue
        for f in fields:
            if ev['given'][f] != ev['seen'][f]:
                bad[f] += 1
                if first is None:
                    first = (i, f, ev['given'][f], ev['seen'][f])
    return bad, first


# ------------------------------------------------------------------ 음성 대조
# 훼손 주입에 쓰는 '확실히 다른 값'. 계약 검사용 표지일 뿐
# 임계값이 아니다 — 전달 여부만 본다.
WRONG = {'oop_vs_aggr': 'XX', 'oop_legacy_abs': 'XX', 'initiative': 'XX',
         'tilt': 'XX', 'bb_chips': 'XX', 'opp_est': 'XX', 'opp_stack_bb': 'XX'}


def _old_semantics(field, pending):
    """수정 전 revise_plan 이 그 필드에 쓰던 값."""
    if field in SNAPSHOT_FIELDS:
        return pending['snapshot'].get(field)
    return RU._mk_default(field)


def _mutator(field, mode):
    """revise_plan 에 도달하기 직전에 한 필드를 훼손한다.

    omit      인자를 빼서 옛 semantics 로 떨어뜨린다
    snapshot  옛 semantics 값으로 덮어쓴다
    wrong     현재값과 반드시 다른 표지값으로 덮어쓴다
    """
    def mut(a, k, pending):
        if pending is None:
            return a, k
        k = dict(k)
        if mode == 'omit':
            k.pop(field, None)
        elif mode == 'snapshot':
            k[field] = _old_semantics(field, pending)
        elif mode == 'wrong':
            k[field] = WRONG[field]
        return a, k
    return mut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='5150')
    ap.add_argument('--fmts', default='standard')
    ap.add_argument('--hands', type=int, default=10)
    ap.add_argument('--entries', type=int, default=100)
    a = ap.parse_args()
    seeds = tuple(int(x) for x in a.seeds.split(','))
    fmts = tuple(a.fmts.split(','))

    print('fixture seeds=%s fmts=%s hands=%d entries=%d'
          % (','.join(map(str, seeds)), ','.join(fmts), a.hands, a.entries))
    print()

    # ---------- A ----------
    print('A. current forwarding')
    events, counts, errors = run_field(seeds, fmts, a.hands, a.entries)
    replans = [e for e in events if e['seen'] is not None]
    ok('A0', not errors, 'engine_errors %d' % len(errors))
    ok('A1', len(replans) > 0,
       'board_changed replan %d건 (update_plan %d)'
       % (len(replans), counts['update_plan']))
    bad, first = mismatches(replans)
    ok('A2', not bad, '7필드 전달 불일치 %s%s'
       % (dict(bad) or 0, '' if first is None else '  최초 %r' % (first,)))
    print()

    # ---------- E / F / G 의 전제: 값이 기본값과 실제로 다른 건수 ----------
    print('E/F. 필드별로 make_plan 이 받은 값이 옛 기본/스냅샷과 다른 건수')
    diff = Counter()
    for ev in replans:
        for f in FIELDS:
            oldv = (ev['snapshot'][f] if f in SNAPSHOT_FIELDS
                    else RU._mk_default(f))
            if ev['seen'][f] != oldv:
                diff[f] += 1
    for f in FIELDS:
        print('    %-16s %4d / %d' % (f, diff[f], len(replans)))
    ok('E1', diff['oop_vs_aggr'] > 0 and diff['initiative'] > 0,
       'blockbet 짝 (oop_vs_aggr, initiative) 둘 다 현재값으로 도착')
    ok('E2', diff['oop_legacy_abs'] > 0,
       'oop_legacy_abs 현재값으로 도착')
    ok('F1', diff['bb_chips'] > 0 and diff['opp_est'] > 0
       and diff['opp_stack_bb'] > 0,
       'core3 (bb_chips, opp_est, opp_stack_bb) 전부 현재값으로 도착')
    print()

    # ---------- B ----------
    print('B. 명시 None 보존 (스냅샷 fallback 금지)')
    seen = _call_revise(oop_vs_aggr=None, oop_legacy_abs=None, initiative=False,
                        tilt=0.0, bb_chips=None, opp_est=None, opp_stack_bb=None)
    ok('B0', seen.get('_hit'), 'make_plan 까지 도달 (board_changed 성립)')
    ok('B1', seen.get('opp_est') is None,
       'opp_est: 스냅샷 %r 있어도 명시 None 이 전달 (받은 값 %r)'
       % (SYN_STATE['opp_est'], seen.get('opp_est')))
    ok('B2', seen.get('opp_stack_bb') is None,
       'opp_stack_bb: 스냅샷 %r 있어도 명시 None (받은 값 %r)'
       % (SYN_STATE['opp_stack_bb'], seen.get('opp_stack_bb')))
    ok('B3', seen.get('oop_vs_aggr') is None,
       'oop_vs_aggr 명시 None 이 그대로 (받은 값 %r)' % seen.get('oop_vs_aggr'))
    ok('B4', seen.get('initiative') is False,
       'initiative 명시 False 가 기본값 True 로 되돌아가지 않음 (받은 값 %r)'
       % seen.get('initiative'))
    print()

    # ---------- G ----------
    print('G. tilt 전달 (fixture 가 0 만 내도 합성값으로 확인)')
    seen2 = _call_revise(oop_vs_aggr=True, oop_legacy_abs=True, initiative=False,
                         tilt=0.37, bb_chips=200, opp_est=None,
                         opp_stack_bb=12.5)
    ok('G1', seen2.get('tilt') == 0.37,
       'tilt 0.37 이 그대로 전달 (받은 값 %r)' % seen2.get('tilt'))
    ok('G2', seen2.get('bb_chips') == 200 and seen2.get('opp_stack_bb') == 12.5,
       'bb_chips/opp_stack_bb 합성값 전달 (%r, %r)'
       % (seen2.get('bb_chips'), seen2.get('opp_stack_bb')))
    print()

    # ---------- C ----------
    print('C. 생략 호환 (옛 직접 호출자)')
    seen3 = _call_revise()
    ok('C1', seen3.get('opp_est') == SYN_STATE['opp_est'],
       '생략 시 opp_est = state 스냅샷 (%r)' % (seen3.get('opp_est'),))
    ok('C2', seen3.get('opp_stack_bb') == SYN_STATE['opp_stack_bb'],
       '생략 시 opp_stack_bb = state 스냅샷 (%r)' % seen3.get('opp_stack_bb'))
    ok('C3', all(seen3.get(f) == RU._mk_default(f)
                 for f in ('oop_vs_aggr', 'oop_legacy_abs', 'initiative',
                           'tilt', 'bb_chips')),
       '생략 시 나머지 5개 = make_plan 기본값 (%s)'
       % {f: seen3.get(f) for f in ('oop_vs_aggr', 'oop_legacy_abs',
                                    'initiative', 'tilt', 'bb_chips')})
    print()

    # ---------- D ----------
    print('D. 음성 대조 — 필드마다 훼손을 주입하면 A 가 FAIL 해야 한다')
    # 현재값이 이미 옛 semantics 값과 같은 필드는 omit/snapshot 으로
    # 구분할 수 없다. 그건 verifier 의 결함이 아니라 이 fixture 의 사실이다
    # (예: tilt 가 전 event 에서 0.0). 그래서 wrong 모드를 따로 둔다 —
    # 그건 모든 필드에서 반드시 검출돼야 한다.
    caught = miss = na = 0
    required = 0
    for f in FIELDS:
        distinguishable = diff[f] > 0
        for mode in ('omit', 'snapshot', 'wrong'):
            ev2, _c2, _e2 = run_field(seeds, fmts, min(a.hands, 6), a.entries,
                                      mutate=_mutator(f, mode))
            r2 = [e for e in ev2 if e['seen'] is not None]
            bad2, _first2 = mismatches(r2, (f,))
            hit = bool(bad2)
            must = (mode == 'wrong') or distinguishable
            if must:
                required += 1
                caught += hit
                miss += (not hit)
                tag = 'OK' if hit else 'MISS'
            else:
                na += 1
                tag = 'N/A (현재값 == 옛 semantics 값이라 구분 불가)'
            print('    %-16s %-9s 훼손 검출 %s (%d건)'
                  % (f, mode, tag, bad2.get(f, 0)))
    ok('D1', miss == 0,
       '검출 필수 %d개 중 %d개 검출, 놓침 %d, 구분 불가 %d'
       % (required, caught, miss, na))
    print()

    bad_tags = [t for t, good, _ in RESULTS if not good]
    if bad_tags:
        print('FAIL %d : %s' % (len(bad_tags), ', '.join(bad_tags)))
        return 1
    print('PASS replan current-context 전달 계약')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
