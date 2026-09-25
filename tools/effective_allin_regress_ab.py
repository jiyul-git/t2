#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fresh-process A/B isolating effective-allin v1 from its parent branch semantics."""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def child(arm):
    import runner as RU

    if arm == 'old':
        real = RU.effective_allin_v1

        def disabled(*args, **kwargs):
            out = dict(real(*args, **kwargs))
            out['effective'] = False
            return out

        RU.effective_allin_v1 = disabled

    from tools import regress as RG
    fp, stats = RG.fingerprint()
    print('RESULT_JSON=' + json.dumps({'arm': arm, 'fp': fp, 'stats': stats},
                                      sort_keys=True))
    return 0


def run_arm(arm):
    p = subprocess.run(
        [sys.executable, os.path.abspath(__file__), '--child', arm],
        env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False)
    if p.returncode != 0:
        print(p.stdout)
        raise SystemExit('child %s failed rc=%d' % (arm, p.returncode))
    marker = 'RESULT_JSON='
    line = next((x for x in reversed(p.stdout.splitlines())
                 if x.startswith(marker)), None)
    if line is None:
        print(p.stdout)
        raise SystemExit('child %s produced no result json' % arm)
    return json.loads(line[len(marker):])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--child', choices=['old', 'new'])
    a = ap.parse_args()
    if a.child:
        return child(a.child)

    old = run_arm('old')
    new = run_arm('new')
    seeds = sorted(set(old['fp']) | set(new['fp']), key=int)
    bad = [s for s in seeds if old['fp'].get(s) != new['fp'].get(s)]

    print('# effective-allin v1 regression A/B')
    print('OLD = current branch with classifier result forced false')
    print('NEW = current branch v1 classifier/execution enabled')
    print()
    for s in seeds:
        tag = 'DIFF' if s in bad else 'same'
        print('seed %s  %-4s  old=%s new=%s'
              % (s, tag, old['fp'].get(s), new['fp'].get(s)))
    print()
    print('changed seeds:', [int(s) for s in bad])
    print('old stats:', old['stats'])
    print('new stats:', new['stats'])
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
