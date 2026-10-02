#!/usr/bin/env python3
"""Semantic completeness check: every strategy decision site must be owned.

Method (reproducible, no judgement at run time):
  1. AST-enumerate *decision sites* in production strategy modules:
     if/elif/while tests, conditional expressions, numeric-literal
     calculations / clamps / rng draws, and calculated returns whose source
     mentions a poker-domain token (rel, eq, need, pot, stack, outs, range,
     bluff, street, rng, ...).  See SITE_RULES below.
  2. A site is OWNED when it lies inside
       a) a code span listed in docs/semantic_audit/completeness/SPAN_MAP.json
          (most specific span wins), or
       b) a function that the concept registry names as producer/function
          of exactly one concept and that is NOT listed as DECOMPOSED
          (multi-meaning functions must be covered span by span).
     Spans whose concept starts with '@nonsemantic:' are explicit
     non-strategy code (logging, provenance, defensive guards, plumbing)
     with a stated reason.
  3. Exit 1 if any site is unowned, a span cannot be resolved, or a span
     names a concept missing from the registry.

Run: python tools/check_semantic_completeness.py [--list]
"""
import ast, csv, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'semantic_audit')
MODS = ['plan', 'preflop', 'ranges', 'session', 'reads', 'persona', 'gto',
        'icm', 'money_pressure', 'texture', 'bot', 'depth', 'runner',
        'action_events', 'dynamics', 'context', 'play', 'fieldsim', 'live2',
        'tourney', 'archetypes', 'field']
DOMAIN = re.compile(
    r'\b(rel|eq|equity|made|need|spr|outs|danger|pot|stack|tocall|to_call|'
    r'initiative|aggr|bluff|value|draw|board|pct|tp|tot|commit|fold|call|'
    r'raise|shove|bet|street|river|turn|flop|range|combo|blocker|nut|adv|bf|'
    r'icm|bubble|m_|bb|ante|open|limp|iso|3bet|4bet|level|n_opp|multiway|mw|'
    r'size|frac|sk\(|temper\(|bias\(|exploit|read|gap|w\b|tilt|rng|random)',
    re.I)


_SEEN = {}


def _defname(m, stack, n):
    """Qualified-name disambiguation for re-defined functions (name, name#2...)."""
    key = (m, '.'.join(stack + [n.name]))
    seen = _SEEN.setdefault(key, [])
    if n.lineno not in seen:
        seen.append(n.lineno)
    i = seen.index(n.lineno)
    return n.name if i == 0 else '%s#%d' % (n.name, i + 1)


def sites():
    out = []
    for m in MODS:
        p = os.path.join(ROOT, m + '.py')
        src = open(p, encoding='utf-8').read()
        tree = ast.parse(src)
        stack = []

        class V(ast.NodeVisitor):
            def visit_FunctionDef(self, n):
                stack.append(_defname(m, stack, n)); self.generic_visit(n); stack.pop()
            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, n):
                stack.append(n.name); self.generic_visit(n); stack.pop()

            def rec(self, n, kind, expr):
                s = ast.get_source_segment(src, expr) or ''
                if DOMAIN.search(s):
                    out.append({'mod': m, 'func': '.'.join(stack) or '<module>',
                                'line': n.lineno, 'kind': kind,
                                'src': re.sub(r'\s+', ' ', s)[:160]})

            def visit_If(self, n):
                self.rec(n, 'if', n.test); self.generic_visit(n)

            def visit_IfExp(self, n):
                self.rec(n, 'ifexp', n.test); self.generic_visit(n)

            def visit_While(self, n):
                self.rec(n, 'while', n.test); self.generic_visit(n)

            def visit_Return(self, n):
                if n.value is not None and isinstance(n.value, (ast.BinOp, ast.Call)):
                    s = ast.get_source_segment(src, n.value) or ''
                    if re.search(r'max\(|min\(|\*|\+', s):
                        self.rec(n, 'return-calc', n.value)
                self.generic_visit(n)

            def visit_Assign(self, n):
                if isinstance(n.value, (ast.BinOp, ast.Call, ast.IfExp,
                                        ast.Compare, ast.BoolOp)):
                    s = ast.get_source_segment(src, n.value) or ''
                    if re.search(r'(?<![\w.])\d*\.\d+', s) or 'random()' in s:
                        self.rec(n, 'calc', n.value)
                self.generic_visit(n)
            visit_AugAssign = visit_Assign
        V().visit(tree)
    return out


def functions():
    """(mod, qualified func) -> (start, end, [source lines])"""
    out = {}
    for m in MODS:
        src = open(os.path.join(ROOT, m + '.py'), encoding='utf-8').read()
        lines = src.split('\n')
        tree = ast.parse(src)

        def walk(node, prefix):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    nm = ch.name if isinstance(ch, ast.ClassDef) else _defname(
                        m, prefix.split('.') if prefix else [], ch)
                    q = (prefix + '.' if prefix else '') + nm
                    if not isinstance(ch, ast.ClassDef):
                        out[(m, q)] = (ch.lineno, ch.end_lineno, lines)
                    walk(ch, q)
        walk(tree, '')
    return out


def registry():
    rows = list(csv.DictReader(open(os.path.join(DOC, 'CONCEPT_FUNCTION_REGISTRY.csv'),
                                    encoding='utf-8')))
    own = {}
    for r in rows:
        for col in ('producer', 'function', 'current_function'):
            for m, f in re.findall(r'\b([a-z_][a-z_0-9]*)\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)',
                                   r.get(col) or ''):
                own.setdefault((m, f), set()).add(r['concept'])
    return rows, own


def resolve(span, funcs):
    key = (span['module'], span['func'])
    if key not in funcs:
        raise KeyError('function not found: %s.%s' % key)
    a, b, lines = funcs[key]
    if not span.get('from'):
        return a, b
    def _marker(mk):
        # 'text@@n' selects the n-th occurrence inside the function
        if '@@' in mk:
            t, n = mk.rsplit('@@', 1)
            return t, int(n)
        return mk, 1
    fm, fn = _marker(span['from'])
    s = e = None
    seen = 0
    for i in range(a, b + 1):
        if s is None and fm in lines[i - 1]:
            seen += 1
            if seen < fn:
                continue
            s = i
            if not span.get('to'):
                e = i
                break
        if s is not None and span.get('to') and span['to'] in lines[i - 1]:
            e = i
            break
    if s is None or e is None:
        raise KeyError('span markers not found in %s.%s: %r..%r'
                       % (key + (span['from'], span.get('to'))))
    return s, e


def main():
    smap = json.load(open(os.path.join(DOC, 'completeness', 'SPAN_MAP.json'), encoding='utf-8'))
    decomposed = {tuple(x.split(':', 1)) for x in smap['decomposed']}
    rows, own = registry()
    concepts = {r['concept'] for r in rows}
    funcs = functions()
    errors = []
    spans = []
    for sp in smap['spans']:
        c = sp['concept']
        if not c.startswith('@nonsemantic:') and c not in concepts:
            errors.append('span concept not in registry: %s' % c)
        try:
            a, b = resolve(sp, funcs)
        except KeyError as e:
            errors.append(str(e)); continue
        if (sp['module'], sp['func']) in decomposed and not sp.get('from'):
            errors.append('whole-function span not allowed for decomposed %s.%s (%s)'
                          % (sp['module'], sp['func'], c))
            continue
        spans.append((sp['module'], sp['func'], a, b, c))
    S = sites()
    unowned = []
    owners = {}
    for x in S:
        key = (x['mod'], x['func'])
        hit = [sp for sp in spans if sp[0] == x['mod'] and sp[1] == x['func']
               and sp[2] <= x['line'] <= sp[3]]
        if hit:
            hit.sort(key=lambda sp: sp[3] - sp[2])
            owners[(x['mod'], x['line'])] = hit[0][4]
            continue
        fn_owner = own.get(key) or own.get((x['mod'], x['func'].split('.')[-1]))
        if key not in decomposed and fn_owner and len(fn_owner) == 1:
            owners[(x['mod'], x['line'])] = next(iter(fn_owner))
            continue
        unowned.append(x)
    # function-level coverage: a function with no decision site can still
    # implement a semantic (e.g. a lookup table or a mapping).
    span_funcs = {(sp[0], sp[1]) for sp in spans}
    nonsem_f = {tuple(k.split(':', 1)) for k in smap.get('nonsemantic_functions', {})}
    nonsem_m = set(smap.get('nonsemantic_modules', {}))
    unowned_funcs = []
    for (m, f) in sorted(funcs):
        if (m, f) in span_funcs or (m, f) in nonsem_f or m in nonsem_m:
            continue
        if own.get((m, f.split('#')[0])) or own.get((m, f.split('.')[-1].split('#')[0])):
            continue
        unowned_funcs.append('%s.%s' % (m, f))
    # part 3: module-level numeric tables in strategy modules are knowledge
    # or parameters; each must map to a concept (or be declared nonsemantic).
    TABLE_MODS = ['plan', 'preflop', 'ranges', 'session', 'reads', 'persona', 'gto',
                  'icm', 'money_pressure', 'texture', 'bot', 'depth', 'runner',
                  'action_events', 'dynamics', 'context']
    tables = smap.get('tables', {})
    unowned_tables = []
    for m in TABLE_MODS:
        src = open(os.path.join(ROOT, m + '.py'), encoding='utf-8').read()
        for n in ast.parse(src).body:
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                tg = n.targets[0] if isinstance(n, ast.Assign) else n.target
                name = getattr(tg, 'id', None)
                if not name or name.startswith('__'):
                    continue
                if re.search(r'\d', ast.get_source_segment(src, n.value) or ''):
                    c = tables.get('%s:%s' % (m, name))
                    if not c:
                        unowned_tables.append('%s.%s' % (m, name))
                    elif not c.startswith('@') and c not in concepts:
                        errors.append('table concept not in registry: %s -> %s' % (name, c))
    # part 4: every module.function named by a registry row must exist
    allmods = {x[:-3] for x in os.listdir(ROOT) if x.endswith('.py')}
    fnames = {(m, f.split('#')[0]) for m, f in funcs} | \
             {(m, f.split('.')[-1].split('#')[0]) for m, f in funcs}
    stale_refs = []
    for r in rows:
        for col in ('producer', 'current_function'):
            for m, f in re.findall(r'\b([a-z_][a-z_0-9]*)\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)',
                                   r.get(col) or ''):
                if m not in MODS:
                    continue
                if (m, f) in fnames or (m, f.split('.')[-1]) in fnames:
                    continue
                src = open(os.path.join(ROOT, m + '.py'), encoding='utf-8').read()
                if re.search(r'^%s\s*=' % re.escape(f.split('.')[-1]), src, re.M):
                    continue
                stale_refs.append('%s: %s %s.%s' % (r['concept'], col, m, f))
    errors.extend('stale registry reference ' + x for x in stale_refs)
    used = {}
    for c in owners.values():
        used[c] = used.get(c, 0) + 1
    report = {
        'sites': len(S),
        'owned': len(S) - len(unowned),
        'unowned': len(unowned),
        'span_errors': errors,
        'nonsemantic_sites': sum(v for k, v in used.items() if k.startswith('@nonsemantic:')),
        'concepts_with_sites': len([k for k in used if not k.startswith('@')]),
        'functions': len(funcs),
        'unowned_functions': len(unowned_funcs),
        'tables': len(tables),
        'unowned_tables': len(unowned_tables),
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if '--list' in sys.argv:
        for x in unowned:
            print('%s.%s:%d %s %s' % (x['mod'], x['func'], x['line'], x['kind'], x['src'][:110]))
        for f in unowned_funcs:
            print('FUNC', f)
        for t in unowned_tables:
            print('TABLE', t)
    if '--json' in sys.argv:
        json.dump({'report': report, 'owners': {'%s:%d' % k: v for k, v in owners.items()},
                   'unowned': unowned, 'unowned_functions': unowned_funcs,
                   'unowned_tables': unowned_tables}, open(sys.argv[sys.argv.index('--json') + 1], 'w'),
                  ensure_ascii=False, indent=1)
    sys.exit(1 if (unowned or errors or unowned_funcs or unowned_tables) else 0)


if __name__ == '__main__':
    main()
