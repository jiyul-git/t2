#!/usr/bin/env python3
"""Independent real 99-bot admission across the existing 55-minute break.

Keep a 60-second no-progress bound outside an independently verified scheduled
break. Never skip a break, speed up clocks, increase worker stall tolerance,
change production code, or alter the original scheduled-UI assertions.
"""
import json, os, pathlib, signal, socket, sqlite3, subprocess, sys, tempfile, time
import urllib.error, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='p17_late_break_') as td:
    install = pathlib.Path(td)/'T2'; data = install/'personal'; system = install/'system'
    env = {k:v for k,v in os.environ.items() if not k.startswith(('T2_', 'PYTHON'))}
    env.update(PYTHONHASHSEED='0', T2_INITIAL_CHIPS='10000', T2_TABLE_WORKERS='4',
               T2_TIMING_V1='enforce', T2_UI_DEFER='0', T2_TELEMETRY='0',
               T2_HERO_ACTION_SECONDS='3', T2_TIMING_TEST_BASE='3', T2_TIMING_TEST_BANK='0')
    subprocess.run([sys.executable,str(ROOT/'ui/tools/install_game.py'),'install',str(install)],env=env,check=True,capture_output=True)
    (data/'schedule.json').write_text(json.dumps([dict(fmt='standard',minute=(int(time.time()//60)+1)%60,buyin=1000,bot_entries=99,late_minutes=10,max_reentries=2)]))
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    base=f'http://127.0.0.1:{port}'; log=open(OUT/'server.log','w'); proc=None
    def call(path,body=None):
        req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def start():
        global proc
        proc=subprocess.Popen([sys.executable,'ui_server.py','--port',str(port)],cwd=system,env=env,stdout=log,stderr=log,start_new_session=True)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            assert proc.poll() is None,'server exited'
            try:
                if call('/api/wallet')[0]==200:return
            except OSError:pass
            time.sleep(.1)
        raise AssertionError('HTTP startup timeout')
    def stop():
        global proc
        if proc is not None:
            os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10);proc=None
    try:
        start();code,lobby=call('/api/lobby');assert code==200 and lobby['wallet']['balance']==10000
        event=next(x for x in lobby['tournaments'] if x['status']=='scheduled');tid=event['id']
        with sqlite3.connect(data/'tournaments.sqlite3') as db:
            now=time.time();starts=now-3300;db.execute('UPDATE tournaments SET starts_at=?,closes_at=? WHERE id=?',(starts,now+600,tid))
        for _ in range(3):
            code,v=call('/api/register',{'tournament_id':tid,'buyin':1,'payout':999999});assert code==200 and v['wallet']['balance']==9000
        assert call('/api/new',{'entries':2})[0]==409
        assert call('/api/enter',{'tournament_id':tid})[0]==200
        began=time.monotonic();last=began;last_done=-1.;nonbreak_stall=0.;break_observed=False;polls=0;previous_done=-1.
        while True:
            code,v=call('/api/state');assert code==200;now=time.monotonic();dt=now-last;last=now;polls+=1
            # Before the first durable snapshot, waiting has only sync fields.
            assert call('/api/wallet')[1]['balance']==9000
            if 'wallet' in v:assert v['wallet']['balance']==9000
            if 'tournament_id' in v:assert v['tournament_id']==tid
            if not v.get('waiting'):break
            done=float(v.get('sync_seconds') or 0);target=float(v.get('sync_target_seconds') or 0)
            assert done>=previous_done-1e-6,'durable catch-up regressed';previous_done=done
            phase=(time.time()-starts)%3600
            scheduled_break=3300<=phase<3600 and target-done<=15
            message=v.get('message','')
            if scheduled_break:
                assert '대회 휴식 중' in message,(phase,done,target,message)
                assert abs(target-3300)<2,(phase,target)
                break_observed=True
            else:
                assert '대회 휴식 중' not in message,(phase,message)
                nonbreak_stall=0. if done>last_done else nonbreak_stall+dt
                assert nonbreak_stall<60,('real worker stalled outside break',nonbreak_stall,v)
            last_done=done
            # Same original 5x catch-up bound, plus only the actual scheduled
            # 300-second pause independently identified above.
            assert now-began<max(90,30+target/5)+(300 if break_observed else 0),('late admission exceeded bound',v)
            if polls%30==0:print(json.dumps({'phase':phase,'sync_seconds':done,'target':target,'scheduled_break':scheduled_break,'nonbreak_stall':nonbreak_stall}),flush=True)
            time.sleep(.5)
        assert break_observed,'fixture did not exercise the real break'
        assert v.get('view') or v.get('game_over');assert v['my_entry']['status'] in ('playing','finished','busted')
        assert call('/api/tournament')[1]['entries']==100
        if (v.get('view') or {}).get('type')=='decision':
            token=v['token'];deadline=call('/api/action-clock',{'token':token})[1]['action_deadline_ms']
            assert deadline is not None;assert call('/api/enter',{'tournament_id':tid})[0]==200
            resumed=call('/api/state')[1];assert resumed['token']==token and not resumed.get('waiting')
            assert call('/api/action-clock',{'token':token})[1]['action_deadline_ms']==deadline
            limit=time.monotonic()+max(0,deadline/1000-time.time())+6
            while True:
                advanced=call('/api/state')[1]
                if advanced['token']!=token or advanced.get('game_over'):break
                assert time.monotonic()<limit,'server timeout did not advance'
                time.sleep(.2)
        stop()
        with sqlite3.connect(data/'tournaments.sqlite3') as db:
            entry_count=db.execute('SELECT COUNT(*) FROM entries WHERE tournament_id=?',(tid,)).fetchone()[0]
            state=db.execute('SELECT state FROM tournaments WHERE id=?',(tid,)).fetchone()[0]
        assert entry_count==1 and state
        subprocess.run([sys.executable,str(ROOT/'ui/tools/install_game.py'),'update',str(install)],env=env,check=True,capture_output=True)
        start();assert call('/api/wallet')[1]['balance']==9000
        with sqlite3.connect(data/'tournaments.sqlite3') as db:
            assert db.execute('SELECT COUNT(*) FROM entries WHERE tournament_id=?',(tid,)).fetchone()[0]==1
        report={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'bots':99,'late_seconds':3300,'break_observed':True,'polls':polls,'seconds':round(time.monotonic()-began,3),'outside_break_stall_limit':60,'min_catchup_rate':5,'wallet_balance':9000,'paid_entries':1,'resume_timeout_update_restart':True}
        (OUT/'summary.json').write_text(json.dumps(report,indent=2));print('PASS',json.dumps(report),flush=True)
    finally:stop();log.close()
