#!/usr/bin/env python3
"""Six-flop pilot panel for one HU terminal: the fixed panel_sub6_v1 boards and texture
weights, plus a class-independent fixed normaliser per player computed from THIS terminal's
arriving ranges (the J1/J2 rule): norm_p = sum_f w_f sum_h r_ph c_hf.

    python3 tools/gto_hu_continuation/make_pilot_panel.py <terminal.json> <out_panel.json>

The normaliser depends only on the ranges and the board blockers, so it is fixed before
any flop of the terminal is solved.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import class_combos, parse_board  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    term = json.load(open(sys.argv[1]))
    base = json.load(open(os.path.join(ROOT, 'data/gto_hu_continuation/panel_sub6_v1.json')))
    assert term['live_count'] == 2
    combos = [class_combos(l) for l in term['class_labels']]
    norm = {}
    for pl in term['players']:
        r = pl['class_reach_normalized']
        tot = 0.0
        for f in base['panel']:
            bc = parse_board(f['board'])
            c = [sum(1 for x in cc if x[0] not in bc and x[1] not in bc) / len(cc) for cc in combos]
            tot += f['weight'] * sum(r[h] * c[h] for h in range(169))
        norm[pl['position']] = tot
    out = {k: v for k, v in base.items() if k not in ('fixed_normaliser', 'fixed_normaliser_note', 'panel_hash_sha256', 'purpose', 'id')}
    out.update({'id': f"pilot6_node{term['terminal_node']}", 'parent_panel': base['id'], 'parent_panel_hash_sha256': base['panel_hash_sha256'],
                'terminal_node': term['terminal_node'], 'terminal_ranges_hash': term['ranges_hash_fnv1a64'],
                'fixed_normaliser': norm,
                'fixed_normaliser_note': 'sum_f w_f sum_h r_h c_hf at this terminal\'s arriving ranges (J1/J2 rule), fixed before any solve',
                'purpose': 'T2 six-flop solved-vs-legacy impact pilot'})
    key = json.dumps({'panel': base['panel'], 'norm': norm, 'terminal': term['terminal_node'], 'ranges': term['ranges_hash_fnv1a64']}, sort_keys=True)
    out['panel_hash_sha256'] = hashlib.sha256(key.encode()).hexdigest()
    json.dump(out, open(sys.argv[2], 'w'), indent=1)
    print(sys.argv[2], {k: round(v, 4) for k, v in norm.items()}, out['panel_hash_sha256'][:12])


if __name__ == '__main__':
    main()
