#!/usr/bin/env python3
"""entries 가 축 분산을 압축하는가 — 모집단 분포를 직접 잰다.

  python3 tools/axis_dispersion.py --entries 24,48,100,250 --n 20000

Spearman 은 순위 기반이라 평균 이동보다 **분산·순위 구조의 압축**이
ρ 의 측정 가능 범위를 정한다. 그래서 sd 하나가 아니라 IQR 과 p5~p95 폭을
같이 본다.

시뮬레이션이 필요 없다. persona.make_player 가 field_quality 하나만
받으므로(fieldsim.py:69 는 aggr_bias·loose_bias 없이 부른다) 모집단을
직접 뽑으면 된다. 읽기 전용.
"""
import os, sys, argparse, random, statistics as stat

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

import persona as PS
import field as FLD


def pcts(v):
    v = sorted(v); n = len(v)
    g = lambda f: v[min(n-1, int(f*n))]
    return stat.pstdev(v), g(0.75)-g(0.25), g(0.95)-g(0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', default='24,48,100,250')
    ap.add_argument('--n', type=int, default=20000)
    ap.add_argument('--buyin', type=float, default=1.0)
    a = ap.parse_args()

    ents = [int(x) for x in a.entries.split(',')]
    fields = {}
    for e in ents:
        q = FLD.field_quality(e, a.buyin)
        rng = random.Random(4242)
        fields[e] = (q, [PS.make_player(rng, q, i) for i in range(a.n)])

    print('# 축 분산 폭 대 entries   N=%d  buyin=%.1f' % (a.n, a.buyin))
    print()
    print('entries  field_q')
    for e in ents:
        print('  %5d  %6.3f' % (e, fields[e][0]))
    print()

    P0 = fields[ents[0]][1][0]
    names = [('c', k) for k in sorted(P0['concepts'])] + \
            [('t', k) for k in sorted(P0['temper'])]

    hdr = '%-20s' % '축'
    for e in ents: hdr += '  %-21s' % ('entries=%d' % e)
    print(hdr)
    print('%-20s' % '' + ''.join('  %6s %6s %7s' % ('sd', 'IQR', 'p5-95') for _ in ents))
    print('-'*(20 + 23*len(ents)))

    rows = []
    for kind, k in names:
        line = '%-20s' % (kind + ':' + k)
        vals = []
        for e in ents:
            src = fields[e][1]
            v = [p['concepts'][k] if kind == 'c' else p['temper'][k] for p in src]
            sd, iqr, p90 = pcts(v)
            vals.append((sd, iqr, p90))
            line += '  %6.2f %6.2f %7.2f' % (sd, iqr, p90)
        rows.append((kind, k, vals, line))
        print(line)

    print()
    print('## 요약 — 첫 조건 대비 마지막 조건의 폭 비율')
    for metric, idx in (('sd', 0), ('IQR', 1), ('p5-95', 2)):
        r = [v[-1][idx]/v[0][idx] for _, _, v, _ in rows if v[0][idx] > 0]
        print('  %-6s  중앙 %.3f   최소 %.3f   최대 %.3f   1.0 미만(압축) %d/%d 축'
              % (metric, stat.median(r), min(r), max(r),
                 sum(1 for x in r if x < 1.0), len(r)))
    print()
    print('  1.0 = 압축 없음.  < 1.0 이면 entries 가 축 폭을 좁힌다.')


if __name__ == '__main__':
    main()
