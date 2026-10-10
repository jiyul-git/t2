"""Read-only frozen comparison. Never invokes regress.save or changes policy."""
import sys, os, json, hashlib, inspect, functools, pathlib, subprocess, concurrent.futures
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'p17-results'
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
def probe(seed, full_hand=0):
    import tourney as T, plan as PL, bot
    calls=[]; hand_no=0
    def norm(x, full=False):
        import random
        if isinstance(x,random.Random): return {'rng_state_sha256':digest(x.getstate())}
        if isinstance(x,dict): return {str(k):norm(v,full) for k,v in x.items()}
        if isinstance(x,(tuple,list)):
            if len(x)>80 and not full: return {'length':len(x),'sha256':digest(x),'first':norm(x[:3])}
            return [norm(v,full) for v in x]
        if x is None or isinstance(x,(str,int,float,bool)):return x
        return {'type':type(x).__name__}
    def wrap(mod,name):
        if not hasattr(mod,name):return
        f=getattr(mod,name);sig=inspect.signature(f)
        @functools.wraps(f)
        def w(*args,**kw):
            frame=inspect.currentframe().f_back
            local=frame.f_locals
            before=norm(dict(sig.bind_partial(*args,**kw).arguments),hand_no==full_hand)
            rec={'function':name,'seat':local.get('s'),'street':local.get('street'),'inputs':before}
            result=f(*args,**kw)
            rec['output']=norm(result,hand_no==full_hand)
            calls.append(rec)
            return result
        setattr(mod,name,w)
    for n in ('preflop_plan','make_plan','act_with_plan','decide_response','response_equity'):wrap(PL,n)
    for n in ('equity_vs_pools','equity_vs_combos'):wrap(bot,n)
    t=T.Tournament(entries=100,start_stack=30000,hero_seat=7,seed=seed,hands_per_level=200)
    rows=['q=%.3f|a=%.2f'%(t.field_q,t.aggr_bias)];hands=[]
    for i in range(30):
        if sum(t.stacks[s]>0 for s in t.seats)<3:break
        hand_no=i+1;calls.clear();st=t.next_hand();guard=0
        while st and not st.get('done') and guard<200:st=t.submit('fold');guard+=1
        log=getattr(t.run,'full_log',[]) or []
        rows.append(';'.join('%s:%s:%s:%s'%tuple(x) for x in log))
        hands.append({'hand':hand_no,'log':norm(log,True),'cards':norm(t.hand.hole,True),'stacks':norm(t.hand.stacks,True),'calls':list(calls),'intents':norm(getattr(t.hand,'intents',[]),True),'pf_seed':norm(getattr(t.hand,'pf_seed',{}),True)})
        t.finish_hand()
    print(json.dumps({'seed':seed,'field_q':t.field_q,'aggr_bias':t.aggr_bias,'fp':hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16],'hands':hands},ensure_ascii=False))

if __name__=='__main__':
    sys.path.insert(0,os.getcwd())
    probe(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv)>2 else 0)
