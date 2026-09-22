#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blockbet 제어흐름 수정의 targeted deterministic selftest.

  python3 tools/selftest_blockbet.py
  python3 tools/selftest_blockbet.py --before-rev 3cc75a9 --n 400

무엇을 보는가
-------------
`plan.py` 의 `eq >= pcz` 분기에서 `plan = 'block'` 직후의 if/elif/else 가
plan 을 무조건 덮어썼다. A5 계측이 gate_true 8 / roll 통과 1 / taken 0 을
냈다 — 굴림을 통과해도 밖으로 나가지 못했다.

수정은 **덮어쓰기만** 막는다. 분기를 else 로 옮기지 않는다. 옮기면
potcontrol 굴림이 소비되지 않아 rng 스트림이 통째로 밀린다.

그래서 이 selftest 는 세 경우를 나눠 **수정 전/후의 rng 소비를 직접
대조**한다.

  A  게이트 거짓            → plan·why·rng 전부 동일해야 한다
  B  게이트 참 + 굴림 실패   → plan·why·rng 전부 동일해야 한다
  C  게이트 참 + 굴림 통과   → plan 만 'block' 으로 바뀌고
                              **rng 소비 순서·최종 state 는 동일**해야 한다
                              나머지 state 키도 전부 동일해야 한다

rng 계측은 상속이 아니라 포함(containment)이다. `random.Random` 을 상속해
`random()` 을 덮으면 CPython 이 `_randbelow` 구현을 바꿔서 `choice()` 결과가
달라진다 — 없는 divergence 를 만들어낸다. 여기서는 진짜 Random 인스턴스를
안에 두고 호출만 기록·전달한다.

fixture 는 tools/axis_freq.py 의 `post_sit`/`build` 를 그대로 쓴다.
새 상황 생성기를 만들지 않는다.
"""
from __future__ import print_function

import argparse
import importlib.util
import os
import random as _real_random
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import persona as PS
import archetypes as A
import axis_freq as AF

MID_MSG = '중간강도'
BLOCK_MSG = '블락벳으로 가격 통제'
MARK = '_block_taken'

# 고정 fixture. 바꾸면 아래 분류 건수가 달라진다.
FIXTURE = {
    'seed': 20260922,
    'n': 400,
    'street': 'flop',
    'n_opp': 1,
    'est_kind': 'mixed',
    'base_seed': 20260915,          # axis_freq 기본 base 와 같은 값
    'profile': "build(base, 'blockbet', 9, {'aggression': 9, 'bluff': 1})",
    'force': 'oop=True, initiative=False',   # axis_freq --force oop_noninitiative
}


# ---------------------------------------------------------------- rng 계측
class RecRandom(object):
    """포함 래퍼. random.Random 을 상속하지 않는다."""

    def __init__(self, seed=None):
        self._r = _real_random.Random(seed)
        self.calls = []

    def random(self):
        self.calls.append('random')
        return self._r.random()

    def uniform(self, a, b):
        self.calls.append('uniform')
        return self._r.uniform(a, b)

    def choice(self, seq):
        self.calls.append('choice')
        return self._r.choice(seq)

    def getstate(self):
        return self._r.getstate()

    def __getattr__(self, name):
        # 계측하지 않은 메서드가 쓰이면 조용히 통과시키지 말고 기록한다.
        attr = getattr(self._r, name)
        if callable(attr):
            def g(*a, **k):
                self.calls.append(name)
                return attr(*a, **k)
            return g
        return attr


class RandomShim(object):
    def __init__(self):
        self.made = []

    def Random(self, seed=None):
        r = RecRandom(seed)
        self.made.append(r)
        return r

    def __getattr__(self, name):
        return getattr(_real_random, name)


# ---------------------------------------------------------------- 모듈 적재
def load_plan(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def extract_before(rev):
    src = subprocess.check_output(['git', '-C', ROOT, 'show', '%s:plan.py' % rev])
    fd, p = tempfile.mkstemp(suffix='_plan_before.py')
    with os.fdopen(fd, 'wb') as fp:
        fp.write(src)
    return p


# ---------------------------------------------------------------- 분류
def block_p_of(profile, dang):
    """plan.py:450-454 와 같은 식. 값을 다시 읽을 뿐 엔진을 바꾸지 않는다."""
    p = 0.12 + 0.05*profile['aggr'] - 0.03*profile.get('bluff', 5)
    p *= (1 + 0.4*dang)
    if A.ARCHETYPES.get(profile.get('type'), (0,)*6 + ('reg', ''))[6] == 'fish':
        p *= 0.25
    return max(0.0, min(0.42, p))


def classify(st, profile, oop_a, ini):
    why = ' | '.join(st.get('why') or [])
    rel = st.get('rel')
    entered = MID_MSG in why
    gate = (entered and oop_a and not ini and rel is not None
            and 0.25 <= rel <= 0.80
            and block_p_of(profile, st.get('danger') or 0.0) > 0
            and PS.sk(profile, 'blockbet')/3.33 >= 1)
    rolled = BLOCK_MSG in why
    if not gate:
        return 'A'
    return 'C' if rolled else 'B'


def run_one(mod, sit, profile):
    shim = RandomShim()
    old = mod.random
    mod.random = shim
    try:
        st = mod.make_plan(sit['hero'], sit['board'], sit['my_range'],
                           sit['opp_range'], profile, sit['pot'], sit['stack'],
                           sit['street'], seed=sit['seed'], n_opp=sit['n_opp'],
                           to_act_behind=sit['to_act_behind'],
                           oop_vs_aggr=True, initiative=False,
                           opp_est=sit['est'])
    finally:
        mod.random = old
    # make_plan 은 자기 rng 하나만 만드는 것이 아니다 — 에퀴티 시뮬레이터가
    # 내용에서 유도한 seed 로 Random 을 또 만든다. 그래서 **생성된 전부**를
    # 생성 순서대로 비교한다. made[-1] 을 보면 make_plan 의 rng 가 아니라
    # 에퀴티 쪽 rng 를 보게 되고, 정작 재려던 굴림이 시야에서 빠진다.
    trace = tuple((tuple(r.calls), r.getstate()) for r in shim.made)
    calls = tuple(tuple(r.calls) for r in shim.made)
    states = tuple(r.getstate() for r in shim.made)
    return st, calls, states


IGNORE = ('plan', 'why', 'plan_goal')


def main():
    ap = argparse.ArgumentParser(description='blockbet 제어흐름 수정 selftest')
    ap.add_argument('--before-rev', default='3cc75a9',
                    help='수정 전 plan.py 를 꺼낼 git rev')
    ap.add_argument('--n', type=int, default=FIXTURE['n'])
    ap.add_argument('--per-class', type=int, default=8)
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()

    before_path = extract_before(a.before_rev)
    after_path = os.path.join(ROOT, 'plan.py')
    bsrc = open(before_path, encoding='utf-8').read()
    asrc = open(after_path, encoding='utf-8').read()
    if MARK in bsrc:
        print('FAIL: --before-rev %s 의 plan.py 에 이미 수정이 들어 있다' % a.before_rev)
        return 2
    if MARK not in asrc:
        print('FAIL: 작업 트리 plan.py 에 수정이 없다')
        return 2

    before = load_plan(before_path, '_plan_before')
    after = load_plan(after_path, '_plan_after')

    print('fixture %s' % FIXTURE)
    print('before  %s:plan.py' % a.before_rev)
    print('after   %s' % after_path)
    print()

    base = PS.make_player(_real_random.Random(FIXTURE['base_seed']), 0.78, 0)
    profile = AF.build(base, 'blockbet', 9, {'aggression': 9, 'bluff': 1})
    print('profile: aggr %.2f  bluff %.2f  sk(blockbet) %.2f (make_plan 스케일 %.2f)'
          % (profile['aggr'], profile.get('bluff', 5),
             PS.sk(profile, 'blockbet'), PS.sk(profile, 'blockbet')/3.33))
    print('block_p(dang=0) = %.3f   clamp 상한 0.42' % block_p_of(profile, 0.0))
    print()

    rng = _real_random.Random(FIXTURE['seed'])
    sits = [AF.post_sit(rng, FIXTURE['street'], n_opp=FIXTURE['n_opp'],
                        est_kind=FIXTURE['est_kind']) for _ in range(a.n)]

    buckets = {'A': [], 'B': [], 'C': []}
    for i, s in enumerate(sits):
        try:
            st, calls, state = run_one(before, s, profile)
        except Exception as e:
            print('  situation %d 예외: %s' % (i, e))
            continue
        cls = classify(st, profile, True, False)
        buckets[cls].append((i, s, st, calls, state))

    print('분류: A(게이트 거짓) %d   B(게이트 참·굴림 실패) %d   C(게이트 참·굴림 통과) %d'
          % (len(buckets['A']), len(buckets['B']), len(buckets['C'])))
    print()

    fails = []
    # 이 selftest 가 공허하지 않은지 먼저 확인한다 — C 분류에서 blockbet 굴림
    # 뒤에 potcontrol 굴림이 실제로 소비되는 사례가 있어야 "덮어쓰기만 막고
    # 굴림은 그대로" 를 시험한 것이 된다.
    _c_draws = [sum(len(c) for c in calls[:1]) for _, _, _, calls, _ in buckets['C']]
    print('C 분류의 make_plan rng draw 수 분포: %s'
          % dict((d, _c_draws.count(d)) for d in sorted(set(_c_draws))))
    for cls in ('A', 'B', 'C'):
        rows = buckets[cls][:a.per_class]
        if not rows:
            fails.append('%s 분류 표본 0 — 이 경우를 시험하지 못했다' % cls)
            continue
        print('## %s (%d건 검사)' % (cls, len(rows)))
        for i, s, st_b, calls_b, state_b in rows:
            st_a, calls_a, state_a = run_one(after, s, profile)

            same_calls = (calls_b == calls_a)
            same_state = (state_b == state_a)
            rest_b = {k: v for k, v in st_b.items() if k not in IGNORE}
            rest_a = {k: v for k, v in st_a.items() if k not in IGNORE}
            same_rest = (rest_b == rest_a)

            if cls in ('A', 'B'):
                ok_plan = (st_b.get('plan') == st_a.get('plan')
                           and st_b.get('why') == st_a.get('why'))
                want = '동일'
            else:
                ok_plan = (st_a.get('plan') == 'block'
                           and st_b.get('plan') != 'block'
                           and BLOCK_MSG in ' | '.join(st_a.get('why') or [])
                           and not any(m in ' | '.join(st_a.get('why') or [])
                                       for m in ('팟 컨트롤', '얇은 밸류',
                                                 '상대레인지 열세')))
                want = "%s -> block" % st_b.get('plan')

            ok = ok_plan and same_calls and same_state and same_rest
            if not ok:
                fails.append('%s sit%d: plan %s calls %s state %s rest %s'
                             % (cls, i, ok_plan, same_calls, same_state, same_rest))
            if a.verbose or not ok:
                print('  sit%-4d %-22s rng 인스턴스 %d, 총 draw %d  calls= %s '
                      'state= %s rest= %s'
                      % (i, want, len(calls_a), sum(len(c) for c in calls_a),
                         'same' if same_calls else 'DIFF',
                         'same' if same_state else 'DIFF',
                         'same' if same_rest else 'DIFF'))
        if not a.verbose:
            print('  plan/why 기대대로, rng 호출열·최종 state·나머지 state 키 전부 동일'
                  if not [f for f in fails if f.startswith(cls)] else '  위 실패 참조')
        print()

    os.unlink(before_path)
    if fails:
        print('FAIL %d건' % len(fails))
        for f in fails:
            print('  ' + f)
        return 1
    print('PASS — 의도된 plan 차이 외 rng consumption 차이 0')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
