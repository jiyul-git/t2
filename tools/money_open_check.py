#!/usr/bin/env python3
"""머니점프 미오픈 range intervention 전용 요약."""
import argparse, collections, json

def load(path):
    out=[]
    with open(path, encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line:
                out.append(json.loads(line))
    return out

def stage(r):
    rem, itm = r.get('remaining'), r.get('itm')
    if not rem or not itm: return 'na'
    if rem <= 9: return 'final9'
    if rem <= itm: return 'itm'
    x=float(rem)/itm
    if x <= 1.2: return 'bubble'
    if x <= 1.5: return 'approach'
    return 'pre'

def pct(n,d):
    return 100.0*n/d if d else 0.0

def quant(xs,p):
    xs=sorted(float(x) for x in xs)
    if not xs: return 0.0
    return xs[min(len(xs)-1,int((len(xs)-1)*p))]

ap=argparse.ArgumentParser()
ap.add_argument('path')
args=ap.parse_args()
rows=load(args.path)
rr=[r for r in rows if r.get('street')=='preflop'
    and r.get('decision_kind')=='unopened'
    and (r.get('unopened_modifiers') or {}).get('range_cf')]

print('=== money-open focused check ===')
print('rows',len(rows),'unopened_cf',len(rr))
print('\n[stage local CF]')
for st in ('pre','approach','bubble','itm','final9'):
    x=[r for r in rr if stage(r)==st]
    if not x: continue
    c=collections.Counter(r['unopened_modifiers']['range_cf'] for r in x)
    fs=[r['unopened_modifiers']['range_factor'] for r in x]
    print('%-9s n=%-4d widen=%-3d(%4.1f%%) narrow=%-3d(%4.1f%%)'
          ' factor p10/p50/p90=%.3f/%.3f/%.3f' %
          (st,len(x),c['widen_entry'],pct(c['widen_entry'],len(x)),
           c['narrow_fold'],pct(c['narrow_fold'],len(x)),
           quant(fs,.1),quant(fs,.5),quant(fs,.9)))

near=[r for r in rr if stage(r) in ('approach','bubble','itm','final9')]
print('\n[topology split]')
for label,fn in (
    ('safe',lambda r:(r.get('covered_by_yet_to_act') or 0)==0),
    ('danger',lambda r:(r.get('covered_by_yet_to_act') or 0)>0),
):
    x=[r for r in near if fn(r)]
    c=collections.Counter(r['unopened_modifiers']['range_cf'] for r in x)
    pr=[r['unopened_modifiers'].get('pressure',0.0) for r in x]
    dg=[r['unopened_modifiers'].get('danger_fraction',0.0) for r in x]
    print('%-7s n=%-4d widen=%-3d narrow=%-3d pressure p50/p90=%.3f/%.3f'
          ' danger p50/p90=%.3f/%.3f' %
          (label,len(x),c['widen_entry'],c['narrow_fold'],
           quant(pr,.5),quant(pr,.9),quant(dg,.5),quant(dg,.9)))

print('\n[changed examples]')
changed=[r for r in near
         if r['unopened_modifiers']['range_cf']!='unchanged']
for r in changed[:20]:
    m=r['unopened_modifiers']; s=r.get('money_signals') or {}
    print('H%s %-8s %-5s stack=%sbb cf=%s'
          ' factor=%.3f p=%.3f danger=%.3f preserve=%.3f urgency=%.3f act=%s' %
          (r.get('hand_no'),stage(r),r.get('pos'),r.get('stack_start_bb'),
           m.get('range_cf'),float(m.get('range_factor') or 1.0),
           float(m.get('pressure') or 0.0),
           float(m.get('danger_fraction') or 0.0),
           float(s.get('self_preservation') or 0.0),
           float(s.get('urgency') or 0.0),r.get('action')))

print('\n[sizing/form shadow only]')
for st in ('approach','bubble','itm','final9'):
    x=[r for r in rr if stage(r)==st]
    if not x: continue
    sz=[r['unopened_modifiers'].get('size_factor_shadow',1.0) for r in x]
    lp=[r['unopened_modifiers'].get('limp_pull_shadow',0.0) for r in x]
    print('%-9s size p50/p90=%.3f/%.3f limp p50/p90=%.3f/%.3f' %
          (st,quant(sz,.5),quant(sz,.9),quant(lp,.5),quant(lp,.9)))
