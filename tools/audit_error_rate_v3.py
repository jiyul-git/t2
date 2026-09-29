#!/usr/bin/env python3
"""Audit persona.error_rate before deciding whether to wire or remove it.

Questions:
1. Does error_rate have any behavioral consumer outside persona.describe?
2. What population distribution does the formula create?
3. Is it mostly a duplicate projection of attention/consistency?
4. Would wiring it as a generic random-action probability overlap already
   modeled concept-specific calculation/perception errors?

Measurement only: this script changes no strategy.
"""
import ast, json, math, pathlib, random, statistics, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import persona as PS

EXCLUDE_DIRS={'.git','vendor','data','__pycache__','.pytest_cache'}

def source_refs():
    rows=[]
    for p in ROOT.rglob('*.py'):
        if any(x in EXCLUDE_DIRS for x in p.parts):
            continue
        rel=str(p.relative_to(ROOT))
        try:
            src=p.read_text(encoding='utf-8')
            tree=ast.parse(src,filename=rel)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                fn=node.func
                name=None
                if isinstance(fn,ast.Name):
                    name=fn.id
                elif isinstance(fn,ast.Attribute):
                    name=fn.attr
                if name=='error_rate':
                    rows.append({
                        'file':rel,
                        'line':getattr(node,'lineno',None),
                        'context':'call',
                    })
            elif isinstance(node,ast.Attribute) and node.attr=='error_rate':
                rows.append({
                    'file':rel,
                    'line':getattr(node,'lineno',None),
                    'context':'attribute_ref',
                })
    # de-duplicate a Call + Attribute pair on same line
    uniq={}
    for r in rows:
        uniq[(r['file'],r['line'])]=r
    return sorted(uniq.values(),key=lambda x:(x['file'],x['line'] or 0))

def corr(a,b):
    ma=statistics.fmean(a); mb=statistics.fmean(b)
    va=sum((x-ma)**2 for x in a); vb=sum((x-mb)**2 for x in b)
    if va<=0 or vb<=0: return 0.0
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(va*vb)

def population(n=12000):
    rng=random.Random(20260929)
    out={}
    for q in (.40,.80,1.20):
        rates=[]; cons=[]; att=[]; overall=[]
        calc_weak=[]; calc_strong=[]
        for i in range(n):
            p=PS.make_player(rng,q,pid=int(q*100000)+i)
            rates.append(PS.error_rate(p))
            cons.append(PS.temper(p,'consistency',5.0))
            att.append(PS.temper(p,'attention',5.0))
            overall.append(PS.overall_skill(p))
            # Compare to actual calc skill axes: a generic lapse should not be
            # mistaken for concept-specific knowledge/accuracy.
            calc_weak.append(statistics.fmean(
                PS.sk(p,k) for k in ('outs','potodds','spr')))
            calc_strong.append(statistics.fmean(
                PS.sk(p,k) for k in ('range_read','blocker','board_texture')))
        s=sorted(rates)
        out[str(q)]={
            'mean':round(statistics.fmean(rates),5),
            'sd':round(statistics.pstdev(rates),5),
            'p05':round(s[int(.05*(n-1))],5),
            'p50':round(s[int(.50*(n-1))],5),
            'p95':round(s[int(.95*(n-1))],5),
            'min':round(s[0],5),'max':round(s[-1],5),
            'corr_consistency':round(corr(rates,cons),4),
            'corr_attention':round(corr(rates,att),4),
            'corr_overall_skill':round(corr(rates,overall),4),
            'corr_calc_outs_potodds_spr':round(corr(rates,calc_weak),4),
            'corr_read_blocker_texture':round(corr(rates,calc_strong),4),
        }
    return out

def formula_reconstruction(n=4000):
    """Confirm error_rate contains no hidden state beyond attention/consistency."""
    rng=random.Random(31029)
    max_abs=0.0
    for i in range(n):
        p=PS.make_player(rng,.78,pid=i)
        cons=PS.temper(p,'consistency',5.0)
        att=PS.temper(p,'attention',5.0)
        exp=max(.01,min(.28,.30-.020*cons-.012*att))
        max_abs=max(max_abs,abs(PS.error_rate(p)-exp))
    return max_abs

def main():
    refs=source_refs()
    behavioral=[r for r in refs
                if not (r['file']=='persona.py'
                        or r['file'].startswith('tools/audit_error_rate_v3.py'))]
    # persona.describe is presentation only; inspect all persona.py calls so the
    # report makes this explicit.
    persona_refs=[r for r in refs if r['file']=='persona.py']
    out={
        'source_refs':refs,
        'persona_refs':persona_refs,
        'behavioral_consumers':behavioral,
        'behavioral_consumer_count':len(behavioral),
        'population':population(),
        'formula_reconstruction_max_abs_error':formula_reconstruction(),
        'interpretation':{
            'dead_for_strategy':len(behavioral)==0,
            'formula_inputs':['temper.consistency','temper.attention'],
            'recommendation':(
                'deprecate presentation-only error_rate; do not wire as generic random action '
                'without a separately validated execution-lapse mechanism'
                if len(behavioral)==0 else
                'review existing consumers before any change'),
        }
    }
    out['pass']=(
        out['formula_reconstruction_max_abs_error']<1e-12
        and out['behavioral_consumer_count']==0
    )
    print(json.dumps(out,indent=2,sort_keys=True))
    raise SystemExit(0 if out['pass'] else 1)

if __name__=='__main__':
    main()
