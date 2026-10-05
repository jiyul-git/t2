"""Clock boundaries, persistence and countdown; no live player state used."""
import ast, math, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import formats as FM, fieldsim as FS, live2 as L
for fmt, minutes in [('standard',10),('turbo',5),('hyper',2),('deep',15),('bounty',10)]:
    f=FS.Field(entries=9, hero_pid=1, seed=5, fmt=fmt)
    f.virtual_play_seconds=minutes*60-0.001; f.level_minutes=minutes
    f.hand_no=1000; f.advance_level(); assert f.level==1
    f.virtual_play_seconds=minutes*60; f.advance_level(); assert f.level==2
    loaded=L._load_field(L._dump(f)); assert loaded.virtual_play_seconds==f.virtual_play_seconds
    assert loaded.level_minutes==minutes
    loaded.virtual_play_seconds=minutes*120; loaded.advance_level(); assert loaded.level==3
# Legacy games remain on their existing hand schedule.
f=FS.Field(entries=9, hero_pid=1, seed=5); f.hand_no=12; f.advance_level(); assert f.level==2
source=ast.parse((ROOT/'ui/server/ui_server.py').read_text())
fns=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('_ui_timing','_clock_values','_sync_clock','_vclock_ready_locked')]
ns={'math':math,'time':time,'PLAY_WINDOW_SECONDS':3300,'VCLOCK':{}};
exec(compile(ast.Module(body=fns,type_ignores=[]),'<timing>','exec'),ns)
st={'field':{'virtual_play_seconds':3300,'level_minutes':10},'ui_break_seconds':0,'ui_break_until':1300}
assert ns['_ui_timing'](st,1000)['break_remaining']==300
assert ns['_ui_timing'](st,1000.1)['break_remaining']==300
assert ns['_ui_timing'](st,1299.1)['break_remaining']==1
assert ns['_ui_timing'](st,1300)['break_remaining']==0
assert ns['_ui_timing'](st,1500)['break_remaining']==0
assert ns['_ui_timing']({},1000)['elapsed_seconds'] is None
wall={'field':{'virtual_play_seconds':0,'level_minutes':1},'ui_clock_started_at':1000,'ui_clock_paused_seconds':0}
assert ns['_ui_timing'](wall,1001.2)['level_remaining_seconds']==59
assert ns['_ui_timing'](wall,1001.2)['session_remaining_seconds']==3299
assert ns['_ui_timing'](wall,1060)['elapsed_seconds']==60
assert ns['_ui_timing'](wall,1060)['level_remaining_seconds']==60
wall_l1={'field':{'virtual_play_seconds':0,'level_minutes':1,'level':1},
         'ui_clock_started_at':1000,'ui_clock_paused_seconds':0}
assert ns['_ui_timing'](wall_l1,1060)['level_remaining_seconds']==0
wall_l2={'field':{'virtual_play_seconds':60,'level_minutes':1,'level':2},
         'ui_clock_started_at':1000,'ui_clock_paused_seconds':0}
assert ns['_ui_timing'](wall_l2,1060)['level_remaining_seconds']==60
assert ns['_clock_values'](wall,1060)[0]==60
ns['_sync_clock'](wall,1060)
f=L._load_field(dict(L._dump(FS.Field(entries=9,hero_pid=1,seed=5)),**wall['field']))
f.advance_level();assert f.level==2
legacy={'field':{'virtual_play_seconds':120,'level_minutes':10},'ui_break_seconds':30}
ns['_sync_clock'](legacy,1000);assert ns['_clock_values'](legacy,1001)==(121,151)
wall.update(ui_break_pending=True,ui_break_started_at=1060,ui_break_until=1360)
assert ns['_clock_values'](wall,1200)==(60,200)
assert ns['_clock_values'](wall,1400)==(60,400)
ns['VCLOCK'].update(barrier_time=90.0,barrier_kind='hand_for_hand',coverage=70.0)
assert not ns['_vclock_ready_locked'](80.0)
assert ns['_vclock_ready_locked'](90.0)
ns['VCLOCK'].update(barrier_time=90.0,barrier_kind='bust',coverage=70.0)
assert ns['_vclock_ready_locked'](65.0)
assert not ns['_vclock_ready_locked'](75.0)
print('PASS: actual elapsed, level boundary, break pause and expiry')
print('PASS: five speed/format boundaries, field persistence, legacy clock, countdown boundaries')
# Real HTTP lifecycle: countdown starts only after a result, survives reload,
# rejects an early deal, and skip resumes exactly once.
import tempfile, subprocess, socket, json, urllib.request, urllib.error, os
with tempfile.TemporaryDirectory(prefix='t2_clock_') as td:
    subprocess.run(['sh', str(ROOT/'ui/tools/setup_run_dir.sh'), td],check=True,stdout=subprocess.DEVNULL)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    proc=subprocess.Popen([sys.executable,'ui_server.py','--port',str(port)],cwd=td,
        env=dict(os.environ,T2_UI_DEFER='0',T2_TIMING_V1='off'),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    def request(path,body=None):
        req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,
            data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=15) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    try:
        for _ in range(100):
            try:request('/api/ready');break
            except OSError:time.sleep(.05)
        code,r=request('/api/new',{'entries':9,'seed':5,'level_minutes':10});assert code==200
        state=pathlib.Path(td)/'live2_state.json'
        _,before=request('/api/ready');time.sleep(2.1);_,after=request('/api/ready')
        assert after['elapsed_seconds']-before['elapsed_seconds']>=2,(before,after)
        st=json.loads(state.read_text());st['ui_clock_started_at']-=2;st['ui_next_break']=1;state.write_text(json.dumps(st))
        for _ in range(30):
            if r['done']:break
            view=r['view'];legal=view.get('legal') or {}
            action='check' if legal.get('check') else 'fold'
            code,r=request('/api/step',{'token':r['token'],'action':action});assert code==200,r
        assert r['done']
        _,ready=request('/api/ready');assert 298<=ready['break_remaining']<=300,ready
        assert ready['elapsed_seconds']>0
        code,_=request('/api/step',{'token':r['token'],'action':None});assert code==409
        assert request('/api/break',{'skip':True})[1]['break_remaining']==0
        code,r=request('/api/step',{'token':r['token'],'action':None});assert code==200,r
        st=json.loads(state.read_text());assert 0<=st['ui_break_seconds']<10 and not st['ui_break_pending']
        print('PASS: HTTP result → countdown → early-deal block → skip → resume; actual skipped break duration counted once')
    finally:
        proc.terminate();proc.wait(timeout=5)
