#!/usr/bin/env python3
"""Reproduce P17's exact production-base packaging failure, not a simulated import."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

base=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
out.mkdir(parents=True,exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('T2_','PYTHON'))}
env.update(T2_TELEMETRY='0',PYTHONHASHSEED='0')
for kind,exe in [('py',sys.executable),('sh','sh')]:
    with tempfile.TemporaryDirectory(prefix='p16_original_failure_') as td:
        setup=[exe,str(base/'ui/tools'/('setup_run_dir.'+kind)),td]
        r=subprocess.run(setup,env=env,capture_output=True,text=True,timeout=60)
        assert r.returncode==0,r.stdout+r.stderr
        assert not (Path(td)/'range_posterior_v1.py').exists()
        probe=[sys.executable,'-I','-c',"import sys;sys.path.insert(0,'.');import live2,ui_server;print('PASS clean installed imports')"]
        p=subprocess.run(probe,cwd=td,env=env,capture_output=True,text=True,timeout=20)
        entry=[sys.executable,'ui_server.py','--port','18916']
        e=subprocess.run(entry,cwd=td,env=env,capture_output=True,text=True,timeout=20)
        for result in (p,e):
            assert result.returncode!=0
            assert "ModuleNotFoundError: No module named 'range_posterior_v1'" in result.stderr
        (out/('original_failure_'+kind+'.log')).write_text(
            'SETUP '+repr(setup)+'\n'+r.stdout+r.stderr+
            'PROBE '+repr(probe)+'\n'+p.stdout+p.stderr+
            'ENTRY '+repr(entry)+'\n'+e.stdout+e.stderr)
        print('PASS expected original failure reproduced:',kind,'setup=0 import=1 entrypoint=1')
