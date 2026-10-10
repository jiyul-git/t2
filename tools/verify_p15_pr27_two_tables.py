#!/usr/bin/env python3
"""Audit-only: actual >=2 nonhero hands; retain all BF provenance in comparison."""
import copy,json,os,sys,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['T2_BOT_LOG']='2'
from tools.verify_parallel_table_processes import warm_dump,run,strip_log
import live2 as L

def main():
    dump=warm_dump(27,0,4)
    plan=L._load_field(copy.deepcopy(dump)).plan_others()
    assert len(plan)==2 and all(len(seeds)>=1 for _,seeds in plan)
    seq,_=run(dump,1);par,_=run(dump,2)
    a,b=strip_log(seq.get('bot_log')),strip_log(par.get('bot_log'))
    assert len(a)>=2 and len(b)==len(a)
    assert a==b,'action/BF provenance mismatch; only compute_ms is excluded'
    sa=copy.deepcopy(seq);pa=copy.deepcopy(par)
    sa.pop('bot_log',None);pa.pop('bot_log',None)
    assert sa==pa, [k for k in sa if sa[k]!=pa.get(k)]
    f1=L._load_field(copy.deepcopy(dump));f2=L._load_field(copy.deepcopy(dump))
    before=sum(t.hands for t in f1.tables.values())
    f1.step_others(simultaneous=True,settle=False)
    f2.step_others(simultaneous=True,runner=L._parallel_tables_runner,settle=False)
    actual1=sum(t.hands for t in f1.tables.values())-before
    actual2=sum(t.hands for t in f2.tables.values())-before
    assert actual1==actual2==2
    assert f1.rng.getstate()==f2.rng.getstate()
    assert L._dump(f1)==L._dump(f2)
    print(json.dumps({'pass':True,'entries':27,'tables':3,'seed':4,'plan':plan,
      'actual_bot_hands_per_mode':len(a),'actual_parallel_workers':2,
      'compute_others_parallel_actual_hands_total':len(a)+len(b),
      'additional_direct_step_others_actual_hands_total':actual1+actual2,
      'full_worker_result_equal':True,'actions_and_all_bf_provenance_equal':True,
      'time_banks_and_coordinator_rng_equal':True,'excluded_log_fields':['compute_ms']} ,indent=2))
if __name__=='__main__':main()
