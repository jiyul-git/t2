#!/usr/bin/env python3
"""E1 flop artifact check for one step: parse, panel_v4 board, ranges hash = this step's R_k terminal, panel hash, one provenance key,
converged <= 0.300% pot. Bad / truncated files are quarantined (kept); capped non-converged boards stay in place and are listed for a
user decision (no exception is inherited from A4c).   python3 tools/gto_hu_continuation/e1_flops_verify.py <step>"""
import json
import os
import sys
import time

E = 'data/gto_terminal_expansion/'
k = int(sys.argv[1])
TERM = {n: E + f'e1/step{k}/R/terminal_node{n}.json' for n in (6, 28)}
tot = {}
for n in (6, 28):
    p = json.load(open(f'data/gto_hu_continuation/panel_v4_node{n}.json'))
    boards = [f['board'] for f in p['panel']]
    term = json.load(open(TERM[n]))
    d = E + f'e1/step{k}/node{n}/flops/'
    os.makedirs(d, exist_ok=True)
    keys, ok, bad, capped = {}, 0, [], []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.json'):
            continue
        b, why = f[:-5], None
        try:
            a = json.load(open(d + f))
            kk = a['provenance_key']
            if b not in boards or a.get('board') != b:
                why = 'not a panel board'
            elif kk['ranges_hash_fnv1a64'] != term['ranges_hash_fnv1a64']:
                why = 'ranges hash != step terminal'
            elif kk['panel_hash_sha256'] != p['panel_hash_sha256']:
                why = 'panel hash'
            elif not (a['converged'] is True and a['exploitability_pct_pot'] <= 0.3):
                if a['iterations'] >= kk['max_iters']:
                    capped.append({'board': b, 'exploitability_pct_pot': a['exploitability_pct_pot']})
                    continue
                why = 'not converged'
            else:
                keys.setdefault(json.dumps(kk, sort_keys=True), []).append(b)
        except Exception as e:
            why = f'unparsable: {type(e).__name__}'
        if why:
            os.makedirs(d + 'quarantine/', exist_ok=True)
            os.replace(d + f, d + f'quarantine/{b}.{int(time.time())}.json')
            bad.append((b, why))
        else:
            ok += 1
    if len(keys) > 1:
        sys.exit(f'node {n}: {len(keys)} provenance-key variants')
    tot[n] = {'ok': ok, 'of': len(boards), 'quarantined': bad, 'capped_pending_user': capped}
print(json.dumps({'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'step': k, 'verify': tot}))
