#!/usr/bin/env python3
"""Snapshot origin audit; compare metadata-only patch with PR24 without rerouting play.

Python 3.12; git history needs BASE. No network access required by this script.
Each probe uses fresh state/archive directories. Both timing OFF and ON are paired.
"""
import argparse, copy, json, os, pathlib, platform, subprocess, sys, tempfile
BASE = '75c6ee2db50a06a0f3141835f063695c26c6ebc7'
ROOT = pathlib.Path(__file__).resolve().parents[1]


def probe(root):
    sys.path.insert(0, str(root))
    import live2 as L, fieldsim as FS
    import random
    snapshots, kept, completed = [], [], []
    original = FS.Field.stamp
    def capture(f, h):
        out = original(f, h)
        before = (random.getstate(), f.rng.getstate(), h.rng.getstate())
        # Read-only provenance must not consume any of the three RNGs.
        prov = h.bf_details(h.seats[0])
        assert before == (random.getstate(), f.rng.getstate(), h.rng.getstate())
        snapshots.append({'hero': h.hero is not None, 'id': h.field_snapshot_id,
                          'phase': getattr(h, 'field_snapshot_phase', 'unknown'),
                          'clock': getattr(h, 'field_snapshot_clock', None),
                          'pids': dict(h.field_pid_stacks), 'bf_phase': prov.get('field_snapshot_phase')})
        kept.append((f,h))
        return out
    old_bot_log, old_archive = FS.Field._log_bot_hand, L._archive
    def capture_result(f, h, res):
        completed.append({'table':h.table_id, 'full_log':res.get('full_log'),
                          'how':res.get('how'),'winners':res.get('winners'),'pot':res.get('pot'),
                          'stacks':dict(h.stacks),'time_banks':copy.deepcopy(getattr(f,'time_banks',{})),
                          'hand_rng':repr(h.rng.getstate()),'field_rng':repr(f.rng.getstate())})
    def bot_log(f,tb,h,run):
        capture_result(f,h,run.result or {})
        return old_bot_log(f,tb,h,run)
    def archive(st,f,h,res,*a,**kw):
        capture_result(f,h,res)
        rec=old_archive(st,f,h,res,*a,**kw)
        if hasattr(h,'field_snapshot_phase'):
            ctx=rec['field_context']
            assert ctx['snapshot_phase']==h.field_snapshot_phase
            assert ctx['snapshot_id']==h.field_snapshot_id
            assert ctx['snapshot_clock']==h.field_snapshot_clock
        return rec
    FS.Field.stamp = capture
    FS.Field._log_bot_hand, L._archive = bot_log, archive
    outcomes, origins = {}, {}
    try:
        for mode in ('default', 'deferred', 'vclock'):
            L.new_game(entries=27, seed=817, fmt='standard')
            snaps0=len(snapshots); hands0=len(kept); done0=len(completed)
            for _ in range(3):
                holder={}
                def started(base):
                    if mode=='deferred':holder['out']=L.compute_others_parallel(base)
                kw={'defer_others':mode=='deferred','vclock_others':mode=='vclock',
                    'on_round_start':started}
                r=L.step(**kw)
                for _ in range(30):
                    if r.get('done'):break
                    raw=r.get('raw') or {}
                    r=L.step('check' if float(raw.get('tocall') or 0)<=0 else 'fold',
                             defer_others=mode=='deferred',others=holder.get('out'),
                             vclock_others=mode=='vclock')
                assert r.get('done'),r
                if mode=='vclock':
                    st=L.load();st['hand_seed']=None
                    target=float(st['field'].get('virtual_play_seconds') or 0)+60
                    work=L.compute_vclock_ahead(st['field'],target,session_end=target)
                    events={k:v['events'] for k,v in work['tables'].items()}
                    L.apply_vclock_events(st,events,{},target,independent_hero=True)
                    L.finalize_vclock_settle(st,independent_hero=True)
                    L.save(st)
            st=L.load()
            # State contains ranks, busted order, moves, table seats, book,
            # banks and clocks. Per-hand stacks/cards/actions plus final RNG
            # states are compared independently of provenance serialization.
            outcomes[mode]={'state':st, 'completed':completed[done0:], 'hands':[
                {'table':h.table_id, 'hole':h.hole, 'board':h.board,
                 'stacks':h.stacks, 'rng':repr(h.rng.getstate()),
                 'field_rng':repr(f.rng.getstate())}
                for f,h in kept[hands0:]]}
            origins[mode]=snapshots[snaps0:]
        # Standalone legacy helper consumes precisely its supplied observed field.
        base=L.load()['field']
        start=len(snapshots)
        old_level=FS.Field.BOT_LOG
        FS.Field.BOT_LOG=1
        try:
            legacy=L.compute_others(base)
            rows=[json.loads(line) for line in legacy['bot_log'].splitlines()]
            assert rows, 'legacy fixture must actually produce summary bot logs'
            if any(x['phase']!='unknown' for x in snapshots[start:]):
                assert all(x['field_snapshot']['phase']=='legacy_input_field' for x in rows)
                assert all(x['field_snapshot']['id'] for x in rows)
        finally:FS.Field.BOT_LOG=old_level
        origins['legacy_helper']=snapshots[start:]
    finally:
        FS.Field.stamp=original
        FS.Field._log_bot_hand, L._archive = old_bot_log, old_archive
    # Metadata in persisted archives/telemetry must not contaminate the
    # independently compared game state, pending results or replay inputs.
    def strip(v):
        if isinstance(v,dict):
            return {k:strip(x) for k,x in v.items() if k not in
                    {'snapshot_id','snapshot_phase','snapshot_hand_no','snapshot_level','snapshot_clock',
                     'field_snapshot_phase','field_snapshot_clock','field_snapshot','telemetry_session_id'} }
        if isinstance(v,list):return [strip(x) for x in v]
        if v=='frozen_reference_epoch_not_decision_current':return 'frozen_common_round_epoch_not_decision_current'
        return v
    return {'outcomes':strip(outcomes),'origins':origins}


def run_probe(root, timing):
    with tempfile.TemporaryDirectory(prefix='p15_state_') as td:
        env=dict(os.environ,T2_LIVE_STATE=str(pathlib.Path(td)/'state.json'),
                 T2_HAND_ARCHIVE=str(pathlib.Path(td)/'hands.jsonl'),
                 T2_BOT_LOG='0',T2_TABLE_WORKERS='1',T2_TIMING_V1=timing,PYTHONHASHSEED='0')
        r=subprocess.run([sys.executable,str(pathlib.Path(__file__).resolve()),'--probe','--root',str(root)],
                         env=env,cwd=td,text=True,capture_output=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        return json.loads(r.stdout)


def verify_origins(data):
    rows=data['origins']
    h=next(x for x in rows['default'] if x['hero'])
    b=next(x for x in rows['default'] if not x['hero'])
    assert h['phase']=='hero_hand_start_observed_field'
    assert b['phase']=='post_hero_settlement'
    assert h['id']!=b['id'],'fixture must witness actual HERO chip change'
    assert h['bf_phase']==h['phase'] and b['bf_phase']==b['phase']
    h=next(x for x in rows['deferred'] if x['hero'])
    b=next(x for x in rows['deferred'] if not x['hero'])
    assert h['id']==b['id']
    assert b['phase']=='round_start_other_tables'
    assert any(x['phase']=='vclock_precompute_batch_start' for x in rows['vclock'])
    assert any(x['phase']=='legacy_input_field' for x in rows['legacy_helper'])
    return {'default_hero_and_bot_epochs_equal':False,'deferred_start_epochs_equal':True,
            'vclock_independent_batch_origin':True,'bf_origin_preserved':True}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',action='store_true');ap.add_argument('--root',type=pathlib.Path,default=ROOT)
    args=ap.parse_args()
    if args.probe:print(json.dumps(probe(args.root),default=str,sort_keys=True));return
    with tempfile.TemporaryDirectory(prefix='p15_baseline_') as td:
        old=pathlib.Path(td)/'base'
        subprocess.run(['git','worktree','add','--detach',str(old),BASE],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        try:
            results=[]
            for timing in ('off','on'):
                before=run_probe(old,timing);after=run_probe(ROOT,timing)
                assert before['outcomes']==after['outcomes'],f'game/state/RNG changed: {timing}'
                results.append(dict(timing=timing,paired_game_state_and_rng_identical=True,**verify_origins(after)))
        finally:subprocess.run(['git','worktree','remove','--force',str(old)],cwd=ROOT,check=True)
    print(json.dumps({'pass':True,'baseline':BASE,'python':platform.python_version(),
                      'platform':platform.platform(),'entries':27,'seed':817,'rounds_per_mode':3,
                      'modes':['default','deferred','vclock'],'results':results},indent=2))

if __name__=='__main__':main()
