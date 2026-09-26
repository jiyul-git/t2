#!/usr/bin/env python3
"""F7-B1D7: verify RNG-free defend likelihoods against live branch semantics.

This is a targeted wiring verifier, not a balance test.

For representative persona/context/hand combinations it:
1) asks preflop.defend_action_likelihoods() for the deterministic category model;
2) feeds scripted RNG rolls into the still-production defend_decision();
3) checks that the live branch chosen for those exact rolls matches the helper's
   hot-zone + mixed-weight boundaries;
4) checks call-off one-hot behavior and probability normalization.

The production function still owns sizing/form RNG.  This verifier compares only
the observable categories required by opponent-range reconstruction:
attack / call / fold.
"""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import persona as PS
import preflop as PF


class SeqRng:
    def __init__(self, values):
        self.values = list(values)
        self.i = 0

    def random(self):
        if self.i < len(self.values):
            v = self.values[self.i]
            self.i += 1
            return v
        return 0.5


def hand_for_class(c):
    if len(c) == 2:
        return (c[0] + 's', c[1] + 'h')
    if c[-1] == 's':
        return (c[0] + 's', c[1] + 's')
    return (c[0] + 's', c[1] + 'h')


def cat(action):
    a = action[0] if isinstance(action, (tuple, list)) else action
    if a in ('3bet', 'raise', 'shove', 'allin'):
        return 'attack'
    if a == 'call':
        return 'call'
    if a == 'fold':
        return 'fold'
    raise AssertionError('unexpected action: %r' % (action,))


def expected_for_rolls(lik, u_hot, u_mix):
    if lik['calloff']:
        if lik['call'] == 1.0:
            return 'call'
        return 'fold'

    if lik['hot_attack'] > 0.0 and u_hot < lik['hot_attack']:
        return 'attack'

    total = lik['total_weight']
    if total <= 0.0:
        return 'fold'
    x = u_mix * total
    if x < lik['w_raise']:
        return 'attack'
    if x < lik['w_raise'] + lik['w_call']:
        return 'call'
    return 'fold'


def main():
    profs = [
        PS.make_player(random.Random(1100 + i), q, i)
        for i, q in enumerate((0.25, 0.55, 0.85, 1.10))
    ]

    exploits = [
        None,
        {'w': 0.65, 'open_gap': 0.30, 'f2tb_gap': 0.22,
         'fold_gap': 0.18, 'fb_gap': 0.16,
         'tb_gap': 0.24, 'tb_polar': 0.12, 'f2fb_gap': 0.20},
        {'w': 0.80, 'open_gap': -0.20, 'f2tb_gap': -0.18,
         'fold_gap': -0.15, 'fb_gap': 0.00,
         'tb_gap': -0.16, 'tb_polar': 0.00, 'f2fb_gap': -0.12},
    ]

    contexts = []
    for prof in profs:
        for def_pos, opener_pos in (
            ('BB', 'BTN'), ('SB', 'CO'), ('CO', 'UTG+1'), ('HJ', 'LJ')
        ):
            for stack_bb in (18.0, 42.0, 110.0):
                for raise_level in (1, 2):
                    for n_callers in (0, 1):
                        for exploit in exploits:
                            contexts.append(dict(
                                prof=prof, def_pos=def_pos, opener_pos=opener_pos,
                                bb=stack_bb, open_bb=(2.5 if raise_level == 1 else 8.5),
                                n_callers=n_callers, raise_level=raise_level,
                                stack_bb=stack_bb, exploit=exploit,
                                bf=1.0, seats=9, ante=True,
                                opener_allin=False, can_raise=True,
                                pot_bb=None, to_call_bb=None,
                            ))

    # Explicit pure call-off / short-shove contexts.
    calloff_contexts = []
    for prof in profs[:2]:
        calloff_contexts.extend([
            dict(prof=prof, def_pos='BB', opener_pos='BTN',
                 bb=20.0, open_bb=19.0, n_callers=0, raise_level=1,
                 stack_bb=20.0, exploit=None, bf=1.0, seats=9, ante=True,
                 opener_allin=True, can_raise=True, pot_bb=22.0, to_call_bb=18.0),
            dict(prof=prof, def_pos='SB', opener_pos='CO',
                 bb=80.0, open_bb=18.0, n_callers=0, raise_level=1,
                 stack_bb=80.0, exploit=None, bf=1.0, seats=9, ante=True,
                 opener_allin=True, can_raise=False, pot_bb=21.0, to_call_bb=17.5),
        ])

    classes = sorted(PF.PCT, key=lambda c: PF.PCT[c])
    # Every class is checked for probability invariants.  Scripted live-branch
    # checks use a deterministic stride to keep Termux runtime modest.
    roll_points = (0.0, 0.03, 0.17, 0.49, 0.73, 0.97, 0.999999)

    inv_n = 0
    branch_n = 0
    calloff_n = 0
    hot_n = 0
    mismatches = []

    for ci, ctx in enumerate(contexts):
        for hi, hc in enumerate(classes):
            hand = hand_for_class(hc)
            lik = PF.defend_action_likelihoods(hand=hand, **ctx)

            vals = [lik['attack'], lik['call'], lik['fold']]
            if any((not math.isfinite(x) or x < -1e-12 or x > 1.0 + 1e-12)
                   for x in vals):
                raise AssertionError(('invalid probability', hc, ctx, lik))
            if abs(sum(vals) - 1.0) > 1e-10:
                raise AssertionError(('probability sum', hc, ctx, lik))
            inv_n += 1

            if lik['hot_attack'] > 0:
                hot_n += 1

            # Deterministic spread across all contexts/classes.
            if (ci * 17 + hi * 31) % 29 != 0:
                continue

            for u0 in roll_points:
                for u1 in roll_points:
                    expected = expected_for_rolls(lik, u0, u1)
                    if lik['hot_attack'] > 0:
                        seq = [u0, u1, 0.5, 0.5]
                    else:
                        seq = [u1, 0.5, 0.5]
                    got = cat(PF.defend_decision(
                        hand=hand, rng=SeqRng(seq),
                        tilt=0.0, field_q=0.6,
                        payout_flat=0.0, reentry=False, progress=0.0,
                        **ctx
                    ))
                    branch_n += 1
                    if got != expected:
                        mismatches.append({
                            'class': hc,
                            'ctx': {k: v for k, v in ctx.items()
                                    if k not in ('prof', 'exploit')},
                            'hot': lik['hot_attack'],
                            'weights': (lik['w_raise'], lik['w_call'], lik['w_fold']),
                            'rolls': (u0, u1),
                            'expected': expected,
                            'got': got,
                        })
                        if len(mismatches) >= 10:
                            break
                if len(mismatches) >= 10:
                    break
            if len(mismatches) >= 10:
                break
        if len(mismatches) >= 10:
            break

    for ctx in calloff_contexts:
        for hc in classes:
            hand = hand_for_class(hc)
            lik = PF.defend_action_likelihoods(hand=hand, **ctx)
            if not lik['calloff']:
                raise AssertionError(('expected calloff', hc, ctx, lik))
            got = cat(PF.defend_decision(
                hand=hand, rng=SeqRng([0.0, 0.99]),
                tilt=0.0, field_q=0.6,
                payout_flat=0.0, reentry=False, progress=0.0,
                **ctx
            ))
            expected = 'call' if lik['call'] == 1.0 else 'fold'
            calloff_n += 1
            if got != expected:
                mismatches.append({
                    'class': hc, 'calloff': True,
                    'expected': expected, 'got': got, 'lik': lik,
                })
                break

    print({
        'probability_invariants': inv_n,
        'scripted_branch_checks': branch_n,
        'calloff_checks': calloff_n,
        'hotzone_positive_states': hot_n,
        'mismatches': len(mismatches),
    })
    if mismatches:
        for row in mismatches[:10]:
            print('MISMATCH', row)
        raise SystemExit(1)

    print('PASS F7-B1D7 defend likelihood shadow contract')
    print('NOTE: defend_decision production control flow is unchanged in this step.')


if __name__ == '__main__':
    main()
