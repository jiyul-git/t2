#!/usr/bin/env python3
"""Stage 9 B1/B2 closeout group A — contract verifiers for A2 and A3.

A2  persona.traits_of()['threebet'] skill input is pf_defend (a proxy: no
    dedicated 3bet skill / solved 3bet prior exists — MISSING_INDEPENDENT_3BET_
    SKILL/PRIOR).  Checks: with aggression/looseness fixed, changing only
    `bluff` leaves the trait unchanged; changing only `pf_defend` changes it;
    at max skill (bluff == pf_defend == 10) it equals the retired formula.

A3  bot.range_combos(pct, dead) is a whole-class floor over the PCT (pf_rank)
    ordering, NOT an exact top-pct.  Checks over a pct grid and dead-card cases:
    monotone in pct, class integrity (no class partially cut except by dead
    cards), realized share <= pct, shortfall below one boundary class, and
    deterministic ordering.
"""
import itertools, json, os, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import persona as PS
import bot

EPS = 1e-9


def prof(bluff=5.0, pf_defend=5.0, aggr=5.0, loose=5.0):
    c = {k: 5.0 for k in PS.ALL_CONCEPTS}
    c['bluff'] = float(bluff); c['pf_defend'] = float(pf_defend)
    t = {k: 5.0 for k in PS.TEMPER}
    t['aggression'] = float(aggr); t['looseness'] = float(loose)
    return {'concepts': c, 'temper': t}


def retired_threebet(p):
    a = PS.temper(p, 'aggression', 5.0); loose = PS.temper(p, 'looseness', 5.0)
    return max(.005, .009*a + .006*PS.sk(p, 'bluff') + .004*(loose-4))


def check_a2():
    out = {}
    rows = []
    bluff_inert = True; pfd_live = True
    for aggr, loose in itertools.product((2, 5, 8), (3, 5, 8)):
        base = PS.traits_of(prof(5, 5, aggr, loose))['threebet']
        for b in (0, 2.5, 7.5, 10):
            bluff_inert &= abs(PS.traits_of(prof(b, 5, aggr, loose))['threebet'] - base) < EPS
        vals = [PS.traits_of(prof(5, d, aggr, loose))['threebet'] for d in (0, 2.5, 5, 7.5, 10)]
        pfd_live &= all(y > x for x, y in zip(vals, vals[1:])) or vals[0] == .005
        rows.append({'aggr': aggr, 'loose': loose, 'pf_defend_curve': [round(v, 4) for v in vals]})
    out['A2a_bluff_only_change_is_inert'] = {'pass': bool(bluff_inert)}
    out['A2b_pf_defend_only_change_moves_trait'] = {'pass': bool(pfd_live), 'rows': rows[:3]}
    mx = prof(10, 10, 5, 5)
    out['A2c_max_skill_equals_retired_formula'] = {
        'pass': abs(PS.traits_of(mx)['threebet'] - retired_threebet(mx)) < EPS,
        'value': PS.traits_of(mx)['threebet']}
    return out


def class_sizes():
    sizes = {}
    for c in bot._ALLCOMBOS:
        k = bot._pf_class(*c); sizes[k] = sizes.get(k, 0) + 1
    return sizes


def check_a3():
    out = {}
    sizes = class_sizes()
    order = sorted(sizes, key=lambda k: bot._PCT[k])
    cum = 0; pct_consistent = True
    for k in order:
        cum += sizes[k]
        pct_consistent &= abs(bot._PCT[k] - cum/1326.0) <= 5e-5   # pf_rank stored to 4 decimals
    out['A3_0_pct_is_cumulative_class_share'] = {'pass': bool(pct_consistent)}

    grid = [i/100.0 for i in range(0, 101)] + [0.0045, 0.0046, 0.2199, 0.35, 0.3501, 0.999]
    grid = sorted(set(grid))
    rng = random.Random(77)
    deck = list(bot.FULLDECK)
    dead_cases = [set()] + [set(rng.sample(deck, n)) for n in (2, 5, 7) for _ in range(4)]

    mono = integ = share_ok = gap_ok = det = True
    worst_gap = 0.0; bad = []
    for dead in dead_cases:
        prev = set()
        for p in grid:
            r = bot.range_combos(p, dead)
            r2 = bot.range_combos(p, set(dead))
            det &= (r == r2)
            s = set(r)
            if not prev <= s:
                mono = False; bad.append(('mono', p, sorted(dead)))
            prev = s
            inc = {bot._pf_class(*c) for c in r}
            # class integrity: every live combo of an included class is present
            for k in inc:
                live = [c for c in bot._ALLCOMBOS if bot._pf_class(*c) == k
                        and c[0] not in dead and c[1] not in dead]
                if not set(live) <= s:
                    integ = False; bad.append(('class', p, k)); break
            if dead:
                continue
            # realized share and shortfall (full deck)
            share = len(r)/1326.0
            if share > p + 5e-5:
                share_ok = False; bad.append(('share', p, share))
            excluded = [k for k in order if k not in inc]
            if excluded:
                nxt = excluded[0]
                gap = p - share
                worst_gap = max(worst_gap, gap)
                if gap >= sizes[nxt]/1326.0 + 5e-5:
                    gap_ok = False; bad.append(('gap', p, gap, nxt))
    out['A3a_monotone_in_pct'] = {'pass': bool(mono)}
    out['A3b_class_integrity'] = {'pass': bool(integ)}
    out['A3c_realized_share_le_requested'] = {'pass': bool(share_ok)}
    out['A3d_shortfall_below_one_boundary_class'] = {
        'pass': bool(gap_ok), 'worst_gap': round(worst_gap, 5),
        'max_class_share': round(max(sizes.values())/1326.0, 5)}
    out['A3e_deterministic'] = {'pass': bool(det)}
    out['A3_examples'] = {'pass': True, 'pct_0.35': len(bot.range_combos(0.35, set())),
                          'share_0.35': round(len(bot.range_combos(0.35, set()))/1326.0, 4)}
    if bad:
        out['violations'] = {'pass': False, 'first': bad[:5]}
    return out


def main():
    checks = {}
    checks.update(check_a2())
    checks.update(check_a3())
    ok = all(v['pass'] for v in checks.values())
    print(json.dumps({'pass': ok, 'checks': checks}, indent=1, sort_keys=True, default=str))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
