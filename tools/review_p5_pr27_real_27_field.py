#!/usr/bin/env python3
"""Independent real 27-player 3-table frozen field -> P5 seed provenance test.

This complements source-level epoch fixtures with actual HandRun bot plans.
No changes to strategy, physical action order, or RNG.
"""
import json
import os
import sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fieldsim as FS
import plan as PL

def main(on):
    old=os.environ.get('T2_RANGE_CONDITIONAL_V1')
    if on:os.environ['T2_RANGE_CONDITIONAL_V1']='1'
    else:os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
    orig=PL.preflop_plan
    records=[]
    def wrapper(ax,pos,hand,bbs,rng,**kwargs):
        fr=sys._getframe(1)
        h=fr.f_locals['h']
        seat=fr.f_locals['s']
        details=h.bf_details(seat)
        assert kwargs['bf']==details['value'],'P5 scalar BF != detailed BF'
        assert details['observed_field_epoch_id'] is None
        assert details['observed_epoch_diverged'] is None
        assert details['snapshot_current'] is False
        assert details['is_exact'] is False
        assert details['field_snapshot_scope']=='simultaneous_frozen'
        assert details['bf_kind']=='generic_default_risk_not_spot_call_prize_ev'
        assert details['price_specific'] is False
        result=orig(ax,pos,hand,bbs,rng,**kwargs)
        records.append((h,seat,details))
        return result
    try:
        PL.preflop_plan=wrapper
        f=FS.Field(entries=27,start_stack=30000,hero_pid=-1,
                   seed=37071,hands_per_level=12)
        assert f.remaining()==27
        tables=[tb for tb in f.tables.values() if tb.n()>=2]
        assert len(tables)==3,len(tables)
        frozen=f._frozen_field=f.field_snapshot()
        try:
            for tb in tables:
                ok=f._play_table(tb)
                assert ok is not None,(tb.id,f.errors)
        finally:
            f._frozen_field=None
        assert not f.errors,f.errors
    finally:
        PL.preflop_plan=orig
        if old is None:os.environ.pop('T2_RANGE_CONDITIONAL_V1',None)
        else:os.environ['T2_RANGE_CONDITIONAL_V1']=old
    assert records
    actor_count=0
    field_modes={}
    source_summaries=[]
    for h,seat,details in records:
        seed=(h.pf_seed or {}).get(seat) or {}
        assert seed['pf_bf_provenance']==details,(
            'BF evidence lost after HandRun',seat)
        field_modes[details['field_epoch_status']]=(
            field_modes.get(details['field_epoch_status'],0)+1)
        if on:
            assert 'pf_opp_range_meta' in seed,('missing actor provenance root',seat)
            for target,meta in seed['pf_opp_range_meta'].items():
                actor=meta.get('actor_bf_provenance')
                if actor is None:continue
                actor_count+=1
                assert meta['observer_model_inputs']['actor_bf_provenance']==actor
                assert meta['observer_model_inputs']['bubble_factor']==actor['value']
                assert meta['actor_bf_evaluation_phase']=='observer_reconstruction'
                assert meta['actor_action_epoch_bf_verified'] is False
                assert actor['observed_field_epoch_id'] is None
                assert actor['observed_epoch_diverged'] is None
                assert actor['snapshot_current'] is False
                assert actor['price_specific'] is False
                consumer=seed.get('pf_calloff_consumer')
                if consumer:
                    assert consumer['opponent_range_evidence'][target]['actor_bf_provenance']==actor
        source_summaries.append((details['method'],details['value']))
    assert set(field_modes)=={'frozen_epoch_reference'},field_modes
    # 27>9 only empirical BF; do not falsely claim current field ICM.
    assert set(x[0] for x in source_summaries)=={
        'field_bf_empirical_approximation'},set(x[0] for x in source_summaries)
    assert actor_count>0 if on else actor_count==0,actor_count
    print(json.dumps({'case':'real_27_player_3table_frozen_P5_input',
       'conditional_on':on,'tables':len(tables),'plans':len(records),
       'epoch_status':field_modes,
       'bf_method':'field_bf_empirical_approximation',
       'actor_bf_provenance_records':actor_count,
       'remote_epoch_falsely_observed':False,
       'bf_seed_matches_planner_input':True,
       'engine_errors':len(f.errors)},sort_keys=True))
    print('PASS 27-player real frozen round BF numeric/hero+actor origin to final P5 seed')

if __name__=='__main__':
    main(False)
    main(True)
