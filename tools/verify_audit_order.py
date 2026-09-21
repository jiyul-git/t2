#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit.py 의 스트리트 액션 순서 검사 D1~D6.

audit 은 그 핸드에 실제로 있었던 포지션 집합의 정규 순서를 써야 한다.
8맥스 상수를 쓰면 9인 핸드의 UTG+2 가 기대 순서에서 빠져 정상 핸드에
거짓 '순서' 경보가 난다.

  D1  9인 preflop  — 거짓 경보가 없어야 한다
  D2  9인 postflop — 거짓 경보가 없어야 한다
  D3  현대 8맥스 아카이브 — 순서 경보 집합이 기존(8맥스 상수)과 완전히 같아야 한다
  D4  구 5인/HU 아카이브 — 같은 조건
  D5  9인 핸드의 순서를 실제로 어겼으면 그 스트리트만 잡아야 한다
  D6  알 수 없는 라벨 집합 — 억지 정렬하지 말고 '순서검사 생략'을 남겨야 한다
"""
import json, os, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import audit
import table as TB

FAILS = []


def _ok(name, cond, detail=''):
    print('  %-4s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        FAILS.append(name)


# ---------- 참조 구현 (테스트가 기대하는 정답) ----------
_C_PRE, _C_POST = TB.orders(9)[1], TB.orders(9)[2]


def ref_orders(labels):
    """그 라벨 집합의 (PRE, POST). 모르면 (None, None)."""
    labs = set(labels)
    try:
        _, pre, post = TB.orders(len(labs))
        if set(pre) == labs:
            return list(pre), list(post)
    except ValueError:
        pass
    pre = [p for p in _C_PRE if p in labs]
    post = [p for p in _C_POST if p in labs]
    if set(pre) == labs:
        return pre, post
    return None, None


def legacy_orders(labels):
    """수정 전 audit 이 쓰던 8맥스 고정 사다리."""
    _, pre8, post8 = TB.orders(8)
    labs = set(labels)
    return [p for p in pre8 if p in labs], [p for p in post8 if p in labs]


def order_flags(rec, derive):
    """audit.py 의 순서 검사만 떼어 재현한다."""
    pos = rec['pos']
    seat_of = {v: int(k) for k, v in pos.items()}
    pre_o, post_o = derive(pos.values())
    out = []
    if pre_o is None:
        return ['생략']
    streets = {}
    for e in rec['full_log']:
        streets.setdefault(e[0], []).append(int(e[1]))
    for stt in ('preflop', 'flop', 'turn', 'river'):
        acts = streets.get(stt)
        if not acts:
            continue
        order = pre_o if stt == 'preflop' else post_o
        expect = [seat_of[p] for p in order if p in seat_of]
        first = []
        for s_ in acts:
            if s_ in first:
                break
            first.append(s_)
        sub = [s_ for s_ in expect if s_ in first]
        if first != sub:
            out.append(stt)
    return out


# ---------- 합성 레코드 ----------
DECK = [r + s for r in '23456789TJQKA' for s in 'cdhs']


def mk9(scramble=False, postflop=False, labels=None):
    labs = labels or ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
    pos = {str(i + 1): labs[i] for i in range(len(labs))}
    seat_of = {v: i + 1 for i, v in enumerate(labs)}
    hole = {str(i + 1): [DECK[2 * i], DECK[2 * i + 1]] for i in range(len(labs))}
    board = DECK[2 * len(labs):2 * len(labs) + 5]
    pre = [p for p in _C_PRE if p in seat_of] if set(labs) <= set(_C_PRE) else labs
    log = []
    if postflop:
        for p in pre:
            s = seat_of[p]
            log.append(['preflop', s, 'call' if p != 'BB' else 'check', 200])
        post = [p for p in _C_POST if p in seat_of]
        if set(labs) == {'SB', 'BB'}:
            post = TB.orders(2)[2]
        seats_fl = [seat_of[p] for p in post]
        if scramble:
            seats_fl = seats_fl[1:] + seats_fl[:1]
        for s in seats_fl:
            log.append(['flop', s, 'check', 0])
    else:
        seats_pf = [seat_of[p] for p in pre if p != 'BB']
        if scramble:
            seats_pf = seats_pf[1:] + seats_pf[:1]
        for s in seats_pf:
            log.append(['preflop', s, 'fold', 0])
    return {'hand_no': 1, 'pos': pos, 'hole': hole, 'board': board,
            'hero': seat_of.get('BB', 1), 'blinds': [100, 200],
            'stacks_before': {str(i + 1): 30000 for i in range(len(labs))},
            'profiles': {}, 'full_log': log,
            'result': {'pot': 300, 'winners': [seat_of.get('BB', 1)]}}


def audit_order_flags(rec):
    """실제 audit.check() 를 돌려 '순서' / '생략' 관련 플래그만 추린다."""
    orig = audit._load
    audit._load = lambda: [rec]
    try:
        out = audit.check(rec['hand_no'])
    finally:
        audit._load = orig
    return [x for x in out if x.startswith('[순서]') or '생략' in x]


def main():
    print('=== D1  9인 preflop 정상 핸드 ===')
    r = mk9()
    f = audit_order_flags(r)
    _ok('D1', not f, '플래그=%s' % f)

    print('=== D2  9인 postflop 정상 핸드 ===')
    r = mk9(postflop=True)
    f = audit_order_flags(r)
    _ok('D2', not f, '플래그=%s' % f)

    recs = []
    for fn in glob.glob(os.path.join(ROOT, '*.jsonl')):
        try:
            for l in open(fn, encoding='utf-8'):
                if l.strip():
                    d = json.loads(l)
                    if d.get('pos') and d.get('full_log'):
                        recs.append(d)
        except Exception:
            pass
    modern = [d for d in recs if ref_orders(d['pos'].values())[0] is not None
              and set(d['pos'].values()) == set(TB.orders(len(d['pos']))[1])]
    legacy = [d for d in recs if d not in modern]

    print('=== D3  현대 아카이브 %d건 — 기존 결과 보존 ===' % len(modern))
    bad = [d for d in modern
           if order_flags(d, ref_orders) != order_flags(d, legacy_orders)]
    _ok('D3', not bad, '기존과 다른 레코드 %d건' % len(bad))

    print('=== D4  구 아카이브 %d건 — 기존 결과 보존 ===' % len(legacy))
    bad = [d for d in legacy
           if order_flags(d, ref_orders) != order_flags(d, legacy_orders)]
    _ok('D4', not bad, '기존과 다른 레코드 %d건' % len(bad))

    print('=== D5  9인 순서 위반은 그 스트리트만 탐지 ===')
    r = mk9(postflop=True, scramble=True)
    f = audit_order_flags(r)
    _ok('D5', any('flop' in x for x in f) and not any('preflop' in x for x in f),
        '플래그=%s' % f)

    print('=== D6  알 수 없는 라벨 집합은 생략을 명시 ===')
    r = mk9(labels=['UTG', 'MP', 'CO', 'BTN', 'SB', 'BB'])
    f = audit_order_flags(r)
    _ok('D6', any('생략' in x for x in f), '플래그=%s' % f)

    print()
    if FAILS:
        print('FAIL %d/%d : %s' % (len(FAILS), 6, ', '.join(FAILS)))
        return 1
    print('PASS audit 순서 검사 D1~D6')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
