#!/usr/bin/env python3
"""B3 integration: same-state paired attribution of each intentional change.

Runs the sealed baseline sim (tools/r2_baseline_sim.py) on the current tree and,
at every decision point touched by B3 integration, evaluates the previous rule
on the identical state without consuming RNG.  The printed digest must equal the
plain sim digest of the same tree (proves the instrumentation is inert).

  OUT=attr.json python tools/b3_integration_attribution.py SEED [CAP]

Changes attributed:
  L-S9-02a  _nonvalue_raise_ev_gate fold_p: live (hand-conditioned) mass vs full mass
  L-S9-03   value-when-called predicate: improved bluff (old eq>=0.54 & rel>=0.55),
            value raise (old eq>0.5), river thin value (old eq>=0.50)
  L-S9-04   overbet continue-range strength: shared joint/perceived vs old HU
            relative_strength on the union range
"""
import sys, os, json, inspect
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import plan as PL, ranges as R

REC = {'gate': [], 'value': [], 'overbet': []}

_g = PL._nonvalue_raise_ev_gate
def gate(profile, hero, board, street, opp_range, opp_ranges, n_opp, pot, tocall, stack,
         hero_contrib, response_context, mult=None, target=None):
    r = _g(profile, hero, board, street, opp_range, opp_ranges, n_opp, pot, tocall, stack,
           hero_contrib, response_context, mult=mult, target=target)
    if r.get('known') and r.get('fold_p') is not None:
        ctx = dict(response_context or {}); fs = ctx.get('facing_seat')
        pool = opp_ranges.get(fs) if isinstance(opp_ranges, dict) and fs in opp_ranges else None
        pool = pool or opp_range
        cont = R.perceived_continue_range(pool, board, street, r['price_frac'], profile=profile)
        bm, cm = R.range_mass(pool), R.range_mass(cont)
        fp_old = max(0.0, min(1.0, 1.0 - cm/bm)) if bm > 0 else None
        allow_old = None
        if fp_old is not None and r['fold_p'] < 1.0:
            ev_cont = (r['ev'] - r['fold_p']*pot) / (1.0 - r['fold_p'])
            allow_old = (fp_old*pot + (1.0-fp_old)*ev_cont) > 0.0
        REC['gate'].append({'street': street, 'fold_p': r['fold_p'], 'fold_p_old': fp_old,
                            'allow': r['allow'], 'allow_old': allow_old})
    return r
PL._nonvalue_raise_ev_gate = gate

_a = PL.ahead_when_called
def ahead(eq):
    new = _a(eq)
    fr = inspect.currentframe().f_back
    fn = fr.f_code.co_name
    if eq is None:
        old = False
    elif fn == 'refresh':
        old = float(eq) >= 0.54 and fr.f_locals.get('rel', 0.0) >= 0.55
    elif fn == 'value_raise_qualification':
        old = float(eq) > 0.5
    else:
        old = float(eq) >= 0.50
    REC['value'].append({'site': fn, 'eq': None if eq is None else round(float(eq), 4),
                         'new': new, 'old': old})
    return new
PL.ahead_when_called = ahead

_o = PL.overbet_value_continue_rel
def ob(hero, board, opp_range, street, rel, profile, opp_ranges=None, n_opp=1, seed=None):
    new = _o(hero, board, opp_range, street, rel, profile, opp_ranges=opp_ranges, n_opp=n_opp, seed=seed)
    cr = R.perceived_continue_range(opp_range, board, street, 1.15, profile)
    old = min(rel, PL.relative_strength(hero, board, cr)) if cr else rel
    REC['overbet'].append({'n_opp': n_opp, 'mw_complete': isinstance(opp_ranges, dict) and int(n_opp or 1) > 1,
                           'rel_new': round(new, 4), 'rel_old': round(old, 4)})
    return new
PL.overbet_value_continue_rel = ob

sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
SIM.main()
out = os.environ.get('OUT')
if out:
    json.dump(REC, open(out, 'w'))
g = REC['gate']; v = REC['value']; o = REC['overbet']
print(json.dumps({
    'gate_calls': len(g), 'gate_allow_flips': sum(1 for x in g if x['allow_old'] is not None and x['allow'] != x['allow_old']),
    'value_calls': {s: sum(1 for x in v if x['site'] == s) for s in sorted({x['site'] for x in v})},
    'value_flips': {s: sum(1 for x in v if x['site'] == s and x['new'] != x['old']) for s in sorted({x['site'] for x in v})},
    'overbet_calls': len(o), 'overbet_rel_changed': sum(1 for x in o if abs(x['rel_new'] - x['rel_old']) > 1e-9),
}))
