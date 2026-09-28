#!/usr/bin/env python3
"""Targeted verifier for Human Model v3 preflop recall -> reasoning -> temperament.

This is deliberately structural.  It does not tune against a target population
or assert that the current GTO reference layer is correct.

Checks:
  M1 matched studied conditions: V3 == V2 for open/defend widths.
  R1 unfamiliar RFI: stronger existing reasoning skills move the remembered
     chart toward the current-condition reference.
  R2 unfamiliar defend: same property for total continue and 3bet widths.
  S1 weak reasoning stays closer to the studied anchor than strong reasoning.
  N1 no new strategic concept was introduced by V3.
  E1 unified exploit base weight matches read_opponent.w under V3.
  E2 exploit evidence weight is monotone in evidence and blind observers stay neutral.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gto as G
import persona as PS
import preflop as PF


def mkprof(knowledge=8.0, loose=5.0, aggr=5.0,
           stack_reason=5.0, positional=5.0, potodds=5.0):
    c = {k: 5.0 for k in PS.ALL_CONCEPTS}
    c['pf_range'] = c['pf_defend'] = float(knowledge)
    c['stack_decay'] = float(stack_reason)
    c['positional'] = float(positional)
    c['potodds'] = float(potodds)
    t = {k: 5.0 for k in PS.TEMPER}
    t['looseness'] = float(loose)
    t['aggression'] = float(aggr)
    return {
        'id': None, 'concepts': c, 'temper': t, 'type': 'X',
        'aggr': float(aggr), 'bluff': 5.0,
    }


def widths(prof, def_pos='BB', opener='HJ', seats=8, bb=40.0,
           ante=True, open_bb=2.5):
    tp, tot = PF.defend_thresholds(
        prof, def_pos, opener, bb, open_bb=open_bb, seats=seats, ante=ante)
    return float(tp), float(tot)


def closer(x, target, anchor):
    return abs(x - target) <= abs(anchor - target) + 1e-12


def main():
    rows = {}
    old_v3 = PS.PREFLOP_REASONING_V3
    old_v2 = PS.GTO_MEMORY_V2
    old_exp = PS.EXPLOIT_WEIGHT_V3
    try:
        # ----- M1: inside studied family, V3 must not change behavior -----
        p = mkprof(knowledge=6.0, loose=7.0, aggr=6.0,
                   stack_reason=1.0, positional=7.0, potodds=2.0)
        PS.GTO_MEMORY_V2 = True
        PS.PREFLOP_REASONING_V3 = False
        o_old = PS.open_pct(p, 'CO', 8, 40.0, True)
        d_old = widths(p, 'BB', 'HJ', 8, 40.0, True, 2.5)
        PS.PREFLOP_REASONING_V3 = True
        o_new = PS.open_pct(p, 'CO', 8, 40.0, True)
        d_new = widths(p, 'BB', 'HJ', 8, 40.0, True, 2.5)
        m1 = (o_old == o_new and d_old == d_new)
        rows['M1_matched_identity'] = {
            'pass': m1, 'open_v2': o_old, 'open_v3': o_new,
            'def_v2': d_old, 'def_v3': d_new,
        }

        # ----- R1: unfamiliar RFI, reasoning repairs anchor -> target -----
        # Neutral temperament isolates condition reasoning from personality.
        low = mkprof(knowledge=8.0, loose=5.0, aggr=5.0,
                     stack_reason=0.0, positional=0.0, potodds=0.0)
        high = mkprof(knowledge=8.0, loose=5.0, aggr=5.0,
                      stack_reason=10.0, positional=10.0, potodds=10.0)
        pos, seats, bb, ante = 'HJ', 9, 150.0, False
        target = G.rfi(pos, seats, bb, ante)
        anchor = PS.gto_studied_anchor('rfi', pos, seats, bb, ante)
        low_v = PS.open_pct(low, pos, seats, bb, ante)
        high_v = PS.open_pct(high, pos, seats, bb, ante)
        # open_pct also applies the long-standing positional flattening.  Use
        # the same flattening on target/anchor for a like-for-like assertion.
        def flattened(pf, width, s, depth, a):
            pos_acc = 0.10 + 0.80 * min(1.0, PS.sk(pf, 'positional') / 8.0)
            flat = (1.0 - pos_acc) * 0.60
            return width*(1.0-flat) + G.avg_rfi(s, depth, a)*flat
        S = PS.GTO_STUDIED['rfi']
        bb_s = max(S['bb'][0], min(S['bb'][1], bb))
        low_target = flattened(low, target, seats, bb, ante)
        low_anchor = flattened(low, anchor, S['seats'], bb_s, S['ante'])
        high_target = flattened(high, target, seats, bb, ante)
        high_anchor = flattened(high, anchor, S['seats'], bb_s, S['ante'])
        r1 = (closer(high_v, high_target, high_anchor)
              and abs(high_v-high_target) < abs(low_v-low_target))
        s1 = abs(low_v-low_anchor) < abs(low_v-low_target)
        rows['R1_rfi_reasoning'] = {
            'pass': r1, 'target': target, 'anchor': anchor,
            'low': low_v, 'high': high_v,
            'low_reasoning': PS.preflop_reasoning_confidence(
                low, 'rfi', pos, seats, bb, ante),
            'high_reasoning': PS.preflop_reasoning_confidence(
                high, 'rfi', pos, seats, bb, ante),
        }
        rows['S1_low_reasoner_stays_near_anchor'] = {
            'pass': s1, 'low': low_v,
            'flattened_anchor': low_anchor, 'flattened_target': low_target,
        }

        # ----- R2: unfamiliar defend, both widths move toward target -----
        dp, op, seats, bb, ante, ob = 'BB', 'HJ', 9, 150.0, False, 2.5
        tgt_tot = G.defend_pct(dp, op, seats, bb, ante, ob)
        tgt_tp = G.threebet_pct(dp, op, seats, bb, ante, ob)
        anc_tp, anc_tot = PS.gto_studied_anchor(
            'defend', dp, seats, bb, ante, opener_pos=op, open_bb=ob)
        low_tp, low_tot = widths(low, dp, op, seats, bb, ante, ob)
        high_tp, high_tot = widths(high, dp, op, seats, bb, ante, ob)
        r2 = (abs(high_tot-tgt_tot) < abs(low_tot-tgt_tot)
              and abs(high_tp-tgt_tp) < abs(low_tp-tgt_tp)
              and closer(high_tot, tgt_tot, anc_tot)
              and closer(high_tp, tgt_tp, anc_tp))
        rows['R2_defend_reasoning'] = {
            'pass': r2,
            'target': {'tp': tgt_tp, 'tot': tgt_tot},
            'anchor': {'tp': anc_tp, 'tot': anc_tot},
            'low': {'tp': low_tp, 'tot': low_tot},
            'high': {'tp': high_tp, 'tot': high_tot},
        }

        # ----- N1: V3 reuses existing concepts only -----
        needed = {'pf_range', 'pf_defend', 'stack_decay', 'positional', 'potodds'}
        rows['N1_existing_concepts_only'] = {
            'pass': needed.issubset(set(PS.ALL_CONCEPTS)),
            'used': sorted(needed),
        }

        # ----- E1/E2: one base exploit weight, evidence monotonicity -----
        exp = mkprof(knowledge=5.0, loose=5.0, aggr=5.0,
                     stack_reason=5.0, positional=5.0, potodds=5.0)
        exp['temper']['adaptability'] = 7.0
        exp['temper']['attention'] = 7.0
        exp['concepts']['range_read'] = 7.0
        exp['concepts']['sizing_tell'] = 7.0
        opp = {'confidence': 0.8, 'n': 12, 'ftb': 0.60, 'bluff': 5.5,
               'aggr': 6.0, 'cbet': 0.65, 'barrel': 0.52}
        PS.EXPLOIT_WEIGHT_V3 = True
        ew = PS.exploit_weight(exp, opp['confidence'], opp['n'])
        rd = PS.read_opponent(exp, opp)
        rows['E1_exploit_base_unified'] = {
            'pass': ew == rd.get('w'), 'exploit_weight': ew,
            'read_w': rd.get('w'),
        }
        seq = [PS.exploit_weight(exp, 0.8, n) for n in (0, 1, 3, 6, 12, 24)]
        mono = all(b >= a for a, b in zip(seq, seq[1:]))
        blind = mkprof()
        blind['temper']['adaptability'] = 9.0
        blind['temper']['attention'] = 0.0
        blind['concepts']['range_read'] = 0.0
        blind['concepts']['sizing_tell'] = 0.0
        blind_rd = PS.read_opponent(blind, opp)
        rows['E2_exploit_evidence_and_perception'] = {
            'pass': mono and blind_rd.get('w', 0.0) == 0.0,
            'n_curve': seq, 'blind_read': blind_rd,
        }

        passed = all(v['pass'] for v in rows.values())
        print(json.dumps({'pass': passed, 'checks': rows}, indent=2, sort_keys=True))
        raise SystemExit(0 if passed else 1)
    finally:
        PS.PREFLOP_REASONING_V3 = old_v3
        PS.GTO_MEMORY_V2 = old_v2
        PS.EXPLOIT_WEIGHT_V3 = old_exp


if __name__ == '__main__':
    main()
