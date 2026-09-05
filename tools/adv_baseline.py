"""STEP 1 수정 전/후 비교용 baseline. **production 코드를 수정하지 않는다.**

    python3 tools/adv_baseline.py [출력파일]

update_plan 을 몽키패치로 감싸서, 호출 시점의 실제 입력(board / my_range /
opp_range)과 결과 계획 상태(nut_adv / range_adv / plan / plan_since)를 남긴다.

검증 목적
  수정 전: 플랍에서 계산된 nut_adv/range_adv 가 턴·리버에 그대로 승계된다
  수정 후: 현재 보드 기준으로 재계산된다

값만 비교하면 우연히 같은 경우를 구분할 수 없으므로 **계산 함수 호출 횟수**도
함께 기록한다(R.nut_advantage / R.range_advantage 를 감싼다).

레인지 해시는 정렬 후 정규화해 결정론적으로 만든다.
"""
import sys, os, json, hashlib, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import plan as PL      # noqa: E402
import ranges as R     # noqa: E402
import tourney as T    # noqa: E402

SEED = 26001
HANDS = 30

CALLS = collections.Counter()
ROWS = []


def rhash(rng_list):
    """레인지를 순서 무관하게 정규화해 해시. 같은 레인지면 항상 같은 값."""
    if not rng_list:
        return ('EMPTY', 0)
    norm = sorted(''.join(sorted(c)) if not isinstance(c, str) else c
                  for c in (''.join(x) if isinstance(x, (list, tuple)) else str(x)
                            for x in rng_list))
    h = hashlib.sha1('|'.join(norm).encode()).hexdigest()[:10]
    return (h, len(norm))


def install():
    _nut, _adv, _up = R.nut_advantage, R.range_advantage, PL.update_plan

    def nut(*a, **k):
        CALLS['nut_advantage'] += 1
        return _nut(*a, **k)

    def adv(*a, **k):
        CALLS['range_advantage'] += 1
        return _adv(*a, **k)

    def up(state, hero, board, my_range, opp_range, profile, pot, stack,
           street, *a, **k):
        before = dict(CALLS)
        st = _up(state, hero, board, my_range, opp_range, profile, pot, stack,
                 street, *a, **k)
        if street != 'preflop':
            mh, mn = rhash(my_range)
            oh, on = rhash(opp_range)
            ROWS.append({
                'street': street,
                'board': ''.join(board or []),
                'my_range': mh, 'my_n': mn,
                'opp_range': oh, 'opp_n': on,
                'nut_adv': st.get('nut_adv'),
                'range_adv': st.get('range_adv'),
                'plan': st.get('plan'),
                'plan_since': st.get('plan_since'),
                'rel': st.get('rel'), 'made': st.get('made'),
                'calls_nut': CALLS['nut_advantage'] - before.get('nut_advantage', 0),
                'calls_adv': CALLS['range_advantage'] - before.get('range_advantage', 0),
            })
        return st

    R.nut_advantage, R.range_advantage, PL.update_plan = nut, adv, up
    # plan 모듈이 이미 R 을 참조하므로 그쪽도 교체
    PL.R.nut_advantage, PL.R.range_advantage = nut, adv


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        _ROOT, 'baseline_adv.json')
    install()
    t = T.Tournament(entries=40, seed=SEED, fmt='standard', hero_seat=7)
    hands = 0
    while hands < HANDS:
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
            break
        st = t.next_hand()
        g = 0
        while st and not st.get('done') and g < 250:
            st = t.submit('fold')
            g += 1
        hands += 1
        for r in ROWS:
            r.setdefault('hand', hands)

    # 핸드 단위로 묶어 스트리트 변화 확인
    with open(out, 'w') as f:
        json.dump({'seed': SEED, 'hands': hands, 'rows': ROWS,
                   'calls': dict(CALLS)}, f, ensure_ascii=False, indent=1)

    print('seed %d / %d핸드 / 기록 %d건 → %s'
          % (SEED, hands, len(ROWS), os.path.basename(out)))
    print('계산 호출: %s' % dict(CALLS))
    print()
    # 같은 (my_range, opp_range) 조합에서 보드만 바뀐 연속 기록 찾기
    print('보드가 바뀌었는데 지표가 그대로인 사례')
    print('  %-6s %-14s %-10s %-8s %-8s %s'
          % ('스트리트', '보드', '레인지', 'nut_adv', 'range_adv', '호출'))
    prev = None
    shown = 0
    for r in ROWS:
        if prev and r['board'] != prev['board'] and len(r['board']) > len(prev['board']):
            same = (r['nut_adv'] == prev['nut_adv']
                    and r['range_adv'] == prev['range_adv'])
            if same and shown < 12:
                shown += 1
                print('  %-6s %-14s %-10s %-8s %-8s nut=%d adv=%d'
                      % (prev['street'], prev['board'], prev['opp_range'],
                         prev['nut_adv'], prev['range_adv'],
                         prev['calls_nut'], prev['calls_adv']))
                print('  %-6s %-14s %-10s %-8s %-8s nut=%d adv=%d   ← 동일'
                      % (r['street'], r['board'], r['opp_range'],
                         r['nut_adv'], r['range_adv'],
                         r['calls_nut'], r['calls_adv']))
        prev = r


if __name__ == '__main__':
    main()
