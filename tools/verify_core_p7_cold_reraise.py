#!/usr/bin/env python3
"""Core P7 cold-vs-reraise verifier.

Checks the new production judgment, not a shadow:
- original opener + re-raiser ranges are both consumed;
- stronger original-opener range cannot make the cold-call easier;
- unresolved players behind raise perceived call requirement;
- higher range/pot-odds skill reacts more strongly to a bad cold-call;
- incomplete seat ranges fall back safely instead of inventing a second range.
"""
import json, pathlib, random, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS
import preflop as PF
import ranges as R

def prof(skill):
    c={k:float(skill) for k in PS.ALL_CONCEPTS}
    t={k:5.0 for k in PS.TEMPER}
    t['aggression']=5.0; t['looseness']=5.0
    return {'id':77,'concepts':c,'temper':t,'type':'TAG',
            'aggr':5.0,'bluff':float(skill),'gamble':5.0,'icm':float(skill)}

def top(frac):
    return [c for c in R.ALL if PF.pct(c) <= frac]

def audit(profile, hand, opener_range, behind=0, seed=991):
    _a,_s,x=PF.cold_reraise_decision(
        profile,'CO','HJ',hand,40.0,8.0,0,random.Random(1234),
        raise_level=2,stack_bb=40.0,exploit=None,bf=1.0,
        seats=9,ante=True,can_raise=True,pot_bb=13.0,to_call_bb=8.0,
        original_opener_range=opener_range,
        reraiser_range=top(0.08),players_behind=behind,
        decision_seed=seed)
    return x

def main():
    tight=top(0.07); wide=top(0.30)
    hands=(['As','Qh'],['Js','Jh'],['Ts','Th'],['Ah','Kh'],['9s','9h'])
    hi=prof(9); lo=prof(1)

    rows=[]
    for k,h in enumerate(hands):
        aw=audit(hi,h,wide,0,100+k)
        at=audit(hi,h,tight,0,100+k)
        ab=audit(hi,h,wide,3,100+k)
        rows.append({'hand':h,'wide':aw,'tight':at,'behind3':ab})

    complete=all(r['wide'].get('complete') and r['tight'].get('complete')
                 and r['behind3'].get('complete') for r in rows)
    # The same reraiser with a tighter original opener should never produce
    # higher multiway showdown equity for every candidate. Require aggregate
    # direction plus at least one material separation.
    d_eq=[r['wide']['equity_vs_open_and_reraise']-
          r['tight']['equity_vs_open_and_reraise'] for r in rows]
    opener_identity_matters=(sum(d_eq) > 0 and max(d_eq) > 0.01)

    behind_need=all(r['behind3']['need_seen'] >= r['wide']['need_seen']-1e-9
                    for r in rows)
    behind_call=all(
        r['behind3']['final_likelihoods']['call']
        <= r['wide']['final_likelihoods']['call']+1e-9
        for r in rows)

    # Pick the most negative wide-range call edge; high skill should suppress
    # generic cold-calling at least as much as low skill.
    cand=min(hands,key=lambda h:
             audit(hi,h,wide,0,777)['equity_vs_open_and_reraise']-
             audit(hi,h,wide,0,777)['need_seen'])
    ah=audit(hi,cand,wide,0,777)
    al=audit(lo,cand,wide,0,777)
    hi_cut=ah['base_likelihoods']['call']-ah['final_likelihoods']['call']
    lo_cut=al['base_likelihoods']['call']-al['final_likelihoods']['call']
    skill_direction=(hi_cut >= lo_cut-1e-9)

    # Missing original-opener range must be an explicit fallback, not a copied
    # reraiser pool.
    _fa,_fs,fb=PF.cold_reraise_decision(
        hi,'CO','HJ',['As','Qh'],40.0,8.0,0,random.Random(7),
        raise_level=2,stack_bb=40.0,pot_bb=13.0,to_call_bb=8.0,
        original_opener_range=None,reraiser_range=top(0.08),
        players_behind=0,decision_seed=1,seats=9,ante=True)
    fallback_ok=(fb.get('complete') is False and
                 fb.get('reason')=='missing_two_ranges_or_price')

    checks={
      'complete_two_range_judgment':complete,
      'original_opener_identity_changes_equity':opener_identity_matters,
      'players_behind_raise_requirement':behind_need,
      'players_behind_do_not_widen_call':behind_call,
      'skill_uses_two_range_evidence_directionally':skill_direction,
      'missing_range_explicit_fallback':fallback_ok,
    }
    out={'pass':all(checks.values()),'checks':checks,
         'equity_delta_wide_minus_tight':d_eq,
         'skill_probe':{'hand':cand,'high_call_cut':hi_cut,'low_call_cut':lo_cut},
         'rows':[{'hand':r['hand'],
                  'wide_eq':r['wide']['equity_vs_open_and_reraise'],
                  'tight_eq':r['tight']['equity_vs_open_and_reraise'],
                  'wide_need':r['wide']['need_seen'],
                  'behind3_need':r['behind3']['need_seen'],
                  'wide_call':r['wide']['final_likelihoods']['call'],
                  'behind3_call':r['behind3']['final_likelihoods']['call']}
                 for r in rows]}
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__':
    main()
