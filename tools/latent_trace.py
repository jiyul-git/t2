"""infer_latent 해부 — 행동에서 잠재요인(study/aggro/exp)을 복원하는가.

    python3 tools/latent_trace.py

**production 코드는 수정하지 않는다.** 순수 경로만 본다.

    실제 latent → 행동 생성 → 관찰 행동 → infer_latent → 추정 latent

관찰자 능력·스타일·라벨은 전부 배제한다. 장부의 원시 빈도를 그대로
est 로 만들어 infer_latent 에 넣는다(노이즈·수축 없음).
"""
import sys, os, math, statistics, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import tourney as T   # noqa: E402
import reads as RD    # noqa: E402

SEEDS = tuple(range(22001, 22013))
HANDS = 45


def corr(x, y):
    if len(x) < 3:
        return 0.0
    mx, my = statistics.mean(x), statistics.mean(y)
    num = sum((a-mx)*(b-my) for a, b in zip(x, y))
    den = math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))
    return num/den if den else 0.0


def slope(x, y):
    """y = a + b*x 의 b. 1.0 이면 스케일이 맞는 것."""
    if len(x) < 3:
        return 0.0
    mx, my = statistics.mean(x), statistics.mean(y)
    den = sum((a-mx)**2 for a in x)
    return (sum((a-mx)*(b-my) for a, b in zip(x, y)) / den) if den else 0.0


def main():
    act = collections.defaultdict(list)
    est = collections.defaultdict(list)
    beh_corr = collections.defaultdict(lambda: ([], []))

    for sd in SEEDS:
        t = T.Tournament(entries=60, seed=sd, fmt='standard', hero_seat=7)
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
        h = getattr(t.run, 'h', None)
        if h is None:
            continue
        truth = {}
        for seat, pr in (h.prof or {}).items():
            if pr.get('latent'):
                key = 'T%s_%s' % (getattr(h, 'table_id', 0), seat)
                truth[key] = pr['latent']
        seen = set()
        for k, r in (h.book.d or {}).items():
            _o, tg = k.split('>')
            if tg in seen or tg not in truth or r.get('hands', 0) < 25:
                continue
            seen.add(tg)
            hn = float(r['hands'])
            # 관찰자 노이즈·수축 없이 **원시 빈도**를 그대로 넣는다.
            e = {
                'vpip': r['vpip']/hn,
                'pfr': r['pfr']/hn,
                'cbet': (r['cbet']/r['cbet_opp']) if r.get('cbet_opp') else None,
                'barrel': (r['barrel']/r['barrel_opp']) if r.get('barrel_opp') else None,
                'pf_3bet': (r.get('pf_3bet', 0)/r['pf_3bet_opp'])
                           if r.get('pf_3bet_opp') else None,
                'sz_sd': None,
            }
            e = {kk: vv for kk, vv in e.items() if vv is not None}
            s_, a_, x_ = RD.infer_latent(e)
            la = truth[tg]
            act['study'].append(la['study']); est['study'].append(s_)
            act['aggro'].append(la['aggro']); est['aggro'].append(a_)
            act['exp'].append(la['exp']); est['exp'].append(x_)
            # 행동 변수 자체가 latent 와 상관이 있는가(입력 신호 점검)
            for bk in ('vpip', 'pfr', 'cbet', 'barrel'):
                if bk in e:
                    beh_corr[(bk, 'aggro')][0].append(e[bk])
                    beh_corr[(bk, 'aggro')][1].append(la['aggro'])
                    beh_corr[(bk, 'study')][0].append(e[bk])
                    beh_corr[(bk, 'study')][1].append(la['study'])

    n = len(act['study'])
    print('표본 %d명 (관찰 노이즈 없음, 스타일/관찰력 배제)' % n)
    print()
    print('%-8s %6s %6s %7s %7s %7s | %7s %7s %7s %7s'
          % ('factor', 'MAE', 'RMSE', 'bias', 'corr', 'slope',
             '실제mean', '추정mean', '실제sd', '추정sd'))
    for kk in ('study', 'aggro', 'exp'):
        a, e = act[kk], est[kk]
        if len(a) < 5:
            continue
        d = [x-y for x, y in zip(e, a)]
        print('%-8s %6.2f %6.2f %+7.2f %+7.2f %+7.2f | %7.2f %7.2f %7.2f %7.2f'
              % (kk, statistics.mean(map(abs, d)),
                 math.sqrt(statistics.mean([x*x for x in d])),
                 statistics.mean(d), corr(e, a), slope(a, e),
                 statistics.mean(a), statistics.mean(e),
                 statistics.pstdev(a), statistics.pstdev(e)))

    print()
    print('입력 신호 점검 — 행동 변수가 latent 와 상관이 있는가')
    print('%-10s %10s %10s' % ('행동변수', 'vs aggro', 'vs study'))
    for bk in ('vpip', 'pfr', 'cbet', 'barrel'):
        ra = beh_corr.get((bk, 'aggro'))
        rs = beh_corr.get((bk, 'study'))
        if not ra or len(ra[0]) < 5:
            continue
        print('%-10s %+10.2f %+10.2f'
              % (bk, corr(ra[0], ra[1]), corr(rs[0], rs[1])))


if __name__ == '__main__':
    main()
