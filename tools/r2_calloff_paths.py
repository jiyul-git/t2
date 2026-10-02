#!/usr/bin/env python3
"""R2 calloff: which quantity answers "call a first-in shove?" — measured on completed 9-max spots.

Read-only.  For the HoldemMath 9-max call-vs-shove spots (ante 0.1bb x 9) at 10/15/20bb with caller
BB, SB or BTN (63 spots; runtime bound) in the GTO DB branch, three decision rules are compared with the DB call set:

  legacy   current preflop.calloff_cap percentile rule (pf_rank <= cap)
  math_db  equity(hand vs the DB's own first-in shove range) >= required equity
           (chip EV, no ICM, single caller — the same assumptions as the DB)
  t2_obs   equity(hand vs the range T2's observer reconstructs for a first-in shover)
           >= required equity.  T2 labels a first-in shove 'open' and rebuilds it with
           ranges.preflop_range(..., 'open', stack) from an empty-Book perceived profile
           (baseline: exploit neutral).  This is the range calloff_layer_judgment sees.

Required equity = cost / (pot_before_call + cost); the shover's jam is the full stack,
dead money = blinds + 0.9bb ante.  Reported per spot: DB call frequency, each rule's call
frequency, and agreement = combo-weighted share of hands where the rule and the DB agree.

Usage: python tools/r2_calloff_paths.py [GTO_DB_REF] [out.json]
"""
import json, os, random, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import preflop as PF, ranges as R, bot as B, reads as RD  # noqa: E402
from r2_freeze_defend_baseline import maxskill, CLASSES, N_COMBO  # noqa: E402

POS = {'utg': 'UTG', 'utg1': 'UTG+1', 'mp': 'UTG+2', 'lj': 'LJ', 'hj': 'HJ', 'co': 'CO',
       'btn': 'BTN', 'sb': 'SB', 'bb': 'BB'}
SIMS = 500
STACKS = (10, 15, 20)
CALLERS = ('BB', 'SB', 'BTN')


def combos_of(k):
    return [list(c) for c in R._SORTED if PF.cls(list(c)) == k]


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else 'origin/chatgpt/gto-reference-20260928'
    out = sys.argv[2] if len(sys.argv) > 2 else None
    rows = [json.loads(l) for l in subprocess.check_output(
        ['git', '-C', ROOT, 'show', ref + ':data/gto_db/preflop_9max_pushfold_v1.jsonl'],
        text=True).splitlines()]
    prof = maxskill()
    oe = RD.perceived_profile(RD.Book(), 0, 1, prof, random.Random(0))
    opp_view = RD.range_profile(oe)
    shove = {}
    for r in rows:
        c = r['conditions']
        if c['ante']['model'] == 'per_player' and c['scenario'] == 'first_in_shove':
            shove[(int(c['prehand_stack_bb']), POS[c['hero_position'].lower()])] = r['strategy']['hands']
    res = []
    for r in rows:
        c = r['conditions']
        if c['ante']['model'] != 'per_player' or c['scenario'] != 'call_vs_shove':
            continue
        S = int(c['prehand_stack_bb'])
        hero, sh = POS[c['hero_position'].lower()], POS[c['shover_position'].lower()]
        if S not in STACKS or hero not in CALLERS:
            continue
        db = r['strategy']['hands']
        posted = 1.0 if hero == 'BB' else 0.5 if hero == 'SB' else 0.0
        cost = S - posted
        pot_before = S + 1.5 + 0.9          # shove + both blinds + antes (hero's blind is in 1.5)
        need = cost / (pot_before + cost)
        sh_hands = shove[(S, sh)]
        db_range = {c2: float(sh_hands[PF.cls(list(c2))].get('jam', 0))
                    for c2 in R._SORTED if float(sh_hands[PF.cls(list(c2))].get('jam', 0)) > 0}
        rep = {k: combos_of(k)[0] for k in CLASSES}
        out_r = {'stack_bb': S, 'shover': sh, 'caller': hero, 'need': round(need, 4)}
        rules = {}
        legacy_cap = PF.calloff_cap(prof, hero, sh, float(S), float(S), 1, bf=1.0, exploit=None,
                                    n_callers=0, seats=9, ante=True)
        rules['legacy'] = {k: 1.0 if PF.PCT[k] <= legacy_cap else 0.0 for k in CLASSES}
        # DB push/fold strategies are pure (0/1), and T2's 'open' reconstruction is an
        # unweighted slice, so both ranges are plain combo lists (fast sampler).
        t2_full = sorted(tuple(c2) for c2 in R.range_support(
            R.preflop_range(opp_view, sh, 'open', float(S), set(), seats=9, ante=True)))
        db_full = sorted(c2 for c2, w in db_range.items() if w >= 0.5)
        for name, base in (('math_db', db_full), ('t2_obs', t2_full)):
            dec = {}
            for k, h in rep.items():
                dead = set(h)
                pool = [list(c2) for c2 in base if c2[0] not in dead and c2[1] not in dead]
                eq = B.equity_vs_pools(h, [], [pool], SIMS, 7) if pool else 0.0
                dec[k] = 1.0 if eq >= need else 0.0
            rules[name] = dec
        out_r['t2_obs_range_width'] = round(len(t2_full) / 1326, 4)
        out_r['db_shove_width'] = round(len(db_full) / 1326, 4)
        dbc = {k: float(db.get(k, {}).get('call', 0)) for k in CLASSES}
        out_r['db_call'] = round(sum(N_COMBO[k] * dbc[k] for k in CLASSES) / 1326, 4)
        out_r['legacy_cap'] = round(legacy_cap, 4)
        for name, dec in rules.items():
            out_r[name + '_call'] = round(sum(N_COMBO[k] * dec[k] for k in CLASSES) / 1326, 4)
            out_r[name + '_agree'] = round(sum(N_COMBO[k] * (1 - abs(dec[k] - dbc[k])) for k in CLASSES) / 1326, 4)
        res.append(out_r)
        print(out_r, flush=True)
    if out:
        open(out, 'w').write(json.dumps({'gto_db_ref': ref, 'sims': SIMS, 'rows': res}, indent=1) + '\n')


if __name__ == '__main__':
    main()
