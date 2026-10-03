#!/usr/bin/env python3
"""B6 integration: same-state attribution of the river new-card effect change.

At every texture.new_card_effect call during the sealed baseline sim, also
compute the retired river variant (flop only vs river card, turn ignored) on the
identical arguments.  No RNG is consumed; the printed digest must equal the plain
sim digest of the same tree.

  OUT=attr.json python tools/b6_integration_attribution.py SEED [CAP]
"""
import sys, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import texture as TX

REC = []
_n = TX.new_card_effect


def nce(prior_board, new_card, aggressor_range_high=True):
    new = _n(prior_board, new_card, aggressor_range_high)
    if len(prior_board) == 4:
        old = _n(prior_board[:3], new_card, aggressor_range_high)
        REC.append({'new': round(new, 4), 'old': round(old, 4)})
    return new
TX.new_card_effect = nce

sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
SIM.main()
out = os.environ.get('OUT')
if out:
    json.dump(REC, open(out, 'w'))
ch = [x for x in REC if abs(x['new'] - x['old']) > 1e-9]
print(json.dumps({'river_calls': len(REC), 'changed': len(ch),
                  'mean_abs_delta': round(sum(abs(x['new'] - x['old']) for x in ch) / max(1, len(ch)), 4)}))
