#!/usr/bin/env python3
"""Test isolated runtime helpers, actual ZIP/repository installers and HTTP entrypoint.

Never inherit repository PYTHONPATH, runtime T2 settings, or the user's wallet.
"""
import hashlib
import contextlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RESULTS = []
EVIDENCE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None


def inspect_zip(path, mode, label):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert 'T2/system/range_posterior_v1.py' in names
        assert z.read('T2/system/range_posterior_v1.py') == (ROOT/'range_posterior_v1.py').read_bytes()
        assert not any(n.endswith(('.sqlite3','.jsonl')) for n in names)
        if mode == 'update':
            assert not any('/personal/' in n for n in names)
        record = dict(builder=label,mode=mode,files=names,
                      posterior_sha256=hashlib.sha256(z.read('T2/system/range_posterior_v1.py')).hexdigest())
        if EVIDENCE:
            EVIDENCE.mkdir(parents=True,exist_ok=True)
            (EVIDENCE/('manifest_'+label+'_'+mode+'.json')).write_text(json.dumps(record,indent=2))
        print('PASS ZIP manifest/bytes/no runtime data:', label, mode, len(names), 'files')


def command(args, cwd, env):
    out = subprocess.run(list(map(str, args)), cwd=cwd, env=env,
                         capture_output=True, text=True, timeout=90)
    print(out.stdout + out.stderr, end='')
    assert out.returncode == 0, (args, out.returncode)
    return out


def check_runtime(path, env, label):
    assert (path / 'range_posterior_v1.py').read_bytes() == (ROOT / 'range_posterior_v1.py').read_bytes()
    # Same isolated import command as P17; assert every engine import came from
    # the install, not the checkout. Importing must not consume global RNG.
    probe = """import sys,random,pathlib,os,json
sys.path.insert(0,'.')
before=random.getstate()
import live2,ui_server,session,range_posterior_v1
assert before==random.getstate()
assert 'T2_RANGE_CONDITIONAL_V1' not in os.environ
base=pathlib.Path.cwd().resolve()
assert all(pathlib.Path(m.__file__).resolve().parent==base for m in (live2,ui_server,session,range_posterior_v1))
print('PASS isolated installed imports, default OFF, import RNG preserved')
"""
    command([sys.executable, '-I', '-c', probe], path, env)
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    # Actual documented entrypoint, scheduler/deferred workers at their defaults.
    args = [sys.executable, '-u', 'ui_server.py', '--port', str(port)]
    with tempfile.TemporaryFile(mode='w+') as log:
        proc = subprocess.Popen(args, cwd=path, env=dict(env, IP='127.0.0.1'),
                                stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while True:
                assert proc.poll() is None, 'UI entrypoint exited before HTTP ready'
                try:
                    with urllib.request.urlopen('http://127.0.0.1:%d/' % port, timeout=1) as r:
                        assert r.status == 200 and r.read(), 'empty lobby'
                    with urllib.request.urlopen('http://127.0.0.1:%d/play' % port, timeout=1) as r:
                        assert r.status == 200 and r.read(), 'empty table'
                    break
                except (OSError, TimeoutError):
                    assert time.monotonic() < deadline, 'UI readiness timeout'
                    time.sleep(0.1)
            RESULTS.append(dict(route=label, entrypoint=args, lobby=200, play=200,
                                posterior_sha256=hashlib.sha256((path/'range_posterior_v1.py').read_bytes()).hexdigest(),
                                default_conditional='OFF', repository_pythonpath=False))
            print('PASS actual HTTP startup:', label)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
            # Also stop forked scheduler workers after parent exit.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            log.seek(0)
            print(log.read(), end='')


def hashes(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


def main():
    with tempfile.TemporaryDirectory(prefix='p16_fresh_install_') as td:
        base = Path(td)
        env = {k:v for k,v in os.environ.items() if not k.startswith(('PYTHON', 'T2_'))}
        # Pass an isolated child HOME; never alter the parent environment.
        env.update(HOME=str(base/'home'), T2_TELEMETRY='0', PYTHONHASHSEED='0')
        (base/'home').mkdir()
        for kind, exe in [('py', sys.executable), ('sh', 'sh')]:
            target = base/('run_'+kind)
            command([exe, ROOT/'ui/tools'/('setup_run_dir.'+kind), target], ROOT, env)
            check_runtime(target, env, 'working_tree_'+kind)
            # Run the real package builder over each helper's prepared output.
            # Harness-only source override; installed child imports stay isolated.
            sys.path.insert(0,str(ROOT/'ui/tools'))
            import build_game_packages as BG
            with patch.object(BG,'prepared_system',lambda:contextlib.nullcontext(target)):
                paths = BG.build_packages(base/('packages_'+kind))
            for mode,path in zip(('install','update'),paths):
                inspect_zip(path,mode,kind)
        # Hermetic git-ref fixture: local remote, no external fetch or branch drift.
        source = base/'ref_source'
        source.mkdir()
        for p in ROOT.glob('*.py'):
            shutil.copy2(p, source/p.name)
        for name in ('pf_rank.json','style_sig.json','style_prior.json'):
            shutil.copy2(ROOT/name, source/name)
        for name in ('ui/server','ui/web','ui/tools','coarse_params'):
            shutil.copytree(ROOT/name, source/name)
        command(['git','init','-q',str(source)], base, env)
        command(['git','add','.'], source, env)
        command(['git','-c','user.name=P16 verifier','-c','user.email=p16@example.invalid',
                 'commit','-qm','hermetic ref fixture'], source, env)
        command(['git','branch','install-fixture'], source, env)
        command(['git','remote','add','origin',str(source)], source, env)
        for kind, exe in [('py',sys.executable),('sh','sh')]:
            target = base/('ref_'+kind)
            command([exe,source/'ui/tools'/('setup_run_dir.'+kind),target], source,
                    dict(env,T2_UI_REF='install-fixture'))
            check_runtime(target, env, 'git_ref_'+kind)
        # A broken source must fail packaging, rather than silently treating a
        # currently imported module as optional.
        (source/'range_posterior_v1.py').unlink()
        for kind, exe in [('py',sys.executable),('sh','sh')]:
            target = base/('broken_'+kind)
            r = subprocess.run([exe,str(source/'ui/tools'/('setup_run_dir.'+kind)),str(target)],
                               env=env,capture_output=True,text=True,timeout=30)
            assert r.returncode != 0 and 'range_posterior_v1.py' in r.stderr
            assert not (target/'UI_SERVER_DIR').exists()
            print('PASS missing required source refused:', kind)
        dest = base/'direct_install'
        command([sys.executable,ROOT/'ui/tools/install_game.py','install',dest], base, env)
        check_runtime(dest/'system', env, 'repository_installer')
        packages = base/'packages'
        command([sys.executable,ROOT/'ui/tools/build_game_packages.py',packages], base, env)
        for mode in ('install','update'):
            inspect_zip(packages/('T2-'+mode+'.zip'),mode,'default_pipeline')
            with zipfile.ZipFile(packages/('T2-'+mode+'.zip')) as z:
                assert 'T2/system/range_posterior_v1.py' in z.namelist()
                assert z.read('T2/system/range_posterior_v1.py') == (ROOT/'range_posterior_v1.py').read_bytes()
                assert not any(n.endswith(('.sqlite3','.jsonl')) for n in z.namelist())
                if mode=='update':
                    assert not any('/personal/' in n for n in z.namelist())
                z.extractall(base/mode)
        installed = base/'install/T2'
        command([sys.executable,installed/'install.py'], base, env)
        check_runtime(installed/'system', env, 'install_zip')
        # Stop server first, then compare all personal bytes across updates.
        before = hashes(installed/'personal')
        (installed/'system/range_posterior_v1.py').unlink()
        command([sys.executable,base/'update/T2/update.py',installed], base, env)
        assert hashes(installed/'personal') == before
        check_runtime(installed/'system', env, 'update_zip_repairs_missing_module')
        before = hashes(installed/'personal')
        shutil.rmtree(installed/'system')
        command([sys.executable,base/'update/T2/update.py',installed], base, env)
        assert hashes(installed/'personal') == before
        check_runtime(installed/'system', env, 'update_zip_rebuilds_empty_system')
    print(json.dumps({'status':'PASS','routes':RESULTS},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
