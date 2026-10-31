#!/usr/bin/env python3
"""Add the flop strategy file to boards solved before strategy export existed (coordinator / user request 2026-10-31).

    python3 tools/gto_precision/strategy_backfill.py <term.json> <menu.json> <panel.json> <flops_dir> [--workers N]

For every <board>.json in flops_dir without <board>.strategy.json: re-solve the board with the SAME inputs (terminal, menu, panel, iteration
budget, target, check interval, algorithm, matrix mode, all read from the artifact's provenance key) into a scratch dir with
T2_EXPORT_STRATEGY=1, then compare the deterministic content digest (tools/gto_spot/flop_digest.py rule) with the stored artifact.
Equal -> the strategy file is moved in; the stored artifact is left untouched. Different -> nothing is moved, the board is listed in
<flops_dir>/strategy_backfill.json as a mismatch (values are never replaced). Needs the strategy-export build of t2_cont_panel
(tools/gto_precision/t2_cont_panel_strategy.patch).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

CALC = os.path.abspath(os.environ.get('PREC_CALC_ROOT', '/home/user/calc'))
BIN = os.path.join(os.environ.get('T2_BIN_DIR', os.path.join(CALC, 'vendor/gtopen/target/release/examples')), 't2_cont_panel')
KEYS = ('board', 'schema', 'players', 'matrix', 'trace', 'exploitability_pct_pot', 'invariant', 'iterations', 'converged', 'provenance_key')


def digest(path):   # same rule as tools/gto_spot/flop_digest.py
    d = json.load(open(path))
    c = {k: d.get(k) for k in KEYS}
    if isinstance(c.get('matrix'), dict):
        c['matrix'] = {k: v for k, v in c['matrix'].items() if k != 'ms'}
    return hashlib.sha256(json.dumps(c, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('term')
    ap.add_argument('menu')
    ap.add_argument('panel')
    ap.add_argument('flops')
    ap.add_argument('--workers', type=int, default=int(os.environ.get('SPOT_PANEL_WORKERS', '4')))
    a = ap.parse_args()
    boards = [f['board'] for f in json.load(open(a.panel))['panel']]
    todo = [b for b in boards if os.path.exists(os.path.join(a.flops, b + '.json')) and not os.path.exists(os.path.join(a.flops, b + '.strategy.json'))]
    logf = os.path.join(a.flops, 'strategy_backfill.json')
    log = json.load(open(logf)) if os.path.exists(logf) else {}
    if not todo:
        return 0
    commit = subprocess.run(['git', '-C', CALC, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    scratch = tempfile.mkdtemp(prefix='strat_backfill_', dir=os.path.dirname(a.flops.rstrip('/')))
    running = []
    bad = 0

    def finish(p, b, sd):
        nonlocal bad
        rc = p.wait()
        new = os.path.join(sd, b + '.json')
        old = os.path.join(a.flops, b + '.json')
        if rc == 0 and os.path.exists(new) and os.path.exists(os.path.join(sd, b + '.strategy.json')):
            same = digest(new) == digest(old)
            log[b] = {'digest_stored': digest(old), 'digest_resolved': digest(new), 'bit_identical': same}
            if same:
                os.replace(os.path.join(sd, b + '.strategy.json'), os.path.join(a.flops, b + '.strategy.json'))
            else:
                bad += 1
        else:
            log[b] = {'error': f'rc {rc}'}
            bad += 1
        json.dump(log, open(logf, 'w'), indent=1)
        shutil.rmtree(sd, ignore_errors=True)
        print(b, log[b], flush=True)

    for b in todo:
        k = json.load(open(os.path.join(a.flops, b + '.json')))['provenance_key']
        sd = os.path.join(scratch, b)
        os.makedirs(sd)
        env = dict(os.environ, T2_EXPORT_STRATEGY='1', T2_PANEL_BOARDS=b, RAYON_NUM_THREADS='1', T2_SOURCE_COMMIT=commit)
        env.pop('T2_ALGO', None)
        env.pop('T2_PANEL_MATRIX', None)
        if k.get('algo'):
            env['T2_ALGO'] = k['algo']
        if k.get('matrix'):
            env['T2_PANEL_MATRIX'] = '1'
        every = json.load(open(os.path.join(a.flops, b + '.json')))['trace'][0][0]
        p = subprocess.Popen([BIN, a.term, a.menu, a.panel, sd, str(k['max_iters']), str(k['target_exploitability_pct_pot']), str(every)],
                             env=env, stdout=open(os.path.join(sd, 'log'), 'w'), stderr=subprocess.STDOUT)
        running.append((p, b, sd))
        while len(running) >= a.workers:
            p0, b0, sd0 = running.pop(0)
            finish(p0, b0, sd0)
    for p0, b0, sd0 in running:
        finish(p0, b0, sd0)
    shutil.rmtree(scratch, ignore_errors=True)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
