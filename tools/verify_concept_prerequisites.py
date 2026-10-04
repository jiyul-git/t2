#!/usr/bin/env python3
"""Verify hard prerequisite caps in persona population generation."""

import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import persona as PS

MARGIN = 2.0
EDGES = (
    ('cbet_flop', 'barrel_turn'),
    ('barrel_turn', 'barrel_river'),
    ('cbet_flop', 'delayed_cbet'),
)


def main():
    violations = []
    max_gap = {('%s->%s' % e): -999.0 for e in EDGES}
    samples = 0

    for qi, fq in enumerate((0.40, 0.78, 1.20)):
        rr = random.Random(20261005 + qi * 100003)
        for i in range(5000):
            p = PS.make_player(rr, fq, pid=qi * 5000 + i)
            c = p['concepts']
            samples += 1
            for pre, post in EDGES:
                gap = float(c[post]) - float(c[pre])
                key = '%s->%s' % (pre, post)
                max_gap[key] = max(max_gap[key], gap)
                if gap > MARGIN + 1e-9:
                    violations.append({
                        'q': fq, 'pid': p.get('id'),
                        'pre': pre, 'pre_score': c[pre],
                        'post': post, 'post_score': c[post],
                        'gap': gap,
                    })
                    if len(violations) >= 20:
                        break
            if len(violations) >= 20:
                break
        if len(violations) >= 20:
            break

    # Same seed must still be deterministic.
    a = PS.make_player(random.Random(424242), 0.78, pid=77)
    b = PS.make_player(random.Random(424242), 0.78, pid=77)
    deterministic = (a == b)

    out = {
        'pass': not violations and deterministic,
        'samples': samples,
        'margin': MARGIN,
        'max_observed_gap': max_gap,
        'violations': violations,
        'same_seed_deterministic': deterministic,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)


if __name__ == '__main__':
    main()
