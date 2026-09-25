#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static inventory of declared poker concepts and their production consumers.

Read-only audit.  It does not prove reachability or behavioral materiality.
"""

from __future__ import print_function

import ast
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persona as PS


GROUP = {}
for _name in PS.EXEC:
    GROUP[_name] = 'EXEC'
for _name in PS.CALC:
    GROUP[_name] = 'CALC'
for _name in PS.PERCEPTION:
    GROUP[_name] = 'PERCEPTION'

CONCEPTS = tuple(PS.ALL_CONCEPTS)
CSET = set(CONCEPTS)

SKIP_DIRS = {
    '.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    'tools', 'tests', 'test', 'venv', '.venv', 'node_modules',
}
PROFILE_NAMES = {'profile', 'prof', 'p', 'ax', 'actor', '_actor'}

STRATEGIC_MARKERS = (
    'TODO/F', 'TODO', 'FIXME', 'shadow', '미연결', '미확정',
    '아직 행동', '행동에는 아직', '잠정',
)


def lit_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        b = dotted(node.value)
        return (b + '.' if b else '') + node.attr
    if isinstance(node, ast.Subscript):
        b = dotted(node.value)
        k = lit_str(node.slice)
        if k is not None:
            return "%s[%r]" % (b, k)
        return b + '[]'
    return ''


def looks_profile_expr(node):
    d = dotted(node)
    if not d:
        return False
    head = d.split('.', 1)[0].split('[', 1)[0]
    return head in PROFILE_NAMES or "['concepts']" in d or '.concepts' in d


def expand_street(base):
    out = []
    for st in ('flop', 'turn', 'river'):
        c = PS.street_concept(base, st)
        if c in CSET and c not in out:
            out.append(c)
    return out


class Scan(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.func = '<module>'
        self.refs = []

    def add(self, concept, node, kind, detail=''):
        if concept not in CSET:
            return
        self.refs.append({
            'concept': concept,
            'path': self.path,
            'line': getattr(node, 'lineno', 0),
            'func': self.func,
            'kind': kind,
            'detail': detail,
        })

    def visit_FunctionDef(self, node):
        old = self.func
        self.func = node.name
        self.generic_visit(node)
        self.func = old

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        fn = dotted(node.func)
        attr = node.func.attr if isinstance(node.func, ast.Attribute) else None
        name = node.func.id if isinstance(node.func, ast.Name) else None

        # Normal persona accessor family.
        if attr in ('sk', 'skill', 'has', 'gate', 'calc_noise'):
            idx = 1
            if len(node.args) > idx:
                c = lit_str(node.args[idx])
                if c:
                    self.add(c, node, 'accessor', fn)
        elif name in ('sk', 'S', '_sk', 'skill', 'has', 'gate'):
            if node.args:
                c = lit_str(node.args[0])
                if c:
                    self.add(c, node, 'local_accessor', name)

        # street_concept('cbet', street) etc.  Expand to the declared leaves.
        if attr == 'street_concept' or name == 'street_concept':
            if node.args:
                base = lit_str(node.args[0])
                if base:
                    for c in expand_street(base):
                        self.add(c, node, 'street_family', base)

        # Direct .get('concept') on profile-like objects or concepts dicts.
        if attr == 'get' and node.args:
            c = lit_str(node.args[0])
            if c in CSET and looks_profile_expr(node.func.value):
                self.add(c, node, 'direct_get', dotted(node.func.value))

        self.generic_visit(node)

    def visit_Subscript(self, node):
        c = lit_str(node.slice)
        if c in CSET and looks_profile_expr(node.value):
            self.add(c, node, 'direct_subscript', dotted(node.value))
        self.generic_visit(node)


def production_py_files():
    for base, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(base, ROOT)
        parts = set(rel.split(os.sep)) if rel != '.' else set()
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if parts & SKIP_DIRS:
            continue
        for fn in files:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(base, fn)
            rp = os.path.relpath(path, ROOT)
            # persona declares/generates the skills; it is not counted as a
            # strategic consumer of its own declarations.
            if rp == 'persona.py':
                continue
            yield path, rp


def scan_refs():
    out = []
    parse_errors = []
    for path, rp in production_py_files():
        try:
            src = open(path, encoding='utf-8').read()
            tree = ast.parse(src, filename=rp)
        except Exception as e:
            parse_errors.append((rp, str(e)))
            continue
        s = Scan(rp)
        s.visit(tree)
        out.extend(s.refs)
    return out, parse_errors


def marker_scan():
    rows = []
    for path, rp in production_py_files():
        try:
            lines = open(path, encoding='utf-8').read().splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            low = line.lower()
            for m in STRATEGIC_MARKERS:
                if m.lower() in low:
                    rows.append((rp, i, line.strip()))
                    break
    return rows


def main():
    refs, parse_errors = scan_refs()
    by = collections.defaultdict(list)
    for r in refs:
        by[r['concept']].append(r)

    print('# concept wiring static audit')
    print('declared concepts: %d  production refs: %d  parse errors: %d'
          % (len(CONCEPTS), len(refs), len(parse_errors)))
    print()
    print('%-22s %-11s %5s %5s  %s'
          % ('concept', 'group', 'refs', 'funcs', 'consumer sites'))
    print('-' * 100)

    zero = []
    single = []
    direct = []
    for c in CONCEPTS:
        rs = by.get(c, [])
        funcs = sorted(set('%s:%s' % (r['path'], r['func']) for r in rs))
        if not rs:
            zero.append(c)
        if rs and len(funcs) <= 1:
            single.append(c)
        if any(r['kind'].startswith('direct_') for r in rs):
            direct.append(c)
        sites = ', '.join(funcs[:5])
        if len(funcs) > 5:
            sites += ', +%d' % (len(funcs)-5)
        print('%-22s %-11s %5d %5d  %s'
              % (c, GROUP.get(c, '?'), len(rs), len(funcs), sites or '-'))

    print()
    print('## zero production consumers')
    print('  ' + (', '.join(zero) if zero else '(none)'))

    print()
    print('## single-function consumers')
    print('  ' + (', '.join(single) if single else '(none)'))

    print()
    print('## concepts with direct profile/dict reads')
    print('  ' + (', '.join(direct) if direct else '(none)'))
    for c in direct:
        for r in by[c]:
            if r['kind'].startswith('direct_'):
                print('    %-20s %s:%d %s [%s]'
                      % (c, r['path'], r['line'], r['func'], r['kind']))

    print()
    print('## detailed low-coverage concepts (<=2 unique functions)')
    for c in CONCEPTS:
        rs = by.get(c, [])
        funcs = sorted(set((r['path'], r['func']) for r in rs))
        if len(funcs) > 2:
            continue
        print('  %s (%s)' % (c, GROUP.get(c, '?')))
        if not rs:
            print('    NO CONSUMER')
            continue
        for r in rs:
            print('    %s:%d %s kind=%s detail=%s'
                  % (r['path'], r['line'], r['func'], r['kind'], r['detail']))

    print()
    print('## strategic TODO/shadow/provisional markers')
    marks = marker_scan()
    for rp, line, txt in marks:
        print('  %s:%d  %s' % (rp, line, txt))
    if not marks:
        print('  (none)')

    if parse_errors:
        print()
        print('## parse errors')
        for p, e in parse_errors:
            print('  %s: %s' % (p, e))

    print()
    print('Interpretation rule: static reference != reachable/material behavior.')
    print('Any zero/single/partial item must be traced or counterfactually tested before edits.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
