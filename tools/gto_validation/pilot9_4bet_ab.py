#!/usr/bin/env python3
"""Conditional 4-bet A/B at one HU 3-bet spot of state T (max_raises = 2 audit; no preflop re-solve).

Subgame rooted at the opener's node facing the 3-bet, ranges fixed at state T:
  opener range  = class_reach_before at that node (T export), 3-bettor range = its terminal range (class_reach_normalized).
  A (current tree): opener fold / call.                         call -> 3-bet-pot flop terminal (gross from the T3 table)
  B (4-bet jam added): opener fold / call / jam; 3-bettor facing the jam: fold / call (all-in, pot x equity, no realization).
Equity table: the preflop solver's own class table (t2_eq_dump, PREFLOP_EQ_SEED=202, 1200 samples).
Solved by CFR+ (opener and 3-bettor simultaneous per-class strategies), 20k iterations.
Caveats: the 3-bettor's 3-bet range is held fixed (in the full game it would adapt); the call branch keeps T's per-class flop
values although B's calling range is narrower (variant B_eq replaces them by pot x equity vs the current 3-bet range to show
the sensitivity). Output: frequencies and EVs per side, A vs B.
    python3 tools/gto_validation/pilot9_4bet_ab.py <name> [<name> ...]     (names from t3_selection.json, e.g. n51 n196)
"""
import json
import sys

import numpy as np

R = '/home/user/gto_ckpt/'
OUT = '/home/user/t2/data/gto_validation/pilot9/step3/'
EQ = np.array(json.load(open(R + 'step3/eq_table_202_1200.json'))['eq'], dtype=np.float64)
SEL = {t['name']: t for t in json.load(open(OUT + 't3_selection.json'))['terminals']}


def combos(h):
    return 6 if len(h) == 2 else (4 if h[2] == 's' else 12)


def solve(name, iters=20000):
    t = json.load(open(R + f'step3/t3/T/export_{name}.json'))
    lab = t['class_labels']
    po = t['path_nodes'][-1]
    spec = SEL[name]['spec'].split(',')
    raises = [i for i, a in enumerate(spec) if a == 'raise']
    p3 = t['path_nodes'][raises[1]]
    op, tb = po['actor'], p3['actor']
    pl = {p['position']: p for p in t['players']}
    a = t['config']['ante'] if 'ante' in t['config'] else 1 / 9
    inv_o, inv_3 = pl[op]['invested_bb'], pl[tb]['invested_bb']      # at the terminal (after the call): both = 3-bet size + ante
    pot_T = t['pot_bb']
    call_amt = inv_o - (2.0 + a) if op != 'SB' else inv_o - (2.5 + a)
    inv_o0 = inv_o - call_amt                                          # opener's investment at the decision
    pot0 = pot_T - call_amt                                            # pot at the decision
    stack = t['config']['stack']
    dead = pot_T - inv_o - inv_3
    pot_ai = 2 * (stack + a) + dead
    w_o = np.array(po['class_reach_before'], dtype=np.float64)
    w_o = w_o / w_o.sum()
    w_3 = np.array(pl[tb]['class_reach_normalized'], dtype=np.float64)
    w_3 = w_3 / w_3.sum()
    g_o = np.array(pl[op]['model_gross'], dtype=np.float64)
    g_3 = np.array(pl[tb]['model_gross'], dtype=np.float64)
    # consistency with T's own EVs at the opener node: fold = -inv_o0, call = g_o - inv_o
    ev_t = np.array(po['ev_bb'])
    chk = {'fold_ev_max_abs_diff': float(np.max(np.abs(ev_t[0] + inv_o0))),
           'call_ev_max_abs_diff_on_reached': float(np.max(np.abs((ev_t[1] - (g_o - inv_o))[w_o > 1e-9])))}
    res = {'name': name, 'line': SEL[name]['line'], 'opener': op, 'three_bettor': tb, 'pot_at_decision': pot0, 'call_amount': call_amt,
           'pot_allin': pot_ai, 'consistency_vs_T_export': chk}
    for variant in ('A', 'B_table', 'B_eq'):
        jam = variant != 'A'
        if variant == 'B_eq':
            call_o = pot_T * (EQ @ w_3) - inv_o                       # opener class value of calling (pot x equity vs 3-bet range)
        else:
            call_o = g_o - inv_o
        fold_o = -inv_o0 * np.ones(169)
        na = 3 if jam else 2
        reg_o = np.zeros((169, na)); sum_o = np.zeros((169, na))
        reg_3 = np.zeros((169, 2)); sum_3 = np.zeros((169, 2))
        for it in range(iters):
            s_o = np.maximum(reg_o, 0); z = s_o.sum(1, keepdims=True); s_o = np.where(z > 0, s_o / np.where(z > 0, z, 1), 1 / na)
            s_3 = np.maximum(reg_3, 0); z = s_3.sum(1, keepdims=True); s_3 = np.where(z > 0, s_3 / np.where(z > 0, z, 1), 0.5)
            u_o = np.stack([fold_o, call_o], 1)
            if jam:
                pf = s_3[:, 0]                                         # 3-bettor fold-to-jam per class
                jam_v = (w_3 * pf).sum() * (pot0 - inv_o0) + (EQ * (w_3 * (1 - pf))[None, :]).sum(1) * pot_ai - (w_3 * (1 - pf)).sum() * (stack + a)
                u_o = np.stack([fold_o, call_o, jam_v], 1)
                # 3-bettor facing the jam: opener jam range
                r_j = w_o * s_o[:, 2]
                mj = r_j.sum()
                if mj > 0:
                    call3 = (EQ @ r_j) / mj * pot_ai - (stack + a)
                else:
                    call3 = EQ @ w_o * pot_ai - (stack + a)
                u_3 = np.stack([-inv_3 * np.ones(169), call3], 1)
                v3 = (s_3 * u_3).sum(1, keepdims=True)
                reg_3 = np.maximum(reg_3 + (u_3 - v3) * (mj if mj > 0 else 1e-6), 0)
                sum_3 += s_3 * (it + 1) * w_3[:, None]
            v = (s_o * u_o).sum(1, keepdims=True)
            reg_o = np.maximum(reg_o + (u_o - v) * w_o[:, None], 0)
            sum_o += s_o * (it + 1) * w_o[:, None]
        av_o = sum_o / np.maximum(sum_o.sum(1, keepdims=True), 1e-300)
        av_o[sum_o.sum(1) == 0] = 1 / na
        out = {'opener_freq': {k: float((w_o * av_o[:, i]).sum()) for i, k in enumerate(['fold', 'call', 'jam'][:na])}}
        ev_o = (av_o * u_o).sum(1)
        out['opener_ev_bb'] = float((w_o * ev_o).sum())
        # 3-bettor EV at this node (fixed 3-bet range): fold -> wins pot0 - inv_3; call -> g_3 (or pot x eq) - inv_3; jam branch
        po_f = (w_o * av_o[:, 0]).sum()
        r_c = w_o * av_o[:, 1]
        if variant == 'B_eq':
            v3_call = pot_T * (EQ @ r_c) / max(r_c.sum(), 1e-300) - inv_3
        else:
            v3_call = g_3 - inv_3
        ev3 = po_f * (pot0 - inv_3) + r_c.sum() * v3_call
        if jam:
            av_3 = sum_3 / np.maximum(sum_3.sum(1, keepdims=True), 1e-300)
            av_3[sum_3.sum(1) == 0] = 0.5
            r_j = w_o * av_o[:, 2]
            mj = r_j.sum()
            if mj > 0:
                call3 = (EQ @ r_j) / mj * pot_ai - (stack + a)
                ev3 = ev3 + mj * (av_3[:, 0] * (-inv_3) + av_3[:, 1] * call3)
            out['three_bettor_fold_vs_jam'] = float((w_3 * av_3[:, 0]).sum())
        out['three_bettor_ev_bb'] = float((w_3 * ev3).sum())
        top = sorted(range(169), key=lambda h: -w_o[h])
        out['opener_hands'] = {lab[h]: [round(float(x), 3) for x in av_o[h]] for h in top[:0]}
        if jam:
            jams = [lab[h] for h in range(169) if w_o[h] > 1e-6 and av_o[h, 2] > 0.5]
            folds = [lab[h] for h in range(169) if w_o[h] > 1e-6 and av_o[h, 0] > 0.5]
            out['opener_jam_classes'] = jams
            out['opener_fold_classes_n'] = len(folds)
        res[variant] = out
    return res


def main():
    names = sys.argv[1:] or ['n51', 'n196']
    allr = {}
    for n in names:
        r = solve(n)
        allr[n] = r
        print(n, r['line'], r['consistency_vs_T_export'])
        for v in ('A', 'B_table', 'B_eq'):
            x = r[v]
            print(f"  {v:8s} opener {({k: round(100 * y, 1) for k, y in x['opener_freq'].items()})} EV {x['opener_ev_bb']:.3f} | "
                  f"3-bettor EV {x['three_bettor_ev_bb']:.3f}" + (f" fold-vs-jam {100 * x['three_bettor_fold_vs_jam']:.1f}%" if 'three_bettor_fold_vs_jam' in x else ''))
        print('  jam classes (B_table):', ' '.join(r['B_table']['opener_jam_classes']))
    json.dump({'schema': 'pilot9_4bet_ab_v1', 'note': __doc__, 'results': allr}, open(OUT + 'fourbet_ab.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
