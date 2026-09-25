#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refined static concept-wiring inventory over core runtime modules.

This corrects two limitations of the first audit:
- persona.py contains real decision consumers and must be scanned;
- root diagnostics (tools_*.py) and legacy modules must not count as production consumers.
"""

from __future__ import print_function
import ast, collections, os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path: sys.path.insert(0, ROOT)
import persona as PS

CORE_FILES = [
    'persona.py','plan.py','preflop.py','session.py','money_pressure.py',
    'ranges.py','reads.py','runner.py','depth.py','gto.py','play.py',
    'fieldsim.py','field.py','bot.py','dynamics.py','context.py','icm.py',
]
CSET=set(PS.ALL_CONCEPTS)
GROUP={c:'EXEC' for c in PS.EXEC}
GROUP.update({c:'CALC' for c in PS.CALC})
GROUP.update({c:'PERCEPTION' for c in PS.PERCEPTION})
PROFILE_NAMES={'profile','prof','p','ax','actor','_actor'}

def lit(n):
    return n.value if isinstance(n,ast.Constant) and isinstance(n.value,str) else None

def dot(n):
    if isinstance(n,ast.Name): return n.id
    if isinstance(n,ast.Attribute):
        b=dot(n.value); return (b+'.' if b else '')+n.attr
    if isinstance(n,ast.Subscript):
        b=dot(n.value); k=lit(n.slice)
        return ("%s[%r]"%(b,k)) if k is not None else b+'[]'
    return ''

def looks_profile(n):
    d=dot(n)
    head=d.split('.',1)[0].split('[',1)[0] if d else ''
    return head in PROFILE_NAMES or "['concepts']" in d

def expand_family(base):
    out=[]
    for st in ('flop','turn','river'):
        c=PS.street_concept(base,st)
        if c in CSET and c not in out: out.append(c)
    return out

class Scan(ast.NodeVisitor):
    def __init__(self,path):
        self.path=path; self.func='<module>'; self.refs=[]
    def add(self,c,node,kind,detail=''):
        if c in CSET:
            self.refs.append((c,self.path,getattr(node,'lineno',0),self.func,kind,detail))
    def visit_FunctionDef(self,node):
        old=self.func; self.func=node.name; self.generic_visit(node); self.func=old
    visit_AsyncFunctionDef=visit_FunctionDef
    def visit_Call(self,node):
        fn=dot(node.func)
        attr=node.func.attr if isinstance(node.func,ast.Attribute) else None
        name=node.func.id if isinstance(node.func,ast.Name) else None
        if attr in ('sk','skill','has','gate','calc_noise') and len(node.args)>1:
            c=lit(node.args[1])
            if c: self.add(c,node,'accessor',fn)
        elif name in ('sk','S','_sk','skill','has','gate') and node.args:
            c=lit(node.args[0])
            if c: self.add(c,node,'local_accessor',name)
        if attr=='street_concept' or name=='street_concept':
            if node.args:
                b=lit(node.args[0])
                if b:
                    for c in expand_family(b): self.add(c,node,'street_family',b)
        if attr=='get' and node.args:
            c=lit(node.args[0])
            if c in CSET and looks_profile(node.func.value):
                self.add(c,node,'direct_get',dot(node.func.value))
        self.generic_visit(node)
    def visit_Subscript(self,node):
        c=lit(node.slice)
        if c in CSET and looks_profile(node.value):
            self.add(c,node,'direct_subscript',dot(node.value))
        self.generic_visit(node)

def main():
    refs=[]; errors=[]
    for rp in CORE_FILES:
        path=os.path.join(ROOT,rp)
        if not os.path.exists(path): continue
        try:
            tree=ast.parse(open(path,encoding='utf-8').read(),filename=rp)
        except Exception as e:
            errors.append((rp,str(e))); continue
        s=Scan(rp); s.visit(tree); refs.extend(s.refs)

    by=collections.defaultdict(list)
    for r in refs: by[r[0]].append(r)

    print('# concept wiring static audit v2')
    print('core runtime files: %d  declared concepts: %d  refs: %d  parse errors: %d'
          %(len(CORE_FILES),len(PS.ALL_CONCEPTS),len(refs),len(errors)))
    print('%-22s %-11s %5s %5s  %s'%('concept','group','refs','funcs','consumer sites'))
    print('-'*100)
    zero=[]; single=[]; direct=[]
    for c in PS.ALL_CONCEPTS:
        rs=by.get(c,[])
        funcs=sorted(set('%s:%s'%(r[1],r[3]) for r in rs))
        if not rs: zero.append(c)
        if rs and len(funcs)<=1: single.append(c)
        if any(r[4].startswith('direct_') for r in rs): direct.append(c)
        sites=', '.join(funcs[:6])
        if len(funcs)>6: sites+=', +%d'%(len(funcs)-6)
        print('%-22s %-11s %5d %5d  %s'%(c,GROUP.get(c,'?'),len(rs),len(funcs),sites or '-'))

    print()
    print('## zero core-runtime consumers')
    print('  '+(', '.join(zero) if zero else '(none)'))
    print()
    print('## single-function core-runtime consumers')
    print('  '+(', '.join(single) if single else '(none)'))
    print()
    print('## direct profile/dict reads in core runtime')
    print('  '+(', '.join(direct) if direct else '(none)'))
    for c in direct:
        for r in by[c]:
            if r[4].startswith('direct_'):
                print('    %-20s %s:%d %s [%s]'%(c,r[1],r[2],r[3],r[4]))

    print()
    print('## low-coverage detail (<=2 unique functions)')
    for c in PS.ALL_CONCEPTS:
        rs=by.get(c,[])
        funcs=sorted(set((r[1],r[3]) for r in rs))
        if len(funcs)>2: continue
        print('  %s (%s)'%(c,GROUP.get(c,'?')))
        if not rs:
            print('    NO CONSUMER')
        else:
            for r in rs:
                print('    %s:%d %s kind=%s detail=%s'%(r[1],r[2],r[3],r[4],r[5]))

    print()
    print('Notes:')
    print('- persona.py is included because open_pct/bias/ICM/variance helpers are behavioral.')
    print('- tools_*.py and legacy_dynamics.py are intentionally excluded from consumer counts.')
    print('- static references still require reachability/materiality checks before edits.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
