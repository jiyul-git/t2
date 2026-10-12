"""Disposition-aware heuristic calloff timing: strategy/RNG and context controls."""
import copy
import math
import random
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import persona as PS
import preflop as PF
import timing as TM
import session as SE


def profile(skill=2, loose=10, gamble=10):
    return {'type':'STATION', 'aggr':5, 'gamble':gamble,
            'concepts':{k:skill for k in PS.ALL_CONCEPTS},
            'temper':dict({k:5 for k in PS.TEMPER}, looseness=loose, gamble=gamble)}


def decision():
    return {'pf_act':'call','pf_timing':{'kind':'defend_calloff','r':.32,'cap':.32}}


def timed(p, d, street='preflop', c=1):
    run=SE.HandRun.__new__(SE.HandRun)
    run.h=SimpleNamespace(pid_of=lambda s:s,hash='calloff-effort',rng=random.Random(123))
    run.timing={'tour_seed':20261009,'fmt_key':'standard','banks':{},'clock':0,'fingerprint':True}
    run.timing_log=[]
    before=run.h.rng.getstate()
    rec=run._timing_decide(2,street,p,c,.3,0,1,False,0,{'pf_defend','potodds'},decision=d)
    assert before==run.h.rng.getstate()
    return rec


def main():
    d=decision(); p=profile()
    slow=timed(p,None); fast=timed(p,d)
    assert fast['c']==slow['c']==1
    assert fast['elapsed']<slow['elapsed']
    assert fast['decision_effort']['source']=='heuristic_calloff_disposition'
    assert fast==timed(p,d)
    assert fast['bank_used']<=slow['bank_used']
    # Continuous response to the SAME existing temperament, no hand/stack cutoff.
    for field in ('loose','gamble','skill'):
        vals=[]
        for value in (0,2,5,8,10):
            args={'skill':2,'loose':10,'gamble':10};args[field]=value
            vals.append(timed(profile(**args),d)['elapsed'])
        if field=='skill':
            weights=[TM.preflop_calloff_effort(profile(skill=v),d)['weight'] for v in (0,2,5,8,10)]
            assert weights==sorted(weights)
        else:
            assert vals==sorted(vals,reverse=True),(field,vals)
    # Exact price judgment, folds, routine defense and postflop are unchanged.
    controls=[]
    for mutation in ({'pf_act':'fold'}, {'pf_timing':{'kind':'calloff_layer','eq':.5,'need':.5}},
                     {'pf_timing':{'kind':'defend','r':.32,'tot':.32}},
                     {'pf_calloff_consumer':{'strategy_consumer':True}}):
        control=copy.deepcopy(d);control.update(mutation)
        assert timed(p,control)['visible']==slow['visible']
        controls.append(control)
    assert timed(p,d,'flop')['visible']==timed(p,None,'flop')['visible']
    assert TM.preflop_calloff_effort({},d)['weight']==1
    assert TM.preflop_calloff_effort(profile(loose=0),d)['weight']==1
    assert TM.preflop_calloff_effort(profile(gamble=0),d)['weight']==1
    # A real K♠ 8♥ 30bb 9-max heuristic call remains the SAME action/RNG.
    actual=profile(skill=0)
    rng=random.Random(1)
    action=PF.defend_decision(actual,'BB','UTG',['Ks','8h'],30,30,0,rng,
        seats=9,stack_bb=30,opener_allin=True,can_raise=False,pot_bb=32,to_call_bb=29)
    bound=PF.take_timing_bound();state=rng.getstate()
    assert action==('call',29.0)
    payload={'pf_act':action[0],'pf_timing':bound}
    rec=timed(actual,payload,c=TM.closeness_preflop(bound))
    assert rng.getstate()==state
    print('PASS: boundary, deterministic time, temperament monotonicity, exact/ordinary/fold/postflop controls, RNG')
    print('Controlled marginal call: before %.6fs / bank %.6fs; after %.6fs / bank %.6fs' %
          (slow['elapsed'],slow['bank_used'],fast['elapsed'],fast['bank_used']))
    print('Real decision fixture K♠ 8♥ BB vs UTG 30bb, 9-max:',action,'c=',rec['c'],'effort=',rec['decision_effort'])

if __name__=='__main__':main()
