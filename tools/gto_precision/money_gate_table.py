#!/usr/bin/env python3
"""money_gate_study.py 결과를 단계 × 스택 분류 표로 묶는다.

  python3 tools/gto_precision/money_gate_table.py <json> [<json> ...]
"""
import json
import sys
from collections import Counter, defaultdict

STAGES = ('early', 'approach', 'bubble', 'itm')
CLS = ('short', 'medium', 'deep')


def med(v):
    v = sorted(x for x in v if x is not None)
    return v[len(v) // 2] if v else None


def fmt(x, nd=3):
    return '-' if x is None else ('%.*f' % (nd, x))


def main(paths):
    rows = []
    for p in paths:
        rows += json.load(open(p))['rows']
    g = defaultdict(list)
    for r in rows:
        g[(r['stage'], r['cls'])].append(r)
    out = []
    out.append('| 단계 | 스택 | 결정 | GTO 사용 | 못 씀(BF/머니/기록 없음) | BF 중앙 | pressure | brake | drive | danger | range_factor | 실제 진입%(기록 있는 결정) | GTO 칩 기준 진입% |')
    out.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for st in STAGES:
        for c in CLS:
            rs = g.get((st, c), [])
            if not rs:
                continue
            n = len(rs)
            used = sum(1 for r in rs if r['gto_used'])
            rb = Counter(('no_record' if r['gto_open'] is None else (r['reason'] or '').split(':')[0])
                         for r in rs if not r['gto_used'])
            cov = [r for r in rs if r['gto_open'] is not None]      # 기준 기록이 있는 결정만 비교
            act_in = (sum(1 for r in cov if r['act'] != 'fold') / len(cov)) if cov else 0.0
            go = [r['gto_open'] for r in cov]
            out.append('| %s | %s | %d | %.0f%% | %d/%d/%d | %s | %s | %s | %s | %s | %s | %.1f | %s |' % (
                st, c, n, 100.0 * used / n, rb.get('bf', 0), rb.get('money', 0), rb.get('no_record', 0),
                fmt(med(r['bf'] for r in rs)),
                fmt(med(r['pressure'] for r in rs), 4), fmt(med(r['brake'] for r in rs), 4),
                fmt(med(r['drive'] for r in rs), 4), fmt(med(r['danger_fraction'] for r in rs), 2),
                fmt(med(r['range_factor'] for r in rs), 3), 100 * act_in,
                fmt(100 * sum(go) / len(go), 1) if go else '-'))
    print('\n'.join(out))
    rb = Counter(('no_record' if r['gto_open'] is None else r['reason']) for r in rows if not r['gto_used'])
    print('\n결정 %d, GTO 사용 %d, 막힘 이유 %s' % (
        len(rows), sum(1 for r in rows if r['gto_used']), dict(rb.most_common())))


if __name__ == '__main__':
    main(sys.argv[1:])
