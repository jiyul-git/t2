#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revise_plan current-context 전달의 **paired** 행동 비교.

  python3 tools/replan_context_paired.py
  python3 tools/replan_context_paired.py --seeds 5150,9001 --hands 12

A6 full fixture(810건)를 돌리지 않는다. 짧은 고정 fixture 에서 **같은 입력**을
두 계약으로 재생해 짝지어 본다.

  before  revise_plan 을 7개 생략으로 호출 = 수정 전 semantics
          (스냅샷 opp_est/opp_stack_bb + make_plan 기본값 5개)
  after   update_plan 이 넘긴 현재 맥락 7개를 그대로 전달 = 현재 production

before 를 "부모 커밋을 체크아웃해서" 가 아니라 **생략 경로로** 만든다.
그 경로가 수정 전과 동일함은 tools/verify_replan_context.py 의 계약 C 가
따로 검증한다. 이렇게 하면 두 팔이 같은 프로세스·같은 입력을 쓰므로
live 진행 차이가 섞이지 않는다.

칩 환산은 엔진 식 그대로다 (plan.py:1363):
    amt = min(stack, int(round(pot*size/100))*100)
여기에 숫자를 새로 만들지 않는다.

RNG: "최종 state 가 항상 같아야 한다" 를 요구하지 않는다. 맥락이 제대로
전달돼 행동이 달라진 뒤 스트림이 갈리는 것은 정상이다. 대신 **최초 행동
divergence 이전까지** 호출열·최종 state·출력이 같은지 보고, 그 최초
divergence 가 7필드 중 무엇의 차이로 설명되는지 귀속한다.

읽기 전용. production 무수정.
"""
from __future__ import print_function

import argparse
import copy
import inspect
import json
import os
import random as _real_random
import sys
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import plan as PL
import runner as RU

FIELDS = ('oop_vs_aggr', 'oop_legacy_abs', 'initiative', 'tilt', 'bb_chips',
          'opp_est', 'opp_stack_bb')
SNAPSHOT_FIELDS = ('opp_est', 'opp_stack_bb')


# ------------------------------------------------------------------ rng 계측
class RecRandom(object):
    """포함 래퍼. random.Random 을 상속하지 않는다 — 상속 후 random() 을
    덮으면 CPython 이 _randbelow 를 바꿔 choice() 결과가 달라진다."""

    def __init__(self, seed=None):
        self._r = _real_random.Random(seed)
        self.calls = []

    def random(self):
        self.calls.append('random'); return self._r.random()

    def uniform(self, a, b):
        self.calls.append('uniform'); return self._r.uniform(a, b)

    def choice(self, seq):
        self.calls.append('choice'); return self._r.choice(seq)

    def getstate(self):
        return self._r.getstate()

    def __getattr__(self, name):
        attr = getattr(self._r, name)
        if callable(attr):
            def g(*a, **k):
                self.calls.append(name); return attr(*a, **k)
            return g
        return attr


class RandomShim(object):
    def __init__(self):
        self.made = []

    def Random(self, seed=None):
        r = RecRandom(seed); self.made.append(r); return r

    def __getattr__(self, name):
        return getattr(_real_random, name)


# ------------------------------------------------------------------ capture
def capture(seeds, fmts, hands, entries):
    orig = PL.update_plan
    sig = inspect.signature(orig)
    events, counts = [], Counter()

    def wrapped(*a, **k):
        b = sig.bind_partial(*a, **k); b.apply_defaults()
        counts['update_plan'] += 1
        state = b.arguments.get('state')
        if state is not None and not b.arguments.get('first'):
            counts['revise_path'] += 1
            if RU.board_changed(b.arguments.get('prev_board'),
                                b.arguments.get('board')):
                counts['board_changed'] += 1
                events.append({
                    'args': copy.deepcopy(a), 'kwargs': copy.deepcopy(k),
                    'street': b.arguments.get('street'),
                    'pot': b.arguments.get('pot'),
                    'stack': b.arguments.get('stack'),
                    'given': {f: copy.deepcopy(b.arguments.get(f))
                              for f in FIELDS},
                    'snapshot': {f: copy.deepcopy((state or {}).get(f))
                                 for f in SNAPSHOT_FIELDS},
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


# ------------------------------------------------------------------ 재생
def _arm(strip):
    """strip=True 면 7개를 떼고 부른다 = 수정 전 semantics."""
    real = RU.revise_plan

    def rev(*a, **k):
        if strip:
            k = {x: v for x, v in k.items() if x not in FIELDS}
        return real(*a, **k)
    return rev


def replay(event, strip):
    orig_rev = RU.revise_plan
    orig_rand = PL.random
    shim = RandomShim()
    try:
        RU.revise_plan = _arm(strip)
        PL.random = shim
        st = PL.update_plan(*copy.deepcopy(event['args']),
                            **copy.deepcopy(event['kwargs']))
    finally:
        RU.revise_plan = orig_rev
        PL.random = orig_rand
    it = PL.intent_of(st, event['street']) or {}
    sig = {'plan': st.get('plan'), 'act': it.get('act'),
           'size': round(it.get('size', 0) or 0, 6)}
    return sig, (tuple(tuple(r.calls) for r in shim.made),
                 tuple(r.getstate() for r in shim.made))


def chips(sig, pot, stack):
    """plan.py:1363 과 같은 식."""
    if sig['act'] != 'bet' or not sig['size']:
        return 0
    return min(stack, int(round(pot * sig['size'] / 100)) * 100)


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

    events, counts, errors = capture(seeds, fmts, a.hands, a.entries)

    ctx_mismatch = Counter()
    for ev in events:
        for f in FIELDS:
            oldv = (ev['snapshot'][f] if f in SNAPSHOT_FIELDS
                    else RU._mk_default(f))
            if ev['given'][f] != oldv:
                ctx_mismatch[f] += 1

    n_plan = n_act = n_size = n_chip = n_round_hidden = 0
    first_change = None
    first_rng = None
    rows = []
    for i, ev in enumerate(events):
        sb, rb = replay(ev, strip=True)
        sa, ra = replay(ev, strip=False)
        cb = chips(sb, ev['pot'], ev['stack'])
        ca = chips(sa, ev['pot'], ev['stack'])
        dplan = sb['plan'] != sa['plan']
        dact = sb['act'] != sa['act']
        dsize = sb['size'] != sa['size']
        dchip = cb != ca
        n_plan += dplan; n_act += dact; n_size += dsize; n_chip += dchip
        if dsize and not dchip:
            n_round_hidden += 1
        if (dplan or dact or dsize) and first_change is None:
            diff_fields = [f for f in FIELDS
                           if ev['given'][f] != (ev['snapshot'][f]
                                                 if f in SNAPSHOT_FIELDS
                                                 else RU._mk_default(f))]
            first_change = {
                'event': i, 'street': ev['street'], 'pot': ev['pot'],
                'stack': ev['stack'], 'before': sb, 'after': sa,
                'chips_before': cb, 'chips_after': ca,
                'context_fields_differing': diff_fields,
            }
        if rb != ra and first_rng is None:
            first_rng = i
        if dplan or dact or dsize:
            rows.append((i, ev['street'], sb, sa, cb, ca))

    # RNG: 최초 행동 divergence 이전까지는 호출열·최종 state 까지 동일해야 한다
    pre = first_change['event'] if first_change else len(events)
    rng_clean_before = (first_rng is None or first_rng >= pre)

    payload = {
        'fixture': {'seeds': list(seeds), 'fmts': list(fmts),
                    'hands': a.hands, 'entries': a.entries},
        'counts': dict(counts),
        'replan_events': len(events),
        'context_mismatch': {f: ctx_mismatch[f] for f in FIELDS},
        'plan_changed': n_plan, 'act_changed': n_act,
        'size_changed': n_size, 'chip_changed': n_chip,
        'size_changed_but_same_chips': n_round_hidden,
        'first_change': first_change,
        'first_rng_divergence_event': first_rng,
        'rng_identical_before_first_behavior_change': rng_clean_before,
    }
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if errors else 0

    print('fixture seeds=%s fmts=%s hands=%d entries=%d'
          % (','.join(map(str, seeds)), ','.join(fmts), a.hands, a.entries))
    print('update_plan %d  revise_path %d  board_changed %d  engine_errors %d'
          % (counts['update_plan'], counts['revise_path'],
             counts['board_changed'], counts['engine_errors']))
    print('replan events %d' % len(events))
    print()
    print('context mismatch (현재값이 옛 semantics 값과 다른 건수)')
    for f in FIELDS:
        print('    %-16s %4d / %d' % (f, ctx_mismatch[f], len(events)))
    print()
    print('행동 변화 (같은 입력, before=생략 semantics / after=현재 맥락)')
    print('    plan changed              %4d' % n_plan)
    print('    act changed               %4d' % n_act)
    print('    normalized size changed   %4d' % n_size)
    print('    실제 chip amount changed  %4d' % n_chip)
    print('    size 는 달랐는데 100칩 반올림 후 같음  %4d' % n_round_hidden)
    print()
    if first_change:
        fc = first_change
        print('최초 행동 divergence — event %d (%s)' % (fc['event'], fc['street']))
        print('    before %r  -> %d칩' % (fc['before'], fc['chips_before']))
        print('    after  %r  -> %d칩' % (fc['after'], fc['chips_after']))
        print('    그 event 에서 값이 다른 맥락 필드: %s'
              % fc['context_fields_differing'])
    else:
        print('행동 divergence 없음')
    print()
    print('RNG: 최초 divergence event = %r, 행동 divergence event = %r'
          % (first_rng, pre if first_change else None))
    print('    최초 행동 변화 이전까지 호출열·최종 state 동일: %s'
          % ('예' if rng_clean_before else '아니오 — 설명되지 않는 선행 divergence'))
    print()
    if rows:
        print('변화한 event 전체 (%d건)' % len(rows))
        for i, street, sb, sa, cb, ca in rows[:40]:
            print('    ev%-4d %-6s %-14s->%-14s size %.3f->%.3f  chips %d->%d'
                  % (i, street, sb['plan'], sa['plan'], sb['size'], sa['size'],
                     cb, ca))
    if errors:
        print('ENGINE ERRORS %d — 해석 중단' % len(errors))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
