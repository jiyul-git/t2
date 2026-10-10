#!/usr/bin/env python3
"""P11 C4: original A6 fixture, true pre-fix boundary replay, and seeded live parity.

No production coefficients, fallbacks, frozen baselines, or global RNG changes.
The 'old' arm removes ONLY tilt/bb_chips on the update->revise boundary.
"""
import argparse
import copy
import hashlib
import json
import os
import pickle
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import plan as PL
import runner as RU
import replan_provenance as RP

ORIGINAL_REVISE = RU.revise_plan


def boundary(arm):
    def run(*args, **kwargs):
        kwargs = dict(kwargs)
        if arm in ('old', 'tilt_only'):
            kwargs['bb_chips'] = None
        if arm in ('old', 'bb_only'):
            kwargs['tilt'] = 0.0
        return ORIGINAL_REVISE(*args, **kwargs)
    return run


def digest(obj):
    return hashlib.sha256(repr(obj).encode('utf-8')).hexdigest()


def serial(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                 default=lambda v: repr(v)))


def capture(mode, dest):
    class TrackingField(RP.FS.Field):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._p11_actions = []
            instances.append(self)

        def _log_bot_hand(self, tb, h, run):
            result = getattr(run, 'result', None) or {}
            self._p11_actions.append({
                'hand_no': self.hand_no,
                'table': tb.id,
                'full_log': copy.deepcopy(result.get('full_log', [])),
                'stacks': copy.deepcopy(h.stacks),
                'winners': copy.deepcopy(result.get('winners')),
                'board': copy.deepcopy(result.get('board')),
                'plans': {str(k): {
                    'plan': p.get('plan'),
                    'goal': p.get('plan_goal'),
                } for k, p in (getattr(h, 'plans', {}) or {}).items()
                    if isinstance(p, dict)},
            })

    instances = []
    saved_field = RP.FS.Field
    saved_revise = RU.revise_plan
    try:
        RP.FS.Field = TrackingField
        RU.revise_plan = boundary('old') if mode == 'old' else ORIGINAL_REVISE
        events, counts, errors = RP._capture_events()
    finally:
        RP.FS.Field = saved_field
        RU.revise_plan = saved_revise

    tournaments = []
    for f in instances:
        tournament = {
            'seed': f.seed,
            'fmt': f.fmt.get('name', str(f.fmt.get('id', 'unknown'))),
            'hand_no': f.hand_no,
            'level': f.level,
            'stacks': sorted((int(pid), int(p['stack']))
                             for pid, p in f.players.items()),
            'busted_order': list(f.busted_order),
            'tables': {str(tid): {'seats': list(tb.seats),
                                  'button_seat': tb.button_seat,
                                  'bb_seat': tb.bb_seat}
                       for tid, tb in f.tables.items()},
            'rng': digest(f.rng.getstate()),
            'actions': f._p11_actions,
        }
        tournament['action_digest'] = digest(tournament['actions'])
        tournaments.append(tournament)
    payload = {'mode': mode, 'counts': dict(counts),
               'engine_errors': [str(e) for e in errors],
               'events': events, 'tournaments': tournaments}
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('wb') as fp:
        pickle.dump(payload, fp, protocol=pickle.HIGHEST_PROTOCOL)
    print(json.dumps({'mode': mode, 'counts': dict(counts),
                      'tournaments': len(tournaments),
                      'action_digests': [t['action_digest'] for t in tournaments],
                      'error_count': len(errors)}, ensure_ascii=False), flush=True)
    if errors:
        raise AssertionError('engine errors: ' + str(errors[:4]))


def replay(ev, arm):
    saved = RU.revise_plan
    original_target = PL.target_commit
    commits = []
    def trace_target(*args, **kwargs):
        result = original_target(*args, **kwargs)
        commits.append({'opp_eff': kwargs.get('opp_eff'),
                        'opp_stack_bb': kwargs.get('opp_stack_bb'),
                        'target': result})
        return result
    state = random.getstate()
    try:
        RU.revise_plan = boundary(arm)
        PL.target_commit = trace_target
        random.seed(117011)
        out = PL.update_plan(*copy.deepcopy(ev['args']),
                             **copy.deepcopy(ev['kwargs']))
        post_rng = digest(random.getstate())
        intent = PL.intent_of(out, ev['street']) or {}
        output = {'plan': out.get('plan'),
                  'goal': out.get('plan_goal'),
                  'act': intent.get('act'),
                  'size': intent.get('size'),
                  'stackoff': serial(out.get('stackoff')),
                  'target_commit_calls': commits,
                  'equity_status': out.get('equity_status'),
                  'rng': post_rng,
                  'full_state_digest': digest(serial(out))}
        return output
    finally:
        random.setstate(state)
        RU.revise_plan = saved
        PL.target_commit = original_target


def diffkind(old, new):
    return [key for key in ('plan', 'goal', 'act', 'size', 'stackoff',
                           'target_commit_calls', 'equity_status',
                           'rng', 'full_state_digest') if old[key] != new[key]]


def compare(old_file, new_file, report_file):
    with old_file.open('rb') as fh:
        old = pickle.load(fh)
    with new_file.open('rb') as fh:
        new = pickle.load(fh)
    if old['engine_errors'] or new['engine_errors']:
        raise AssertionError('engine errors in seeded fixture')
    events = old['events']
    counts = Counter()
    examples = []
    by_arm = {}
    baseline_outputs = [replay(ev, 'old') for ev in events]
    for arm in ('tilt_only', 'bb_only', 'fixed'):
        total = 0
        kinds = Counter()
        for i, ev in enumerate(events):
            baseline = baseline_outputs[i]
            patched = replay(ev, arm)
            kinds_here = diffkind(baseline, patched)
            for k in kinds_here:
                kinds[k] += 1
            if any(k in kinds_here for k in ('plan','act','size')):
                total += 1
                if len(examples) < 16:
                    examples.append({'event': i, 'arm': arm,
                                     'street': ev['street'],
                                     'context': serial(ev['current']),
                                     'snapshot': serial(ev['snapshot']),
                                     'before': baseline, 'after': patched,
                                     'differences': kinds_here})
        by_arm[arm] = {'decision_changed': total, 'diff_kinds': dict(kinds)}
    for i, (o, n) in enumerate(zip(old['tournaments'], new['tournaments'])):
        if o['action_digest'] != n['action_digest']:
            counts['live_tournament_action_changed'] += 1
        if o['stacks'] != n['stacks']:
            counts['live_final_stack_changed'] += 1
        if o['rng'] != n['rng']:
            counts['live_rng_changed'] += 1
        if o['busted_order'] != n['busted_order']:
            counts['live_busted_order_changed'] += 1
    report = {
        'origin_sha': '3f30cc82540dc6d69fbf22295f49da20194626a4',
        'fixture': {'seeds': RP.SEEDS, 'formats': RP.FMTS,
                    'hands': RP.HANDS, 'entries': RP.ENTRIES},
        'historic_A6_board_changed_count': 810,
        'old_counts': old['counts'], 'new_counts': new['counts'],
        'old_event_count': len(events),
        'new_event_count': len(new['events']),
        'arms': by_arm,
        'live': dict(counts),
        'old_live': [{k: v for k, v in f.items() if k != 'actions'}
                     for f in old['tournaments']],
        'new_live': [{k: v for k, v in f.items() if k != 'actions'}
                     for f in new['tournaments']],
        'examples': examples,
    }
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, ensure_ascii=False,
                                      indent=2, sort_keys=True))
    print(json.dumps({k: report[k] for k in (
        'old_event_count','new_event_count','old_counts',
        'new_counts','arms','live')}, ensure_ascii=False, indent=2), flush=True)
    assert len(old['tournaments']) == len(new['tournaments']) == 9
    assert old['counts']['engine_errors'] == new['counts']['engine_errors'] == 0
    assert len(events) > 0
    print('PASS paired A6 seeded capture, decision arms and final-state audit')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['old','fixed','compare'])
    parser.add_argument('first', type=Path)
    parser.add_argument('second', nargs='?', type=Path)
    parser.add_argument('third', nargs='?', type=Path)
    args = parser.parse_args()
    if args.mode == 'compare':
        assert args.second and args.third
        compare(args.first, args.second, args.third)
    else:
        capture(args.mode, args.first)


if __name__ == '__main__':
    main()
