#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_plan 입력 계약: 최초 수립 경로 vs 보드변화 재계획 경로.

plan.update_plan 은 계획을 두 경로로 만든다.

  first 이거나 state 가 없다  -> make_plan 을 직접 부른다   (플랍)
  그 외                       -> runner.revise_plan 경유     (턴·리버)
                                 board_changed 일 때만 make_plan

두 경로가 **같은 함수로 같은 dict 를 새로 만드는데** 넘기는 상황 입력이
다르다. revise 쪽이 빠뜨린 인자는 make_plan 의 기본값으로 떨어진다.
기본값은 중립이 아니다. initiative=True 는 '공격권 보유'를,
tilt=0.0 는 '틸트 없음'을, bb_chips=None 은 '현재 BB 알 수 없음'을 뜻한다.

이력:
  A6 최초 누락 5개: oop_vs_aggr, oop_legacy_abs, initiative, tilt, bb_chips.
  이후 위치/공격권 3개 전달 복구(A5 후속).
  PR #31 SHA 3f30cc82540dc6d69fbf22295f49da20194626a4 실제 누락 2개:
    tilt, bb_chips. 그러나 과거 5개를 KNOWN_MISSING 으로 잘못 기대하여 C4 실패.
  P11 수정 후 기대 누락 0개. 실제 재계획 경로 양쪽 함수 경계를 검증한다.

과거 A6 고정 fixture (seed 5150/9001/4242 x standard/deep/turbo x 16핸드):
  update_plan 4,736 / revise 경로 2,580 / board_changed make_plan 810.
  이전 실험 결과: tilt 단독 출력 변화 0, bb_chips 단독 사이징 차이 2.
  이 수치는 과거 관측값이며 P11 수정본의 실행 결과를 의미하지 않는다.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 과거 5개 누락 -> PR31 시점 2개 누락 -> P11 수정 후 0개.
HISTORICAL_A6_MISSING = frozenset(
    {'oop_vs_aggr', 'oop_legacy_abs', 'initiative', 'tilt', 'bb_chips'})
PR31_MISSING = frozenset({'tilt', 'bb_chips'})
KNOWN_MISSING = frozenset()

FAILS = []


def ok(name, cond, detail=''):
    print('  %-6s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        FAILS.append(name)


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError('함수를 찾지 못했다: %s' % name)


def _calls(node, name):
    out = []
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if (isinstance(f, ast.Name) and f.id == name) or \
           (isinstance(f, ast.Attribute) and f.attr == name):
            out.append(n)
    return out


def main():
    plan = ast.parse(open(os.path.join(ROOT, 'plan.py'), encoding='utf-8').read())
    runner = ast.parse(open(os.path.join(ROOT, 'runner.py'), encoding='utf-8').read())

    mk = _fn(plan, 'make_plan')
    params = [a.arg for a in mk.args.args]
    n_required = len(params) - len(mk.args.defaults)
    print('make_plan 인자 %d개 (위치 필수 %d개)' % (len(params), n_required))

    up_calls = _calls(_fn(plan, 'update_plan'), 'make_plan')
    rv_fn = _fn(runner, 'revise_plan')
    rv_calls = _calls(rv_fn, 'make_plan')
    route_calls = _calls(_fn(plan, 'update_plan'), 'revise_plan')
    session = ast.parse(open(os.path.join(ROOT, 'session.py'), encoding='utf-8').read())
    source_calls = _calls(session, 'update_plan')
    ok('C1', len(up_calls) == 1, 'update_plan 안의 make_plan 호출 %d개' % len(up_calls))
    ok('C2', len(rv_calls) == 1, 'revise_plan 안의 make_plan 호출 %d개' % len(rv_calls))
    if FAILS:
        return 1
    up, rv = up_calls[0], rv_calls[0]

    up_kw = {k.arg for k in up.keywords if k.arg}
    rv_kw = {k.arg for k in rv.keywords if k.arg}
    ok('C3', len(up.args) == n_required and len(rv.args) == n_required,
       '두 경로 모두 위치 인자 %d개 (%d / %d)' % (n_required, len(up.args), len(rv.args)))

    missing = up_kw - rv_kw
    extra = rv_kw - up_kw
    print()
    print('  %-18s %-8s %-8s' % ('상황 입력', '최초', '재계획'))
    for p in params[n_required:]:
        print('  %-18s %-8s %-8s%s' % (
            p, 'O' if p in up_kw else '-', 'O' if p in rv_kw else '-',
            '   <= 알려진 누락' if p in KNOWN_MISSING else ''))
    print()
    # 이름만 있는 것이 아니라 session -> update -> revise -> make
    # 네 단계에서 실제 tilt / bb_chips 문맥을 그대로 전달하는지 고정한다.
    forwarded = {}
    if len(route_calls) == 1:
        forwarded = {k.arg: k.value for k in route_calls[0].keywords if k.arg}
    source = {}
    if len(source_calls) == 1:
        source = {k.arg: ast.unparse(k.value)
                  for k in source_calls[0].keywords if k.arg}
    rv_params = {a.arg for a in rv_fn.args.args}
    links_ok = (
        len(route_calls) == 1 and len(source_calls) == 1
        and source.get('tilt') == 'h.axes(s)[1]'
        and source.get('bb_chips') == 'h.bb'
        and all(f in rv_params and f in forwarded
                and isinstance(forwarded[f], ast.Name)
                and forwarded[f].id == f and f in rv_kw
                for f in ('tilt', 'bb_chips')))
    ok('C4', missing == KNOWN_MISSING and links_ok,
       '재계획 누락=%s; session/update/revise/make 값 전달=%s'
       % (sorted(missing), links_ok))
    ok('C5', not extra, '재계획에만 있는 인자 = %s' % sorted(extra))

    # 기본값이 중립이 아님을 고정한다
    defaults = dict(zip(params[n_required:],
                        [ast.literal_eval(d) if isinstance(d, ast.Constant) else '?'
                         for d in mk.args.defaults]))
    ok('C6', defaults.get('initiative') is True,
       "initiative 기본값 %r — '공격권 보유' 라는 주장" % defaults.get('initiative'))
    ok('C7', defaults.get('oop_vs_aggr') is None and defaults.get('oop_legacy_abs') is None,
       'oop_vs_aggr/oop_legacy_abs 기본값 None — 442 게이트가 닫힌다')

    print()
    if FAILS:
        print('FAIL %d : %s' % (len(FAILS), ', '.join(FAILS)))
        print('C4 원인을 확인할 것. 기대값만 변경해 실제 전달 결함을 숨기지 말 것.')
        return 1
    print('PASS 재계획 입력 계약 (A6 누락 5 -> PR31 누락 2 -> P11 누락 0)')
    print('  과거 A6 누락=%s' % sorted(HISTORICAL_A6_MISSING))
    print('  PR31 누락=%s' % sorted(PR31_MISSING))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
