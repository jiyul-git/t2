#!/usr/bin/env python3
"""Independent-seed and built-in perceived-range sensitivity for HAND130.

Archive stores only 288-combo COUNT/signature, not exact combo weights nor
draw trace. These are explicitly RECONSTRUCTED observer-archetype posteriors,
never misreported as original B37 equity or a solver solution. Seed sampling
uses original cards and archived game geometry. The 800-sample estimator's
uncertainty is compared with the original 0.001128 equity-point margin.
"""
import json
import math
import os
import statistics
import sys
import zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bot
import ranges as R
from tools.verify_hand130_b37_replay import original

def run():
    o=original(); pf=o['actor_pf_seed']
    hero=o['hole']['3']
    assert set(hero)=={'Ac','Kh'}
    observed_eq=pf['pf_call_ev_shadow']['effective_equity']
    old_need=pf['pf_calloff_compare']['icm_required_equity']
    old_margin=observed_eq-old_need
    expected_n=pf['pf_opp_ranges_n']['9']
    assert expected_n==288
    n=800
    # Each layer has 800 simulations; independent seeds combine estimates
    # with pot fractions as weights (Hoeffding, shares in [0,1]).
    amounts=[p['amount'] for p in pf['pf_call_ev_shadow']['layers']]
    total=sum(amounts)
    weights=[v/total for v in amounts]
    halfwidth=math.sqrt(sum(w*w for w in weights)*math.log(40)/(2*n))
    assert halfwidth>old_margin
    report={'hand':o['hash'],'saved_observer_count':expected_n,
            'saved_observer_equity':observed_eq,
            'saved_icm_required':old_need,
            'saved_point_margin':old_margin,
            'two_layer_800_sample_independent_95pct_hoeffding_halfwidth':halfwidth,
            'original_288_weights_archived':False,
            'conditional_proxies':[]}
    # A different archetype label can produce the same reconstructed combo
    # support: do not mistake independent RNG variation for range sensitivity.
    # Instead vary observable counterfactual action context via the EXISTING
    # T2 range producer (no fabricated probability multipliers).
    contexts=[
        ('observed_BB_vs_LJ_6p3442bb', 'LJ', 6.3442, 2.0),
        ('deeper_BB_vs_LJ_20bb', 'LJ', 20.0, 2.0),
        ('deeper_BB_vs_LJ_40bb', 'LJ', 40.0, 2.0),
        ('deeper_BB_vs_BTN_40bb', 'BTN', 40.0, 2.0),
        ('deeper_BB_vs_UTG_40bb', 'UTG', 40.0, 2.0),
        ('larger_raise_BB_vs_LJ_40bb', 'LJ', 40.0, 4.0),
    ]
    signatures=set()
    for kind, opener, opp_stack, raise_size in contexts:
        pool=R.preflop_range('TAG','BB','3bet',opp_stack,set(hero),
             n_callers=0,opener_pos=opener,open_bb=raise_size,
             seats=8,ante=True,raise_level=1)
        assert pool and R.range_mass(pool)>0,kind
        signatures.add(repr(sorted(pool.items())) if isinstance(pool,dict)
                       else repr(sorted(pool)))
        # Exactly the same sampled Monte Carlo function as the actual engine.
        seeds=[zlib.crc32(('%s|%s|independent|%d'%(o['hash'],kind,j)).encode())
               for j in range(6)]
        eqs=[bot.equity_vs_combos(hero,[],[pool],sims=n,seed=seed)
             for seed in seeds]
        assert 0<=min(eqs) and max(eqs)<=1
        report['conditional_proxies'].append({
            'scenario':kind,'source':'T2 built-in observer conditional 3bet model; counterfactual public context',
            'opener_pos':opener,'opponent_stack_bb':opp_stack,
            'opener_raise_bb':raise_size,
            'card_combo_support':len(pool), 'weighted_range_mass':R.range_mass(pool),
            'seed_ids':seeds,'n_requested_per_seed':n,
            'equities':[round(e,6) for e in eqs],
            'mean_equity':statistics.mean(eqs),
            'seed_sd':statistics.stdev(eqs),
            'min':min(eqs),'max':max(eqs),
            'call_by_old_objective_bf_point':sum(x>=old_need for x in eqs),
            'call_by_8player_exact_no_tie_breakeven_point':sum(x>=0.3715371093145927 for x in eqs),
        })
    assert len(report['conditional_proxies'])==len(contexts)
    report['distinct_range_signatures']=len(signatures)
    assert len(signatures)>=2,'No actual range sensitivity; context variations collapsed'
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    print('PASS independent-seed reconstructed-proxy sensitivity; original range missing')

if __name__=='__main__':
    run()
