#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Describe tournament-state signals on effective-all-in promotions.

Read-only.  No leave-behind threshold is chosen here.
"""

import argparse
import collections
import csv
import math


def num(v):
    try:
        if v is None or str(v).strip() == '':
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def yes(v):
    return str(v).strip().lower() in ('1', 'true', 'yes')


def q(vals, p):
    xs = sorted(x for x in vals if x is not None and math.isfinite(x))
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    lo = int(math.floor(k)); hi = int(math.ceil(k))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi-k) + xs[hi] * (k-lo)


def fmt(x, nd=3):
    if x is None:
        return '-'
    if abs(x-round(x)) < 1e-9:
        return str(int(round(x)))
    return ('%.*f' % (nd, x)).rstrip('0').rstrip('.')


def stat_line(name, vals):
    xs = [x for x in vals if x is not None]
    if not xs:
        print('  %-28s n=0' % name)
        return
    print('  %-28s n=%-3d min=%-7s q25=%-7s med=%-7s q75=%-7s max=%-7s'
          % (name, len(xs), fmt(min(xs)), fmt(q(xs,.25)), fmt(q(xs,.50)),
             fmt(q(xs,.75)), fmt(max(xs))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv_path')
    ap.add_argument('--top', type=int, default=40)
    a = ap.parse_args()

    with open(a.csv_path, newline='', encoding='utf-8') as fp:
        rows = list(csv.DictReader(fp))

    promoted = []
    for r in rows:
        if not yes(r.get('effective_allin_applied')):
            continue
        pre = num(r.get('pre_effective_target'))
        actor = num(r.get('actor_cap'))
        if pre is None or actor is None or pre >= actor - 1e-9:
            continue

        bb = num(r.get('bb')) or 1.0
        med = num(r.get('money_median_shorter_ratio'))
        sev = max(0.0, min(1.0, 1.0-med)) if med is not None else 0.0
        pay = num(r.get('money_payout_importance')) or 0.0
        lad = num(r.get('money_ladder_buffer')) or 0.0
        wait = num(r.get('money_waiting_feasibility')) or 0.0

        r['_pre_resid'] = actor - pre
        r['_pre_resid_bb'] = (actor-pre)/bb
        r['_shorter_severity'] = sev
        # This is the existing ladder term inside objective_self_preservation,
        # separated from BF only for descriptive audit.
        r['_ladder_survival_component'] = pay * lad * sev * wait
        r['_preserve_minus_urgency'] = (
            (num(r.get('money_self_preservation')) or 0.0)
            - (num(r.get('money_urgency')) or 0.0))
        promoted.append(r)

    print('# leave-behind state audit')
    print('rows=%d promoted_effective_allin=%d' % (len(rows), len(promoted)))

    missing = sum(not str(r.get('money_decision_kind') or '').strip()
                  for r in promoted)
    print('money-observation join missing:', missing)

    by_kind = collections.Counter(r.get('money_decision_kind') or '<missing>'
                                  for r in promoted)
    print('decision kind:', ' / '.join('%s=%d' % x for x in sorted(by_kind.items())))

    print()
    print('## descriptive distributions — no threshold')
    metrics = [
        ('pre-v1 residual BB', '_pre_resid_bb'),
        ('BF', 'money_bf'),
        ('payout importance', 'money_payout_importance'),
        ('ladder buffer', 'money_ladder_buffer'),
        ('shorter severity', '_shorter_severity'),
        ('waiting feasibility', 'money_waiting_feasibility'),
        ('ladder survival component', '_ladder_survival_component'),
        ('self preservation objective', 'money_self_preservation_objective'),
        ('self preservation perceived', 'money_self_preservation'),
        ('urgency objective', 'money_urgency_objective'),
        ('urgency perceived', 'money_urgency'),
        ('commitment budget', 'money_commitment_budget'),
        ('preservation - urgency', '_preserve_minus_urgency'),
        ('players to jump', 'money_players_to_jump'),
        ('n shorter', 'money_n_shorter'),
        ('forced cost share', 'money_forced_cost_share_of_stack'),
        ('stack after next BB', 'money_stack_after_next_bb_if_fold_all'),
    ]
    for label, key in metrics:
        vals = [num(r.get(key)) if not key.startswith('_') else r.get(key)
                for r in promoted]
        stat_line(label, vals)

    print()
    print('## promoted rows — ladder/survival component descending')
    shown = sorted(promoted,
                   key=lambda r: (r['_ladder_survival_component'],
                                  r['_preserve_minus_urgency']),
                   reverse=True)[:a.top]
    for r in shown:
        print(
            '  seed %s H%s %s %s kind=%s plan=%s '
            'commit=%s postSPR=%s preRemain=%sBB '
            'BF=%s pay=%s ladder=%s sev=%s wait=%s ladderComp=%s '
            'preserve=%s urgency=%s budget=%s P-U=%s '
            'jump=%s shorter=%s forced=%s nextBB=%s pos=%s'
            % (
                r.get('seed'), r.get('hand_no'), r.get('street'), r.get('action'),
                r.get('money_decision_kind'), r.get('plan'),
                fmt(num(r.get('effective_allin_commit'))),
                fmt(num(r.get('effective_allin_post_spr'))),
                fmt(r['_pre_resid_bb']),
                fmt(num(r.get('money_bf'))),
                fmt(num(r.get('money_payout_importance'))),
                fmt(num(r.get('money_ladder_buffer'))),
                fmt(r['_shorter_severity']),
                fmt(num(r.get('money_waiting_feasibility'))),
                fmt(r['_ladder_survival_component']),
                fmt(num(r.get('money_self_preservation'))),
                fmt(num(r.get('money_urgency'))),
                fmt(num(r.get('money_commitment_budget'))),
                fmt(r['_preserve_minus_urgency']),
                fmt(num(r.get('money_players_to_jump'))),
                fmt(num(r.get('money_n_shorter'))),
                fmt(num(r.get('money_forced_cost_share_of_stack'))),
                fmt(num(r.get('money_stack_after_next_bb_if_fold_all'))),
                r.get('money_pos') or '-',
            ))

    print()
    print('No leave-behind cutoff is chosen by this tool.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
