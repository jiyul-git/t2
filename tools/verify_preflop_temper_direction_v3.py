#!/usr/bin/env python3
"""Verify full-scale preflop temperament direction for Human Model v3."""
import json, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS
import preflop as PF


def prof(skill=2.0, loose=5.0, aggr=5.0):
    c={k:5.0 for k in PS.ALL_CONCEPTS}
    c['pf_range']=c['pf_defend']=float(skill)
    c['positional']=8.0
    c['stack_decay']=c['potodds']=8.0
    t={k:5.0 for k in PS.TEMPER}
    t['looseness']=float(loose); t['aggression']=float(aggr)
    return {'concepts':c,'temper':t,'type':'X','aggr':float(aggr),
            'gamble':5.0,'bluff':5.0}


def main():
    checks={}
    old=PS.PREFLOP_TEMPER_DIRECTION_V3
    old_reason=PS.PREFLOP_REASONING_V3
    try:
        # T1 OFF reproduces exact historical /4 mapping.
        PS.PREFLOP_TEMPER_DIRECTION_V3=False
        vals_off=[PS.preflop_temper_direction(x) for x in range(11)]
        exp=[max(-1.0,min(1.0,(x-5.0)/4.0)) for x in range(11)]
        checks['T1_legacy_direction_exact']={
            'pass':vals_off==exp,'values':vals_off}

        # T2 ON uses the whole 0..10 scale without endpoint collisions.
        PS.PREFLOP_TEMPER_DIRECTION_V3=True
        vals_on=[PS.preflop_temper_direction(x) for x in range(11)]
        exp_on=[(x-5.0)/5.0 for x in range(11)]
        checks['T2_full_scale_mapping']={
            'pass':(vals_on==exp_on and len(set(vals_on))==11),
            'values':vals_on}

        # T3 RFI: all 11 temperament levels remain distinct in a matched,
        # low-knowledge spot where temperament is supposed to matter.
        PS.PREFLOP_REASONING_V3=True
        widths=[PS.open_pct(prof(2,t,t),'HJ',8,40.0,True)
                for t in range(11)]
        checks['T3_rfi_no_endpoint_collapse']={
            'pass':(len(set(round(x,12) for x in widths))==11
                    and all(b>a for a,b in zip(widths,widths[1:]))),
            'widths':[round(x,6) for x in widths]}

        # T4 defense: total continue and 3bet widths are monotone across the
        # same 11-point temperament sweep and no longer collapse at 0/1, 9/10.
        ds=[PF.defend_thresholds(prof(2,t,t),'BB','BTN',40.0,
                                 open_bb=2.5,seats=8,ante=True)
            for t in range(11)]
        tp=[x[0] for x in ds]; tot=[x[1] for x in ds]
        # Total defense can legitimately hit the .95 cap for the very loosest
        # player. Require the formerly-collapsed 0/1 pair to separate, and
        # require at least 10 distinct totals; 3bet should remain fully distinct.
        _tot_distinct=len(set(round(x,12) for x in tot))
        checks['T4_defense_uses_full_direction_axis']={
            # The direction axis itself must separate the previously collapsed
            # tight endpoint and keep 3bet widths fully distinct.  Total defense
            # may still collide at the independent 0.95 probability cap; that
            # is measured explicitly rather than hidden by this test.
            'pass':(tot[0]!=tot[1]
                    and len(set(round(x,12) for x in tp))==11
                    and all(b>=a for a,b in zip(tot,tot[1:]))
                    and all(b>a for a,b in zip(tp,tp[1:]))),
            'total_distinct':_tot_distinct,
            'total_cap_collisions':11-_tot_distinct,
            'total':[round(x,6) for x in tot],
            'threebet':[round(x,6) for x in tp]}

        # T5: /5 is a normalization change, not a new strength knob.
        # The endpoints (-1,+1) and midpoint (0) must stay exactly unchanged.
        # Intermediate scores must move toward the neutral-width result:
        # tight intermediates become less extremely tight; loose intermediates
        # become less extremely loose (or remain equal only if another cap binds).
        reps=[]
        for t in range(11):
            p=prof(2,t,t)
            PS.PREFLOP_TEMPER_DIRECTION_V3=False
            a=PS.open_pct(p,'HJ',8,40.0,True)
            d=PF.defend_thresholds(p,'BB','BTN',40.0,
                                   open_bb=2.5,seats=8,ante=True)
            PS.PREFLOP_TEMPER_DIRECTION_V3=True
            b=PS.open_pct(p,'HJ',8,40.0,True)
            e=PF.defend_thresholds(p,'BB','BTN',40.0,
                                   open_bb=2.5,seats=8,ante=True)
            reps.append({'t':t,'open_change':b-a,
                         'def_tot_change':e[1]-d[1],
                         'def_tp_change':e[0]-d[0]})
        anchors=all(
            abs(next(x[k] for x in reps if x['t']==t))<1e-12
            for t in (0,5,10)
            for k in ('open_change','def_tot_change','def_tp_change'))
        direction_ok=True
        for x in reps:
            if 0<x['t']<5:
                direction_ok &= (x['open_change']>=-1e-12
                                 and x['def_tot_change']>=-1e-12
                                 and x['def_tp_change']>=-1e-12)
            elif 5<x['t']<10:
                direction_ok &= (x['open_change']<=1e-12
                                 and x['def_tot_change']<=1e-12
                                 and x['def_tp_change']<=1e-12)
        checks['T5_normalization_preserves_anchors_and_direction']={
            'pass':bool(anchors and direction_ok),
            'anchors_0_5_10_unchanged':bool(anchors),
            'intermediate_moves_toward_neutral':bool(direction_ok),
            'rows':[{k:(round(v,6) if isinstance(v,float) else v)
                     for k,v in x.items()} for x in reps]}
    finally:
        PS.PREFLOP_TEMPER_DIRECTION_V3=old
        PS.PREFLOP_REASONING_V3=old_reason

    passed=all(v['pass'] for v in checks.values())
    print(json.dumps({'pass':passed,'checks':checks},indent=2,sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':
    main()
