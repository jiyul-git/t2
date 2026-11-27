#!/usr/bin/env python3
"""두 단계 트리 덤프의 프리플랍 빈도 변화(마감용 실용 수렴 기준, 사용자 일정 11-27: 2%p).
  python3 ft_freq_change.py <이전 dump.jsonl[.gz]> <새 dump.jsonl[.gz]> [최소 도달확률 0.005]
도달확률 >= 기준인 결정 노드마다 행동 빈도(행동자 레인지 가중) 차이의 최대값. 출력 마지막 줄: FREQ_MAX <값> <노드>"""
import gzip, json, sys
import numpy as np
def load(p):
    f = gzip.open(p, 'rt') if p.endswith('.gz') else open(p)
    return {'|'.join(d['line']): d for d in map(json.loads, f)}
A, B = load(sys.argv[1]), load(sys.argv[2]); th = float(sys.argv[3]) if len(sys.argv) > 3 else 0.005
worst, wl, rows = 0.0, '', []
for l, b in B.items():
    a = A.get(l)
    if a is None or b['reach_prob'] < th or a['actions'] != b['actions']:
        continue
    fa = [float((np.array(a['actor_reach']) / max(sum(a['actor_reach']), 1e-12) * np.array(s)).sum()) for s in a['sigma']]
    fb = [float((np.array(b['actor_reach']) / max(sum(b['actor_reach']), 1e-12) * np.array(s)).sum()) for s in b['sigma']]
    d = max(abs(x - y) for x, y in zip(fa, fb))
    rows.append((d, l, b['reach_prob']))
    if d > worst:
        worst, wl = d, l
rows.sort(reverse=True)
for d, l, r in rows[:8]:
    print('%.3f reach %.3f %s' % (d, r, l[-90:]))
print('FREQ_MAX %.4f %s' % (worst, wl[-80:]))
