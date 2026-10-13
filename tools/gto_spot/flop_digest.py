#!/usr/bin/env python3
"""sha256 of the deterministic content of a flop artifact (t2_cont_panel output), for bit-level reproduction checks across machines.
Excluded: cost (timings, RSS), matrix.ms (matrix-pass timing) and solver_commit (the build's git commit). Included: players, matrix, trace, exploitability_pct_pot,
invariant, iterations, converged, provenance_key, board, schema.
    python3 tools/gto_spot/flop_digest.py <flop.json>..."""
import hashlib
import json
import sys

KEYS = ('board', 'schema', 'players', 'matrix', 'trace', 'exploitability_pct_pot', 'invariant', 'iterations', 'converged', 'provenance_key')

for p in sys.argv[1:]:
    d = json.load(open(p))
    c = {k: d.get(k) for k in KEYS}
    if isinstance(c.get('matrix'), dict):
        c['matrix'] = {k: v for k, v in c['matrix'].items() if k != 'ms'}
    blob = json.dumps(c, sort_keys=True, separators=(',', ':')).encode()
    print(hashlib.sha256(blob).hexdigest(), p)
