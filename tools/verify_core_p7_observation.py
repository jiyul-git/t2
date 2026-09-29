#!/usr/bin/env python3
"""Verify dedicated P7 cold-reraise observation semantics."""
import json, pathlib, random, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import reads as RD
import session as SS
import persona as PS

def m(seat, action, full=False, raised=False, allin_call=False):
    return {'seat':seat,'action':action,'full_raise':bool(full),
            'raised':bool(raised),'allin_call':bool(allin_call)}

def main():
    # C has not acted when two full raises are in front -> cold response.
    call_meta=[
        m('A','raise',True,True),
        m('B','raise',True,True),
        m('C','call',False,False),
    ]
    fold_meta=[
        m('A','raise',True,True),
        m('B','raise',True,True),
        m('C','fold',False,False),
    ]
    raise_meta=[
        m('A','raise',True,True),
        m('B','raise',True,True),
        m('C','raise',True,True),
    ]
    opener_back=[
        m('A','raise',True,True),
        m('B','raise',True,True),
        m('A','fold',False,False),
    ]
    caller_back=[
        m('A','raise',True,True),
        m('C','call',False,False),
        m('B','raise',True,True),
        m('C','fold',False,False),
    ]
    fc=SS._pf_observation_flags(call_meta,'C')
    ff=SS._pf_observation_flags(fold_meta,'C')
    fr=SS._pf_observation_flags(raise_meta,'C')
    fo=SS._pf_observation_flags(opener_back,'A')
    fb=SS._pf_observation_flags(caller_back,'C')

    bk=RD.Book()
    obs=['observer']
    # Four independent opportunities: call, call, raise, fold.
    for action in ('call','call','raise','fold'):
        bk.observe_preflop(obs,'vill',vpip=(action!='fold'),
                           pfr=(action=='raise'),limp=False,
                           limp_chance=False,rfi_exp=None)
        bk.observe_cold_reraise(
            obs,'vill',True,
            called=(action=='call'),
            raised=(action=='raise'),
            folded=(action=='fold'))
    rec=bk.rec('observer','vill')

    c={k:5.0 for k in PS.ALL_CONCEPTS}
    t={k:5.0 for k in PS.TEMPER}
    observer={'id':1,'concepts':c,'temper':t,'type':'TAG'}
    est=RD.estimate(bk,'observer','vill',observer,random.Random(44))
    pp=RD.perceived_profile(
        bk,'observer','vill',observer,random.Random(44))

    checks={
      'cold_call_classified':
          fc['cold_reraise_chance'] and fc['cold_reraise_call']
          and not fc['cold_reraise_raise'] and not fc['cold_reraise_fold'],
      'cold_fold_classified':
          ff['cold_reraise_chance'] and ff['cold_reraise_fold'],
      'cold_raise_classified':
          fr['cold_reraise_chance'] and fr['cold_reraise_raise'],
      'opener_response_not_mislabeled_cold':
          not fo['cold_reraise_chance'] and fo['faced_threebet_as_opener'],
      'caller_squeeze_response_not_mislabeled_cold':
          not fb['cold_reraise_chance'] and fb['backraise_chance_as_caller'],
      'book_counts_exact':
          rec['pf_cold_reraise_opp']==4
          and rec['pf_cold_reraise_call']==2
          and rec['pf_cold_reraise_raise']==1
          and rec['pf_cold_reraise_fold']==1,
      'raw_rates_exact_no_invented_prior':
          est['pf_cold_reraise_n']==4
          and est['pf_cold_reraise_call']==0.5
          and est['pf_cold_reraise_raise']==0.25
          and est['pf_cold_reraise_fold']==0.25,
      'perceived_profile_carries_p7_observation':
          pp['pf_cold_reraise_n']==4
          and pp['pf_cold_reraise_call']==0.5,
    }
    out={'pass':all(checks.values()),'checks':checks,
         'flags':{'call':fc,'fold':ff,'raise':fr,
                  'opener_back':fo,'caller_back':fb},
         'book':{k:rec[k] for k in (
             'pf_cold_reraise_opp','pf_cold_reraise_call',
             'pf_cold_reraise_raise','pf_cold_reraise_fold')},
         'estimate':{k:est.get(k) for k in (
             'pf_cold_reraise_n','pf_cold_reraise_call',
             'pf_cold_reraise_raise','pf_cold_reraise_fold')}}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__':
    main()
