#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V7 NUMERIC 6개 concept 의 코드 경로표. 읽기 전용, 정적 스캔만 한다.

각 사용처마다
  - 감싸는 함수
  - 그 줄
  - 그 함수가 상대 추정치(opp_est / read_opponent 결과)를 만지는가
를 낸다. 마지막 항목이 "자기 계산 정확도"와 "상대 수치 해석"을 가르는 표지다.
분류 자체는 사람이 코드를 읽고 한다 — 이 도구는 후보를 빠뜨리지 않기 위한 것이다.
"""
from __future__ import print_function

import argparse
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONCEPTS = ('range_read', 'potodds', 'spr', 'blocker', 'fold_equity',
            'board_texture')
COMPARATORS = ('sizing_tell', 'attention', 'adaptability')

# 상대의 관측 추정치를 만지는 표지. 자기 계산과 구분한다.
OPP_MARKERS = ('opp_est', 'read_opponent', 'perceived_profile', 'rd[', 'rd.get',
               'reads[', 'opp_read', 'fold_gap', 'barrel_gap', 'tb_gap',
               'size_gap', 'opp_profile', 'villain')

SKIP_DIRS = ('legacy', '__pycache__', 'ui', 'web', 'docs')
SKIP_PREFIX = ('tools_',)


def files():
    out = []
    for dirpath, dirnames, fnames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and not d.startswith('.')]
        rel = os.path.relpath(dirpath, ROOT)
        if rel.startswith('tools'):
            continue
        for f in fnames:
            if f.endswith('.py') and not f.startswith(SKIP_PREFIX):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def func_map(tree, src_lines):
    """줄번호 -> (함수명, 함수 본문 텍스트)"""
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, 'end_lineno', None) or node.lineno
            body = '\n'.join(src_lines[node.lineno - 1:end])
            spans.append((node.lineno, end, node.name, body))
    spans.sort(key=lambda x: (x[1] - x[0]))      # 가장 안쪽 함수 우선
    def lookup(ln):
        for lo, hi, name, body in spans:
            if lo <= ln <= hi:
                return name, body
        return None, ''
    return lookup


def scan(concepts):
    hits = {c: [] for c in concepts}
    pats = {c: re.compile(r"""['"]%s['"]""" % re.escape(c)) for c in concepts}
    for path in files():
        try:
            src = open(path, encoding='utf-8').read()
        except OSError:
            continue
        lines = src.split('\n')
        try:
            look = func_map(ast.parse(src), lines)
        except SyntaxError:
            continue
        rel = os.path.relpath(path, ROOT)
        for i, line in enumerate(lines, start=1):
            for c in concepts:
                if not pats[c].search(line):
                    continue
                fn, body = look(i)
                # 선언/목록 줄은 사용처가 아니다
                decl = ('CALC =' in line or 'EXEC =' in line
                        or 'TIER_V7_NUMERIC' in line or 'PERCEPTION =' in line
                        or re.match(r"\s*'%s':" % re.escape(c), line))
                hits[c].append({
                    'file': rel, 'line': i, 'func': fn,
                    'text': line.strip()[:150],
                    'declaration': bool(decl),
                    'touches_opp_est': bool(fn and any(m in body for m in OPP_MARKERS)),
                })
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-comparators', action='store_true')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    cs = CONCEPTS + (COMPARATORS if a.with_comparators else ())
    hits = scan(cs)
    for c in cs:
        use = [h for h in hits[c] if not h['declaration']]
        opp = [h for h in use if h['touches_opp_est']]
        print('=== %-14s 사용처 %2d (선언 제외)  그중 상대추정치 함수 안 %d ==='
              % (c, len(use), len(opp)))
        for h in use:
            print('   %-14s:%-5d %-26s %s %s'
                  % (h['file'], h['line'], h['func'] or '-',
                     'OPP' if h['touches_opp_est'] else '   ', h['text'][:96]))
        print()
    if a.out:
        json.dump(hits, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
