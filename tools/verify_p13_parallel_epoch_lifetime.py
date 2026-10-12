#!/usr/bin/env python3
"""P13/P15 whole-field observation, frozen lifetime, and real live2.finish audit.

No policy/RNG/hand scheduling change: only controls and epoch provenance.
"""
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import icm as I
import fieldsim as FS
import live2 as L
from tools.verify_p13_field_epoch_freshness import field, stamped


def partial_roster_unobservable():
    f=field()
    h=stamped(f)
    original=h.bf_details(3)
    assert original['is_exact'] and original['snapshot_current']
    all_stacks=dict(h.field_pid_stacks)
    # Real mini workers have only local player rows while the frozen context
    # contains all survivors. Never label such a partial map a new full epoch.
    mini=SimpleNamespace(
        players={str(s):{'pid':'P%s'%s,'stack':all_stacks['P%s'%s]}
                 for s in (1,3,5,8,9)},
        hand_no=f.hand_no,level=f.level,_frozen_field=None)
    h._field_epoch_owner=mini
    partial=h.bf_details(3)
    assert partial['field_epoch_status']=='unobservable_partial_field',partial
    assert partial['field_observation_status']=='incomplete_current_field_roster'
    assert partial['observed_field_epoch_id'] is None
    assert partial['observed_epoch_diverged'] is None
    assert not partial['snapshot_current'] and not partial['snapshot_epoch_exact']
    assert not partial['is_exact']
    assert partial['reason']=='current_field_unobservable_partial_roster'
    assert partial['method']=='field_bf_empirical_approximation'
    assert partial['value']!=1.0

    frozen=f.field_snapshot()
    f._frozen_field=frozen
    h2=stamped(f)
    full=h2.bf_details(3)
    assert full['method']=='frozen_epoch_reference_icm'
    mini._frozen_field=frozen
    h2._field_epoch_owner=mini
    small=h2.bf_details(3)
    assert small==full, (small,full)
    assert small['observed_field_epoch_id'] is None
    assert small['observed_epoch_diverged'] is None
    assert small['snapshot_epoch_exact'] and not small['snapshot_current']
    print(json.dumps({'case':'partial_worker',
                      'full_roster_method':original['method'],
                      'partial_method':partial['method'],
                      'partial_observed_epoch':partial['observed_field_epoch_id'],
                      'partial_divergence':partial['observed_epoch_diverged'],
                      'frozen_provenance_equal_full_vs_mini':small==full,
                      'frozen_bf':full['value']},sort_keys=True))
    return f,h2,mini,frozen


def frozen_lifetime():
    f,h,mini,frozen=partial_roster_unobservable()
    assert frozen['hand_no']==0 and frozen['level']==1
    for field_name,next_value in [('hand_no',1),('level',2)]:
        original=getattr(mini,field_name)
        setattr(mini,field_name,next_value)
        expired=h.bf_details(3)
        assert expired['field_epoch_status']=='expired_frozen_epoch',expired
        assert expired['reason']=='frozen_snapshot_lifecycle_expired'
        assert expired['field_observation_status']=='frozen_clock_mismatch'
        assert expired['observed_field_epoch_id'] is None
        assert expired['observed_epoch_diverged'] is None
        assert not expired['snapshot_epoch_exact']
        assert not expired['snapshot_current'] and not expired['is_exact']
        assert expired['method']=='field_bf_empirical_approximation'
        print(json.dumps({'case':'frozen_clock_expiry',
                          'changed':field_name,
                          'old':original,'new':next_value,
                          'method':expired['method'],
                          'reason':expired['reason']},sort_keys=True))
        setattr(mini,field_name,original)
    # Full-roster coordinator is also forbidden from renewing a frozen epoch
    # after its tournament clock moved, even with the same frozen object.
    f.hand_no=1
    expired_full=h.bf_details(3) if False else None
    h._field_epoch_owner=f
    expired_full=h.bf_details(3)
    assert expired_full['field_epoch_status']=='expired_frozen_epoch'
    f.hand_no=0
    f.level=2
    assert h.bf_details(3)['field_epoch_status']=='expired_frozen_epoch'
    f.level=1
    f._frozen_field=None
    assert h.bf_details(3)['field_epoch_status']=='expired_frozen_epoch'
    assert h.bf_details(3)['field_observation_status']=='frozen_reference_released_or_replaced'
    print('PASS frozen hand 0->1, level 1->2, release, complete/partial owner lifetime')


def synchronous_finish_epoch():
    f0=FS.Field(entries=18,start_stack=30000,hero_pid=0,seed=943)
    st={'field':L._dump(f0),'hand_seed':943001,
        'actions':[],'decisions':[],'notes':[],'hero_memos':{}}
    f,tb,alive,h,hero=L.build_hand(st)
    assert f.remaining()>len(alive)
    start_epoch=h.field_snapshot_id
    assert start_epoch
    # Controlled finished HERO chip movement (not a constructed poker result).
    other=next(s for s in h.seats if s!=hero)
    h.stacks[hero]+=100
    h.stacks[other]-=100
    captured=[]
    before_other=[]
    real_step=f.step_others
    def recorded_step(*args,**kwargs):
        before_other.append(f.field_snapshot()['epoch_id'])
        return real_step(*args,**kwargs)
    f.step_others=recorded_step
    run=SimpleNamespace(result={'full_log':[]},recorded=[],
                        full_action_meta=[],preflop_errors=[])
    # All production finish routing is executed, but telemetry is captured
    # instead of writing files or contaminating any user tournament.
    with patch.object(L,'save'), patch.object(L,'_archive_write',
                    side_effect=lambda rec:captured.append(rec)), \
         patch.object(FS.Field,'_log_bot_hand',lambda *a,**kw:None), \
         patch.object(L.TM,'emit_round'), patch.object(L.TM,'read_bot_round',
                    return_value=[]):
        result=L.finish(st,f,tb,alive,h,run,defer_others=False)
    assert result['done'] and captured and before_other
    logged=captured[0]['field_epoch_timing']
    assert logged['execution_path']=='synchronous_after_hero'
    assert logged['hero_hand_start_phase']=='before_hero_hand_action'
    assert logged['hero_hand_start_epoch_id']==start_epoch
    assert logged['other_tables_reference_epoch_id']==before_other[0]
    assert logged['hero_hand_start_epoch_id']!=logged['other_tables_reference_epoch_id']
    assert logged['other_tables_reference_phase']==(
        'after_hero_hand_completed_before_other_table_work')
    assert logged['common_start_epoch_verified'] is False
    assert run.result['hero_seat']==hero
    print(json.dumps({'case':'live2.finish(defer_others=False)',
                      'hero_start_epoch':start_epoch,
                      'other_table_reference_epoch':before_other[0],
                      'different_phase':True,
                      'same_epoch_claim':logged['common_start_epoch_verified'],
                      'archived':True},sort_keys=True))


if __name__=='__main__':
    frozen_lifetime()
    synchronous_finish_epoch()
    print('PASS P13/P15 partial roster, exact epoch lifetime, and synchronous finish timing')
