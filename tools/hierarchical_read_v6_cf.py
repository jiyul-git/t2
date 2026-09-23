#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V6 paired counterfactual.

CONTROL: current persona.read_opponent
V6:      reads.hierarchical_read_v6 monkeypatched only inside this process

Production files are not switched.
"""
import os, sys, json, hashlib, argparse, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persona as PS
import reads as RD
import tourney as T

HANDS = 30


def _hash_hands(hands):
    rows = []
    for log in hands:
        rows.append(';'.join('%s:%s:%s:%s' % tuple(x) for x in log))
    return hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]


def _inner(seed, arm):
    orig = PS.read_opponent
    def _axis_zero():
        return {
            'freq': {'coarse':0.0,'trait':0.0,'detail':0.0},
            'line': {'coarse':0.0,'trait':0.0,'detail':0.0},
            'size': {'coarse':0.0,'trait':0.0,'detail':0.0},
        }
    stats = {
        'calls': 0, 'w_positive': 0,
        'bins': {'LOW':0, 'MID':0, 'HIGH':0},
        'axis': _axis_zero(),
        'by_bin': {
            'LOW': {'calls':0, 'w_positive':0, 'axis':_axis_zero()},
            'MID': {'calls':0, 'w_positive':0, 'axis':_axis_zero()},
            'HIGH': {'calls':0, 'w_positive':0, 'axis':_axis_zero()},
        },
    }

    if arm == 'v6':
        def wrapped(prof, opp_est):
            out = RD.hierarchical_read_v6(prof, opp_est)
            dep = RD.observer_resolution_v4(prof)
            da = dep['detail_access']
            b = 'LOW' if da < .34 else ('MID' if da < .67 else 'HIGH')
            stats['calls'] += 1
            stats['bins'][b] += 1
            stats['by_bin'][b]['calls'] += 1
            if out.get('w', 0.0) > 0:
                stats['w_positive'] += 1
                stats['by_bin'][b]['w_positive'] += 1
            sw = out.get('source_weights') or {}
            for axis in ('freq','line','size'):
                q = sw.get(axis) or {}
                for layer in ('coarse','trait','detail'):
                    v = float(q.get(layer,0.0))
                    stats['axis'][axis][layer] += v
                    stats['by_bin'][b]['axis'][axis][layer] += v
            return out
        PS.read_opponent = wrapped

    hands = []
    errors = []
    try:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=seed, hands_per_level=200)
        for hi in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            try:
                st = t.next_hand()
                guard = 0
                while st and not st.get('done') and guard < 200:
                    st = t.submit('fold')
                    guard += 1
                if guard >= 200:
                    errors.append('guard:%d' % hi)
                    break
                log = list(getattr(t.run, 'full_log', []) or [])
                hands.append([list(x) for x in log])
                t.finish_hand()
            except Exception as e:
                errors.append('%s:%s' % (type(e).__name__, str(e)))
                break
    finally:
        PS.read_opponent = orig

    if stats['calls']:
        for axis in ('freq','line','size'):
            for layer in ('coarse','trait','detail'):
                stats['axis'][axis][layer] /= stats['calls']
    for b in ('LOW','MID','HIGH'):
        bc = stats['by_bin'][b]['calls']
        if bc:
            for axis in ('freq','line','size'):
                for layer in ('coarse','trait','detail'):
                    stats['by_bin'][b]['axis'][axis][layer] /= bc

    return {
        'seed': seed, 'arm': arm, 'hands_n': len(hands),
        'hash': _hash_hands(hands), 'hands': hands,
        'engine_errors': len(errors), 'errors': errors,
        'read_stats': stats,
    }


def _spawn(seed, arm):
    cp = subprocess.run(
        [sys.executable, __file__, '--inner', '--seed', str(seed), '--arm', arm],
        cwd=ROOT, text=True, capture_output=True, timeout=900)
    if cp.returncode != 0:
        raise RuntimeError('%s rc=%s stderr=%s stdout=%s'
                           % (arm, cp.returncode, cp.stderr[-1500:], cp.stdout[-1500:]))
    line = next((x for x in cp.stdout.splitlines() if x.startswith('INNER_JSON=')), None)
    if not line:
        raise RuntimeError('%s missing INNER_JSON: %s' % (arm, cp.stdout[-2000:]))
    return json.loads(line.split('=',1)[1])


def _outer(seed):
    c = _spawn(seed, 'control')
    v = _spawn(seed, 'v6')
    n = max(len(c['hands']), len(v['hands']))
    diff_hands = 0
    diff_entries = 0
    first_diff = None
    for i in range(n):
        a = c['hands'][i] if i < len(c['hands']) else []
        b = v['hands'][i] if i < len(v['hands']) else []
        if a != b:
            diff_hands += 1
            m = max(len(a), len(b))
            for j in range(m):
                xa = a[j] if j < len(a) else None
                xb = b[j] if j < len(b) else None
                if xa != xb:
                    diff_entries += 1
                    if first_diff is None:
                        first_diff = {'hand':i, 'entry':j, 'control':xa, 'v6':xb}

    out = {
        'seed': seed,
        'control_hash': c['hash'],
        'v6_hash': v['hash'],
        'hands_control': c['hands_n'],
        'hands_v6': v['hands_n'],
        'diff_hands': diff_hands,
        'diff_entries': diff_entries,
        'first_diff': first_diff,
        'engine_errors': c['engine_errors'] + v['engine_errors'],
        'control_errors': c['errors'],
        'v6_errors': v['errors'],
        'read_stats': v['read_stats'],
    }
    print('V6_CF_JSON=' + json.dumps(out, separators=(',',':'), sort_keys=True))
    return 0 if out['engine_errors'] == 0 else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--arm', choices=['control','v6'])
    ap.add_argument('--inner', action='store_true')
    a = ap.parse_args()
    if a.inner:
        if not a.arm:
            raise SystemExit('--inner requires --arm')
        print('INNER_JSON=' + json.dumps(_inner(a.seed, a.arm),
                                         separators=(',',':'), sort_keys=True))
        return 0
    return _outer(a.seed)


if __name__ == '__main__':
    raise SystemExit(main())
