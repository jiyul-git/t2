# -*- coding: utf-8 -*-
"""2번 — made == 0 을 고정하고 delta_eq 가 기존 변수의 재표현인지 본다.

eq_decomp.json(계산 결과) + hand_archive2_alt.jsonl(기존 변수) 조인.
구간을 자르지 않는다. 연속값 그대로 본다.
표본이 얕으므로 p-value 로 결론내지 않는다.
"""
import sys, os, json, statistics as st
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

D = os.path.dirname(os.path.abspath(__file__))
dec = json.load(open(os.path.join(D, 'eq_decomp.json')))

# 기존 변수 조인 — (hole, board, n_opp) 키
extra = {}
NB = {'flop': 3, 'turn': 4, 'river': 5}
for ln in open(os.path.join(D, 'hand_archive2_alt.jsonl')):
    r = json.loads(ln)
    for it in r.get('intents', []):
        if it.get('made') is None or it['street'] not in NB:
            continue
        hero = r['hole'].get(str(it['seat']))
        if not hero:
            continue
        k = (tuple(hero), tuple(r['board'][:NB[it['street']]]), it['n_opp'])
        extra.setdefault(k, dict(
            nadv=it['nut_adv'], radv=it['range_adv'], blk=it.get('blocker'),
            danger=it['danger'], init=bool(it['init']), behind=it.get('behind'),
            spr=it.get('spr')))

R = []
for x in dec:
    k = (tuple(x['hole']), tuple(x['board']), x['n_opp'])
    e = extra.get(k)
    if not e:
        continue
    y = dict(x); y.update(e); R.append(y)

M0 = [x for x in R if x['made'] == 0]
M0D = [x for x in M0 if x['outs'] > 0]
print('made == 0 전체 %d건  (그중 outs>0 %d건)' % (len(M0), len(M0D)))


def rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i])
    rk = [0.0]*len(v)
    i = 0
    while i < len(s):
        j = i
        while j+1 < len(s) and v[s[j+1]] == v[s[i]]:
            j += 1
        avg = (i+j)/2.0 + 1
        for t in range(i, j+1):
            rk[s[t]] = avg
        i = j+1
    return rk


def corr(a, b):
    n = len(a)
    if n < 3: return None
    ma, mb = sum(a)/n, sum(b)/n
    va = sum((x-ma)**2 for x in a); vb = sum((x-mb)**2 for x in b)
    if va == 0 or vb == 0: return None
    return sum((a[i]-ma)*(b[i]-mb) for i in range(n)) / (va*vb)**0.5


def report(lab, g):
    print('\n### %s  (n=%d)' % (lab, len(g)))
    d = [x['d'] for x in g]
    print('  delta_eq  중앙 %+.3f  범위 %+.3f ~ %+.3f' % (st.median(d), min(d), max(d)))
    print('  %-12s %-10s %-10s' % ('변수', 'Pearson', 'Spearman'))
    for f in ('rel', 'outs', 'cur', 'eq_rec', 'nadv', 'radv', 'blk', 'danger'):
        v = [x[f] for x in g]
        p = corr(d, v)
        s = corr(rank(d), rank(v))
        if p is None:
            print('  %-12s (상수)' % f); continue
        print('  %-12s %+-10.2f %+-10.2f' % (f, p, s))


report('made == 0 전체', M0)
report('made == 0 ∧ outs > 0', M0D)

print('\n\n### delta_eq ↔ 현재 plan  (made == 0)')
g = defaultdict(list)
for x in M0:
    g[x['plan']].append(x)
print('%-15s %-5s %-10s %-18s %-10s %s'
      % ('plan', 'n', 'delta중앙', 'delta범위', 'outs중앙', 'rel중앙'))
for p in sorted(g, key=lambda k: -st.median([y['d'] for y in g[k]])):
    v = g[p]
    d = [y['d'] for y in v]
    print('%-15s %-5d %+-10.3f %+.3f ~ %+.3f   %-10.1f %.2f'
          % (p, len(v), st.median(d), min(d), max(d),
             st.median([y['outs'] for y in v]),
             st.median([y['rel'] for y in v])))

print('\n\n### outs 를 고정했을 때 delta_eq 의 잔여 변동 (made==0)')
byo = defaultdict(list)
for x in M0D:
    byo[x['outs']].append(x)
print('%-6s %-5s %-20s %-8s %s' % ('outs', 'n', 'delta 범위', '폭', '같은 outs 안의 건'))
for o in sorted(byo):
    v = byo[o]
    d = [y['d'] for y in v]
    if len(v) < 2:
        print('%-6s %-5d %+.3f              -        %s'
              % (o, len(v), d[0], '%s %s' % (v[0]['h'], ''.join(v[0]['hole']))))
        continue
    print('%-6s %-5d %+.3f ~ %+.3f     %-8.3f %s'
          % (o, len(v), min(d), max(d), max(d)-min(d),
             ', '.join('h%s %s(%+.2f)' % (y['h'], ''.join(y['hole']), y['d'])
                       for y in sorted(v, key=lambda z: -z['d']))))

print('\n\n### outs=9 만: 기존 신호가 delta 차이를 설명하는가 (made==0)')
n9 = [x for x in M0D if x['outs'] == 9]
print('%-4s %-6s %-5s %-11s %-8s %-7s %-7s %-7s %-7s %-7s %s'
      % ('h', 'street', 'hole', 'board', 'delta', 'rel', 'nadv', 'radv',
         'blk', 'danger', 'plan'))
for x in sorted(n9, key=lambda y: -y['d']):
    print('%-4s %-6s %-5s %-11s %+-8.3f %-7.2f %-7.2f %-7.2f %-7.2f %-7.2f %s'
          % (x['h'], x['street'], ''.join(x['hole']), ''.join(x['board']),
             x['d'], x['rel'], x['nadv'], x['radv'], x['blk'], x['danger'],
             x['plan']))
