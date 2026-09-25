#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trace the first seed-3002 divergence caused by effective-allin v1.

Replays the exact tools/regress.py fixture in two fresh processes:
- OLD: classifier computes diagnostics but effective=False
- NEW: classifier/execution enabled

Prints the first divergent hand, both full logs, and raw v1 candidate calls/intents.
"""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SEED = 3002
HANDS = 30


def child(arm):
    import runner as RU
    import tourney as T

    raw_events = []
    real = RU.effective_allin_v1

    def wrapped(*args, **kwargs):
        out = dict(real(*args, **kwargs))
        raw_events.append({
            'target': float(args[0]) if args else float(kwargs.get('target', 0)),
            'actor_cap': float(args[1]) if len(args) > 1 else float(kwargs.get('actor_cap', 0)),
            'opp_cap_max': float(args[2]) if len(args) > 2 else float(kwargs.get('opp_cap_max', 0)),
            'contrib_before': float(args[3]) if len(args) > 3 else float(kwargs.get('contrib_before', 0)),
            'pot_before': float(args[4]) if len(args) > 4 else float(kwargs.get('pot_before', 0)),
            'actor_effective': bool(out.get('actor_effective')),
            'effective_raw': bool(out.get('effective')),
            'commit_frac': float(out.get('commit_frac', 0)),
            'post_spr': float(out.get('post_spr', 0)),
            'residual': float(out.get('residual', 0)),
        })
        if arm == 'old':
            out['effective'] = False
        return out

    RU.effective_allin_v1 = wrapped

    t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                     seed=SEED, hands_per_level=200)
    out = []
    for hi in range(HANDS):
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
            break
        raw_events[:] = []
        st = t.next_hand()
        guard = 0
        while st and not st.get('done') and guard < 200:
            st = t.submit('fold')
            guard += 1

        log = list(getattr(t.run, 'full_log', []) or [])
        h = getattr(t.run, 'h', None)
        intents = []
        for it in (getattr(h, 'intents', None) or []):
            if (it.get('effective_allin_candidate')
                    or it.get('effective_allin_applied')
                    or it.get('effective_allin_actor')):
                intents.append({
                    'street': it.get('street'),
                    'seat': it.get('seat'),
                    'plan': it.get('plan'),
                    'action': it.get('action'),
                    'amt': it.get('amt'),
                    'pre_effective_target': it.get('pre_effective_target'),
                    'candidate': it.get('effective_allin_candidate'),
                    'actor_effective': it.get('effective_allin_actor'),
                    'commit_frac': it.get('effective_allin_commit'),
                    'post_spr': it.get('effective_allin_post_spr'),
                    'applied': it.get('effective_allin_applied'),
                    'mode': it.get('allin_execution_mode'),
                    'stack': it.get('stack'),
                    'pot': it.get('pot'),
                    'tocall': it.get('tocall'),
                })

        out.append({
            'hand_index': hi + 1,
            'log': log,
            'raw_candidates': [x for x in raw_events if x['effective_raw']],
            'intents': intents,
        })
        t.finish_hand()

    print('RESULT_JSON=' + json.dumps(out, sort_keys=True))
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
        raise SystemExit('child %s produced no RESULT_JSON' % arm)
    return json.loads(line[len(marker):])


def short_log(log):
    return ['%s:%s:%s:%s' % tuple(x) for x in log]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--child', choices=['old', 'new'])
    a = ap.parse_args()
    if a.child:
        return child(a.child)

    old = run_arm('old')
    new = run_arm('new')
    n = min(len(old), len(new))
    first = None
    for i in range(n):
        if old[i]['log'] != new[i]['log']:
            first = i
            break

    print('# effective-allin seed 3002 first-divergence trace')
    if first is None:
        print('No divergent hand found in %d paired hands.' % n)
        return 0

    o, nn = old[first], new[first]
    print('first divergent hand index:', first + 1)
    print()
    print('OLD raw v1 candidates:')
    print(json.dumps(o['raw_candidates'], indent=2, ensure_ascii=False))
    print('NEW raw v1 candidates:')
    print(json.dumps(nn['raw_candidates'], indent=2, ensure_ascii=False))
    print()
    print('NEW candidate/applied intents:')
    print(json.dumps(nn['intents'], indent=2, ensure_ascii=False))

    ol = short_log(o['log'])
    nl = short_log(nn['log'])
    j = 0
    while j < min(len(ol), len(nl)) and ol[j] == nl[j]:
        j += 1
    print()
    print('first differing log row:', j + 1)
    print('OLD:', ol[j] if j < len(ol) else '<end>')
    print('NEW:', nl[j] if j < len(nl) else '<end>')
    lo = max(0, j - 4)
    hi = j + 7
    print()
    print('OLD log window:')
    for k, x in enumerate(ol[lo:hi], lo + 1):
        print('  %3d  %s' % (k, x))
    print('NEW log window:')
    for k, x in enumerate(nl[lo:hi], lo + 1):
        print('  %3d  %s' % (k, x))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
