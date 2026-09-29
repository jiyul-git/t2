#!/usr/bin/env python3
"""Human Model V3 behavior-quality gate.

Combines integration, semantic-liveness and pairwise-composition audits. It does
not claim population realism: no external human target dataset is available.
"""
import json, pathlib, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]

def run(path, timeout=3600):
    p=subprocess.run([sys.executable,str(ROOT/path)],cwd=str(ROOT),capture_output=True,text=True,timeout=timeout)
    text=p.stdout.strip()
    try: obj=json.loads(text)
    except Exception: obj={'pass':False,'stdout_tail':text[-4000:],'stderr_tail':p.stderr[-4000:]}
    obj['_returncode']=p.returncode
    return obj

def main():
    integration=run('tools/verify_human_model_v3_integration.py')
    semantic=run('tools/audit_human_v3_live_attribution.py',600)
    interactions=run('tools/audit_human_v3_interactions.py')
    off=integration.get('aggregate',{}).get('off',{})
    on=integration.get('aggregate',{}).get('all_on',{})
    checks={
      'integration':integration.get('pass') is True,
      'semantic_liveness':semantic.get('pass') is True,
      'pairwise_composition':interactions.get('pass') is True,
    }
    out={
      'pass':all(checks.values()),'checks':checks,
      'aggregate_delta':{
        'vpip_rate':round(on.get('vpip_rate',0)-off.get('vpip_rate',0),4),
        'pfr_rate':round(on.get('pfr_rate',0)-off.get('pfr_rate',0),4),
        'flop_hands':on.get('flop_hands',0)-off.get('flop_hands',0)},
      'remaining_validation_gap':[
        'skill-bin behavioral monotonicity',
        'repeated-opponent read/exploit adaptation',
        'fold/call/raise tail anomaly scan',
        'external human population calibration'],
      'semantic_checks':semantic.get('checks',{}),
      'single_endpoint_live':interactions.get('single_endpoint_live',{}),
    }
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)
if __name__=='__main__': main()
