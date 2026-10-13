#!/usr/bin/env python3
"""Reproduction reference for a Plan A spot: step-0 spot solve (no tables / matrices), its terminal j JSON, and one flop of that
terminal solved alone (T2_PANEL_BOARDS), exactly as spot_loop.py step 0 does it. Prints sha256 of the terminal JSON and the
flop_digest of the flop artifact.
    python3 tools/gto_spot/plan_a_repro_step0.py <spec.json> <j> <board> <out_dir>"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spot_loop as L  # noqa: E402

spec = json.load(open(sys.argv[1]))
j, board, out = int(sys.argv[2]), sys.argv[3], sys.argv[4]
os.makedirs(out + '/flops/logs', exist_ok=True)
lp = L.Loop.__new__(L.Loop)
lp.spec, lp.v3 = spec, spec.get('rule') == 'v3'
sp = lp.spot({}, {})
terms = lp.terminals(sp)
line, t = sorted(terms.items())[j]
tj = lp.term_json(sp, line, t)
tf = os.path.join(out, f'term{j}.json')
json.dump(tj, open(tf, 'w'))
env = dict(os.environ, T2_PANEL_BOARDS=board, RAYON_NUM_THREADS='1')
if lp.v3 and lp.is_matrix_line(line):
    env['T2_PANEL_MATRIX'] = '1'
binp = os.path.join(L.ROOT, 'vendor/gtopen/target/release/examples/t2_cont_panel')
subprocess.run([binp, tf, L.MENU, L.PANEL, out + '/flops', '1000', '0.3', '25'], env=env, check=True, stdout=open(out + '/flops/logs/' + board + '.log', 'w'),
               stderr=subprocess.STDOUT)
print('line', line)
print('term_sha256', hashlib.sha256(open(tf, 'rb').read()).hexdigest(), tf)
subprocess.run([sys.executable, os.path.join(HERE, 'flop_digest.py'), os.path.join(out, 'flops', board + '.json')], check=True)
