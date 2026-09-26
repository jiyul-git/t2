#!/usr/bin/env python3
"""Attribute the seed-3005 regression delta to the F8-D6-D2 consumer only.

Runs the exact regress.py tournament twice:
  1) current D6-D2 behavior;
  2) same code with only application of calloff_layer_judgment disabled.

The second run must return exactly to the frozen current baseline fingerprint.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import preflop as PF
import tourney as T

SEED = 3005
HANDS = 30
BASE = os.path.join(os.path.dirname(__file__), 'baseline_9max_post_oop.json')


def _consumer_events(hand, hand_no):
    out = []
    pf_seed = getattr(hand, 'pf_seed', {}) or {}
    for seat, seed in sorted(pf_seed.items(), key=lambda kv: str(kv[0])):
        for line_no, row in enumerate(seed.get('pf_line') or []):
            c = row.get('calloff_consumer')
            if not c or not c.get('changed'):
                continue
            sh = row.get('call_ev_shadow') or {}
            out.append({
                'hand_no': hand_no,
                'hand_hash': getattr(hand, 'hash', None),
                'seat': seat,
                'pos': getattr(hand, 'pos', {}).get(seat),
                'line_no': line_no,
                'pure_calloff': bool(sh.get('pure_calloff')),
                'complete': bool(sh.get('complete')),
                'call_cost': sh.get('call_cost'),
                'contestable_after_call': sh.get('contestable_after_call'),
                'legacy_action': c.get('legacy_action'),
                'selected_action': c.get('selected_action'),
                'layer_effective_equity': c.get('layer_effective_equity'),
                'perceived_required_equity': c.get('perceived_required_equity'),
                'objective_bubble_factor': c.get('objective_bubble_factor'),
                'perceived_bubble_factor': c.get('perceived_bubble_factor'),
                'pf_defend_gate_p': c.get('pf_defend_gate_p'),
                'pf_defend_gate_roll': c.get('pf_defend_gate_roll'),
                'gate_pass': bool(c.get('gate_pass')),
            })
    return out


def _run(disable_consumer=False):
    original = PF.calloff_layer_judgment

    if disable_consumer:
        def legacy_only(*args, **kwargs):
            out = original(*args, **kwargs)
            if out is None:
                return None
            out = dict(out)
            # Keep all D6-A~R calculations/provenance, disable only the D6-D2
            # application gate. No shared RNG is consumed by this wrapper.
            out['gate_pass'] = False
            out['_attribution_forced_off'] = True
            return out
        PF.calloff_layer_judgment = legacy_only

    try:
        t = T.Tournament(
            entries=100, start_stack=30000, hero_seat=7,
            seed=SEED, hands_per_level=200)
        rows = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
        hand_logs = []
        events = []

        for hand_no in range(1, HANDS + 1):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1

            log = list(getattr(t.run, 'full_log', []) or [])
            row = ';'.join('%s:%s:%s:%s' % x for x in log)
            rows.append(row)
            hand_logs.append(log)
            events.extend(_consumer_events(t.hand, hand_no))
            t.finish_hand()

        fp = hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
        return {
            'fp': fp,
            'logs': hand_logs,
            'events': events,
        }
    finally:
        PF.calloff_layer_judgment = original


def _first_log_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i, a[i], b[i]
    if len(a) != len(b):
        return n, (a[n] if n < len(a) else None), (b[n] if n < len(b) else None)
    return None


def main():
    baseline = json.load(open(BASE))
    base_fp = baseline['fp'][str(SEED)]

    current = _run(False)
    legacy = _run(True)

    assert current['fp'] != base_fp, (
        'seed 3005 no longer differs; attribution fixture is stale',
        current['fp'], base_fp)
    assert legacy['fp'] == base_fp, (
        'disabling only D6-D2 did not restore baseline',
        legacy['fp'], base_fp)

    first_hand = None
    diff = None
    for i, (a, b) in enumerate(zip(current['logs'], legacy['logs']), start=1):
        if a != b:
            first_hand = i
            diff = _first_log_diff(a, b)
            break
    assert first_hand is not None, 'fingerprints differ but no hand log differs'

    first_events = [
        e for e in current['events'] if e['hand_no'] == first_hand]
    assert first_events, (
        'first divergent hand has no changed D6-D2 consumer event',
        first_hand)

    ev = first_events[0]
    assert ev['pure_calloff'] is True, ev
    assert ev['complete'] is True, ev
    assert ev['gate_pass'] is True, ev
    assert ev['legacy_action'] != ev['selected_action'], ev

    idx, cur_rec, legacy_rec = diff
    assert cur_rec is not None and legacy_rec is not None, diff
    assert cur_rec[0] == legacy_rec[0] == 'preflop', diff
    assert cur_rec[1] == legacy_rec[1] == ev['seat'], (diff, ev)
    assert cur_rec[2] == ev['selected_action'], (diff, ev)
    assert legacy_rec[2] == ev['legacy_action'], (diff, ev)

    print('PASS seed 3005 current fingerprint differs from frozen baseline',
          {'current': current['fp'], 'baseline': base_fp})
    print('PASS disabling only F8-D6-D2 restores frozen fingerprint exactly',
          {'consumer_off': legacy['fp'], 'baseline': base_fp})
    print('PASS first divergent action is the changed D6-D2 consumer event', {
        'hand_no': first_hand,
        'log_index': idx,
        'current': cur_rec,
        'consumer_off': legacy_rec,
    })
    print('PASS D6-D2 activation provenance', ev)
    print('4/4 F8-D6-D2 attribution checks passed')


if __name__ == '__main__':
    main()
