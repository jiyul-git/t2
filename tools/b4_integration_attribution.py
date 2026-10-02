#!/usr/bin/env python3
"""B4 integration: same-state paired attribution of the call-bias change.

Runs the sealed baseline sim on the current tree.  At every final call/fold
branch of plan.decide_response it recomputes what the retired second bias
application (station / bluff_fear / old hero_call, ledger L148) would have
decided on the identical state, without consuming RNG.  The printed digest must
equal the plain sim digest of the same tree.

  OUT=attr.json python tools/b4_integration_attribution.py SEED [CAP]
"""
import sys, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import plan as PL, persona as PS

REC = []


def old_hero_call(prof, street):
    if not prof or not prof.get('concepts'):
        return 0.0
    bc = PS.street_concept('bluffcatch', street) if street else 'bluffcatch_river'
    return PS._z(0.45*PS.sk(prof, bc) + 0.35*PS.temper(prof, 'aggression', 5.0)
                 + 0.20*PS.temper(prof, 'tilt_prone', 5.0))


def old_reapply(need, size_frac, street, st, bf, hc):
    need *= max(0.55, 1.0 - 0.22*max(0.0, st))
    late = min(1.0, size_frac/0.9) * (1.0 if street == 'river' else 0.65)
    need *= 1.0 + 0.30*max(0.0, bf)*late
    need *= max(0.60, 1.0 - 0.18*max(0.0, hc)*late)
    return max(0.02, min(0.97, need))


_d = PL.decide_response
def dr(profile, hero, board, street, plan, plan_state, eq, need, made_now, opp_range,
       pot, tocall, stack, committed, rng, *a, **k):
    r = _d(profile, hero, board, street, plan, plan_state, eq, need, made_now, opp_range,
           pot, tocall, stack, committed, rng, *a, **k)
    if isinstance(r[3], str) and r[3].startswith('eq ') and ' vs 체감 need ' in r[3] \
            and profile and profile.get('concepts'):
        call_eq, call_need = k.get('call_eq'), k.get('call_need')
        layer = call_eq is not None and call_need is not None
        eq_seen = float(call_eq) if layer else eq
        need_in = float(call_need) if layer else need
        sz = tocall/max(1.0, float(pot) - tocall)
        old_need = old_reapply(need_in, sz, street, PS.bias(profile, 'station'),
                               PS.bias(profile, 'bluff_fear', street), old_hero_call(profile, street))
        old_act = 'call' if eq_seen >= old_need else 'fold'
        REC.append({'street': street, 'act': r[0], 'old_act': old_act,
                    'need': round(need_in, 4), 'old_need': round(old_need, 4), 'eq': round(eq_seen, 4)})
    return r
PL.decide_response = dr

sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
SIM.main()
out = os.environ.get('OUT')
if out:
    json.dump(REC, open(out, 'w'))
fl = [x for x in REC if x['act'] != x['old_act']]
print(json.dumps({'final_branch_calls': len(REC), 'flips': len(fl),
                  'call_to_fold': sum(1 for x in fl if x['old_act'] == 'call'),
                  'fold_to_call': sum(1 for x in fl if x['old_act'] == 'fold')}))
