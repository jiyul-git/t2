#!/usr/bin/env python3
"""계산 브랜치의 단계별 판정(report.json: 끝점 terminal × 자리별 D, U, pass)을 모은다 — 읽기만.

  python3 tools/gto_precision/collect_step_du.py <out_json> <branch>...

data/gto_spot/plan_a/progress/<spot>/step<k>/report.json 을 git 으로 읽는다(브랜치를 체크아웃하지 않음).
spot 마다 단계가 가장 많은 브랜치를 쓴다. 단계별로 terminal·자리마다 D(이번 단계와 앞 단계 끝점 값 차이),
U(그 차이의 허용폭 = 패널 표본오차 기반), D/U 를 남기고, spot 요약으로 마지막 단계 max(D/U), 단계 수,
D/U 가 줄었는지(수렴 방향)를 낸다.
"""
import json
import re
import subprocess
import sys
from collections import defaultdict


def git(*a):
    return subprocess.run(('git',) + a, capture_output=True, text=True, check=True).stdout


def main():
    out, branches = sys.argv[1], sys.argv[2:]
    best = {}
    for b in branches:
        names = git('ls-tree', '-r', '--name-only', b).split('\n')
        steps = defaultdict(list)
        for n in names:
            m = re.match(r'.*progress/([^/]+)/step(\d+)/report\.json$', n)
            if m:
                steps[m.group(1)].append((int(m.group(2)), n))
        for spot, lst in steps.items():
            if spot not in best or len(lst) > len(best[spot][1]):
                best[spot] = (b, sorted(lst))
    res = {}
    for spot, (b, lst) in sorted(best.items()):
        per = []
        for k, path in lst:
            try:
                rep = json.loads(git('show', '%s:%s' % (b, path)))
            except Exception as e:          # noqa: BLE001
                per.append({'step': k, 'error': str(e)[:200]})
                continue
            rows = []
            for line, t in (rep.get('terminals') or {}).items():
                for seat, v in (t.get('seats') or {}).items():
                    D, U = v.get('D'), v.get('U')
                    if D is None or U is None:
                        continue
                    rows.append({'term': t.get('term'), 'seat': seat, 'D': round(D, 4), 'U': round(U, 4),
                                 'r': round(D / U, 3) if U else None, 'pass': v.get('pass'),
                                 'exempt': v.get('exempt'), 'opp_combos': v.get('opp_arriving_combos')})
            live = [r for r in rows if not r['exempt'] and r['r'] is not None]
            per.append({'step': k, 'decision': rep.get('decision'), 'all_pass': rep.get('all_pass'),
                        'max_r': max((r['r'] for r in live), default=None),
                        'max_D': max((r['D'] for r in live), default=None),
                        'min_U': min((r['U'] for r in live), default=None), 'rows': rows})
        rs = [p['max_r'] for p in per if p.get('max_r') is not None]
        res[spot] = {'branch': b, 'n_steps': len(per), 'max_r_by_step': rs,
                     'last_max_r': rs[-1] if rs else None,
                     'shrinking': (len(rs) >= 2 and rs[-1] < rs[0]), 'steps': per}
    json.dump(res, open(out, 'w'), indent=1)
    for s, v in res.items():
        print(s, v['branch'].split('/')[-1], v['n_steps'], v['max_r_by_step'])


if __name__ == '__main__':
    main()
