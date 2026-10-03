#!/usr/bin/env python3
"""Beta A #1: same-state attribution of the odd-size probability rewiring.

At every persona.shape_size call in the max-skill baseline sim, the retired rule
(label table SIZING_FAMILY_SIG['odd']) is evaluated on a clone of the same RNG
state.  The real call consumes the RNG exactly as before, so the printed digest
must equal the plain sim digest of the current tree.

  OUT=attr.json python tools/fix1_attribution.py SEED [CAP]
"""
import collections, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import persona as PS

C = collections.Counter()
EX = []
_ss = PS.shape_size


def shape_size(amount, ptype, rng, pot=None, odd=None):
    clone = random.Random(); clone.setstate(rng.getstate())
    old = _ss(amount, ptype, clone, pot=pot, odd=None)
    new = _ss(amount, ptype, rng, pot=pot, odd=odd)
    C['calls'] += 1
    C['with_pot'] += bool(pot)
    if old != new:
        C['diff'] += 1
        if len(EX) < 20:
            EX.append({'amount': amount, 'pot': pot, 'old': old, 'new': new, 'odd': odd})
    return new


PS.shape_size = shape_size
sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
try:
    SIM.main()
finally:
    if os.environ.get('OUT'):
        json.dump({'counts': dict(C), 'examples': EX}, open(os.environ['OUT'], 'w'), indent=1)
    print(json.dumps(dict(C), sort_keys=True))
