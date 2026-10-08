#!/usr/bin/env python3
"""Core F7-D sizing ownership verifier.

Strategic/human sizing must be decided in PLAN.  Session/runner execution may
only replay and enforce legality/caps.
"""
import inspect, json, pathlib, random, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS
import plan as PL
import runner as RU
import session as SS

def prof(ptype='fish'):
    c={k:5.0 for k in PS.ALL_CONCEPTS}
    t={k:5.0 for k in PS.TEMPER}
    return {'id':901,'concepts':c,'temper':t,'type':ptype,
            'aggr':5.0,'bluff':5.0,'gamble':5.0,'icm':5.0}

def main():
    # Stage 9 B5: the runner compatibility wrapper was removed; persona owns the
    # single sizing-habit formula and runner must not re-expose it.

    p=prof('Fish')
    target,meta=PL.shape_planned_target(
        1375,p,2500,5000,seed=73)
    expected=PS.shape_size(1375,'Fish',random.Random(73),pot=2500,profile=p)
    ai,meta_ai=PL.shape_planned_target(
        5000,p,2500,5000,seed=73)

    session_src=inspect.getsource(SS.HandRun._run)
    act_sig=inspect.signature(PL.act_with_plan)

    # Direct no-wager plan execution: raw intent target is pot*0.60, then PLAN
    # owns human shaping before returning the action.
    st={'plan':'value_2street','rel':.8,'outs':0,
        'intents':{'flop':{'act':'bet','size':.60,'src':'test'}}}
    act,_,_=PL.act_with_plan(
        ['As','Ah'],['Kd','7c','2s'],p,st,
        pot=2000,tocall=0,stack=10000,street='flop',
        seed=11,size_shape_seed=73)
    raw=1200
    expected_bet=PS.shape_size(raw,'Fish',random.Random(73),pot=2000,profile=p)

    checks={
      'runner_has_no_sizing_formula': not hasattr(RU, 'shape_size'),
      'plan_helper_matches_canonical_habit': target==expected,
      'allin_target_not_jittered': ai==5000 and not meta_ai['called'],
      'session_has_no_execution_shape_call': 'RU.shape_size(' not in session_src,
      'act_with_plan_accepts_plan_shape_seed':
          'size_shape_seed' in act_sig.parameters,
      'direct_bet_is_shaped_in_plan': act==('bet',expected_bet),
      'direct_bet_provenance_is_plan':
          st.get('_last_size_shape',{}).get('source')=='plan'
          and st.get('_last_size_shape',{}).get('before')==raw
          and st.get('_last_size_shape',{}).get('after')==expected_bet,
    }
    out={'pass':all(checks.values()),'checks':checks,
         'helper':{'raw':1375,'expected':expected,'target':target,'meta':meta},
         'direct_bet':{'raw':raw,'expected':expected_bet,'action':act,
                       'meta':st.get('_last_size_shape')}}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__':
    main()
