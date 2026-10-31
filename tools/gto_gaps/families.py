#!/usr/bin/env python3
"""rank_gaps.py 결과 → 계산 단위(가족)별 묶음. python3 tools/gto_gaps/families.py <rank_json>"""
import json, sys
from collections import Counter, defaultdict
d = json.load(open(sys.argv[1]))
H = d['hands']
fam = Counter(); top = defaultdict(list)
for r in d['rows']:
    sit, bk, pk = r['situation'], r['bucket'], r['pair']
    me = pk.split('>')[-1]
    who = 'BB' if me == 'BB' else 'SB' if me == 'SB' else 'other'
    if sit == 'vs_open':
        f = 'vs_open|%s|%s' % (bk, who)
    elif sit == 'first_in':
        f = 'first_in|%s|%s' % (bk, 'SB' if me == 'SB' else 'non-SB')
    elif sit == 'vs_3bet':
        three = pk.split('>')[0]
        f = 'vs_3bet|%s|by_%s' % (bk, 'SB' if three == 'SB' else 'BB' if three == 'BB' else 'IP')
    else:
        f = '%s|%s' % (sit, bk)
    fam[f] += r['gap']
    top[f].append(r)
out = []
for f, g in fam.most_common():
    if g <= 0:
        continue
    rs = sorted(top[f], key=lambda r: -r['gap'])
    out.append({'family': f, 'gap': round(g, 1), 'per_1000_hands': round(1000 * g / H, 1),
                'n_pairs': sum(1 for r in rs if r['gap'] > 0),
                'top_pairs': [(r['pair'], round(1000 * r['gap'] / H, 1), r['sizes']) for r in rs[:6]]})
print(json.dumps({'hands': H, 'families': out}, ensure_ascii=False, indent=1))
