#!/usr/bin/env python3
"""R2-B: freeze what the current code produces for 9-max (and 8-max) vs-open defense.

Read-only.  No production value is changed.  Three layers are reported per spot:

  L0 prior     gto.defend_pct / gto.threebet_pct (the reference layer itself)
  L1 threshold preflop.defend_thresholds for the max-skill neutral-temper profile
               (normalize/saturate, callers=0, short-stack partition, raise_level=1)
  L2 realized  combo-weighted preflop.defend_action_likelihoods over all 1326 combos
               for the same profile (attack / call / fold actually played),
               exploit=None, stack_bb=bb, can_raise=True

open_bb is the deterministic part of preflop.open_size_bb for the max-skill feel
(ante=True); the max-skill player adds about +-2.3% noise and chip rounding on top.

Usage: python tools/r2_freeze_defend_baseline.py [out.json]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import persona as PS, preflop as PF, gto as G, table as TB, ranges as R  # noqa: E402

STACKS = [15, 20, 25, 30, 40, 60, 100]


def maxskill():
    p = {'concepts': {k: 10.0 for k in PS.ALL_CONCEPTS},
         'latent': {'study': 10.0, 'aggro': 5.0, 'exp': 10.0},
         'temper': {'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0, 'tilt_prone': 0.0,
                    'tilt_recovery': 10.0, 'discipline': 10.0, 'adaptability': 10.0,
                    'consistency': 10.0, 'attention': 10.0, 'slowplay_taste': 5.0,
                    'tilt_swing': 5.0, 'tilt_stack': 0.0}}
    p.update(PS.derive(p))
    return p


def open_size(prof, pos, bb):
    feel = PF.feel_of(prof, bb)
    base = 2.15 + 0.35 * max(0.0, feel - 0.40) + (0.6 if pos == 'SB' else 0.0)
    return round(base, 3)


CLASSES = {}
for c in R._SORTED:
    CLASSES.setdefault(PF.cls(list(c)), list(c))
N_COMBO = {k: (6 if len(k) == 2 else 4 if k.endswith('s') else 12) for k in CLASSES}


def realized(prof, dp, op, bb, ob, seats):
    a = c = f = hot = 0.0
    for k, hand in CLASSES.items():
        lk = PF.defend_action_likelihoods(prof, dp, op, hand, bb, ob, 0, raise_level=1,
                                          stack_bb=bb, exploit=None, bf=1.0, seats=seats,
                                          ante=True, can_raise=True)
        n = N_COMBO[k]
        a += n * lk['attack']; c += n * lk['call']; f += n * lk['fold']
        hot += n * lk['hot_attack']
    return a / 1326, c / 1326, f / 1326, hot / 1326


def spots(seats):
    _, pre, _ = TB.orders(seats)
    for i, op in enumerate(pre[:-1]):
        for dp in pre[i + 1:]:
            yield op, dp


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    prof = maxskill()
    rows = []
    for seats in (9, 8):
        for bb in STACKS:
            for op, dp in spots(seats):
                ob = open_size(prof, op, bb)
                tot0 = G.defend_pct(dp, op, seats, bb, True, ob)
                tp0 = G.threebet_pct(dp, op, seats, bb, True, ob)
                tp1, tot1 = PF.defend_thresholds(prof, dp, op, bb, ob, 0, 1, seats, True)
                a, c, f, hot = realized(prof, dp, op, bb, ob, seats)
                rows.append({
                    'seats': seats, 'bb': bb, 'opener': op, 'defender': dp, 'open_bb': ob,
                    'ante': '1bb BBA',
                    'path': 'mtt8_calibrated' if G._use_mtt8_ante_defense(dp, seats, True)
                            else 'legacy_formula',
                    'L0_defend': round(tot0, 4), 'L0_3bet': round(tp0, 4),
                    'L0_call': round(tot0 - tp0, 4), 'L0_fold': round(1 - tot0, 4),
                    'L0_3bet_share': round(tp0 / tot0, 4) if tot0 else None,
                    'L1_defend': round(tot1, 4), 'L1_3bet': round(tp1, 4),
                    'L2_attack': round(a, 4), 'L2_call': round(c, 4), 'L2_fold': round(f, 4),
                    'L2_defend': round(a + c, 4), 'L2_hot_reshove': round(hot, 4),
                    'L2_3bet_share': round(a / (a + c), 4) if a + c > 0 else None,
                })
    res = {'base_commit': os.popen('git -C %s rev-parse HEAD' % ROOT).read().strip(),
           'profile': 'max-skill (all concepts 10, neutral temperament 5, tilt 0, exploit None)',
           'rows': rows}
    s = json.dumps(res, indent=1, ensure_ascii=False)
    if out_path:
        open(out_path, 'w').write(s + '\n')
    else:
        print(s)


if __name__ == '__main__':
    main()
