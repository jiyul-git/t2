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
fn=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='_ui_timing')
ns={'math':math,'time':time};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<timing>','exec'),ns)
st={'field':{'virtual_play_seconds':3300,'level_minutes':10},'ui_break_seconds':0,'ui_break_until':1300}
assert ns['_ui_timing'](st,1000)['break_remaining']==300
assert ns['_ui_timing'](st,1000.1)['break_remaining']==300
assert ns['_ui_timing'](st,1299.1)['break_remaining']==1
assert ns['_ui_timing'](st,1300)['break_remaining']==0
assert ns['_ui_timing'](st,1500)['break_remaining']==0
assert ns['_ui_timing']({},1000)['elapsed_seconds'] is None
print('PASS: five speed/format boundaries, field persistence, legacy clock, countdown boundaries')
# Real HTTP lifecycle: countdown starts only after a result, survives reload,
# rejects an early deal, and skip resumes exactly once.
import tempfile, subprocess, socket, json, urllib.request, urllib.error, os
with tempfile.TemporaryDirectory(prefix='t2_clock_') as td:
    subprocess.run(['sh', str(ROOT/'ui/tools/setup_run_dir.sh'), td],check=True,stdout=subprocess.DEVNULL)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    proc=subprocess.Popen([sys.executable,'ui_server.py','--port',str(port)],cwd=td,
        env=dict(os.environ,T2_UI_DEFER='0'),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
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
        st=json.loads(state.read_text());st['ui_next_break']=1;state.write_text(json.dumps(st))
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
        st=json.loads(state.read_text());assert st['ui_break_seconds']==300 and not st['ui_break_pending']
        print('PASS: HTTP result → countdown → early-deal block → skip → resume; virtual break counted once')
    finally:
        proc.terminate();proc.wait(timeout=5)
