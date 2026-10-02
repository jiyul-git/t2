#!/usr/bin/env python3
"""A4c bootstrap integrity check (read-only; run after boot, before analyze is trusted).

    python3 tools/gto_hu_continuation/a4c_boot_verify.py [--rerun 38,5]

1. replicate set: keys exactly 1..60, every replicate complete ('done' and all metric blocks present).
2. draw provenance: the joint draws are regenerated from seed 20261005 (amendment 1); their sha256 must equal the stored
   manifest, and for every replicate the solved tables (boot/rNN/{144,ext}/table_node{6,28}.json) must equal the tables rebuilt
   from draw NN exactly -> replicate NN was solved on draw NN, no shift / mix-up.
3. result provenance: stored gaps / evs of each replicate equal its own terminal exports; every swap file names the right base
   and donor profiles for its replicate and the right seat.
4. distinctness: no two replicates share a draw, and no two solved profiles are byte-identical (this is NOT a test of
   statistical independence, which rests on the seeded RNG design of amendment 1).
5. interrupted replicates (default 38) + one control: the swap evaluations are re-run into a scratch dir and must reproduce the
   stored swap files exactly (no partial / stale output kept from the interrupted run); profile files older than every swap
   that read them.
"""
import argparse
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a4c_run as C  # noqa: E402
import a4r_robust as A  # noqa: E402
from a4c_design2 import pools  # noqa: E402

OUT = C.OUT


def sha_file(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rerun', default='38,5')
    ap.add_argument('--reps', type=int, default=60)
    ap.add_argument('--partial', action='store_true', help='code check while boot runs: only finished replicates, output to scratch')
    a = ap.parse_args()
    R = json.load(open(OUT + 'boot.json'))
    P = json.load(open(OUT + 'points.json'))
    res = {'errors': []}
    err = res['errors'].append
    keys = sorted(R['reps'], key=int)
    if a.partial:
        keys = [k for k in keys if R['reps'][k].get('done')]
        keys = [str(i) for i in range(1, len(keys) + 1) if str(i) in keys]
        a.reps = len(keys)
    need = ['144', 'ext', 'err144', 'errext', 's144_to_Gext_r', 'sext_to_G144_r', 'done']
    res['replicates'] = len(keys)
    if keys != [str(i) for i in range(1, a.reps + 1)]:
        err(f'replicate keys are not exactly 1..{a.reps}: {keys}')
    for k in keys:
        if any(f not in R['reps'][k] for f in need):
            err(f'replicate {k} incomplete: {sorted(R["reps"][k])}')
    # 2. draws
    st = C.setup()
    J = C.joint_structure(st)
    rng = random.Random(20261005)
    draws, manifest = [], []
    for _ in range(a.reps):
        d, man = C.joint_draw(rng, J)
        draws.append(d)
        manifest.append(man)
    stored = json.load(open(OUT + 'boot_draw_manifest.json'))
    if json.loads(json.dumps(stored['draws'][:a.reps])) != json.loads(json.dumps(manifest)):
        err('stored draw manifest differs from the regenerated draws')
    if not a.partial and stored['sha256'] != hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest():
        err('draw manifest sha256 differs from the regenerated draws')
    if len(stored['draws']) != (60 if a.partial else a.reps):
        err(f"stored manifest has {len(stored['draws'])} draws")
    K = {s: len(v) for s, v in pools().items()}
    ref = {n: {'144': C.stratum_means(st[n]['vals'], st[n]['compat'], st[n]['old']), 'ext': C.stratum_means(st[n]['vals'], st[n]['compat'], st[n]['all'])} for n in (6, 28)}
    lam = {n: {'144': {s: math.sqrt((1 - 12 / K[s]) * 12 / 11) for s in st[n]['old']},
               'ext': {s: math.sqrt((1 - len(st[n]['all'][s]) / K[s]) * len(st[n]['all'][s]) / (len(st[n]['all'][s]) - 1)) for s in st[n]['old']}} for n in (6, 28)}
    tab_mism = []
    for i, k in enumerate(keys[:a.reps], 1):
        for size in ('144', 'ext'):
            for n in (6, 28):
                o, w = draws[i - 1][n]
                dr = o if size == '144' else {s: o[s] + w[s] for s in o}
                g = C.estimate(st[n]['vals'], st[n]['compat'], dr, st[n]['p_str'], lam[n][size], ref[n][size])
                saved = {s['position']: s['gross'] for s in json.load(open(OUT + f'boot/r{i:02d}/{size}/table_node{n}.json'))['seats']}
                if any(saved[p] != g[p] for p in g):
                    tab_mism.append((i, size, n))
    res['table_vs_draw_mismatches'] = tab_mism
    if tab_mism:
        err(f'{len(tab_mism)} replicate tables do not match their own draw')
    # 3. result provenance
    swap_dirs = {'err144': ('G144', '144'), 'errext': ('Gext', 'ext'), 's144_to_Gext': ('ext', '144'), 'sext_to_G144': ('144', 'ext')}
    prof = {'G144': P['G144']['profile'], 'Gext': P['Gext']['profile']}
    for i, k in enumerate(keys, 1):
        rd = OUT + f'boot/r{i:02d}/'
        for size in ('144', 'ext'):
            t = json.load(open(rd + f'{size}/terminal_node6.json'))
            if t['gaps'] != R['reps'][k][size]['gaps'] or t['evs'] != R['reps'][k][size]['evs']:
                err(f'rep {i} {size}: stored gaps/evs differ from its terminal export')
            if R['reps'][k][size]['profile'] != rd + f'{size}/profile.gtop':
                err(f'rep {i} {size}: profile path {R["reps"][k][size]["profile"]}')
        for sd, (base, donor) in swap_dirs.items():
            bp = prof.get(base, rd + f'{base}/profile.gtop')
            dp = rd + f'{donor}/profile.gtop'
            for name, (seat, _) in C.SEATS.items():
                f = rd + f'{sd}/swap_{name}.json'
                d = json.load(open(f))
                if d['base'] != bp or d['donor'] != dp or d['seat'] != seat or d['position'] != name:
                    err(f'rep {i} {sd}/{name}: base/donor/seat mismatch ({d["base"]}, {d["donor"]}, {d["seat"]})')
                for p in (bp, dp):
                    if os.path.getmtime(p) > os.path.getmtime(f):
                        err(f'rep {i} {sd}/{name}: profile {p} newer than the swap that read it')
    # 4. distinctness (not a statistical-independence test)
    dk = [json.dumps(m, sort_keys=True) for m in manifest]
    res['distinct_draws'] = len(set(dk))
    ph = [sha_file(OUT + f'boot/r{i:02d}/{s}/profile.gtop') for i in range(1, len(keys) + 1) for s in ('144', 'ext')]
    res['distinct_profiles'] = len(set(ph))
    if res['distinct_draws'] != a.reps or res['distinct_profiles'] != 2 * len(keys):
        err('duplicate draws or duplicate solved profiles')
    # 5. rerun swaps of the interrupted replicate(s) and a control
    rer = {}
    tmp = tempfile.mkdtemp(dir=os.path.join(OUT, '..'), prefix='.a4c_verify_')
    for i in [int(x) for x in a.rerun.split(',') if x]:
        rd = OUT + f'boot/r{i:02d}/'
        same = True
        for sd, (base, donor) in swap_dirs.items():
            bp = prof.get(base, rd + f'{base}/profile.gtop')
            bm = {'G144': P['G144']['manifest'], 'Gext': P['Gext']['manifest']}.get(base, rd + f'{base}/manifest.json')
            for name, (seat, root) in C.SEATS.items():
                o = os.path.join(tmp, f'r{i}_{sd}_{name}.json')
                A.splice({'profile': bp, 'manifest': bm}, {'profile': rd + f'{donor}/profile.gtop'}, seat, root, o)
                if json.load(open(o)) != json.load(open(rd + f'{sd}/swap_{name}.json')):
                    same = False
                    err(f'rep {i} {sd}/{name}: re-run differs from the stored swap')
        rer[i] = same
    res['rerun_identical'] = rer
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    res['ok'] = not res['errors']
    res['scope'] = ('bootstrap draw assignment / replay / restart integrity verified' if res['ok'] else 'integrity check FAILED') + \
        '; statistical independence of the replicates is not tested by this script (it follows from the seeded RNG design, amendment 1)'
    C.atomic(res, os.path.join(tempfile.gettempdir(), 'a4c_boot_verify_partial.json') if a.partial else OUT + 'boot_verify.json')
    print(json.dumps(res, indent=1))
    sys.exit(0 if res['ok'] else 1)


if __name__ == '__main__':
    main()
