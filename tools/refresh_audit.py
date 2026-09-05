"""STEP 7 계측기 — 좌석 x 스트리트 단위로 갱신 정당성을 판정한다.

    python3 tools/refresh_audit.py <출력>

이전 계측기는 update_plan 호출 순서대로 이웃끼리 비교해서, **서로 다른
좌석의 레인지를 비교**하는 오류가 있었다(A/turn → B/turn → A/turn 에서
A 와 B 를 비교). 같은 좌석 + 같은 스트리트의 연속 호출끼리만 본다.

좌석 식별: session 이 update_plan 에 h.hole[s] 를 넘기므로 홀카드로 구분한다.

판정
  새 스트리트                갱신되어야 함
  같은 스트리트 + 레인지 변화  갱신되어야 함
  같은 스트리트 + 레인지 동일  재계산하지 않아야 함(낭비)
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
ROWS = []


def rh(rg):
    if not rg:
        return 'EMPTY'
    return hashlib.sha1('|'.join(sorted(''.join(map(str, c)) for c in rg))
                        .encode()).hexdigest()[:10]


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
        prev_rsig = (state or {}).get('_rsig')
        first = (street != (state or {}).get('street_made')
                 and street not in ((state or {}).get('refreshed') or []))
        st = _up(state, hero, board, my_range, opp_range, profile, pot, stack,
                 street, *a, **k)
        if street != 'preflop':
            ROWS.append({
                'who': ''.join(map(str, hero or [])),      # 좌석 식별자
                'street': street, 'board': ''.join(board or []),
                'opp': rh(opp_range), 'my': rh(my_range),
                'first': first,
                'prev_rsig_none': prev_rsig is None,
                'calls': (CALLS['nut'] - b.get('nut', 0)
                          + CALLS['adv'] - b.get('adv', 0)),
                'nut': st.get('nut_adv'), 'adv': st.get('range_adv'),
            })
        return st
    R.nut_advantage = PL.R.nut_advantage = n2
    R.range_advantage = PL.R.range_advantage = a2
    PL.update_plan = up


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'refresh_audit.json'
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

    # 좌석(홀카드) x 스트리트 x 보드 로 묶어 연속 호출만 비교
    grp = collections.defaultdict(list)
    for r in ROWS:
        grp[(r['who'], r['street'], r['board'])].append(r)
    cat = collections.Counter()
    stale_ex = []
    for k, rows in grp.items():
        for i, r in enumerate(rows):
            if r['first']:
                cat['새 스트리트(첫 갱신)'] += 1
                if r['calls'] == 0:
                    cat['  └ 갱신 안 됨(문제)'] += 1
                continue
            p = rows[i - 1]
            moved = (p['opp'] != r['opp']) or (p['my'] != r['my'])
            if moved and r['calls'] > 0:
                cat['레인지 변화 → 갱신(정당)'] += 1
            elif moved and r['calls'] == 0:
                cat['레인지 변화 → 미갱신(stale)'] += 1
                if len(stale_ex) < 6:
                    stale_ex.append((r['street'], r['board'],
                                     p['opp'], r['opp'], p['nut'], r['nut']))
            elif not moved and r['calls'] > 0:
                cat['레인지 동일 → 재계산(낭비)'] += 1
            else:
                cat['레인지 동일 → 미갱신(정당)'] += 1
    ah = hashlib.sha1('\n'.join(sigs).encode()).hexdigest()[:16]
    json.dump({'action_hash': ah, 'calls': dict(CALLS), 'cat': dict(cat)},
              open(out, 'w'), ensure_ascii=False, indent=1)
    print('%s' % os.path.basename(out))
    print('  액션 해시 %s / 계산 호출 %s / 기록 %d건'
          % (ah, dict(CALLS), len(ROWS)))
    for k, v in cat.most_common():
        print('    %-30s %d' % (k, v))
    if stale_ex:
        print('  stale 사례')
        for e in stale_ex:
            print('    %-6s %-12s opp %s→%s nut %s→%s' % e)


if __name__ == '__main__':
    main()
