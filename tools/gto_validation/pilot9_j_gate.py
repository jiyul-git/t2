#!/usr/bin/env python3
"""Plan J gate A2: line-resolved manifest exports vs original T exports at the same checkpoint, exact (no tolerance).
Every top-level field must be equal except t2_cont_file (the manifest path string)."""
import glob
import hashlib
import json
import os

R = '/home/user/gto_ckpt/step3/'
OUT = '/home/user/t2/data/gto_validation/pilot9/step3/'
res = {'schema': 'pilot9_j_gate_v1', 'compared': 0, 'diffs': [], 'ignored_fields': ['t2_cont_file']}
names = sorted(os.path.basename(f)[7:-5] for f in glob.glob(R + 't3/T/export_*.json'))
for n in names:
    a = json.load(open(R + f't3/T/export_{n}.json'))
    fb = R + f'j/gate/export_{n}.json'
    if not os.path.exists(fb):
        res['diffs'].append(f'{n}: missing gate export')
        continue
    b = json.load(open(fb))
    keys = set(a) | set(b)
    for k in sorted(keys - {'t2_cont_file'}):
        if a.get(k) != b.get(k):
            res['diffs'].append(f'{n}: field {k} differs')
    res['compared'] += 1
res['n_paths'] = len(names)
res['pass'] = not res['diffs'] and res['compared'] == 33
res['manifest_sha256'] = hashlib.sha256(open(R + 'j/mr2_resolved/manifest.json', 'rb').read()).hexdigest()
json.dump(res, open(OUT + 'j_gate.json', 'w'), indent=1)
print(json.dumps({k: res[k] for k in ('compared', 'n_paths', 'pass')}), res['diffs'][:10])
