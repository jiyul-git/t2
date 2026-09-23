#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""persona concept 전체를 '상대 정량분석 파이프라인 6단계'에 매핑한다. 읽기 전용.

이름이 비슷한지가 아니라 **실제 소비 경로**로 가른다. 각 concept 의 모든
사용처를 찾아 감싸는 함수로 단계를 판정한다.

  RECORD    관측을 장부에 적는다            reads.Book.observe_*
  ESTIMATE  장부에서 추정치를 만든다        reads.estimate / obs_from_profile /
                                            perceived_profile / estimate_concepts / _shrink
  INTERPRET 추정치를 익스플로잇 신호로 번역  persona.read_resolution / read_opponent /
                                            street_gap, plan.line_bluff_prior,
                                            ranges.perceived_range
  APPLY     자기 행동을 정한다              plan / preflop / depth / money_pressure / bot

APPLY 만 있는 concept 은 상대 정량분석 파이프라인에 **참여하지 않는다.**
"""
from __future__ import print_function

import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persona as PS

STAGE_FUNCS = {
    'ESTIMATE': {('reads.py', 'estimate'), ('reads.py', 'obs_from_profile'),
                 ('reads.py', 'perceived_profile'), ('reads.py', 'estimate_concepts'),
                 ('reads.py', '_shrink')},
    'INTERPRET': {('persona.py', 'read_resolution'), ('persona.py', 'read_opponent'),
                  ('persona.py', 'street_gap'), ('persona.py', 'exploit_weight'),
                  ('plan.py', 'line_bluff_prior'), ('ranges.py', 'perceived_range'),
                  ('ranges.py', 'narrow_by_actions')},
}
RECORD_PREFIX = 'observe_'
APPLY_FILES = ('plan.py', 'preflop.py', 'depth.py', 'money_pressure.py',
               'bot.py', 'gto.py', 'icm.py', 'texture.py', 'dynamics.py',
               'session.py', 'runner.py')
SKIP_DIRS = ('legacy', '__pycache__', 'ui', 'web', 'docs', 'tools')


def files():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith('.')]
        if os.path.relpath(dp, ROOT).startswith('tools'):
            continue
        for f in fn:
            if f.endswith('.py') and not f.startswith('tools_'):
                out.append(os.path.join(dp, f))
    return sorted(out)


def func_lookup(tree, lines):
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, 'end_lineno', None) or node.lineno
            spans.append((node.lineno, end, node.name))
    spans.sort(key=lambda x: x[1] - x[0])
    def look(ln):
        for lo, hi, nm in spans:
            if lo <= ln <= hi:
                return nm
        return None
    return look


def stage_of(rel, fn):
    if fn and fn.startswith(RECORD_PREFIX):
        return 'RECORD'
    for st, s in STAGE_FUNCS.items():
        if (rel, fn) in s:
            return st
    if rel in APPLY_FILES:
        return 'APPLY'
    return 'OTHER'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    concepts = list(PS.ALL_CONCEPTS) + list(PS.TEMPER)
    pats = {c: re.compile(r"""['"]%s['"]""" % re.escape(c)) for c in concepts}
    hits = {c: [] for c in concepts}

    for path in files():
        src = open(path, encoding='utf-8').read()
        lines = src.split('\n')
        try:
            look = func_lookup(ast.parse(src), lines)
        except SyntaxError:
            continue
        rel = os.path.relpath(path, ROOT)
        for i, line in enumerate(lines, 1):
            for c in concepts:
                if not pats[c].search(line):
                    continue
                if ('CALC =' in line or 'EXEC =' in line or 'TEMPER =' in line
                        or 'PERCEPTION =' in line or 'TIER_V7_NUMERIC' in line
                        or re.match(r"\s*'%s':" % re.escape(c), line)
                        or 'ALL_CONCEPTS' in line):
                    continue
                fn = look(i)
                hits[c].append({'file': rel, 'line': i, 'func': fn,
                                'stage': stage_of(rel, fn),
                                'text': line.strip()[:110]})

    print('%-18s %-8s %s' % ('concept', 'group', 'stages (사용처 수)'))
    print('-' * 78)
    summary = {}
    for c in concepts:
        grp = ('TEMPER' if c in PS.TEMPER else
               'CALC' if c in PS.CALC else
               'PERCEPT' if c in PS.PERCEPTION else 'EXEC')
        st = {}
        for h in hits[c]:
            st[h['stage']] = st.get(h['stage'], 0) + 1
        pipe = [k for k in ('RECORD', 'ESTIMATE', 'INTERPRET') if st.get(k)]
        summary[c] = {'group': grp, 'stages': st, 'pipeline': pipe,
                      'sites': hits[c]}
        tag = '  <== 파이프라인 참여' if pipe else ''
        print('%-18s %-8s %s%s'
              % (c, grp,
                 ' '.join('%s:%d' % (k, v) for k, v in sorted(st.items())) or '(사용처 없음)',
                 tag))

    inpipe = [c for c in concepts if summary[c]['pipeline']]
    print('\n상대 정량분석 파이프라인(RECORD/ESTIMATE/INTERPRET)에 들어가는 concept: %d개'
          % len(inpipe))
    for c in inpipe:
        print('   %-18s %s' % (c, summary[c]['pipeline']))
        for h in summary[c]['sites']:
            if h['stage'] in ('RECORD', 'ESTIMATE', 'INTERPRET'):
                print('        %-12s:%-5d %-22s %s'
                      % (h['file'], h['line'], h['func'], h['text'][:78]))
    if a.out:
        json.dump(summary, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('\nwrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
