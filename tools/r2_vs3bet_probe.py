#!/usr/bin/env python3
"""R2-B: what the code does for an opener facing a heads-up 3bet (raise_level=2).

Read-only.  In production (plan.preflop_plan, single live range) this spot goes to
preflop.defend_decision with def_pos = the opener's seat, opener_pos = the 3bettor's
seat, open_bb = the 3bet size, raise_level=2.  That is the vs-open defend prior with
the positions swapped, then LEVEL_TIGHTEN[3].  There is no independent vs-3bet prior.

Population = hands the opener opened, either per the reference RFI chart
(8-max, EP->UTG1, MP->LJ) or per the code's own open width for the max-skill profile.
Reported: continue / 4bet(attack) / call / fold conditional on having opened.

Usage: python tools/r2_vs3bet_probe.py <chart_root> [out.json]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import preflop as PF, persona as PS, gto as G  # noqa: E402
from r2_freeze_defend_baseline import maxskill, open_size, CLASSES, N_COMBO  # noqa: E402

NODES = [('MPopen-vs-IP3bet', 'LJ', 'BTN', 'LJ'), ('EPopen-vs-IP3bet', 'UTG+1', 'BTN', 'UTG1'),
         ('MPopen-vs-blind3bet', 'LJ', 'BB', 'LJ'), ('EPopen-vs-blind3bet', 'UTG+1', 'BB', 'UTG1'),
         ('BTNopen-vs-blind3bet', 'BTN', 'BB', 'BTN'), ('SBopen-vs-BB3bet', 'SB', 'BB', 'SB')]


def chart(root, st, sub, name):
    p = os.path.join(root, st, sub, name + '.json')
    return json.load(open(p))['actions'] if os.path.exists(p) else None


def cond(pop, f):
    tot = sum(N_COMBO[k] * pop.get(k, 0) for k in CLASSES)
    return sum(N_COMBO[k] * pop.get(k, 0) * f(k) for k in CLASSES) / tot if tot else None


def main():
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    prof = maxskill()
    rows = []
    for seats in (8, 9):
        for st in ('30bb', '100bb'):
            bb = int(st[:-2])
            for node, op, tb, rkey in NODES:
                a = chart(root, st, 'vs-open', node)
                rf = chart(root, st, 'rfi', rkey)
                if not a or not rf:
                    continue
                ref_pop = {k: float(v.get('raise', 0)) + float(v.get('allin', 0))
                           for k, v in rf.items()}
                ow = PS.open_pct(prof, op, seats, bb, True)
                code_pop = {k: (1.0 if PF.PCT[k] <= ow else 0.0) for k in CLASSES}
                ob = open_size(prof, op, bb)
                tb_size = ob * PF.reraise_mult(1, tb)
                lik = {k: PF.defend_action_likelihoods(
                    prof, op, tb, h, bb, tb_size, 0, raise_level=2, stack_bb=bb,
                    exploit=None, bf=1.0, seats=seats, ante=True, can_raise=True)
                       for k, h in CLASSES.items()}
                tp, tot = PF.defend_thresholds(prof, op, tb, bb, tb_size, 0, 2, seats, True)
                ref_c = lambda k: 1 - float(a.get(k, {}).get('fold', 0)) if k in a else 0.0
                ref_4 = lambda k: float(a.get(k, {}).get('raise', 0)) + float(a.get(k, {}).get('allin', 0))
                row = {'seats': seats, 'stack': st, 'node': node, 'opener': op, 'three_bettor': tb,
                       'code_3bet_size_bb': round(tb_size, 2),
                       'code_prior_used': 'gto.defend_pct(def_pos=%s, opener_pos=%s) x LEVEL_TIGHTEN[3]'
                                          % (op, tb),
                       'code_threshold_tp_tot': [round(tp, 4), round(tot, 4)],
                       'ref_continue|ref_open': round(cond(ref_pop, ref_c), 4),
                       'ref_4bet|ref_open': round(cond(ref_pop, ref_4), 4),
                       'code_continue|ref_open': round(cond(ref_pop, lambda k: lik[k]['attack'] + lik[k]['call']), 4),
                       'code_4bet|ref_open': round(cond(ref_pop, lambda k: lik[k]['attack']), 4),
                       'code_continue|code_open': round(cond(code_pop, lambda k: lik[k]['attack'] + lik[k]['call']), 4),
                       'code_4bet|code_open': round(cond(code_pop, lambda k: lik[k]['attack']), 4),
                       'code_open_width': round(ow, 4)}
                rows.append(row)
                print(row)
    if out:
        open(out, 'w').write(json.dumps({'rows': rows}, indent=1) + '\n')


if __name__ == '__main__':
    main()
