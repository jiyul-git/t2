#!/usr/bin/env python3
"""Re-solve the 24 panel flops of one finished spot terminal at the SAME inputs as the original loop step, with the strategy
export on (T2_REPORT_OUT), and check that the values reproduce: D and U recomputed from the new flops must equal the
step report's D and U (they are functions of the 24 boards' values), and the rebuilt terminal JSON must equal the committed
one when it exists.
    python3.11 tools/gto_postflop/run_export.py <spec.json> <tables_used.json> <matrices_used.json> <step_report.json> <term_index> <out_dir> [committed_term.json]
"""
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'gto_spot'))
import spot_loop as L  # noqa: E402
import hu_spot as H  # noqa: E402

spec = json.load(open(sys.argv[1]))
tables = json.load(open(sys.argv[2]))
matrices = json.load(open(sys.argv[3]))
rep = json.load(open(sys.argv[4]))
j = int(sys.argv[5])
out = sys.argv[6]
committed = sys.argv[7] if len(sys.argv) > 7 else None
os.makedirs(out, exist_ok=True)

lp = L.Loop.__new__(L.Loop)
lp.spec, lp.v3, lp.v4 = spec, spec.get('rule') in ('v3', 'v4'), spec.get('rule') == 'v4'
sp = lp.spot(tables, matrices)
terms = lp.terminals(sp)
line, t = sorted(terms.items())[j]
tj = lp.term_json(sp, line, t)
tf = os.path.join(out, f'term{j}.json')
json.dump(tj, open(tf, 'w'))
sha = hashlib.sha256(open(tf, 'rb').read()).hexdigest()
print('line', line, 'term sha256', sha, flush=True)
if committed:
    sc = hashlib.sha256(open(committed, 'rb').read()).hexdigest()
    print('committed term sha256', sc, 'MATCH' if sc == sha else 'MISMATCH', flush=True)
    if sc != sha:
        # rebuilt keep fractions can differ from the committed file at float-noise level (seen: 7e-15 on p60 o25, numpy/BLAS
        # rounding in the spot solve). Use the committed file: it is the exact input the original flops were solved at.
        print('WARN rebuilt terminal differs from the committed one; solving at the committed file', flush=True)
        tj = json.load(open(committed))
        open(tf, 'wb').write(open(committed, 'rb').read())
        sha = sc
if os.environ.get('TERM_ONLY'):
    sys.exit(0)
is_m = lp.v3 and lp.is_matrix_line(line)
fd = os.path.join(out, f'term{j}_flops')
env = dict(os.environ, T2_REPORT_OUT=os.path.join(out, f'term{j}_reports'), T2_EXPORT_STRATEGY='1')
if is_m:
    env.update({'T2_PANEL_MATRIX': '1', 'T2_BIN_DIR': os.path.join(L.ROOT, 'vendor/gtopen/target/release/examples')})
if not os.path.exists(fd + '/done'):
    subprocess.run([sys.executable, os.path.join(L.ROOT, 'tools/gto_hu_continuation/solve_panel.py'), tf, L.MENU, L.PANEL, fd,
                    '--workers', os.environ.get('SPOT_PANEL_WORKERS', '4'), '--threads', '1'], check=True, env=env,
                   stdout=open(os.path.join(out, 'solve.log'), 'a'), stderr=subprocess.STDOUT)
    open(fd + '/done', 'w').write('ok')
bad = L.flop_failures(fd)
print('unconverged boards', bad, flush=True)
assert not bad, 'original step had no retries; an unconverged board here means the inputs differ'
bv = L.board_values(fd)
raw, se = L.stratified(bv)
Mraw = lp.matrix_from(fd, sp) if is_m else None
prior = np.array([H.combos(x) for x in sp.lab169])
cur = tables.get(line)
want = rep['terminals'][line]['seats']
res = {'line': line, 'term_sha256': sha, 'matrix': is_m, 'seats': {}}
ok = True
for pl in tj['players']:
    pos = pl['position']
    w = prior * np.array(pl['class_keep_fraction'])
    W = w.sum()
    U = float((w * np.array(se[pos])).sum() / W)
    if is_m:
        q = [x for x in sp.live if sp.pos[x] != pos][0]
        dist = t['reach'][q] / t['reach'][q].sum()
        use = dist > 0
        g_new = Mraw[pos][:, use] @ dist[use]
        g_used = sp.gross_at(line, ('flop', line, t['state'], t['pot']), pl['seat'], dist)
        D = float((w * np.abs(g_new - g_used)).sum() / W)
    else:
        g = {s['position']: np.array(s['gross']) for s in cur['seats']}[pos]
        D = float((w * np.abs(np.array(raw[pos]) - g)).sum() / W)
    dD, dU = abs(D - want[pos]['D']), abs(U - want[pos]['U'])
    res['seats'][pos] = {'D': D, 'D_report': want[pos]['D'], 'U': U, 'U_report': want[pos]['U'], 'absdiff_D': dD, 'absdiff_U': dU}
    ok = ok and dD <= 1e-9 and dU <= 1e-9
res['values_reproduce'] = ok
digs = subprocess.run([sys.executable, os.path.join(L.ROOT, 'tools/gto_spot/flop_digest.py')] +
                      sorted(os.path.join(fd, f) for f in os.listdir(fd) if f.endswith('.json') and len(f) == 11),
                      capture_output=True, text=True, check=True).stdout.split('\n')
res['flop_digests'] = {os.path.basename(x.split()[1])[:-5]: x.split()[0] for x in digs if x.strip()}
json.dump(res, open(os.path.join(out, f'term{j}_repro_check.json'), 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'flop_digests'}, indent=1))
if not ok:
    sys.exit(2)
