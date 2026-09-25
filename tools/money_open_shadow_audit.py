#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only confirmatory audit for unopened money-jump size/limp shadows."""

import argparse
import collections
import copy
import os
import sys

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


def q(xs,p):
    ys=sorted(float(x) for x in xs if x is not None)
    if not ys: return 0.0
    return ys[min(len(ys)-1,int((len(ys)-1)*p))]


def stage(r):
    rem,itm=r.get('remaining'),r.get('itm')
    if not rem or not itm: return 'na'
    if rem<=9: return 'final9'
    if rem<=itm: return 'itm'
    x=float(rem)/float(itm)
    if x<=1.2: return 'bubble'
    if x<=1.5: return 'approach'
    return 'pre'


def pct(n,d):
    return 100.0*n/d if d else 0.0


def dist(label,xs):
    xs=[float(x) for x in xs if x is not None]
    if not xs:
        print('  %-24s n=0'%label); return
    print('  %-24s n=%-4d min=%.3f q25=%.3f med=%.3f q75=%.3f max=%.3f'
          %(label,len(xs),min(xs),q(xs,.25),q(xs,.5),q(xs,.75),max(xs)))


def clear_tilt_cache():
    c=getattr(PS,'_TILT_VIEW_CACHE',None)
    if hasattr(c,'clear'): c.clear()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',default='6400-6415')
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
        for obs in (getattr(h,'money_jump_obs',[]) or []):
            if (obs.get('street')=='preflop'
                    and obs.get('decision_kind')=='unopened'
                    and obs.get('unopened_modifiers')):
                r=copy.deepcopy(obs)
                r['_seed']=self.seed
                r['_hand_no']=self.hand_no
                r['_table']=tb.id
                rows.append(r)

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
    print('# money-open shadow audit')
    print('seeds=%d field_hands=%d unopened_rows=%d engine_errors=%d'
          %(len(seeds),field_hands,len(rows),len(errors)))

    # ----- size shadow -----
    size=[]
    for r in rows:
        m=r.get('unopened_modifiers') or {}
        if m.get('applied_open_size_bb') is None or m.get('applied_money_size_bb_shadow') is None:
            continue
        z=dict(r)
        z['_base']=float(m['applied_open_size_bb'])
        z['_shadow']=float(m['applied_money_size_bb_shadow'])
        z['_reduction']=z['_base']-z['_shadow']
        size.append(z)

    changed=[r for r in size if abs(r['_reduction'])>1e-9]
    at2=[r for r in size if abs(r['_shadow']-2.0)<1e-9]

    print()
    print('## open-size shadow')
    print('legal unopened raises:',len(size))
    print('changed: %d (%.1f%%)'%(len(changed),pct(len(changed),len(size))))
    print('shadow at legal 2BB floor: %d (%.1f%%)'%(len(at2),pct(len(at2),len(size))))
    dist('base size BB',[r['_base'] for r in size])
    dist('shadow size BB',[r['_shadow'] for r in size])
    dist('base-shadow reduction',[r['_reduction'] for r in changed])

    print()
    print('### size by stage')
    for st in ('pre','approach','bubble','itm','final9'):
        x=[r for r in size if stage(r)==st]
        if not x: continue
        ch=[r for r in x if abs(r['_reduction'])>1e-9]
        fl=sum(1 for r in x if abs(r['_shadow']-2.0)<1e-9)
        print('  %-9s n=%-4d changed=%-4d(%5.1f%%) base_med=%.2f shadow_med=%.2f at2=%d'
              %(st,len(x),len(ch),pct(len(ch),len(x)),
                q([r['_base'] for r in x],.5),q([r['_shadow'] for r in x],.5),fl))

    near=[r for r in size if stage(r) in ('approach','bubble','itm','final9')]
    print()
    print('### size by position near ladder')
    for pos in ('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB'):
        x=[r for r in near if r.get('pos')==pos]
        if not x: continue
        ch=[r for r in x if abs(r['_reduction'])>1e-9]
        print('  %-6s n=%-4d changed=%-4d(%5.1f%%) base_med=%.2f shadow_med=%.2f'
              %(pos,len(x),len(ch),pct(len(ch),len(x)),
                q([r['_base'] for r in x],.5),q([r['_shadow'] for r in x],.5)))

    if changed:
        print()
        print('### changed-size signal distributions')
        dist('restraint',[ (r.get('unopened_modifiers') or {}).get('restraint_shadow') for r in changed])
        dist('size awareness',[ (r.get('unopened_modifiers') or {}).get('size_awareness_shadow') for r in changed])
        dist('stack start BB',[r.get('stack_start_bb') for r in changed])

    # ----- limp shadow -----
    limp=[r for r in rows if (r.get('unopened_modifiers') or {}).get('limp_cf') is not None]
    add=[r for r in limp if (r.get('unopened_modifiers') or {}).get('limp_cf')=='add_limp']

    print()
    print('## limp-form same-roll shadow')
    print('eligible:',len(limp))
    cc=collections.Counter((r.get('unopened_modifiers') or {}).get('limp_cf') for r in limp)
    print('add_limp=%d base_limp=%d unchanged_raise=%d'
          %(cc['add_limp'],cc['base_limp'],cc['unchanged_raise']))

    print()
    print('### limp by stage')
    for st in ('pre','approach','bubble','itm','final9'):
        x=[r for r in limp if stage(r)==st]
        if not x: continue
        c=collections.Counter((r.get('unopened_modifiers') or {}).get('limp_cf') for r in x)
        print('  %-9s n=%-4d add=%-4d base=%-4d unchanged_raise=%-4d'
              %(st,len(x),c['add_limp'],c['base_limp'],c['unchanged_raise']))

    near_limp=[r for r in limp if stage(r) in ('approach','bubble','itm','final9')]
    print()
    print('### limp by position near ladder')
    for pos in ('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB'):
        x=[r for r in near_limp if r.get('pos')==pos]
        if not x: continue
        c=collections.Counter((r.get('unopened_modifiers') or {}).get('limp_cf') for r in x)
        print('  %-6s n=%-4d add=%-4d base=%-4d unchanged_raise=%-4d'
              %(pos,len(x),c['add_limp'],c['base_limp'],c['unchanged_raise']))

    sbadd=[r for r in add if r.get('pos')=='SB']
    print()
    print('SB add-limp candidates: %d / %d total add-limp'%(len(sbadd),len(add)))

    if add:
        print()
        print('### add-limp signal distributions')
        dist('pressure',[ (r.get('unopened_modifiers') or {}).get('pressure') for r in add])
        dist('restraint',[ (r.get('unopened_modifiers') or {}).get('restraint_shadow') for r in add])
        dist('late fraction',[ (r.get('unopened_modifiers') or {}).get('late_fraction_shadow') for r in add])
        dist('form awareness',[ (r.get('unopened_modifiers') or {}).get('form_awareness_shadow') for r in add])
        dist('stack start BB',[r.get('stack_start_bb') for r in add])

        print()
        print('### add-limp examples')
        for r in add[:a.top]:
            m=r.get('unopened_modifiers') or {}
            print('  seed=%s H%s %-8s %-5s stack=%sBB baseP=%.3f shadowP=%.3f roll=%.3f'
                  ' pressure=%.3f restraint=%.3f late=%.3f aware=%.3f%s'
                  %(r.get('_seed'),r.get('_hand_no'),stage(r),r.get('pos'),
                    r.get('stack_start_bb'),
                    float(m.get('base_limp_p') or 0.0),
                    float(m.get('money_limp_p_shadow') or 0.0),
                    float(m.get('limp_roll') or 0.0),
                    float(m.get('pressure') or 0.0),
                    float(m.get('restraint_shadow') or 0.0),
                    float(m.get('late_fraction_shadow') or 0.0),
                    float(m.get('form_awareness_shadow') or 0.0),
                    ' [SB currently blocked]' if r.get('pos')=='SB' else ''))

    print()
    print('No production behavior was changed by this audit.')
    if errors:
        print('ERROR SAMPLE:',errors[:3])
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
