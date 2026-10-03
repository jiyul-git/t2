#!/usr/bin/env python3
"""Combined Human Model v3 integration verifier on canonical 9-max MTT fixtures.

This does not fit target VPIP/PFR values. It checks composition:
- all V3 flags together are deterministic;
- they actually reach live decision paths;
- recency state stays bounded;
- no engine/book errors or unfinished hands occur;
- aggregate changes are reported, not scored against an external target.
"""
import argparse, collections, hashlib, json, os, pathlib, subprocess, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
# Stage 9 B4/B5: T2_CALC_NOISE_V3, T2_PREFLOP_TEMPER_DIRECTION_V3 and
# T2_EXPLOIT_WEIGHT_V3 were retired
# (their V3 semantics are the only production path); the remaining flags are
# the ones still awaiting their integration step.
FLAGS=(
    'T2_PREFLOP_REASONING_V3',
)
SEEDS=(5150,9001,4242)
HANDS=24


def _stats_from_log(log, hero):
    s=collections.Counter()
    seen=set()
    for street,seat,act,_amt in log:
        if street!='preflop' or seat==hero or seat in seen:
            continue
        seen.add(seat); s['n']+=1
        if act in ('bet','raise','allin'):
            s['vpip']+=1; s['pfr']+=1
        elif act=='call':
            s['vpip']+=1
    if any(x[0]=='flop' for x in log): s['flop']=1
    return s


def child(seed):
    import tourney as T
    t=T.Tournament(entries=100, hero_seat=7, seats=9, seed=seed, fmt='standard')
    rows=[]; stats=collections.Counter(); errors=[]; done_hands=0
    for _ in range(HANDS):
        if sum(1 for s in t.seats if t.stacks.get(s,0)>0)<3:
            break
        state=t.next_hand(); guard=0
        while state and not state.get('done') and guard<300:
            state=t.submit('fold'); guard+=1
        if guard>=300:
            errors.append('action_guard')
            break
        log=list(getattr(t.run,'full_log',[]) or [])
        rows.append(';'.join('%s:%s:%s:%s'%x for x in log))
        stats.update(_stats_from_log(log,t.hero))
        if hasattr(t.hand,'book_errors'):
            errors.extend(list(getattr(t.hand,'book_errors') or []))
        t.finish_hand(); done_hands+=1
    book=t.book.d
    hist=[len(r.get('_hand_hist',[]) or []) for r in book.values()]
    fp=hashlib.sha256(('\n'.join(rows)+'|'+json.dumps(t.stacks,sort_keys=True)).encode()).hexdigest()[:20]
    out={
        'seed':seed,'hands':done_hands,'fingerprint':fp,'stats':dict(stats),
        'errors':errors,
        'book_records':len(book),
        'history_records':sum(1 for x in hist if x>0),
        'history_max':max(hist) if hist else 0,
        'history_ge13':sum(1 for x in hist if x>=13),
    }
    print(json.dumps(out,sort_keys=True))


def run(seed, enabled):
    env=dict(os.environ)
    env['PYTHONPATH']=str(ROOT)
    env['T2_GTO_MEMORY_V2']='0'
    for f in FLAGS:
        env[f]='1' if f in enabled else '0'
    p=subprocess.run([sys.executable,__file__,'--child',str(seed)],
                     cwd=str(ROOT),env=env,capture_output=True,text=True,timeout=900)
    if p.returncode:
        raise RuntimeError(p.stderr[-4000:])
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--child',type=int)
    a=ap.parse_args()
    if a.child is not None:
        child(a.child); return

    off={}; on1={}; on2={}
    for sd in SEEDS:
        off[str(sd)]=run(sd,set())
        on1[str(sd)]=run(sd,set(FLAGS))
        on2[str(sd)]=run(sd,set(FLAGS))

    deterministic=all(on1[k]==on2[k] for k in on1)
    changed=sum(off[k]['fingerprint']!=on1[k]['fingerprint'] for k in off)
    error_free=all(not x['errors'] and x['hands']==HANDS
                   for group in (off,on1,on2) for x in group.values())
    recency_ok=all(x['history_max']<=121 and x['history_records']>0
                   for x in on1.values())
    # stage9 closeout A1: the recency window is the only path, so every run
    # (flags off or on) records bounded history.
    recency_single_path=all(x['history_max']<=121 and x['history_records']>0 for x in off.values())

    # One seed, one feature at a time: attribution only. Interaction is allowed
    # and expected, so these are reported rather than required to add linearly.
    singles={}
    anchor_seed=SEEDS[0]
    for flag in FLAGS:
        x=run(anchor_seed,{flag})
        singles[flag]={
            'fingerprint':x['fingerprint'],
            'changed_vs_off':x['fingerprint']!=off[str(anchor_seed)]['fingerprint'],
            'stats':x['stats'],
            'history_records':x['history_records'],
            'history_max':x['history_max'],
        }

    def agg(group):
        z=collections.Counter()
        for x in group.values(): z.update(x['stats'])
        n=max(1,z['n'])
        return {
            'hands':sum(x['hands'] for x in group.values()),
            'opponent_decisions':z['n'],
            'vpip_n':z['vpip'],'pfr_n':z['pfr'],'flop_hands':z['flop'],
            'vpip_rate':round(z['vpip']/n,4),
            'pfr_rate':round(z['pfr']/n,4),
        }

    checks={
        'I1_all_on_deterministic':deterministic,
        'I2_live_path_changes':changed>0,
        'I3_error_free_complete':error_free,
        'I4_recency_bounded_and_live':recency_ok,
        'I5_recency_single_path':recency_single_path,
    }
    out={
        'pass':all(checks.values()),'checks':checks,
        'changed_seed_fingerprints':changed,
        'aggregate':{'off':agg(off),'all_on':agg(on1)},
        'per_seed':{'off':off,'all_on':on1},
        'single_feature_anchor_seed':anchor_seed,
        'single_feature_attribution':singles,
        'flags':list(FLAGS),
    }
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)


if __name__=='__main__':
    main()
