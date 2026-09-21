#!/usr/bin/env python3
"""`sizing_tell` 이 응답 판단에서 실제로 무엇을 하는가. **읽기 전용이다.**

  python3 tools/cf_stell.py --n 400 --street flop

2-A 재측정(TRACE_SZSEEN.md)에서 `sizing_tell` 의 뒤집힘 비율이
덮어쓰기 유지 14.5% / 체인보존 1.8% 로 갈렸다. 비율만으로는
"축이 제대로 설계됐는가"를 못 가른다. 여기서 보는 것:

  1. sizing_tell 이 오르면 콜이 느는가 폴드가 느는가
  2. 벳 크기별로 방향이 다른가 (작은 벳 / 표준 / 큰 벳)
  3. 인지한 사이즈를 크게 읽는가 작게 읽는가
  4. need 를 절대값으로 얼마나 움직이는가
  5. potodds·range_read 와 충돌하면 누가 이기는가 (2×2 요인)

변종은 `tools/cf_szseen.py` 가 만든 것을 그대로 쓴다
(① 예전 덮어쓰기 = BASE_REV 원문 / ③ 현재 = 입력 교체).
plan.py 는 건드리지 않는다.
"""
import argparse, copy, os, random, sys, statistics as ST
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)
sys.path.insert(0, os.path.join(D, 'tools'))

import bot, plan as PL, persona as PS
import cf_szseen as SZ

# ① 예전(덮어쓰기) 과 ③ 현재(입력 교체) 만 본다. ② 는 cf_szseen 이 맡는다.
TAGS = [SZ.TAGS[0], SZ.TAGS[2]]


def bucket(sz):
    if sz <= 0.55: return '작은 벳(≤0.55)'
    if sz <= 0.80: return '표준(0.66~0.75)'
    return '큰 벳(≥1.0)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--street', default='flop', choices=list(SZ.BOARD_N))
    ap.add_argument('--bf', type=float, default=1.0)
    ap.add_argument('--seed', type=int, default=20260914)
    a = ap.parse_args()

    _all = SZ.build_all()
    fns = {t: _all[t] for t in TAGS}
    cur = PL.calldown_need

    rng = random.Random(a.seed)
    sits = []
    for i in range(a.n):
        sit = SZ.situation(rng, a.street)
        prof = PS.make_player(rng, 0.78, i)
        est = SZ.fake_read(rng)
        rv = rng.uniform(0.10, 0.70)
        s = rng.randrange(1 << 30)
        sits.append((sit, prof, est, rv, s))

    def run(fn, sit, prof, ps, s, est, rv):
        PL.calldown_need = fn
        try:
            (act, _), _eq, need = PL.act_with_plan(
                sit['hero'], sit['board'], prof, copy.deepcopy(ps),
                sit['pot'], sit['tocall'], sit['stack'], sit['street'],
                initiative=sit['initiative'],
                opp_range=sit['opp_range'], seed=s, n_opp=1, bf=a.bf,
                to_act_behind=sit['to_act_behind'], opp_est=est, read=rv)
        finally:
            PL.calldown_need = cur
        return act, need

    acts = {t: {1: Counter(), 9: Counter()} for t in TAGS}
    trans = {t: Counter() for t in TAGS}
    by_bkt = {t: defaultdict(Counter) for t in TAGS}
    dneed = {t: [] for t in TAGS}
    dseen = []           # sz_seen(9) − sz_seen(1)
    seen_vs_true = Counter()
    bkt_n = Counter()
    # 2×2 요인: st × other
    fact = {t: {o: {(sv, ov): 0 for sv in (1, 9) for ov in (1, 9)}
                for o in ('range_read', 'potodds')} for t in TAGS}
    # 순 콜비율은 fold→call 과 call→fold 가 서로 지우므로 뒤집힘도 같이 센다
    fflip = {t: {o: Counter() for o in ('range_read', 'potodds')} for t in TAGS}
    fact_n = 0
    ident = 0            # size_read 가 항등으로 동작한 건수

    for (sit, prof, est, rv, s) in sits:
        try:
            ps = PL.make_plan(sit['hero'], sit['board'], sit['my_range'],
                              sit['opp_range'], prof, sit['pot'], sit['stack'],
                              sit['street'], seed=s, n_opp=1,
                              to_act_behind=sit['to_act_behind'],
                              oop=sit['oop'], initiative=sit['initiative'],
                              opp_est=est)
        except Exception:
            continue
        sz_true = sit['tocall']/max(1.0, float(sit['pot']) - sit['tocall'])
        bk = bucket(sz_true); bkt_n[bk] += 1
        p = {}
        seen = {}
        for v in (1, 9):
            p[v] = SZ.perturb(prof, 'sizing_tell', v)
            rdz = PS.read_opponent(p[v], est)
            norm = PS.opp_size_norm(rdz, sz_true, sit['street'])
            seen[v] = PS.size_read(p[v], norm)
            if abs(seen[v] - norm) < 1e-12:
                ident += 1
        dseen.append(seen[9] - seen[1])
        seen_vs_true['%s / st=9 %s' % (bk, '크게 읽음' if seen[9] > sz_true
                                       else ('작게 읽음' if seen[9] < sz_true
                                             else '그대로'))] += 1
        try:
            for t in TAGS:
                r1 = run(fns[t], sit, p[1], ps, s, est, rv)
                r9 = run(fns[t], sit, p[9], ps, s, est, rv)
                acts[t][1][r1[0]] += 1; acts[t][9][r9[0]] += 1
                by_bkt[t][bk][r9[0]] += 1
                by_bkt[t][bk + ' |st=1'][r1[0]] += 1
                if r1[1] is not None and r9[1] is not None:
                    dneed[t].append(r9[1] - r1[1])
                if r1[0] != r9[0]:
                    trans[t]['%s → %s' % (r1[0], r9[0])] += 1
        except Exception:
            continue
        # 2×2 요인
        try:
            for o in ('range_read', 'potodds'):
                cell = {}
                for sv in (1, 9):
                    for ov in (1, 9):
                        q = SZ.perturb(prof, 'sizing_tell', sv)
                        q = SZ.perturb(q, o, ov)
                        for t in TAGS:
                            act, _ = run(fns[t], sit, q, ps, s, est, rv)
                            cell[(t, sv, ov)] = act
                            if act == 'call': fact[t][o][(sv, ov)] += 1
                for t in TAGS:
                    for ov in (1, 9):
                        if cell[(t, 1, ov)] != cell[(t, 9, ov)]:
                            fflip[t][o]['st@%d' % ov] += 1
                    for sv in (1, 9):
                        if cell[(t, sv, 1)] != cell[(t, sv, 9)]:
                            fflip[t][o]['other@%d' % sv] += 1
            fact_n += 1
        except Exception:
            pass

    n = max(1, sum(bkt_n.values()))
    print('# sizing_tell 해부 — %s, 상황 %d개, bf=%.1f' % (a.street, n, a.bf))
    print('# baseline 6574360 (1-A 적용). plan.py 무수정\n')

    print('## 0. 배선 — `size_read` 는 이 표본에서 항등이다')
    print('   size_read(prof, norm) == norm 인 건수 %d / %d (%.1f%%)'
          % (ident, 2*n, 100*ident/max(1, 2*n)))
    print('   size_read 는 사이즈가 2.0팟을 넘을 때만 sizing_tell 을 쓴다')
    print('   (persona.py:755 `if s <= 2.0: return s`).')
    print('   그래서 sizing_tell 이 _sz_seen 에 닿는 경로는 size_read 가 아니라')
    print('   read_opponent 의 see_size → size_gap/size_big → opp_size_norm 이다.\n')

    print('## 1. 방향 — sizing_tell 1 → 9')
    print('%-14s %8s %8s %8s %8s' % ('', '폴드1', '폴드9', '콜1', '콜9'))
    for t in TAGS:
        c1, c9 = acts[t][1], acts[t][9]
        m = max(1, sum(c1.values()))
        print('%-14s %7.1f%% %7.1f%% %7.1f%% %7.1f%%'
              % (t, 100*c1['fold']/m, 100*c9['fold']/m,
                 100*c1['call']/m, 100*c9['call']/m))
        print('     전환  %s' % ('  '.join('%s ×%d' % (k, v)
                                          for k, v in trans[t].most_common())
                                or '없음'))
    print()

    print('## 2. 인지한 사이즈를 어느 쪽으로 읽는가')
    print('   sz_seen(9) − sz_seen(1)  중앙 %+.4f  평균 %+.4f'
          % (ST.median(dseen), sum(dseen)/max(1, len(dseen))))
    for k, v in sorted(seen_vs_true.items()):
        print('   %-34s %4d' % (k, v))
    print()

    print('## 3. 벳 크기별 (st=1 → st=9 의 콜 비율)')
    print('%-14s %-18s %8s %8s' % ('변종', '구간', 'n', '콜 1→9'))
    for t in TAGS:
        for bk in ('작은 벳(≤0.55)', '표준(0.66~0.75)', '큰 벳(≥1.0)'):
            g = bkt_n[bk]
            if not g: continue
            c1 = by_bkt[t][bk + ' |st=1']['call']; c9 = by_bkt[t][bk]['call']
            print('%-14s %-18s %8d   %.1f%% → %.1f%%'
                  % (t, bk, g, 100*c1/g, 100*c9/g))
    print()

    print('## 4. need 를 얼마나 움직이는가 (need(9) − need(1))')
    for t in TAGS:
        d = dneed[t]
        if not d: continue
        ab = sorted(abs(x) for x in d)
        print('   %-14s 부호있는 중앙 %+.4f   |Δ| 중앙 %.4f   |Δ| 90분위 %.4f'
              % (t, ST.median(d), ab[len(ab)//2], ab[int(0.9*len(ab))]))
    print()

    print('## 5. 충돌 — 2×2 요인 (셀 값 = 콜 비율, n=%d)' % fact_n)
    for t in TAGS:
        for o in ('range_read', 'potodds'):
            f = fact[t][o]; m = max(1, fact_n)
            print('   %s × %s' % (t, o))
            print('      %-12s %12s %12s' % ('', o+'=1', o+'=9'))
            for sv in (1, 9):
                print('      st=%-10d %11.1f%% %11.1f%%'
                      % (sv, 100*f[(sv, 1)]/m, 100*f[(sv, 9)]/m))
            st_at1 = (f[(9, 1)] - f[(1, 1)])/m
            st_at9 = (f[(9, 9)] - f[(1, 9)])/m
            o_at1 = (f[(1, 9)] - f[(1, 1)])/m
            o_at9 = (f[(9, 9)] - f[(9, 1)])/m
            print('      순 콜비율 주효과 — st %+.1f%%p(상대=1) / %+.1f%%p(상대=9)'
                  % (100*st_at1, 100*st_at9))
            print('                       %s %+.1f%%p(st=1) / %+.1f%%p(st=9)'
                  % (o, 100*o_at1, 100*o_at9))
            ff = fflip[t][o]
            print('      뒤집힘  — st  %.1f%%(상대=1) / %.1f%%(상대=9)   '
                  '%s  %.1f%%(st=1) / %.1f%%(st=9)'
                  % (100*ff['st@1']/m, 100*ff['st@9']/m, o,
                     100*ff['other@1']/m, 100*ff['other@9']/m))
    print()
    print('주효과가 상대 축의 값에 따라 사라지면 그 축에 눌린 것이다.')


if __name__ == '__main__':
    main()
