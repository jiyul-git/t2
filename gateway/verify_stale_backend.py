#!/usr/bin/env python3
"""A game server left over from a killed gateway must not share its run folder with a new one.

    python3 gateway/verify_stale_backend.py

1) Backends._kill_stale stops a ui_server.py whose cwd is the run folder (pid from server.pid),
   and leaves other processes alone (wrong cwd, wrong command, missing pid file).
2) live2.save from two processes at once never fails (per-process / per-thread temp files).
"""
import os, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gateway as GW

ok = 0
def check(name, cond):
    global ok
    assert cond, name
    ok += 1
    print('PASS', name)

def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:   # a zombie child still answers kill(0); count it as gone
        return open('/proc/%d/stat' % pid).read().split()[2] != 'Z'
    except OSError:
        return False

with tempfile.TemporaryDirectory(prefix='t2_stale_') as td:
    run = os.path.join(td, 'run'); os.mkdir(run)
    other = os.path.join(td, 'other'); os.mkdir(other)
    # stand-in processes: a script named ui_server.py in the run folder, and one elsewhere
    for d in (run, other):
        open(os.path.join(d, 'ui_server.py'), 'w').write('import time\nwhile True: time.sleep(1)\n')
    p_run = subprocess.Popen([sys.executable, 'ui_server.py'], cwd=run)
    p_other = subprocess.Popen([sys.executable, 'ui_server.py'], cwd=other)
    p_sleep = subprocess.Popen(['sleep', '60'], cwd=run)
    time.sleep(0.3)
    try:
        GW.Backends._kill_stale(run)          # no pid file -> nothing happens
        check('no server.pid -> nothing killed', alive(p_run.pid) and alive(p_other.pid))
        open(os.path.join(run, 'server.pid'), 'w').write(str(p_other.pid))
        GW.Backends._kill_stale(run)
        check('pid with another cwd is left alone', alive(p_other.pid))
        open(os.path.join(run, 'server.pid'), 'w').write(str(p_sleep.pid))
        GW.Backends._kill_stale(run)
        check('pid that is not ui_server.py is left alone', alive(p_sleep.pid))
        open(os.path.join(run, 'server.pid'), 'w').write(str(p_run.pid))
        GW.Backends._kill_stale(run)
        p_run.wait(5)
        check('stale ui_server.py in the run folder is stopped', not alive(p_run.pid))
        open(os.path.join(run, 'server.pid'), 'w').write('999999')
        GW.Backends._kill_stale(run)
        check('pid file of a dead process is harmless', True)
    finally:
        for p in (p_run, p_other, p_sleep):
            if p.poll() is None:
                p.kill()

# concurrent saves from two processes into one folder
with tempfile.TemporaryDirectory(prefix='t2_save_') as td:
    subprocess.run(['sh', os.path.join(REPO, 'ui/tools/setup_run_dir.sh'), td], check=True,
                   stdout=subprocess.DEVNULL, env=dict(os.environ, T2_TELEMETRY='0'))
    probe = ("import sys, ui_view; sys.modules['view'] = ui_view\n"
             "import live2 as L\n"
             "for i in range(200): L.save({'n': i, 'who': sys.argv[1]})\n"
             "print('ok')\n")
    ps = [subprocess.Popen([sys.executable, '-c', probe, str(k)], cwd=td, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True) for k in range(3)]
    outs = [p.communicate(timeout=120) for p in ps]
    check('3 processes x 200 concurrent saves, no error',
          all(p.returncode == 0 and 'ok' in o for p, (o, e) in zip(ps, outs)))
    left = [f for f in os.listdir(td) if f.endswith('.tmp')]
    check('no temp files left behind', not left)
print('%d stale-backend checks passed' % ok)
