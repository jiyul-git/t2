#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static inventory for street-concept granularity and obvious cross-wire gaps."""

import ast
import collections
import os
import re
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

FILES=['persona.py','plan.py','preflop.py','session.py','money_pressure.py',
       'ranges.py','reads.py','runner.py','field.py','fieldsim.py']


def read(p):
    with open(os.path.join(ROOT,p),encoding='utf-8') as f:
        return f.read()


def street_map():
    src=read('persona.py')
    tree=ast.parse(src)
    out={}
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name=='street_concept':
            for x in ast.walk(node):
                if isinstance(x,ast.Assign) and isinstance(x.value,ast.Dict):
                    for k,v in zip(x.value.keys,x.value.values):
                        if (isinstance(k,ast.Tuple) and len(k.elts)==2
                                and all(isinstance(e,ast.Constant) for e in k.elts)
                                and isinstance(v,ast.Constant)):
                            fam=k.elts[0].value; st=k.elts[1].value
                            if fam in ('cbet','barrel','checkraise','bluffcatch','thin_value'):
                                out[(fam,st)]=v.value
            break
    return out


def consumers():
    pat=re.compile(r"street_concept\(\s*['\"]([^'\"]+)['\"]\s*,\s*([^\)]+)\)")
    out=collections.defaultdict(list)
    for p in FILES:
        src=read(p)
        for i,line in enumerate(src.splitlines(),1):
            m=pat.search(line)
            if m:
                out[m.group(1)].append((p,i,line.strip()))
    return out


def fn_source(src,name):
    tree=ast.parse(src)
    lines=src.splitlines()
    for n in tree.body:
        if isinstance(n,ast.FunctionDef) and n.name==name:
            return '\n'.join(lines[n.lineno-1:n.end_lineno])
    return ''


def quoted_plans(expr):
    return set(re.findall(r"['\"]([a-zA-Z0-9_]+)['\"]",expr))


def main():
    sm=street_map()
    cons=consumers()

    print('# street concept granularity audit')
    print()
    print('## mapping matrix')
    fams=sorted(set(k[0] for k in sm))
    for fam in fams:
        vals=[(st,sm.get((fam,st))) for st in ('flop','turn','river') if (fam,st) in sm]
        print('  %-12s %s'%(fam,' | '.join('%s->%s'%x for x in vals)))

    print()
    print('## shared-skill groups across streets')
    for fam in fams:
        rev=collections.defaultdict(list)
        for (f,st),skill in sm.items():
            if f==fam:
                rev[skill].append(st)
        for skill,sts in rev.items():
            if len(sts)>1:
                print('  %-12s %-22s streets=%s'%(fam,skill,','.join(sts)))

    print()
    print('## street_concept consumers')
    for fam in fams:
        print('  [%s]'%fam)
        for p,i,line in cons.get(fam,[]):
            print('    %s:%d  %s'%(p,i,line))

    psrc=read('plan.py')
    ck=fn_source(psrc,'checkraise_decision')

    # Explicit plans that seed p via direct branches in checkraise_decision.
    base_plans=set()
    for line in ck.splitlines():
        if re.search(r"\b(?:if|elif)\s+plan\s*==",line):
            base_plans |= quoted_plans(line)
    # Plans called bluff in downstream opponent-read adjustment.
    m=re.search(r"is_bluff\s*=\s*plan\s+in\s*\(([^\)]*)\)",ck)
    bluff_tagged=quoted_plans(m.group(1)) if m else set()

    print()
    print('## checkraise cross-wire structural check')
    print('  explicit base-probability plans:', ', '.join(sorted(base_plans)) or '(none)')
    print('  downstream bluff-tagged plans :', ', '.join(sorted(bluff_tagged)) or '(none)')
    missing=sorted(bluff_tagged-base_plans)
    print('  bluff-tagged without explicit base branch:', ', '.join(missing) or '(none)')

    # Some families are named by one street while backing multiple streets.
    print()
    print('## naming / granularity flags')
    flags=[]
    for (fam,st),skill in sm.items():
        if st not in skill and skill not in ('checkraise_late','bluffcatch_early'):
            # only report obviously named mismatch such as thin_value_turn on flop
            if any(x in skill for x in ('flop','turn','river','early','late')):
                flags.append((fam,st,skill))
    # force the intentionally aggregated aliases into report too
    for fam in ('checkraise','bluffcatch','thin_value'):
        rev=collections.defaultdict(list)
        for (f,st),skill in sm.items():
            if f==fam: rev[skill].append(st)
        for skill,sts in rev.items():
            if len(sts)>1:
                flags.append((fam,'+'.join(sts),skill))
    seen=set()
    for x in flags:
        if x in seen: continue
        seen.add(x)
        print('  %-12s %-12s -> %s'%x)

    print()
    print('Static result only: shared mapping != defect by itself; each flagged family needs semantic review.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
