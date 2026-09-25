#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze an existing near_allin_audit CSV without rerunning tournaments.

Classifies the remaining near-all-in tail by the last sizing mechanism visible
in the audit rows:

  legal_floor
      executed target > pre_clamp; session's legal min-raise floor enlarged it.

  bet_decision_target
      tocall==0 and reconstructed pot*intent_size target equals pre_clamp.

  bet_shape_changed
      tocall==0 and reconstructed decision target differs from pre_clamp;
      personality shape_size changed a non-full-stack target.

  raise_pre_target
      raise with executed==pre_clamp.  The CSV cannot reconstruct the response
      multiplier before shape_size, so this stays deliberately unresolved.

This tool is descriptive only.  It does not choose an effective-all-in cutoff.
"""
from __future__ import print_function

import argparse
import collections
import csv


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rnd100(x):
    return int(round(float(x) / 100.0)) * 100


def classify(r):
    committed = num(r.get('committed')) or 0.0
    pre = num(r.get('pre_clamp')) or 0.0
    tocall = num(r.get('tocall')) or 0.0
    action = r.get('action')

    if committed > pre + 1e-9:
        return 'legal_floor'

    if action == 'bet' and tocall <= 0:
        size = num(r.get('intent_size'))
        pot = num(r.get('pot'))
        stack = num(r.get('stack'))
        if size is not None and pot is not None and stack is not None and size > 0:
            raw = min(stack, rnd100(pot * size))
            if abs(raw - pre) < 1e-9:
                return 'bet_decision_target'
            return 'bet_shape_changed'
        return 'bet_unknown'

    if action == 'raise':
        return 'raise_pre_target'

    return 'other'


def f(x, nd=2):
    if x is None:
        return '-'
    if nd == 0:
        return str(int(round(x)))
    return ('%.*f' % (nd, x)).rstrip('0').rstrip('.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv_path')
    ap.add_argument('--min-commit', type=float, default=0.80)
    ap.add_argument('--top', type=int, default=40)
    a = ap.parse_args()

    with open(a.csv_path, newline='', encoding='utf-8') as fp:
        rows = list(csv.DictReader(fp))

    for r in rows:
        r['_commit'] = num(r.get('commit_frac')) or 0.0
        r['_rbb'] = num(r.get('residual_bb'))
        r['_rpot'] = num(r.get('residual_pot'))
        r['_source'] = classify(r)

    nonall = [r for r in rows if r['_commit'] < 1.0 - 1e-12]
    tail = [r for r in nonall if r['_commit'] >= a.min_commit]

    print('# near-all-in existing-row source analysis')
    print('rows=%d non-all-in=%d commit>=%.0f%%=%d'
          % (len(rows), len(nonall), 100*a.min_commit, len(tail)))
    print()

    print('## source by commit threshold')
    print('%-22s %7s %7s %7s %7s'
          % ('source', '>=80', '>=90', '>=95', '<=2BB'))
    sources = sorted(set(r['_source'] for r in nonall))
    for s in sources:
        q = [r for r in nonall if r['_source'] == s]
        c80 = sum(r['_commit'] >= .80 for r in q)
        c90 = sum(r['_commit'] >= .90 for r in q)
        c95 = sum(r['_commit'] >= .95 for r in q)
        c2 = sum(r['_commit'] >= .80 and r['_rbb'] is not None and r['_rbb'] <= 2
                 for r in q)
        print('%-22s %7d %7d %7d %7d' % (s, c80, c90, c95, c2))

    print()
    print('## candidate grid (descriptive only)')
    for cf in (.90, .95):
        for bb in (1.0, 2.0, 3.0, 5.0):
            n = sum(r['_commit'] >= cf and r['_rbb'] is not None and r['_rbb'] <= bb
                    for r in nonall)
            print('  commit>=%.0f%% AND residual<=%.0fBB : %d'
                  % (100*cf, bb, n))
    for cf in (.90, .95):
        for rp in (.02, .05, .10):
            n = sum(r['_commit'] >= cf and r['_rpot'] is not None and r['_rpot'] <= rp
                    for r in nonall)
            print('  commit>=%.0f%% AND residual<=%.0f%%pot : %d'
                  % (100*cf, 100*rp, n))

    have_eff = any(num(r.get('effective_cap')) for r in rows)
    if have_eff:
        print()
        print('## effective-stack side split (non-all-in only)')
        sides = collections.Counter()
        for r in nonall:
            actor = num(r.get('actor_cap'))
            opp = num(r.get('opp_cap_max'))
            eff = num(r.get('effective_cap'))
            committed = num(r.get('committed')) or 0.0
            if not actor or not opp or not eff:
                continue
            side = ('actor_effective' if actor <= opp + 1e-9
                    else 'opponent_effective')
            eff_frac = min(committed, eff) / eff
            sides[(side, 'all')] += 1
            for t in (.90, .95, .98, 1.0):
                if eff_frac >= t - 1e-12:
                    sides[(side, t)] += 1

        print('%-20s %7s %7s %7s %7s %7s'
              % ('side', 'all', '>=90', '>=95', '>=98', '>=100'))
        for side in ('actor_effective', 'opponent_effective'):
            print('%-20s %7d %7d %7d %7d %7d'
                  % (side,
                     sides[(side, 'all')],
                     sides[(side, .90)],
                     sides[(side, .95)],
                     sides[(side, .98)],
                     sides[(side, 1.0)]))

        # Unmatched excess is a round-accounting question, not a near-all-in-only
        # question, so count it over every aggressive row, including physical all-ins.
        overshoot = []
        for r in rows:
            actor = num(r.get('actor_cap'))
            opp = num(r.get('opp_cap_max'))
            committed = num(r.get('committed')) or 0.0
            if not actor or not opp:
                continue
            if actor > opp + 1e-9 and committed > opp + 1e-9:
                overshoot.append((committed - opp, r))

        print()
        print('## target beyond deepest opponent cap (all aggressive actions)')
        n_allin = sum((num(r.get('commit_frac')) or 0.0) >= 1.0 - 1e-12
                      for _, r in overshoot)
        print('  count: %d  (physical all-in %d / non-all-in %d)'
              % (len(overshoot), n_allin, len(overshoot) - n_allin))
        if overshoot:
            print('  total excess chips: %d'
                  % int(round(sum(x[0] for x in overshoot))))
            print('  largest examples:')
            for over, r in sorted(overshoot, key=lambda x: x[0], reverse=True)[:10]:
                print('    seed %s H%s %s %s plan=%s actor=%s oppmax=%s '
                      'target=%s excess=%s'
                      % (r.get('seed'), r.get('hand_no'), r.get('street'),
                         r.get('action'), r.get('plan'), r.get('actor_cap'),
                         r.get('opp_cap_max'), r.get('committed'), f(over, 0)))

    print()
    print('## remaining tail')
    ranked = sorted(tail, key=lambda r: r['_commit'], reverse=True)
    for r in ranked[:max(0, a.top)]:
        print(
            '  %(src)-19s seed %(seed)s H%(hand)s %(street)s %(action)s '
            'plan=%(plan)s commit=%(commit)s remain=%(remain)sBB '
            'remain/pot=%(rpot)s stack=%(stack)s exec=%(exec)s pre=%(pre)s '
            'intent=%(intent)s'
            % {
                'src': r['_source'],
                'seed': r.get('seed'),
                'hand': r.get('hand_no'),
                'street': r.get('street'),
                'action': r.get('action'),
                'plan': r.get('plan'),
                'commit': '%.1f%%' % (100*r['_commit']),
                'remain': f(r['_rbb']),
                'rpot': f(r['_rpot']),
                'stack': r.get('stack'),
                'exec': r.get('committed'),
                'pre': r.get('pre_clamp'),
                'intent': r.get('intent_size'),
            })

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
