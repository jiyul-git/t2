#!/usr/bin/env python3
"""R2-B: compare current defend output with the external reference chart summary.

Read-only.  Inputs: the reference summary JSON written by tools/r2_reference_charts.py.
For each reference vs-open node and stack, the code is evaluated at
  8-max + 1bb BBA  (the condition the reference is closest to), and
  9-max + 1bb BBA  (production standard/main/lowbuyin; reference only, mismatch flagged)
with the max-skill neutral profile, the code's own open size, no callers, raise_level=1.

Position mapping of the reference names is an assumption (the source does not
define EP/MP):  EP -> UTG+1, MP -> LJ.  The same names are used in 9-max, where the
number of seats behind differs; those rows are labelled REFERENCE_ONLY.

Reported per row: reference defend/3bet/call/fold, code prior (L0) and realized (L2)
defend/3bet/call/fold, differences (code - reference) and 3bet share.

Usage: python tools/r2_compare_defend_reference.py <ref_summary.json> [out.json]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import gto as G  # noqa: E402
from r2_freeze_defend_baseline import maxskill, open_size, realized  # noqa: E402

MAP = {'EP': 'UTG+1', 'MP': 'LJ', 'BTN': 'BTN', 'SB': 'SB', 'BB': 'BB'}


def main():
    ref = json.load(open(sys.argv[1]))
    out = sys.argv[2] if len(sys.argv) > 2 else None
    prof = maxskill()
    rows = []
    for key, v in ref['vs_open'].items():
        st, node = key.split('|')
        if '-vs-' not in node or 'open-vs' in node:
            continue
        bb = int(st[:-2])
        if bb < 15:
            continue
        o, d = node.split('-vs-')
        op, dp = MAP[o], MAP[d]
        for seats in (8, 9):
            ob = open_size(prof, op, bb)
            tot0 = G.defend_pct(dp, op, seats, bb, True, ob)
            tp0 = G.threebet_pct(dp, op, seats, bb, True, ob)
            a, c, f, hot = realized(prof, dp, op, bb, ob, seats)
            rows.append({
                'stack_bb': bb, 'ref_node': node, 'opener': op, 'defender': dp,
                'seats': seats, 'open_bb': ob,
                'condition': ('8-max ante; open size/ante size of reference unknown'
                              if seats == 8 else
                              'REFERENCE_ONLY: 9-max code vs 8-max chart (position-name mapping)'),
                'path': 'mtt8_calibrated' if G._use_mtt8_ante_defense(dp, seats, True)
                        else 'legacy_formula',
                'ref_defend': v['defend'], 'ref_3bet': v['3bet'], 'ref_call': v['call'],
                'ref_fold': v['fold'], 'ref_3bet_share': v['3bet_share'],
                'L0_defend': round(tot0, 4), 'L0_3bet': round(tp0, 4),
                'L2_defend': round(a + c, 4), 'L2_3bet': round(a, 4),
                'L2_call': round(c, 4), 'L2_fold': round(f, 4),
                'L2_3bet_share': round(a / (a + c), 4) if a + c else None,
                'diff_L0_defend': round(tot0 - v['defend'], 4),
                'diff_L2_defend': round(a + c - v['defend'], 4),
                'diff_L2_3bet': round(a - v['3bet'], 4),
                'diff_L2_call': round(c - v['call'], 4),
            })
    res = {'reference': ref.get('source'), 'reference_commit': ref.get('source_commit'),
           'mapping': MAP, 'rows': rows}
    if out:
        open(out, 'w').write(json.dumps(res, indent=1) + '\n')
    for r in rows:
        print(r['stack_bb'], r['ref_node'], r['seats'], r['path'][:6],
              'ref %.2f/%.2f/%.2f' % (r['ref_defend'], r['ref_3bet'], r['ref_call']),
              'L0 %.2f/%.2f' % (r['L0_defend'], r['L0_3bet']),
              'L2 %.2f/%.2f/%.2f' % (r['L2_defend'], r['L2_3bet'], r['L2_call']),
              'dDef %+.2f' % r['diff_L2_defend'])


if __name__ == '__main__':
    main()
