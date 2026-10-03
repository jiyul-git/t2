#!/usr/bin/env python3
"""Build t2_hu_continuation tables for the 4 pilot nodes.   pilot9_tables.py legacy <export_dir> <out_dir>
legacy: gross = the exported legacy_gross of each live seat at the terminal (static payoff at the export's profile)."""
import json
import os
import sys

NODES = {'btn': 24, 'co': 73, 'hj': 242, 'utg': 24726}


def main():
    mode, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    assert mode == 'legacy'
    os.makedirs(out, exist_ok=True)
    files = []
    for n, node in NODES.items():
        t = json.load(open(os.path.join(src, f'legacy_{n}.json')))
        assert t['terminal_node'] == node, (n, t['terminal_node'])
        tab = {'schema': 't2_hu_continuation_table_v1', 'node': node, 'live': t['terminal_live_mask'], 'pot_bb': t['pot_bb'],
               'value_convention': 'gross_share', 'zero_reach_definition': 'eps_tremble_avg',
               'seats': [{'seat': p['seat'], 'position': p['position'], 'gross': p['legacy_gross']} for p in t['players']],
               'provenance': {'kind': 'C1a static payoff frozen at the 100-iteration profile', 'source': f'legacy_{n}.json'}}
        json.dump(tab, open(os.path.join(out, f'node{node}.json'), 'w'))
        files.append({'file': f'node{node}.json'})
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': files}, open(os.path.join(out, 'manifest.json'), 'w'))


if __name__ == '__main__':
    main()
