"""계산 호출의 **원인**을 태깅한다. STEP 7 확정용.

    python3 tools/calc_origin.py

47건이 refresh 낭비인지 make_plan 재생성인지 확정한다.
nut_advantage / range_advantage 호출을 스택 프레임으로 구분해 원인을 붙인다.

  new_street        새 스트리트 첫 계획
  opp_range_changed 같은 스트리트인데 상대 레인지가 좁혀짐
  make_plan(revise) board_changed 로 계획 재생성
  first_plan        그 스트리트에서 계획이 처음 만들어짐(street_made)
  unknown           위 어디에도 안 맞음 → 진짜 낭비 후보
"""
import sys, os, inspect, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import plan as PL     # noqa: E402
import ranges as R    # noqa: E402
import tourney as T   # noqa: E402

SEEDS = tuple(range(31001, 31005))
HANDS = 45
TAG = collections.Counter()
CTX = {'first': None, 'moved': None, 'street': None, 'made': None}


def caller_chain(depth=8):
    out = []
    f = inspect.currentframe().f_back
    for _ in range(depth):
        if f is None:
            break
        out.append(f.f_code.co_name)
        f = f.f_back
    return out


def install():
    _n, _a, _up = R.nut_advantage, R.range_advantage, PL.update_plan

    def tag_of():
        ch = caller_chain()
        via = 'refresh' if 'refresh' in ch else (
            'make_plan' if 'make_plan' in ch else 'other')
        if via == 'make_plan':
            if 'revise_plan' in ch:
                return 'make_plan(revise)'
            return 'first_plan' if CTX['street'] == CTX['made'] else 'new_street'
        if via == 'refresh':
            if CTX['first']:
                return 'new_street'
            if CTX['moved']:
                return 'opp_range_changed'
            return 'unknown(refresh)'
        return 'other(%s)' % (ch[1] if len(ch) > 1 else '?')

    def n2(*x, **k):
        TAG['nut|' + tag_of()] += 1
        return _n(*x, **k)

    def a2(*x, **k):
        TAG['adv|' + tag_of()] += 1
        return _a(*x, **k)

    def up(state, hero, board, my_range, opp_range, profile, pot, stack,
           street, *a, **k):
        prev = (state or {}).get('_rsig')
        rs = 0 if not opp_range else hash(frozenset(map(str, opp_range)))
        CTX['first'] = (street != (state or {}).get('street_made')
                        and street not in ((state or {}).get('refreshed') or []))
        CTX['moved'] = (prev is not None and prev != rs)
        CTX['street'] = street
        CTX['made'] = (state or {}).get('street_made')
        return _up(state, hero, board, my_range, opp_range, profile, pot,
                   stack, street, *a, **k)
    R.nut_advantage = PL.R.nut_advantage = n2
    R.range_advantage = PL.R.range_advantage = a2
    PL.update_plan = up


def main():
    install()
    for sd in SEEDS:
        t = T.Tournament(entries=40, seed=sd, fmt='standard', hero_seat=7)
        n = 0
        while n < HANDS:
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
            n += 1
    tot = sum(TAG.values())
    print('계산 호출 %d회의 원인' % tot)
    for k, v in TAG.most_common():
        print('  %-28s %5d  %4.1f%%' % (k, v, 100.0 * v / tot))
    bad = sum(v for k, v in TAG.items() if 'unknown' in k)
    print()
    print('  진짜 낭비 후보(unknown) %d회' % bad)


if __name__ == '__main__':
    main()
