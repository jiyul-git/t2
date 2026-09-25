#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fresh-process A/B for the uncalled-excess accounting change.

Both arms include all earlier fixes on the current branch (including planned-allin
preservation).  The OLD arm only restores the three pre-change Round semantics:

- to_call = raw current - contrib
- decision pot sees all current-street contributions
- no round-end uncalled return

This isolates whether the new accounting change itself alters the frozen regression
fixture, instead of conflating it with the already-known seed-3001 mismatch from the
earlier planned-allin fix.
"""
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
        def old_to_call(self, seat):
            return max(0, self.current - self.contrib.get(seat, 0))

        def old_contestable(self, seat):
            return sum(self.contrib.values())

        def old_settle(self):
            return None

        RU.Round.to_call = old_to_call
        RU.Round.contestable_contrib = old_contestable
        RU.Round.settle_uncalled = old_settle

    from tools import regress as RG
    fp, stats = RG.fingerprint()
    print('RESULT_JSON=' + json.dumps({'arm': arm, 'fp': fp, 'stats': stats},
                                      sort_keys=True))
    return 0


def run_arm(arm):
    env = dict(os.environ)
    p = subprocess.run(
        [sys.executable, os.path.abspath(__file__), '--child', arm],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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

    print('# uncalled-excess regression A/B')
    print('OLD = current branch with only uncalled-excess semantics monkeypatched out')
    print('NEW = current branch as implemented')
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
