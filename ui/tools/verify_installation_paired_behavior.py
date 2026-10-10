#!/usr/bin/env python3
"""Compare actual field actions/state against the exact production base."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
base = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
env = {k:v for k,v in os.environ.items() if not k.startswith(('T2_', 'PYTHON'))}
env['PYTHONHASHSEED'] = '0'
for mode in ('0', '1'):
    for seed in (11, 12):
        records = []
        for label, root in [('base', base), ('fixed', ROOT)]:
            path = out/('%s_%s_%s.json' % (label, mode, seed))
            args = [sys.executable,'tools/r2_baseline_sim.py',str(seed),'8',str(path)]
            child = dict(env)
            if mode == '1':
                child['T2_RANGE_CONDITIONAL_V1'] = '1'
            r = subprocess.run(args, cwd=root, env=child, capture_output=True,text=True,timeout=180)
            (out/('%s_%s_%s.log' % (label,mode,seed))).write_text(r.stdout+r.stderr)
            assert r.returncode == 0, r.stdout+r.stderr
            records.append(json.loads(path.read_text()))
        assert records[0] == records[1], (mode, seed, 'behavior changed')
        print(json.dumps(dict(mode=('default_OFF' if mode=='0' else 'ON'),seed=seed,
                             decisions=len(records[0]['pf']), hands=len(records[0]['hands']),
                             full_record_equal=True)))
print('PASS exact production paired behavior/state; no claim of strategic optimality')
