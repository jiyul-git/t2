#!/usr/bin/env python3
"""`quick` preflop chart from a Plan A parent full-tree dump (user decision 2026-10-19: RFI, BB defence, 3-bet response first).

Exports, per node, the parent average strategy (sigma) and action EVs per class for the heads-up-relevant decisions:
  rfi        everyone before the actor folded
  vs_open    exactly one open (Raise / Limp) and everyone else before the actor folded (cold call / 3-bet / fold, incl. BB defence)
  vs_3bet    the opener facing one 3-bet with everyone else folded (the static-continuation answer; HU spots refine some pairs,
             see data/gto_spot/quick/<spot>.json, which take precedence)
Multiway lines (a caller before the actor) are not exported. Status `quick`, symmetric-stack assumption, parent static continuation.

    python3 tools/gto_spot/export_parent_chart.py <dump.jsonl> <cfg.json> <bucket_label> <parent_gap_bb> <out.json>
"""
import json
import sys

def lab169():
    """engine class order (same as hu_spot.Spot.class_labels): ranks 2..A, row i / column j, j > i offsuit, j < i suited"""
    ranks = '23456789TJQKA'
    out = []
    for i in range(13):
        for j in range(13):
            hi, lo = max(i, j), min(i, j)
            out.append(ranks[i] * 2 if i == j else ranks[hi] + ranks[lo] + ('o' if j > i else 's'))
    return out


def kind(line, actor):
    acts = [t.split(':', 1) for t in line]
    aggr = [(p, a) for p, a in acts if not a.startswith('Fold')]
    if not aggr:
        return 'rfi'
    if len(aggr) == 1 and (aggr[0][1].startswith('Raise') or aggr[0][1].startswith('Limp')):
        return 'vs_open'
    if (len(aggr) == 2 and aggr[0][1].startswith('Raise') and aggr[1][1].startswith('3-bet') and aggr[0][0] == actor):
        return 'vs_3bet'
    return None


def main():
    dump, cfgf, bucket, gap, outf = sys.argv[1:6]
    cfg = json.load(open(cfgf))
    L = None
    nodes = []
    for line in open(dump):
        d = json.loads(line)
        k = kind(d['line'], d['actor'])
        if k is None:
            continue
        if L is None:
            L = lab169() if len(d['sigma'][0]) == 169 else None
            assert L is not None
        reach = d['actor_reach']
        hands = {}
        for h, lab in enumerate(L):
            c = reach[h] * 1326   # actor_reach is the class probability (combos / 1326 at the root): arriving combos = reach x 1326
            if c < 1e-3:
                continue
            hands[lab] = {'combos': round(c, 3),
                          'freq': {a: round(d['sigma'][i][h], 4) for i, a in enumerate(d['actions'])},
                          'ev_bb': {a: round(d['ev'][i][h], 3) for i, a in enumerate(d['actions'])}}
        tot = sum(x['combos'] for x in hands.values())
        mix = {a: round(sum(x['combos'] * x['freq'][a] for x in hands.values()) / tot, 4) for a in d['actions']} if tot > 0 else None
        nodes.append({'kind': k, 'line': d['line'], 'path': d['path'], 'actor': d['actor'], 'actions': d['actions'],
                      'reach_combos': round(tot, 2), 'mix': mix, 'hands': hands})
    rec = {'schema': 'parent_chart_quick_v1', 'bucket': bucket, 'status': 'quick', 'db_promotion': 'forbidden',
           'source': dump, 'cfg': cfgf, 'parent_gap_exact_bb': float(gap),
           'tree': cfg.get('label') or cfg.get('tree_label'),
           'stack_assumption': 'symmetric stacks (all seats at the bucket stack); lookup by effective stack',
           'continuation': 'parent static continuation (no HU re-solve); vs_3bet nodes are overridden by data/gto_spot/quick/<spot>.json where present',
           'decision': 'user 2026-10-19: fill fast first (RFI / BB defence / 3-bet response), refine later',
           'counts': {k: sum(n['kind'] == k for n in nodes) for k in ('rfi', 'vs_open', 'vs_3bet')},
           'nodes': nodes}
    json.dump(rec, open(outf, 'w'))
    print(bucket, rec['counts'])
    for n in nodes:
        if n['kind'] == 'rfi':
            print('  RFI', n['actor'], n['mix'])


if __name__ == '__main__':
    main()
