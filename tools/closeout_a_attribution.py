#!/usr/bin/env python3
"""Stage 9 B1/B2 closeout (group A) attribution: fallback preflop ordering.

At every bot.range_combos call during the sealed baseline sim, also build the
retired `_pf_score` fallback (reference formula reproduced here) on the identical
arguments and record how different the two combo sets are.  No RNG consumed; the
printed digest must equal the plain sim digest of the same tree.

A1 (recency window) and A2 (3bet trait input) are inert in this harness: the
baseline keeps the read book empty (exploit neutral) and every profile has
pf_defend == bluff == 10.  Their evidence is in the verifiers / field check.

  OUT=attr.json python tools/closeout_a_attribution.py SEED [CAP]
"""
import sys, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import bot


def _old_score(c1, c2):
    a, b = sorted([bot.RV[c1[0]], bot.RV[c2[0]]], reverse=True)
    s = a*2 + b
    if a == b: s += 22
    if c1[1] == c2[1]: s += 4
    gap = a - b
    if 0 < gap <= 4: s += (5 - gap)
    return s


_OLD = sorted(bot._ALLCOMBOS, key=lambda t: -_old_score(*t))
REC = {}
_rc = bot.range_combos


def rc(pct, dead):
    new = _rc(pct, dead)
    n = int(len(_OLD)*pct)
    old = [c for c in _OLD[:n] if c[0] not in dead and c[1] not in dead]
    k = round(float(pct), 4)
    a, b = set(new), set(old)
    e = REC.setdefault(k, {'calls': 0, 'jaccard_sum': 0.0, 'new_n': 0, 'old_n': 0})
    e['calls'] += 1
    e['jaccard_sum'] += len(a & b) / max(1, len(a | b))
    e['new_n'] += len(a); e['old_n'] += len(b)
    return new
bot.range_combos = rc

sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
SIM.main()
summ = {k: {'calls': v['calls'], 'mean_jaccard': round(v['jaccard_sum']/v['calls'], 4),
            'mean_new_n': round(v['new_n']/v['calls'], 1), 'mean_old_n': round(v['old_n']/v['calls'], 1)}
        for k, v in sorted(REC.items())}
out = os.environ.get('OUT')
if out:
    json.dump(summ, open(out, 'w'))
print(json.dumps(summ))
