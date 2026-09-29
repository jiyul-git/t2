#!/usr/bin/env python3
"""Verify seat-aware multiway read/stack selection in the core plan layer."""
import json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS
import plan as PL

def prof():
    c={k:7.0 for k in PS.ALL_CONCEPTS}
    t={k:7.0 for k in PS.TEMPER}
    return {'id':1,'concepts':c,'temper':t,'type':'TAG',
            'aggr':7.0,'bluff':7.0,'gamble':5.0,'icm':7.0}

def est(ftb=.52,cbet=.55,barrel=.42,aggr=5.0,n=40,confidence=.9):
    return {'confidence':confidence,'n':n,'ftb':ftb,
            'ftb_flop':ftb,'ftb_turn':ftb,'ftb_river':ftb,
            'cbet':cbet,'barrel':barrel,'aggr':aggr,'bluff':4.5,
            'pf_3bet':.07,'pf_4bet':.04,'pf_fold_to_3bet':.55,
            'pf_fold_to_4bet':.60,'pf_limp':.06,
            'pf_fold_after_limp_raise':.48,'rfi_rel':1.0,
            'sz_mean':.62,'sz_sd':.22,'sz_n':0,'sz_big':.15,
            'sz_river':.62}

def main():
    p=prof()
    station=est(ftb=.18,cbet=.25,barrel=.20,aggr=2.5)
    folder=est(ftb=.86,cbet=.48,barrel=.30,aggr=4.0)
    bettor=est(ftb=.55,cbet=.90,barrel=.82,aggr=9.0)
    m={'station':station,'folder':folder,'bettor':bettor}

    fold_pick=PL.select_field_opponent(p,m,'flop','fold_constraint')
    bet_pick=PL.select_field_opponent(p,m,'flop','bet_probability')

    # If one opponent is unread, exploiting another opponent's over-fold is not
    # enough to assume the whole field folds.
    unknown=est(ftb=.90,cbet=.90,barrel=.90,aggr=9,n=0,confidence=0.0)
    unknown_pick=PL.select_field_opponent(
        p,{'folder':folder,'unknown':unknown},'flop','fold_constraint')

    checks={
      'sticky_opponent_constrains_field_bluff':
          fold_pick is not None and fold_pick['seat']=='station',
      'likely_bettor_drives_trap_candidate':
          bet_pick is not None and bet_pick['seat']=='bettor',
      'unknown_opponent_blocks_overconfident_fold_exploit':
          unknown_pick is not None and unknown_pick['seat']=='unknown',
      'max_live_stack_preserved':
          PL.field_effective_stack_bb({'a':12.0,'b':45.0,'c':7.5},20.0)==45.0,
      'fallback_stack_preserved':
          PL.field_effective_stack_bb({},20.0)==20.0,
    }
    out={
      'pass':all(checks.values()),'checks':checks,
      'fold_pick':None if fold_pick is None else {
        'seat':fold_pick['seat'],'score':round(fold_pick['score'],6)},
      'bet_pick':None if bet_pick is None else {
        'seat':bet_pick['seat'],'score':round(bet_pick['score'],6)},
      'unknown_pick':None if unknown_pick is None else {
        'seat':unknown_pick['seat'],'score':round(unknown_pick['score'],6)},
    }
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__':
    main()
