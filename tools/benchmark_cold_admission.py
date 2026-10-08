"""Isolated real-backend timing/determinism comparison; no user state touched."""
import argparse
import hashlib
import itertools
import json
import os
import pathlib
import sys
import tempfile
import time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
os.environ['T2_BOT_LOG']='0';os.environ['T2_TELEMETRY']='0'
os.environ['T2_FIELD_BACKEND']='real';os.environ['T2_TIMING_V1']='enforce'
import bot
import scheduled_runtime as SR
import tournament_store as TS
parser=argparse.ArgumentParser();parser.add_argument('--legacy-evaluator',action='store_true')
parser.add_argument('--seconds',type=float,default=90);parser.add_argument('--budget',type=int,default=18)
parser.add_argument('--state-out')
args=parser.parse_args()
if args.legacy_evaluator:
    bot._eval_best=lambda cs:max(bot.eval5(list(c)) for c in itertools.combinations(cs,5))
with tempfile.TemporaryDirectory() as td:
    store=TS.Store(td,10000,[dict(fmt='turbo',minute=0,buyin=500,bot_entries=44,
                               late_minutes=30,max_reentries=2)])
    start=1790000000-1790000000%3600
    store.ensure_schedule(start)
    event=store.event('turbo:%d'%start)
    store.reserve(event['id'],now=start+args.seconds)
    store.request_enter(event['id'],now=start+args.seconds)
    event=store.event(event['id'])
    # A paid entry at t cannot occupy a hand that ends after t until that
    # boundary is reached. Allow the same advancing clock as a live admission.
    target=args.seconds+90
    t=time.perf_counter();cpu=time.process_time();batches=0;first=None
    while True:
        result=SR.advance(event,target,budget=args.budget,parallel=False)
        if first is None:first=time.perf_counter()-t
        store.save_state(event['id'],result['state'],event['revision'],result['assignments'],now=start+args.seconds)
        event=store.event(event['id']);batches+=1
        state=event['state']
        if state.get('hero_ready') and state.get('background_seconds',0)>=target-15:
            break
        assert batches<100, (state.get('background_seconds'),state.get('hero_ready'))
    digest=hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if args.state_out:pathlib.Path(args.state_out).write_text(json.dumps(state,sort_keys=True))
    print(json.dumps({'pass':True,'legacy':args.legacy_evaluator,'target_seconds':target,
          'budget':args.budget,'batches':batches,'first_snapshot_seconds':first,
          'wall_seconds':time.perf_counter()-t,'cpu_seconds':time.process_time()-cpu,
          'state_sha256':digest,'backend':event['rules']['field_backend']}))
