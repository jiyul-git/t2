#!/usr/bin/env python3
"""hand_records_v1: per-(spot, hand) strategy record with measured uncertainty (docs/GTO_EXPANSION_DESIGN_V1.md section 1).

Fixed parameters (user decision 2026-10-03): Z = 2, A = 0.95 (with 60 bootstrap replicates: modal action in >= 57 / 60).
Statuses: stable / near_indifferent / unstable / unassessed. Frequency intervals (q05/q50/q95), modal-action consistency and
L1 dispersion are stored separately; near_indifferent is NOT a statement about frequency precision, and no frequency-precision
threshold is defined here. Action identities are never merged: groups are a lookup-layer view computed from stored fields.
"""
import math

Z = 2.0
A = 0.95
STATUSES = ('stable', 'near_indifferent', 'unstable', 'unassessed')


def quantiles(xs, ps=(0.05, 0.5, 0.95)):
    s = sorted(xs)
    return [s[min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))] for p in ps]


def sd(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0


def classify(gap, u, agreement, policy_argmax, ev_argmax):
    """status from stored measurements; agreement None -> unassessed."""
    if agreement is None or u is None:
        return 'unassessed'
    if gap <= Z * u:
        return 'near_indifferent'
    if agreement >= A and policy_argmax == ev_argmax:
        return 'stable'
    return 'unstable'


def record(actions, freq_point, ev_point, freq_reps, ev_reps, u_outer=None):
    """build one hand record. freq_point / ev_point: lists by action; freq_reps / ev_reps: list over replicates of lists."""
    na = len(actions)
    order = sorted(range(na), key=lambda k: -ev_point[k])
    best, second = order[0], order[1]
    gap = ev_point[best] - ev_point[second]
    u_solver = max(0.0, max(ev_point) - sum(freq_point[k] * ev_point[k] for k in range(na)))
    u_panel = sd([e[best] - e[second] for e in ev_reps]) if ev_reps else None
    u_total = None if u_panel is None else math.sqrt(u_panel ** 2 + (u_outer or 0.0) ** 2) + u_solver
    pol = max(range(na), key=lambda k: freq_point[k])
    agree = sum(1 for f in freq_reps if max(range(na), key=lambda k: f[k]) == pol) / len(freq_reps) if freq_reps else None
    l1 = [sum(abs(f[k] - freq_point[k]) for k in range(na)) for f in freq_reps]
    rec = {
        'freq': {actions[k]: freq_point[k] for k in range(na)},
        'ev': {actions[k]: ev_point[k] for k in range(na)},
        'ev_best': actions[best], 'ev_second': actions[second], 'gap': gap,
        'u': {'panel': u_panel, 'outer': u_outer, 'outer_measured': u_outer is not None, 'solver': u_solver, 'total': u_total},
        'freq_q05_q50_q95': {actions[k]: quantiles([f[k] for f in freq_reps]) for k in range(na)} if freq_reps else None,
        'policy_argmax': actions[pol], 'modal_action_consistency': agree,
        'l1_dispersion': {'mean': sum(l1) / len(l1), 'q50_q95': quantiles(l1, (0.5, 0.95))} if l1 else None,
        'replicates': len(freq_reps),
    }
    rec['status'] = classify(gap, u_total, agree, actions[pol], actions[best])
    return rec


def near_indifferent_group(rec):
    """lookup-layer view only: actions whose point EV is within Z * u of the best. Never written back into stored data."""
    if rec['u']['total'] is None:
        return None
    top = max(rec['ev'].values())
    return sorted(a for a, e in rec['ev'].items() if e >= top - Z * rec['u']['total'])


def validate(strategy):
    """hand_records_v1 structural check; raises ValueError."""
    if strategy.get('format') != 'hand_records_v1':
        raise ValueError('format must be hand_records_v1')
    acts = strategy['actions']
    if len(set(acts)) != len(acts):
        raise ValueError('duplicate action identities')
    for h, r in strategy['hands'].items():
        if set(r['freq']) != set(acts) or set(r['ev']) != set(acts):
            raise ValueError(f'{h}: every action must be stored (no merging)')
        if r['status'] not in STATUSES:
            raise ValueError(f'{h}: status {r["status"]}')
        if abs(sum(r['freq'].values()) - 1) > 1e-4:
            raise ValueError(f'{h}: frequencies do not sum to 1')
        if r['status'] != 'unassessed' and (r['freq_q05_q50_q95'] is None or r['modal_action_consistency'] is None or r['l1_dispersion'] is None):
            raise ValueError(f'{h}: assessed record without frequency interval / consistency / dispersion')
    return True
