#!/usr/bin/env python3
"""F7-B1D7: exact behavior/RNG parity for the defend wiring refactor.

Reference:
    git commit 5eb848c
    (the user-validated B1D7 likelihood-shadow checkpoint, before production
     defend_decision was rewired to consume the helper)

Current:
    working-tree preflop.defend_decision

For deterministic persona/context/hand/RNG combinations this compares:
- exact returned action tuple, including sizing;
- exact random.Random state after the call.

Any mismatch means the refactor changed production behavior or RNG consumption.
No live state/files are touched.
"""
import random
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import persona as PS
import preflop as CUR

REF = '5eb848c'


def load_reference():
    src = subprocess.check_output(
        ['git', 'show', '%s:preflop.py' % REF],
        cwd=str(ROOT), text=True)
    mod = types.ModuleType('preflop_b1d7_reference')
    # preflop.py derives D from __file__ to load pf_rank.json.
    mod.__file__ = str(ROOT / 'preflop.py')
    exec(compile(src, mod.__file__, 'exec'), mod.__dict__)
    return mod


def hand_for_class(c):
    if len(c) == 2:
        return (c[0] + 's', c[1] + 'h')
    if c[-1] == 's':
        return (c[0] + 's', c[1] + 's')
    return (c[0] + 's', c[1] + 'h')


def main():
    old = load_reference()

    profs = [
        PS.make_player(random.Random(2100 + i), q, 100 + i)
        for i, q in enumerate((0.20, 0.50, 0.80, 1.10))
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
    for pi, prof in enumerate(profs):
        for def_pos, opener_pos in (
            ('BB', 'BTN'), ('SB', 'CO'), ('BTN', 'HJ'),
            ('CO', 'UTG+1'), ('HJ', 'LJ')
        ):
            for stack_bb in (13.0, 18.0, 26.0, 42.0, 110.0):
                for raise_level in (1, 2, 3):
                    for n_callers in (0, 1, 2):
                        # Deterministically thin the Cartesian product but keep
                        # every semantic axis represented.
                        for ei, exploit in enumerate(exploits):
                            if (pi + int(stack_bb) + raise_level
                                    + n_callers + ei) % 3:
                                continue
                            open_bb = (
                                2.5 if raise_level == 1 else
                                8.5 if raise_level == 2 else 19.0
                            )
                            contexts.append(dict(
                                prof=prof,
                                def_pos=def_pos,
                                opener_pos=opener_pos,
                                bb=stack_bb,
                                open_bb=open_bb,
                                n_callers=n_callers,
                                raise_level=raise_level,
                                stack_bb=stack_bb,
                                tilt=0.0,
                                field_q=0.6,
                                exploit=exploit,
                                bf=1.0,
                                payout_flat=0.0,
                                reentry=False,
                                progress=0.0,
                                seats=9,
                                ante=True,
                                opener_allin=False,
                                can_raise=True,
                                pot_bb=None,
                                to_call_bb=None,
                            ))

    # Public-action edge cases that matter to the observer contract.
    for prof in profs:
        contexts.extend([
            # incomplete raise: raising rights closed, but not a pure all-in calloff
            dict(prof=prof, def_pos='BB', opener_pos='BTN',
                 bb=80.0, open_bb=9.0, n_callers=0, raise_level=1,
                 stack_bb=80.0, tilt=0.0, field_q=0.6, exploit=None, bf=1.0,
                 payout_flat=0.0, reentry=False, progress=0.0,
                 seats=9, ante=True, opener_allin=False, can_raise=False,
                 pot_bb=12.0, to_call_bb=8.0),
            # short all-in, no raise right -> pure calloff
            dict(prof=prof, def_pos='SB', opener_pos='CO',
                 bb=80.0, open_bb=18.0, n_callers=0, raise_level=1,
                 stack_bb=80.0, tilt=0.0, field_q=0.6, exploit=None, bf=1.0,
                 payout_flat=0.0, reentry=False, progress=0.0,
                 seats=9, ante=True, opener_allin=True, can_raise=False,
                 pot_bb=21.0, to_call_bb=17.5),
            # hero effectively all-in to call
            dict(prof=prof, def_pos='BB', opener_pos='BTN',
                 bb=20.0, open_bb=19.0, n_callers=0, raise_level=1,
                 stack_bb=20.0, tilt=0.0, field_q=0.6, exploit=None, bf=1.35,
                 payout_flat=0.0, reentry=False, progress=0.0,
                 seats=9, ante=True, opener_allin=True, can_raise=True,
                 pot_bb=22.0, to_call_bb=18.0),
            # opener all-in but raising is still legally available
            dict(prof=prof, def_pos='BB', opener_pos='BTN',
                 bb=100.0, open_bb=22.0, n_callers=0, raise_level=1,
                 stack_bb=100.0, tilt=0.0, field_q=0.6,
                 exploit=exploits[1], bf=1.0,
                 payout_flat=0.0, reentry=False, progress=0.0,
                 seats=9, ante=True, opener_allin=True, can_raise=True,
                 pot_bb=25.0, to_call_bb=21.0),
        ])

    classes = sorted(CUR.PCT, key=lambda c: CUR.PCT[c])
    checked = 0
    hot_context_checks = 0
    calloff_checks = 0
    raise_checks = 0
    mismatches = []

    for ci, ctx in enumerate(contexts):
        for hi, hc in enumerate(classes):
            # Full hand-class coverage, three deterministic RNG streams spread
            # across the space.  The stride keeps runtime reasonable.
            if (ci * 13 + hi * 7) % 5:
                continue
            hand = hand_for_class(hc)
            for ri in range(3):
                seed = 700000 + ci * 1009 + hi * 37 + ri * 1000003
                ro = random.Random(seed)
                rn = random.Random(seed)

                ao = old.defend_decision(hand=hand, rng=ro, **ctx)
                an = CUR.defend_decision(hand=hand, rng=rn, **ctx)
                checked += 1

                lik = CUR.defend_action_likelihoods(
                    prof=ctx['prof'], def_pos=ctx['def_pos'],
                    opener_pos=ctx['opener_pos'], hand=hand,
                    bb=ctx['bb'], open_bb=ctx['open_bb'],
                    n_callers=ctx['n_callers'],
                    raise_level=ctx['raise_level'],
                    stack_bb=ctx['stack_bb'],
                    exploit=ctx['exploit'], bf=ctx['bf'],
                    seats=ctx['seats'], ante=ctx['ante'],
                    opener_allin=ctx['opener_allin'],
                    can_raise=ctx['can_raise'],
                    pot_bb=ctx['pot_bb'], to_call_bb=ctx['to_call_bb'])
                if lik['hot_attack'] > 0:
                    hot_context_checks += 1
                if lik['calloff']:
                    calloff_checks += 1
                if ao[0] in ('3bet', 'raise', 'shove', 'allin'):
                    raise_checks += 1

                same_action = (ao == an)
                same_rng = (ro.getstate() == rn.getstate())
                if not (same_action and same_rng):
                    mismatches.append({
                        'class': hc,
                        'seed': seed,
                        'ctx': {k: v for k, v in ctx.items()
                                if k not in ('prof', 'exploit')},
                        'old': ao,
                        'new': an,
                        'same_rng': same_rng,
                        'lik': {
                            'hot_attack': lik['hot_attack'],
                            'weights': (lik['w_raise'],
                                        lik['w_call'],
                                        lik['w_fold']),
                            'calloff': lik['calloff'],
                        },
                    })
                    if len(mismatches) >= 10:
                        break
            if len(mismatches) >= 10:
                break
        if len(mismatches) >= 10:
            break

    print({
        'reference_commit': REF,
        'exact_checks': checked,
        'hotzone_checks': hot_context_checks,
        'calloff_checks': calloff_checks,
        'attack_outputs': raise_checks,
        'action_or_rng_mismatches': len(mismatches),
    })
    if mismatches:
        for row in mismatches:
            print('MISMATCH', row)
        raise SystemExit(1)

    print('PASS F7-B1D7 defend rewire exact action/RNG parity')


if __name__ == '__main__':
    main()
