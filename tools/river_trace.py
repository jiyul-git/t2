#!/usr/bin/env python3
"""리버에서 `semibluff` 를 죽이는 **호출 지점**을 특정한다. 읽기 전용이다.

  python3 tools/river_trace.py 200          # 200핸드
  python3 tools/river_trace.py 200 --seed 7

아카이브에는 중간 상태가 없다. 그래서 파이프라인 함수들을 **메모리에서
감싸고**(plan.py 는 건드리지 않는다) 봇 대전을 돌리며, 리버 단계에서
`plan` 이 들어갈 때와 나올 때를 함수별로 기록한다.

가르려는 것은 둘이다.

  A  river_fix 까지 semibluff 가 살아서 못 들어간다   → 앞단이 원인
  B  semibluff 로 들어가는데 river_bluff 가 안 나온다 → river_fix 내부가 원인

**why 로 판정하지 않는다.** 앞선 조사에서 why 가 비어 있다는 이유로
"그 함수가 안 바꿨다"고 단정했다가 틀렸다. 여기서는 반환된 state 의
plan 값 자체를 본다.
"""
import argparse, os, sys
from collections import Counter

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import plan as PL

LOG = Counter()          # (함수, 스트리트, plan_in, plan_out) -> n
SANITY = Counter()       # harness 가 실제로 돌았는지 확인하는 카운터
RF = Counter()           # river_fix 전용: plan_in == semibluff 일 때의 결과
WRAPPED = ('revise_plan', 'update_plan', 'refresh', 'river_fix', '_allowed',
           'attach_intent', 'make_plan')


def _plan_of(x):
    if isinstance(x, dict):
        return x.get('plan')
    return x if isinstance(x, str) else None


def wrap(name):
    orig = getattr(PL, name)

    def w(*a, **kw):
        # state 는 첫 인자, street 는 위치가 함수마다 달라 kw/위치를 같이 본다.
        st_in = a[0] if a else None
        p_in = _plan_of(st_in)
        street = kw.get('street')
        if street is None:
            for x in a:
                if x in ('flop', 'turn', 'river'):
                    street = x
                    break
        out = orig(*a, **kw)
        p_out = _plan_of(out if not isinstance(out, tuple) else out[0])
        if name == '_allowed':
            # _allowed(profile, plan, rng) — plan 이 두 번째 인자다
            p_in = a[1] if len(a) > 1 else None
            p_out = out
        if street == 'river' and p_in != p_out:
            LOG[(name, p_in, p_out)] += 1
        if name == 'river_fix' and p_in == 'semibluff':
            # **보드 길이로 가른다.** river_fix 는 street 를 인자로 받지 않고
            # `if len(board) < 5: return state` 로 스스로 막는다(plan.py:1529).
            # 그래서 플랍·턴에서도 호출되지만 즉시 반환한다 — 그 no-op 호출을
            # 같이 세면 '리버에서 5회 받았다'는 틀린 숫자가 나온다.
            _bd = a[2] if len(a) > 2 else kw.get('board') or []
            RF[('리버' if len(_bd) >= 5 else '리버아님(no-op)', p_out)] += 1
        if name == 'river_fix':
            _bd2 = a[2] if len(a) > 2 else kw.get('board') or []
            SANITY['river_fix 호출(보드5장)' if len(_bd2) >= 5
                   else 'river_fix 호출(보드<5장)'] += 1
        if name == 'make_plan':
            SANITY['make_plan 호출'] += 1
        if street == 'river' and p_in == 'semibluff':
            LOG[('__진입__' + name, 'semibluff', p_out)] += 1
        return out
    w.__name__ = name
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hands', type=int, nargs='?', default=200)
    ap.add_argument('--seed', type=int, default=20260915)
    a = ap.parse_args()

    missing = [n for n in WRAPPED if not hasattr(PL, n)]
    for n in WRAPPED:
        if hasattr(PL, n):
            setattr(PL, n, wrap(n))
    if missing:
        print('# 감싸지 못한 함수(plan.py 에 없음): %s' % ', '.join(missing))
    # tourney 는 plan 을 모듈 속성으로 부르므로 감싼 것이 그대로 쓰인다.
    import tourney as T

    done = 0
    seed = a.seed
    while done < a.hands:
        t = T.Tournament(entries=40, start_stack=30000, hero_seat=7,
                         seed=seed, hands_per_level=12)
        seed += 1
        while done < a.hands:
            try:
                st = t.next_hand()
            except Exception:
                break
            guard = 0
            while isinstance(st, dict) and not st.get('done'):
                guard += 1
                if guard > 400:
                    break
                try:
                    st = t.submit('fold', 0)
                except Exception:
                    break
            done += 1
            SANITY['핸드'] += 1
            if not isinstance(st, dict):
                SANITY['핸드 비정상 종료'] += 1
                break

    print('## harness 건전성 — 실제로 돌았는지부터 본다')
    for k, v in sorted(SANITY.items()):
        print('   %-26s %6d' % (k, v))
    print()
    print('# 리버 파이프라인 추적 — %d핸드' % done)
    print('# plan.py 는 수정하지 않았다. 함수를 메모리에서 감쌌을 뿐이다.\n')

    print('## river_fix 가 `semibluff` 를 받은 횟수와 결과')
    riv = {k: v for k, v in RF.items() if k[0] == '리버'}
    noop = sum(v for k, v in RF.items() if k[0] != '리버')
    tot = sum(riv.values())
    print('   보드 5장(실제 진입)  %d회' % tot)
    for k, v in sorted(riv.items(), key=lambda x: -x[1]):
        print('     → %-16s %4d' % (k[1], v))
    print('   보드 <5장(즉시 반환) %d회  ← 세면 안 되는 no-op' % noop)
    print()

    print('## 리버 단계에서 `semibluff` 를 받은 함수 (진입 여부)')
    ent = {k: v for k, v in LOG.items() if k[0].startswith('__진입__')}
    if not ent:
        print('   리버 단계에서 semibluff 를 받은 함수가 하나도 없다')
    for k, v in sorted(ent.items(), key=lambda x: -x[1]):
        print('   %-26s semibluff → %-16s %4d'
              % (k[0].replace('__진입__', ''), k[2], v))
    print()

    print('## 리버 단계의 모든 plan 변경 (함수별)')
    for k, v in sorted(((k, v) for k, v in LOG.items()
                        if not k[0].startswith('__진입__')),
                       key=lambda x: -x[1])[:25]:
        print('   %-16s %-16s → %-16s %4d' % (k[0], k[1], k[2], v))


if __name__ == '__main__':
    main()
