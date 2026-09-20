#!/usr/bin/env python3
"""머니점프 미오픈 sizing/limp shadow 전용 요약."""
import argparse, json

def load(path):
    out=[]
    with open(path, encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if line:
                out.append(json.loads(line))
    return out

def stage(r):
    rem,itm=r.get('remaining'),r.get('itm')
    if not rem or not itm: return 'na'
    if rem<=9: return 'final9'
    if rem<=itm: return 'itm'
    x=float(rem)/itm
    if x<=1.2: return 'bubble'
    if x<=1.5: return 'approach'
    return 'pre'

def q(xs,p):
    xs=sorted(float(x) for x in xs if x is not None)
    if not xs: return 0.0
    return xs[min(len(xs)-1,int((len(xs)-1)*p))]

ap=argparse.ArgumentParser()
ap.add_argument('path')
args=ap.parse_args()
rows=load(args.path)
rr=[r for r in rows if r.get('street')=='preflop'
    and r.get('decision_kind')=='unopened'
    and r.get('unopened_modifiers')]

print('=== money-open form shadow ===')
print('rows',len(rows),'unopened',len(rr))

print('\n[limp probability shadow by stage]')
for st in ('approach','bubble','itm','final9'):
    x=[r for r in rr if stage(r)==st
       and r['unopened_modifiers'].get('base_limp_p') is not None]
    if not x: continue
    b=[r['unopened_modifiers']['base_limp_p'] for r in x]
    m=[r['unopened_modifiers']['money_limp_p_shadow'] for r in x]
    pull=[r['unopened_modifiers'].get('limp_pull_shadow',0.0) for r in x]
    print('%-9s n=%-4d base p50/p90=%.3f/%.3f shadow=%.3f/%.3f pull=%.3f/%.3f' %
          (st,len(x),q(b,.5),q(b,.9),q(m,.5),q(m,.9),q(pull,.5),q(pull,.9)))

print('\n[limp shadow by position near ladder]')
near=[r for r in rr if stage(r) in ('approach','bubble','itm','final9')
      and r['unopened_modifiers'].get('base_limp_p') is not None]
for pos in ('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB'):
    x=[r for r in near if r.get('pos')==pos]
    if not x: continue
    b=[r['unopened_modifiers']['base_limp_p'] for r in x]
    m=[r['unopened_modifiers']['money_limp_p_shadow'] for r in x]
    late=[r['unopened_modifiers'].get('late_fraction_shadow',0.0) for r in x]
    print('%-6s n=%-4d base p50=%.3f shadow p50/p90=%.3f/%.3f late=%.3f' %
          (pos,len(x),q(b,.5),q(m,.5),q(m,.9),q(late,.5)))

print('\n[raise-size shadow by stage]')
for st in ('approach','bubble','itm','final9'):
    x=[r for r in rr if stage(r)==st
       and r['unopened_modifiers'].get('base_open_size_bb') is not None]
    if not x: continue
    b=[r['unopened_modifiers']['base_open_size_bb'] for r in x]
    m=[r['unopened_modifiers']['money_open_size_bb_shadow'] for r in x]
    atmin=sum(1 for v in m if abs(float(v)-2.0)<1e-9)
    print('%-9s raises=%-4d base p50/p90=%.2f/%.2f shadow=%.2f/%.2f at2bb=%d(%.1f%%)' %
          (st,len(x),q(b,.5),q(b,.9),q(m,.5),q(m,.9),
           atmin,100.0*atmin/len(x)))

print('\n[raise-size shadow by position near ladder]')
for pos in ('UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB'):
    x=[r for r in near if r.get('pos')==pos
       and r['unopened_modifiers'].get('base_open_size_bb') is not None]
    if not x: continue
    b=[r['unopened_modifiers']['base_open_size_bb'] for r in x]
    m=[r['unopened_modifiers']['money_open_size_bb_shadow'] for r in x]
    print('%-6s raises=%-3d base p50=%.2f shadow p50/p90=%.2f/%.2f' %
          (pos,len(x),q(b,.5),q(m,.5),q(m,.9)))

print('\n[SB limp shadow]')
sb=[r for r in near if r.get('pos')=='SB'
    and r['unopened_modifiers'].get('base_limp_p') is not None]
if sb:
    b=[r['unopened_modifiers']['base_limp_p'] for r in sb]
    m=[r['unopened_modifiers']['money_limp_p_shadow'] for r in sb]
    print('n=%d base p50/p90=%.3f/%.3f shadow p50/p90=%.3f/%.3f'
          ' currentSBBlock=%d' %
          (len(sb),q(b,.5),q(b,.9),q(m,.5),q(m,.9),
           sum(1 for r in sb if r['unopened_modifiers'].get('sb_limp_currently_blocked'))))
