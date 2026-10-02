#!/usr/bin/env python3
"""L-S9-02 impact measurement: hero-card-incompatible combos in hand-level counts.

Read-only observation on the sealed baseline sim (tools/r2_baseline_sim.py).
Wrappers add no RNG consumption; the printed sim digest must equal the R2 seal
(seed 11 e6d8b5e5..., seed 12 c13a5bf4...), which proves the run is unperturbed.

  LS902_OUT=out.json python tools/l_s9_02_measure.py SEED [CAP]

Measured (no fix applied — stage9 B3 rule: seal repro + impact path first):
  * plan._nonvalue_raise_ev_gate: fold_p = 1 - cont_mass/base_mass over the
    full perceived pool vs. over hero/board-compatible combos only
    (opponent strategy slices the full range; the hand-conditioned fold share
    is the compatible ratio).  allow flips are the action-eligibility impact.
  * plan.response_equity tier reached (tier 2 counts len(opp_range) incl.
    incompatible combos).
  * make_plan opp_range: compatible support below ranges._MIN_KEEP while the
    total is not (narrow_by_actions floor counts total support).
"""
import sys, os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import plan as PL, ranges as R, bot

def compat_mass(r, dead):
    wr = R.weighted_range(r) if r else {}
    tot = sum(wr.values()); comp = sum(w for c, w in wr.items() if not (set(c) & dead))
    return tot, comp, len(wr), sum(1 for c in wr if not (set(c) & dead))

G = []; EQ = []; MP = []
_g = PL._nonvalue_raise_ev_gate
def gate(profile, hero, board, street, opp_range, opp_ranges, n_opp, pot, tocall, stack,
         hero_contrib, response_context, mult=None, target=None):
    r = _g(profile, hero, board, street, opp_range, opp_ranges, n_opp, pot, tocall, stack,
           hero_contrib, response_context, mult=mult, target=target)
    if r.get('known') and r.get('fold_p') is not None:
        ctx = dict(response_context or {}); fs = ctx.get('facing_seat')
        pool = opp_ranges.get(fs) if isinstance(opp_ranges, dict) and fs in opp_ranges else None
        pool = pool or opp_range
        dead = set(hero) | set(board)
        cont = R.perceived_continue_range(pool, board, street, r['price_frac'], profile=profile)
        bt, bc, bn, bnc = compat_mass(pool, dead); ct, cc, cn, cnc = compat_mass(cont, dead)
        fp = r['fold_p']; fpc = max(0.0, min(1.0, 1.0 - cc/bc)) if bc > 0 else None
        ev = r['ev']
        evc = None
        if fpc is not None and fp < 1.0:
            ev_cont = (ev - fp*pot)/(1.0 - fp)
            evc = fpc*pot + (1.0-fpc)*ev_cont
        G.append({'street': street, 'fold_p': fp, 'fold_p_compat': fpc, 'ev': ev, 'ev_compat': evc,
                  'allow': r['allow'], 'allow_compat': (evc > 0.0) if evc is not None else None,
                  'base_n': bn, 'base_n_compat': bnc, 'base_mass': bt, 'base_mass_compat': bc,
                  'cont_mass': ct, 'cont_mass_compat': cc, 'hero': list(hero), 'board': list(board), 'pot': pot})
    return r
PL._nonvalue_raise_ev_gate = gate

_re = PL.response_equity
def resp_eq(hero, board, profile, opp_range, opp_ranges, n_opp, opp_est, pot, tocall, street, response_context, seed):
    dead = set(hero) | set(board or [])
    raw = PL._normalize_opp_pools(opp_range, n_opp, opp_ranges)
    pools = [bot._filter_pool(p, dead, sort_legacy=True) if p else ['fallback'] for p in raw]
    tier = 1 if any(pools) else (2 if (opp_range and len(opp_range) >= 20) else 3)
    rec = {'tier': tier, 'n_opp': n_opp, 'opp_n': len(opp_range) if opp_range else 0,
           'opp_n_compat': (sum(1 for c in R.range_support(opp_range) if not (set(c) & dead)) if opp_range else 0)}
    eq = _re(hero, board, profile, opp_range, opp_ranges, n_opp, opp_est, pot, tocall, street, response_context, seed)
    rec['eq'] = eq; EQ.append(rec)
    return eq
PL.response_equity = resp_eq

_mp = PL.make_plan
def mk(hero, board, my_range, opp_range, *a, **k):
    if opp_range and board:
        dead = set(hero) | set(board)
        sup = R.range_support(opp_range)
        nc = sum(1 for c in sup if not (set(c) & dead))
        MP.append({'n': len(sup), 'n_compat': nc, 'n_hero_blocked': sum(1 for c in sup if set(c) & set(hero)),
                   'below_keep_compat': nc < R._MIN_KEEP <= len(sup)})
    return _mp(hero, board, my_range, opp_range, *a, **k)
PL.make_plan = mk

sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
out = os.environ.get('LS902_OUT')
SIM.main()
json.dump({'gate': G, 'resp_eq': EQ, 'make_plan': MP}, open(out, 'w'))
