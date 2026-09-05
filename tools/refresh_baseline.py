"""STEP 7 전후 비교 — 같은 스트리트 안에서 레인지가 바뀔 때의 갱신.

    python3 tools/refresh_baseline.py <출력>

기록
  update_plan 호출마다: 스트리트 / 보드 / 내·상대 레인지 해시 / 지표 / 호출 횟수
  분류: 진짜 stale / 갱신됨 / 레인지 동일(정상)
  액션 해시(판단 변화 추적)
"""
import sys, os, json, hashlib, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import plan as PL     # noqa: E402
import ranges as R    # noqa: E402
import tourney as T   # noqa: E402

SEEDS = tuple(range(31001, 31007))
HANDS = 45
CALLS = collections.Counter()
SEQ = []


def rh(rg):
    if not rg:
        return ['EMPTY', 0]
    norm = sorted(''.join(map(str, c)) for c in rg)
    return [hashlib.sha1('|'.join(norm).encode()).hexdigest()[:8], len(norm)]


def install():
    _n, _a, _up = R.nut_advantage, R.range_advantage, PL.update_plan

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
            SEQ.append({'street': street, 'board': ''.join(board or []),
                        'opp': rh(opp_range), 'my': rh(my_range),
                        'nut': st.get('nut_adv'), 'adv': st.get('range_adv'),
                        'cn': CALLS['nut'] - b.get('nut', 0),
                        'ca': CALLS['adv'] - b.get('adv', 0)})
        return st
    R.nut_advantage = PL.R.nut_advantage = n2
    R.range_advantage = PL.R.range_advantage = a2
    PL.update_plan = up


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'refresh_before.json'
    install()
    sigs = []
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
            h = getattr(t.run, 'h', None)
            res = getattr(t.run, 'result', None) or {}
            log = getattr(t.run, 'full_log', []) or []
            sigs.append('%d|%d|%s|%s|%s' % (
                sd, n, ''.join((h.board or []) if h else []),
                ';'.join('%s%s%s' % (x[0][:2], x[1], x[2]) for x in log),
                res.get('pot')))

    cat = collections.Counter()
    prev = None
    for r in SEQ:
        if prev and prev['street'] == r['street'] and prev['board'] == r['board']:
            opp_ch = prev['opp'][0] != r['opp'][0]
            same = (prev['nut'] == r['nut'] and prev['adv'] == r['adv'])
            called = (r['cn'] + r['ca']) > 0
            if not opp_ch:
                cat['레인지 동일(재계산 불필요)'] += 1
                if called:
                    cat['  └ 그런데 재계산함(낭비)'] += 1
            elif called and not same:
                cat['갱신됨(값 변화)'] += 1
            elif called and same:
                cat['갱신됨(값 우연히 같음)'] += 1
            else:
                cat['진짜 stale'] += 1
        prev = r
    ah = hashlib.sha1('\n'.join(sigs).encode()).hexdigest()[:16]
    json.dump({'action_hash': ah, 'calls': dict(CALLS),
               'cat': dict(cat), 'n_seq': len(SEQ)},
              open(out, 'w'), ensure_ascii=False, indent=1)
    print('%s' % os.path.basename(out))
    print('  액션 해시   %s' % ah)
    print('  계산 호출   %s' % dict(CALLS))
    print('  update_plan 기록 %d건' % len(SEQ))
    for k, v in cat.most_common():
        print('    %-28s %d' % (k, v))


if __name__ == '__main__':
    main()
