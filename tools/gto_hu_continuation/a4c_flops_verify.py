#!/usr/bin/env python3
"""A4c flop artifact check before/after each (re)launch: every present a4c/node{6,28}/flops/<board>.json must parse, belong to the
panel_v4 new-board list, carry the P14 ranges hash, the panel_v4 hash, one common provenance key (apart from the panel hash), and be
converged with exploitability <= 0.300% pot. Failing files are moved to flops/quarantine/ (kept, never deleted) so the resumable
driver re-solves only them. Prints counts; exit 0."""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
E = os.path.join(ROOT, 'data/gto_terminal_expansion/')
tot = {}
for n in (6, 28):
    p = json.load(open(os.path.join(ROOT, f'data/gto_hu_continuation/panel_v4_node{n}.json')))
    new = [f['board'] for f in p['panel'] if not f['in_panel_v3_144']]
    term = json.load(open(E + f'outer_m28_6/k14/terminal_node{n}.json'))
    d = E + f'a4c/node{n}/flops/'
    os.makedirs(d, exist_ok=True)
    keys, ok, bad = {}, 0, []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.json'):
            continue
        b, why = f[:-5], None
        try:
            a = json.load(open(d + f))
            k = a['provenance_key']
            if b not in new:
                why = 'not a panel_v4 new board'
            elif a.get('board') != b:
                why = 'board field mismatch'
            elif k['ranges_hash_fnv1a64'] != term['ranges_hash_fnv1a64']:
                why = 'ranges hash != P14'
            elif k['panel_hash_sha256'] != p['panel_hash_sha256']:
                why = 'panel hash != panel_v4'
            elif not (a['converged'] is True and a['exploitability_pct_pot'] <= 0.3):
                why = f"not converged ({a['exploitability_pct_pot']})"
            else:
                keys.setdefault(json.dumps({x: y for x, y in k.items() if x != 'panel_hash_sha256'}, sort_keys=True), []).append(b)
        except Exception as e:  # truncated / unparsable output
            why = f'unparsable: {type(e).__name__}'
        if why:
            q = d + 'quarantine/'
            os.makedirs(q, exist_ok=True)
            os.replace(d + f, q + f'{b}.{int(time.time())}.json')
            bad.append((b, why))
        else:
            ok += 1
    if len(keys) > 1:
        sys.exit(f'node {n}: {len(keys)} provenance-key variants among finished artifacts')
    tot[n] = {'ok': ok, 'of': len(new), 'quarantined': bad}
print(json.dumps({'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'verify': tot}))
