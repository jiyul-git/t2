"""multiway_passivity_diag.py 기록 요약(진단 전용).  python3 tools/multiway_passivity_report.py 파일...

밸류 사다리 구간(band)을 기록된 eq·rel 로 다시 계산한다(상대 읽기 보정 rd 는 생략 — 정보 없는 초반엔 0).
반사실: mw=0(다인원 가산 없음), eq^(1/N)(헤즈업 환산 지분), rel=rel_union(합집합 rel), eq=eq_f35/eq_rand(넓은 기준 레인지).
"""
import sys, os, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import plan as P

rows = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
ST = {3: 'flop', 4: 'turn', 5: 'river'}


def band(eq, rel, n, mw0=False):
    _, v3, v2, pcz = P.multiway_value_thresholds(1 if mw0 else n, 0, 0)
    v3, v2 = P.relative_strength_value_threshold_shift(v3, v2, rel)
    return 'v3' if eq >= v3 else 'v2' if eq >= v2 else 'mid' if eq >= pcz else 'low'


def term(r):
    w, p = r['why_bet'], r['plan']
    if p == 'pot_control':
        return 'pot_control'
    if p in ('showdown', 'giveup'):
        return p + ('(no-init)' if '이니셔티브 없음' in w else '(river)' if '리버' in w else '(cbet-freq)')
    if p == 'trap':
        return 'trap'
    if '상대에게 액션 우선' in w or '라인은 상대 것' in w:
        return 'line_owner'
    if p.startswith('value'):
        return 'value(p<1)'
    return p


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float('nan')


for mode in (False, True):
    R = [r for r in rows if r['old'] == mode]
    if not R:
        continue
    print('\n==== %s ranges  rows=%d' % ('OLD(pre-sync)' if mode else 'CURRENT(GTO-sync)', len(R)))
    for s in (3, 4, 5):
        for cls in ('tp_weak', 'tp_gk', 'overpair', '2p+'):
            g = [r for r in R if r['street'] == s and r['cls'] == cls]
            if not g:
                continue
            nb = sum(r['bet'] for r in g)
            print('%-5s %-8s n=%4d bet=%5.1f%% p_bet=%.2f eq=%.2f eq35=%.2f eqR=%.2f relJ=%.2f relU=%.2f'
                  % (ST[s], cls, len(g), 100.0*nb/len(g), avg([r['p_bet'] for r in g]),
                     avg([r['eq'] for r in g]), avg([r['eq_f35'] for r in g]), avg([r['eq_rand'] for r in g]),
                     avg([r['rel_joint'] for r in g]), avg([r['rel_union'] for r in g])))
    tp = [r for r in R if r['cls'] in ('tp_weak', 'tp_gk')]
    print('-- top pair (tp_weak+tp_gk) checks: blocking term counts per street')
    for s in (3, 4, 5):
        g = [r for r in tp if r['street'] == s]
        ch = [r for r in g if not r['bet']]
        c = collections.Counter(term(r) for r in ch)
        print('  %s n=%d checks=%d  %s' % (ST[s], len(g), len(ch), dict(c.most_common())))
        pl = collections.Counter(r['plan'] for r in g)
        print('     plans: %s' % dict(pl.most_common()))
    print('-- top pair band (re-computed now) and counterfactual bands')
    for s in (3, 4, 5):
        g = [r for r in tp if r['street'] == s and r['eq'] is not None and r['rel'] is not None]
        if not g:
            continue
        def dist(f):
            c = collections.Counter(f(r) for r in g)
            return ' '.join('%s %3.0f%%' % (k, 100.0*c[k]/len(g)) for k in ('v3', 'v2', 'mid', 'low'))
        print('  %s n=%d' % (ST[s], len(g)))
        print('    actual           : ' + dist(lambda r: band(r['eq'], r['rel'], r['n_opp'])))
        print('    mw=0 (no +0.06/opp): ' + dist(lambda r: band(r['eq'], r['rel'], r['n_opp'], True)))
        print('    rel=union        : ' + dist(lambda r: band(r['eq'], r['rel_union'] or r['rel'], r['n_opp'])))
        print('    eq=field35       : ' + dist(lambda r: band(r['eq_f35'], r['rel'], r['n_opp'])))
        print('    eq=random        : ' + dist(lambda r: band(r['eq_rand'], r['rel'], r['n_opp'])))
        print('    HU-equiv eq^(1/N), mw=0, rel=union : ' + dist(lambda r: band(r['eq'] ** (1.0/r['n_opp']), r['rel_union'] or r['rel'], r['n_opp'], True)))
        print('    mw=0 + rel=union : ' + dist(lambda r: band(r['eq'], r['rel_union'] or r['rel'], r['n_opp'], True)))
        # 문턱 상승량 분해(평균): 다인원 가산 vs rel 가산
        mwadd = avg([0.07*max(0, r['n_opp']-1) for r in g])
        reladd = avg([P.relative_strength_value_threshold_shift(0, 0, r['rel'])[1] for r in g])
        reladdU = avg([P.relative_strength_value_threshold_shift(0, 0, r['rel_union'] or r['rel'])[1] for r in g])
        print('    v2 raise: multiway +%.3f, rel(joint) +%.3f, rel(union) +%.3f ; mean eq %.3f vs base v2 0.66'
              % (mwadd, reladd, reladdU, avg([r['eq'] for r in g])))
