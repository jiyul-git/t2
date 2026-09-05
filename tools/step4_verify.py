"""STEP 4 통합 검증 — 관측했던 결함 5종이 구조적으로 사라졌는가.

    python3 tools/step4_verify.py

**같은 핸드를 재현하는 것이 아니다.** 시드를 잃어 #9/#54 등은 복원할 수 없다.
'그 결함 조건이 새 코드에서 발생하는가'를 본다.

STEP 1 로 판단이 바뀌는 것은 정상이므로 action hash 동일성은 기준으로 쓰지 않는다.

known issues (이번 판정에서 제외)
  A. response_src 가 비어 있음 — 기록 출처 문제. response 자체는 정상
  B. 같은 스트리트 2회차 update_plan 에서 레인지 지표 미갱신
     보드 의존 지표는 해결됐으나, 레인지만 좁혀진 경우의 lifetime 문제
"""
import sys, os, re, json, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import ranges as R    # noqa: E402
import plan as PL     # noqa: E402
import tourney as T   # noqa: E402

SEED, HANDS = 26001, 40
PCT = re.compile(r'\((\d+)%\)')
CALLS = collections.Counter()


def install():
    _n, _a, _up = R.nut_advantage, R.range_advantage, PL.update_plan
    ROWS = []

    def n2(*x, **k):
        CALLS['nut'] += 1
        return _n(*x, **k)

    def a2(*x, **k):
        CALLS['adv'] += 1
        return _a(*x, **k)

    def up(state, hero, board, my_range, opp_range, profile, pot, stack,
           street, *a, **k):
        b = dict(CALLS)
        st = _up(state, hero, board, my_range, opp_range, profile, pot, stack,
                 street, *a, **k)
        if street != 'preflop':
            ROWS.append({'street': street, 'board': ''.join(board or []),
                         'nut_adv': st.get('nut_adv'),
                         'range_adv': st.get('range_adv'),
                         'calls_nut': CALLS['nut'] - b.get('nut', 0),
                         'calls_adv': CALLS['adv'] - b.get('adv', 0),
                         'first': street not in (state or {}).get('refreshed', [])})
        return st

    R.nut_advantage = PL.R.nut_advantage = n2
    R.range_advantage = PL.R.range_advantage = a2
    PL.update_plan = up
    return ROWS


def main():
    rows = install()
    intents = []
    t = T.Tournament(entries=40, seed=SEED, fmt='standard', hero_seat=7)
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
        h = getattr(t.run, 'h', None)
        for i in (getattr(h, 'intents', None) or []):
            if i.get('street') != 'preflop':
                intents.append(i)

    # 1) stale board metric — 보드가 커졌는데 첫 갱신인데도 호출 0
    stale = tot_stale = 0
    prev = None
    for r in rows:
        if prev and len(r['board']) > len(prev['board']):
            tot_stale += 1
            if r['first'] and r['calls_nut'] == 0 and r['calls_adv'] == 0:
                stale += 1
        prev = r

    # 2) 확률 표시
    bad = tot_p = 0
    for i in intents:
        m = PCT.search(i.get('intent_src') or '')
        if not m:
            continue
        tot_p += 1
        if int(m.group(1)) > 97:
            bad += 1

    # 3) 저항 상황 의도/대응
    resp = [i for i in intents if (i.get('tocall') or 0) > 0]
    miss = sum(1 for i in resp
               if i.get('response_act') is None or i.get('intent_act') is None)

    # 4) why 혼입
    mix = tot_w = 0
    for i in intents:
        w = i.get('why_by_street')
        if not w:
            continue
        tot_w += 1
        others = [p for p in ('flop:', 'turn:', 'river:')
                  if not p.startswith(i['street'])]
        if any(x.startswith(tuple(others)) for x in w):
            mix += 1

    # 5) trap goal 연속성
    trap = [i for i in intents if i.get('plan_mode') == 'trap'
            or i.get('plan') == 'trap']
    bad_goal = sum(1 for i in trap
                   if not (i.get('plan_goal') or '').startswith('value'))

    print('seed %d / %d핸드 / 포스트플랍 기록 %d건' % (SEED, n, len(intents)))
    print()
    print('  %-28s %s' % ('stale board metric', '%d / %d' % (stale, tot_stale)))
    print('  %-28s %s' % ('probability mismatch', '%d / %d' % (bad, tot_p)))
    print('  %-28s %s' % ('response missing', '%d / %d' % (miss, len(resp))))
    print('  %-28s %s' % ('why contamination', '%d / %d' % (mix, tot_w)))
    print('  %-28s %s' % ('trap goal discontinuity',
                          '%d / %d' % (bad_goal, len(trap))))
    print()
    ok = (stale == 0 and bad == 0 and miss == 0 and mix == 0 and bad_goal == 0)
    print('  판정: %s' % ('PASS' if ok else 'FAIL'))
    print()
    print('  known issues (판정 제외)')
    print('    A. response_src 비어 있음 — 기록 출처, response 자체는 정상')
    print('    B. 같은 스트리트 2회차 갱신 — 레인지만 좁혀진 경우의 lifetime')


if __name__ == '__main__':
    main()
