#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""포스트플랍 포지션 술어와 그 행동 영향 검증.

A1~A10  session.oop_field / oop_vs 의 정의
C1~C2   불변식
B2      line_bluff_prior 의 aggressor_pos_oop
B1      옛 절대식 팔 vs 새 팔을 같은 입력에 재생 — 출력이 달라지면
        반드시 바뀐 플래그가 있어야 한다 (설명 불가 = 0)
C3      난수 소비량 특성화:
          출력 동일  -> 소비량 동일
          출력 변화  -> decide_size 호출 여부 때문에 소비량이 달라질 수 있다

난수 소비 계측은 **위임(delegation) 프록시만** 쓴다. random.Random 을
서브클래싱해 random() 을 덮으면 CPython 이 _randbelow 구현을 바꿔
choice() 결과 자체가 달라진다 — 계측이 실험을 오염시킨다. 실제로 그
방식으로 존재하지 않는 divergence 한 건이 만들어졌다.
"""
import copy, inspect, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import plan as PL
import session as SE
import table as TB

FAILS = []


def ok(name, cond, detail=''):
    print('  %-5s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        FAILS.append(name)


def POST(n):
    return TB.orders(n)[2]


# ---------- 위임 프록시 (서브클래싱 금지) ----------
_BASE = random.Random
_CNT = {'n': 0}
_COUNTED = ('random', 'uniform', 'gauss', 'choice', 'randrange', 'randint',
            'shuffle', 'betavariate', 'sample', 'triangular', 'choices')


class _Proxy:
    __slots__ = ('_r',)

    def __init__(self, *a, **k):
        object.__setattr__(self, '_r', _BASE(*a, **k))

    def __getattr__(self, name):
        f = getattr(object.__getattribute__(self, '_r'), name)
        if name in _COUNTED:
            def g(*a, **k):
                _CNT['n'] += 1
                return f(*a, **k)
            return g
        return f


def main():
    p2, p8, p9 = POST(2), POST(8), POST(9)
    keep = lambda names: [x for x in p9 if x not in names]

    print('=== A. 술어 ===')
    ok('A1', SE.oop_field(p2, 'SB') is False, '헤즈업 SB 는 IP')
    ok('A2', SE.oop_field(p2, 'BB') is True, '헤즈업 BB 는 OOP')
    ok('A3', SE.oop_vs(p9, 'CO', 'BTN') is True, '9맥스 CO vs BTN')
    ok('A4', SE.oop_vs(p8, 'CO', 'BTN') is True, '8맥스 CO vs BTN')
    ok('A5', SE.oop_vs(p9, 'HJ', 'CO') is True, '9맥스 HJ vs CO')
    ok('A6', SE.oop_vs(p9, 'UTG', 'SB') is False, '9맥스 UTG vs SB')
    ok('A7', SE.oop_field(p9, 'CO', keep({'CO', 'BTN'})) is True, 'CO·BTN 만 생존')
    ok('A8', SE.oop_field(p9, 'CO', keep({'UTG', 'CO'})) is False, 'UTG·CO 만 생존')
    ok('A9', SE.oop_field(p9, 'BB', (), [x for x in p9
                                        if p9.index(x) > p9.index('BB')]) is False,
       '뒤가 전원 올인')
    ok('A10', SE.oop_field(p9, 'BTN') is False, 'BTN 은 항상 IP')
    # edge: 액션 불가 좌석이 뒤에 있어도 '뒤에 액션할 사람'이 아니다
    ok('A11', SE.oop_field(p2, 'BB', (), ('SB',)) is False,
       '헤즈업에서 뒤 한 명이 올인')
    ok('A12', SE.oop_field(p9, 'HJ', ('CO',), ('BTN',)) is False,
       '뒤는 폴드·올인뿐, 앞에만 행동 가능한 상대')
    ok('A13', SE.oop_field(p9, 'SB', keep({'SB', 'BB'}), ('BB',)) is False,
       'actor 자신이 마지막 행동 가능자')
    ok('A14', SE.oop_field(p9, 'SB', keep({'SB', 'BB'})) is True,
       '같은 상황에서 뒤가 올인이 아니면 True (A13 대조군)')

    print('=== C. 불변식 ===')
    ok('C1', all(SE.oop_field(POST(n), POST(n)[-1]) is False for n in range(2, 10)),
       '마지막 액션자는 모든 n 에서 IP')
    ok('C2', all(SE.oop_vs(p9, a, b) != SE.oop_vs(p9, b, a)
                 for a in p9 for b in p9 if a != b), '반대칭')

    print('=== B2. aggressor_pos_oop ===')
    ok('B2a', SE.oop_vs(p9, 'BTN', 'CO') is False, '어그레서 BTN, 관찰자 CO')
    ok('B2b', SE.oop_vs(p9, 'UTG', 'SB') is False, '어그레서 UTG, 관찰자 SB')
    ok('B2c', SE.oop_vs(p9, 'UTG', 'CO') is True, '어그레서 UTG, 관찰자 CO')

    print('=== B1/C3. 같은 입력, 옛 팔 vs 새 팔 ===')
    orig = PL.update_plan
    rec = []

    def probe(*a, **k):
        fr = sys._getframe(1).f_locals
        h, s, r2, ag = fr.get('h'), fr.get('s'), fr.get('r2'), fr.get('aggressor')
        ctx = None
        if h is not None and s is not None and r2 is not None and s in r2.order:
            order = list(r2.order)
            live_ag = (ag is not None and ag != s and ag in order
                       and ag not in r2.folded and ag not in r2.allin)
            ctx = {'field': SE.oop_field(order, s, r2.folded, r2.allin),
                   'vs_aggr': SE.oop_vs(order, s, ag) if live_ag else None,
                   'legacy': h.POST.index(h.pos[s]) < 3}
            # 어그레서가 폴드했거나 올인이면 '그보다 먼저 액션하는가'는 성립하지
            # 않는다 — 그때 vs_aggr 이 None 인지를 실제 엔진 상태로 확인한다.
            if ag is not None and ag != s and ag in order:
                ctx['ag_dead'] = (ag in r2.folded or ag in r2.allin)
            else:
                ctx['ag_dead'] = None
        rec.append({'a': copy.deepcopy(a), 'k': copy.deepcopy(k), 'ctx': ctx})
        return orig(*a, **k)

    PL.update_plan = probe
    f = FS.Field(entries=100, seed=5150, fmt='standard')
    for _ in range(18):
        if f.remaining() <= 8:
            break
        f.hand_no += 1
        f.advance_level()
        for tb in list(f.tables.values()):
            if tb.n() >= 2:
                f._play_table(tb)
        f._collect_busts()
        f._balance()
    PL.update_plan = orig
    sig = list(inspect.signature(orig).parameters)
    OI = sig.index('oop')

    def run(r, oop, vs_aggr, legacy):
        a = list(copy.deepcopy(r['a']))
        k = copy.deepcopy(r['k'])
        a[OI] = oop
        k['oop_vs_aggr'] = vs_aggr
        k['oop_legacy_abs'] = legacy
        _CNT['n'] = 0
        random.Random = _Proxy
        try:
            out = orig(*a, **k)
        finally:
            random.Random = _BASE
        return out, _CNT['n']

    pairs = diffs = unexplained = cnt_only = 0
    unexplained_rows = []
    for r in rec:
        c = r['ctx']
        if c is None or len(r['a']) <= OI:
            continue
        street = r['a'][8]
        o_out, o_n = run(r, c['legacy'], None, c['legacy'])       # 옛 팔
        n_out, n_n = run(r, c['field'], c['vs_aggr'], c['legacy'])  # 새 팔
        io = PL.intent_of(o_out, street) or {}
        inn = PL.intent_of(n_out, street) or {}
        outd = (o_out.get('plan') != n_out.get('plan')
                or io.get('act') != inn.get('act')
                or round(io.get('size', 0) or 0, 6) != round(inn.get('size', 0) or 0, 6))
        flagd = (c['field'] != c['legacy']
                 or (c['vs_aggr'] is not None and c['vs_aggr'] != c['legacy']))
        pairs += 1
        if outd:
            diffs += 1
            if not flagd:
                unexplained += 1
                unexplained_rows.append({
                    'street': street, 'ctx': c,
                    'old': {'plan': o_out.get('plan'), 'intent': io, 'rng': o_n},
                    'new': {'plan': n_out.get('plan'), 'intent': inn, 'rng': n_n},
                    'args_oop_old': c['legacy'], 'args_oop_new': c['field'],
                    'vs_aggr': c['vs_aggr'], 'legacy': c['legacy'],
                })
        if (o_n != n_n) and not outd:
            cnt_only += 1
    dead = [r['ctx'] for r in rec if r['ctx'] and r['ctx'].get('ag_dead')]
    ok('A15', all(c['vs_aggr'] is None for c in dead),
       '어그레서가 폴드·올인인 실제 결정 %d건에서 vs_aggr 이 None' % len(dead))
    ok('B1a', pairs > 0, '재생한 결정 %d건' % pairs)
    ok('B1b', diffs > 0, '출력이 달라진 결정 %d건' % diffs)
    if unexplained_rows:
        print('  B1c details:', repr(unexplained_rows[:10]))
    ok('B1c', unexplained == 0, '바뀐 플래그 없이 출력만 달라진 건 %d' % unexplained)
    ok('C3', cnt_only == 0,
       '출력은 같은데 난수 소비량만 달라진 건 %d (위임 프록시 계측)' % cnt_only)

    print()
    if FAILS:
        print('FAIL %d : %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('PASS oop 술어·행동 영향·난수 특성화')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
