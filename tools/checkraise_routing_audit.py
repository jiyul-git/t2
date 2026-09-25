#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only runtime audit of actual check-raise routing sources."""

import argparse, collections, copy, os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import fieldsim as FS
import persona as PS


def parse_seeds(spec):
    s=str(spec).strip()
    if ',' in s:
        return [int(x.strip()) for x in s.split(',') if x.strip()]
    if '-' in s:
        a,b=s.split('-',1)
        return list(range(int(a),int(b)+1))
    return [int(s)]


def clear_tilt_cache():
    c=getattr(PS,'_TILT_VIEW_CACHE',None)
    if hasattr(c,'clear'): c.clear()


def pct(n,d):
    return 100.0*n/d if d else 0.0


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='6500-6515')
    ap.add_argument('--entries',type=int,default=24)
    ap.add_argument('--hpl',type=int,default=12)
    ap.add_argument('--start-stack',type=int,default=30000)
    ap.add_argument('--cap',type=int,default=3000)
    ap.add_argument('--fmt',default='standard')
    ap.add_argument('--top',type=int,default=30)
    a=ap.parse_args()

    seeds=parse_seeds(a.seeds)
    rows=[]
    errors=[]
    field_hands=0

    old_log=FS.Field._log_bot_hand

    def capture(self,tb,h,run):
        for r in (getattr(h,'checkraise_audit',[]) or []):
            z=copy.deepcopy(r)
            z['_seed']=self.seed
            z['_hand_no']=self.hand_no
            z['_table']=tb.id
            rows.append(z)

    FS.Field._log_bot_hand=capture
    try:
        for i,seed in enumerate(seeds,1):
            print('[%d/%d] seed %d start'%(i,len(seeds),seed),flush=True)
            clear_tilt_cache()
            f=FS.Field(entries=a.entries,start_stack=a.start_stack,
                       hero_pid=0,seed=seed,hands_per_level=a.hpl,fmt=a.fmt)
            while f.remaining()>1 and f.hand_no<a.cap:
                f.hand_no+=1
                f.advance_level()
                for _tid,tb in list(f.tables.items()):
                    if tb.n()>=2:
                        f._play_table(tb)
                f._collect_busts()
                f._balance()
                f.notes=[]
            field_hands+=f.hand_no
            ee=list(getattr(f,'errors',()) or [])
            errors.extend((seed,x) for x in ee)
            print('[%d/%d] seed %d hands %d errors %d'
                  %(i,len(seeds),seed,f.hand_no,len(ee)),flush=True)
    finally:
        FS.Field._log_bot_hand=old_log

    print()
    print('# checkraise routing audit')
    print('seeds=%d field_hands=%d opportunities=%d engine_errors=%d'
          %(len(seeds),field_hands,len(rows),len(errors)))

    print()
    print('## by street / source')
    for st in ('flop','turn','river'):
        x=[r for r in rows if r.get('street')==st]
        c=collections.Counter(r.get('source') for r in x)
        raises=c['generic_response_raise']+c['checkraise_gate']+c['forced_replay']
        print('  %-6s n=%-4d raises=%-4d(%5.1f%%) generic=%-4d gate=%-4d forced=%-3d no_raise=%-4d'
              %(st,len(x),raises,pct(raises,len(x)),c['generic_response_raise'],
                c['checkraise_gate'],c['forced_replay'],c['no_raise']))

    print()
    print('## actual checkraises by plan and source')
    actual=[r for r in rows if r.get('final_act')=='raise']
    cc=collections.Counter((r.get('street'),r.get('plan'),r.get('source')) for r in actual)
    for (st,pl,src),n in sorted(cc.items(), key=lambda kv:(kv[0][0],-kv[1],str(kv[0][1]),kv[0][2])):
        print('  %-6s %-18s %-24s %d'%(st,str(pl),src,n))

    print()
    print('## river focus')
    rv=[r for r in rows if r.get('street')=='river']
    rc=collections.Counter((r.get('plan'),r.get('source')) for r in rv)
    for (pl,src),n in sorted(rc.items(),key=lambda kv:(str(kv[0][0]),kv[0][1])):
        print('  %-18s %-24s %d'%(str(pl),src,n))

    rbl=[r for r in rv if r.get('plan')=='river_bluff']
    print()
    print('river_bluff opportunities:',len(rbl))
    print('river_bluff actual raises:',sum(1 for r in rbl if r.get('final_act')=='raise'))
    print('  generic_response_raise:',sum(1 for r in rbl if r.get('source')=='generic_response_raise'))
    print('  checkraise_gate        :',sum(1 for r in rbl if r.get('source')=='checkraise_gate'))
    print('  no_raise               :',sum(1 for r in rbl if r.get('source')=='no_raise'))

    stale=[r for r in rv if r.get('plan')=='bluff_2street']
    print()
    print('river bluff_2street opportunities:',len(stale))
    print('river bluff_2street actual raises:',sum(1 for r in stale if r.get('final_act')=='raise'))
    print('  generic_response_raise:',sum(1 for r in stale if r.get('source')=='generic_response_raise'))
    print('  checkraise_gate        :',sum(1 for r in stale if r.get('source')=='checkraise_gate'))

    print()
    print('## source share among non-forced actual checkraises')
    nf=[r for r in actual if r.get('source')!='forced_replay']
    c=collections.Counter(r.get('source') for r in nf)
    for k in ('generic_response_raise','checkraise_gate'):
        print('  %-24s %d (%.1f%%)'%(k,c[k],pct(c[k],len(nf))))

    print()
    print('## examples of generic-response checkraises')
    ex=[r for r in actual if r.get('source')=='generic_response_raise']
    for r in ex[:a.top]:
        print('  seed=%s H%s %-6s plan=%-16s rel=%s outs=%s ckr=%s rr=%s bluff=%s semi=%s'
              %(r.get('_seed'),r.get('_hand_no'),r.get('street'),str(r.get('plan')),
                r.get('rel'),r.get('outs'),r.get('checkraise_skill'),r.get('reraise_skill'),
                r.get('bluff_skill'),r.get('semibluff_skill')))

    print()
    print('No poker decision formula was changed; session instrumentation is provenance only.')
    if errors:
        print('ERROR SAMPLE:',errors[:3])
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
