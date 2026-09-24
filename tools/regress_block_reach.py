#!/usr/bin/env python3
"""regress.py 의 지문 레시피에서 block 경로가 실제로 도달되는가. 읽기 전용.

A5 수정(`plan.py:457` 의 `else:`)은 두 가지를 바꾼다.
  1) block 선택이 머징 체인에 덮어써지지 않는다
  2) block 선택 시 `sk('potcontrol') >= 1` 이면 소비되던 `_pc_p` 굴림이
     이제 소비되지 않는다 → 그 시점부터 RNG 스트림이 밀린다

`regress.py check` 가 전 시드 지문 일치를 냈다. 그 이유가
"레시피에서 block 이 한 번도 선택되지 않아서"인지 코드로 확인한다.
통계로 추정하지 않는다 (CLAUDE.md 작업원칙 4, FIX_PLAN 1-C 선례).

레시피는 regress.fingerprint() 와 **동일**하다:
  entries=100, start_stack=30000, hero_seat=7, hands_per_level=200,
  seeds 3000-3005, 30핸드, 히어로는 계속 fold.
"""
import os
import sys
import collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

BLOCK_MSG = '블락벳으로 가격 통제'
SEEDS = list(range(3000, 3006))
HANDS = 30


def main():
    import tourney as T
    import plan as PL
    import persona as PS
    cnt = collections.Counter()
    _omk = PL.make_plan

    def wrap(hero, board, my_range, opp_range, profile, pot, stack, street,
             **kw):
        st = _omk(hero, board, my_range, opp_range, profile, pot, stack,
                  street, **kw)
        cnt['make_plan'] += 1
        w = ' | '.join(st.get('why') or [])
        if '중간강도' in w:
            cnt['mid_branch'] += 1
        if BLOCK_MSG in w:
            cnt['block_selected'] += 1
            # 옛 코드에서 추가로 소비되던 굴림: block 선택 + potcontrol 게이트
            if PS.sk(profile, 'potcontrol') / 3.33 >= 1:
                cnt['extra_roll_would_have_fired'] += 1
        if st.get('plan') == 'block':
            cnt['plan_block'] += 1
        return st

    PL.make_plan = wrap
    try:
        for sd in SEEDS:
            t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                             seed=sd, hands_per_level=200)
            for _ in range(HANDS):
                if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                    break
                st = t.next_hand()
                guard = 0
                while st and not st.get('done') and guard < 200:
                    st = t.submit('fold')
                    guard += 1
                t.finish_hand()
            print('  seed %d 누적: make_plan %d  중간강도 %d  block선택 %d'
                  % (sd, cnt['make_plan'], cnt['mid_branch'],
                     cnt['block_selected']), flush=True)
    finally:
        PL.make_plan = _omk

    print('\n## regress 레시피에서의 block 도달')
    for k in ('make_plan', 'mid_branch', 'block_selected', 'plan_block',
              'extra_roll_would_have_fired'):
        print('  %-30s %d' % (k, cnt[k]))
    print()
    if cnt['block_selected'] == 0:
        print('  block 선택 0건 → A5 의 `else:` 는 이 레시피에서 **한 번도**')
        print('  평가되지 않는다. 덮어쓰기도, 굴림 소비 차이도 발생할 수 없다.')
        print('  => 전 시드 지문 일치는 "행동이 안 바뀌었다"가 아니라')
        print('     **"이 레시피가 바뀐 분기를 건드리지 않는다"** 는 뜻이다.')
    else:
        print('  block 선택 %d건 (그중 옛 코드가 굴림을 더 쓰던 것 %d건).'
              % (cnt['block_selected'], cnt['extra_roll_would_have_fired']))
        print('  경로가 열려 있는데 지문이 같다면 별도 설명이 필요하다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
