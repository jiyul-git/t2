#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_plan 입력 계약: 최초 수립 경로 vs 보드변화 재계획 경로.

plan.update_plan 은 계획을 두 경로로 만든다.

  first 이거나 state 가 없다  -> make_plan 을 직접 부른다   (플랍)
  그 외                       -> runner.revise_plan 경유     (턴·리버)
                                 board_changed 일 때만 make_plan

두 경로가 **같은 함수로 같은 dict 를 새로 만드는데** 넘기는 상황 입력이
다르다. revise 쪽이 빠뜨린 인자는 make_plan 의 기본값으로 떨어진다.
기본값은 중립이 아니라 특정 주장이다 — initiative=True 는 '내가 공격권을
갖고 있다', oop_vs_aggr=None 은 '어그레서 대비 관계가 없다' 이다.

이것은 **고쳐지지 않은 알려진 불일치**다. 저장소를 깨뜨리지 않기 위해
실패로 만들지 않고, 차이를 **정확히 고정**한다. 하나라도 전달되기
시작하면 이 테스트가 실패하므로, 고칠 때 이 목록도 같이 줄여야 한다.

측정 근거 (seed 5150/9001/4242 x standard/deep/turbo x 16핸드):
  update_plan 4,736 호출 중 revise 경로 2,580, 그중 make_plan 도달 810.
  그 810 지점에서 oop_field 는 기본 False 와 478건(59.0%) 다르고,
  oop_vs_aggr 은 기본 None 과 315건(38.9%) 다르다.
  반사실 재생: 포지션만/initiative만/tilt만 고치면 출력 변화 0,
  bb_chips 를 넘기면 810 중 2건에서 사이즈가 바뀐다.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 현재 알려진 불일치. 하나라도 revise 쪽에 추가되면 여기서 빼야 한다.
KNOWN_MISSING = {'oop_vs_aggr', 'oop_legacy_abs', 'initiative', 'tilt', 'bb_chips'}

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
    rv_calls = _calls(_fn(runner, 'revise_plan'), 'make_plan')
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
    ok('C4', missing == KNOWN_MISSING,
       '재계획이 빠뜨리는 인자 = %s' % sorted(missing))
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
        print('계약이 바뀌었다. 고의로 고쳤다면 KNOWN_MISSING 을 갱신할 것.')
        return 1
    print('PASS 재계획 입력 계약 (알려진 누락 %d개 고정)' % len(KNOWN_MISSING))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
