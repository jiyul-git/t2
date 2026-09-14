#!/usr/bin/env python3
"""`gto.mdf` 반사실 — 오픈 사이즈 보정이 실제 행동을 얼마나 정하는가.

  python3 tools/cf_mdf.py --n 3000
  python3 tools/cf_mdf.py --table          표와 이론 MDF 대조만

**읽기 전용이다.** gto.py / preflop.py 를 고치지 않는다.
`gto.mdf` 를 메모리에서만 갈아 끼운다 (`defend_pct` 가 전역으로 조회한다).

변종
  M0 현재        _MDF 보간표. 6bb 에서 포화한다
  M1 제거        비율 항을 1.0 으로 — 오픈 사이즈가 디펜스 폭에 영향 없음
  M2 이론 MDF    1.5/(1.5+X). 포화 없이 계속 줄어든다
                 (프리플랍에서 오프너는 X bb 를 걸어 블라인드 1.5bb 를 딴다)
"""
import argparse, os, random, sys
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import gto as G, preflop as pf, persona as PS

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
OPENERS = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB']

_orig_mdf = G.mdf


def mdf_none(open_bb):
    return _orig_mdf(3.0)                      # 비율이 항상 1.0


def mdf_theory(open_bb):
    return 1.5/(1.5 + max(1.5, float(open_bb or 3.0)))


def band(x):
    return ('≤3bb' if x <= 3 else '3~6bb' if x <= 6
            else '6~12bb' if x <= 12 else '>12bb')


def show_table():
    t3 = _orig_mdf(3.0)
    print('%-8s %9s %10s %10s %10s' % ('오픈', '표', '이론 MDF', '표 비율', '이론 비율'))
    for x in (2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 9.0, 15.0, 25.0, 50.0):
        th = mdf_theory(x)
        print('%-8.1f %9.3f %10.3f %10.3f %10.3f'
              % (x, _orig_mdf(x), th, _orig_mdf(x)/t3, th/mdf_theory(3.0)))
    print('\n표는 6bb 에서 포화한다 — 6bb 와 50bb 가 같은 값이다.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=3000)
    ap.add_argument('--seed', type=int, default=20260914)
    ap.add_argument('--table', action='store_true')
    a = ap.parse_args()
    if a.table:
        return show_table()

    rng = random.Random(a.seed)
    q = 0.78
    acts = {k: Counter() for k in ('M0 현재', 'M1 제거', 'M2 이론')}
    by_band = defaultdict(lambda: defaultdict(Counter))
    flip = Counter(); nb = Counter()
    tot_by_band = Counter()

    for i in range(a.n):
        d = DECK[:]; rng.shuffle(d)
        hand = d[:2]; op = rng.choice(OPENERS)
        # 아카이브 실측 분포에 맞춘다 (REVIEW_2/TRACE_DEFEND): 대부분 2~3bb,
        # 24% 가 6bb 초과다
        u = rng.random()
        obb = (rng.choice([2.0, 2.2, 2.5, 2.5, 3.0]) if u < 0.72
               else rng.uniform(3.0, 6.0) if u < 0.76
               else rng.uniform(6.0, 12.0) if u < 0.84
               else rng.uniform(12.0, 45.0))
        st = rng.choice([20, 25, 35, 50, 80, 120])
        prof = PS.make_player(rng, q, i)
        s = rng.randrange(1 << 30)
        bd = band(obb)
        res = {}
        for name, fn in (('M0 현재', _orig_mdf), ('M1 제거', mdf_none),
                         ('M2 이론', mdf_theory)):
            G.mdf = fn
            try:
                res[name] = pf.defend_decision(prof, 'BB', op, hand, 100.0, obb, 0,
                                               random.Random(s), raise_level=1,
                                               stack_bb=st)[0]
            except Exception:
                res = None; break
            finally:
                G.mdf = _orig_mdf
        if not res:
            continue
        tot_by_band[bd] += 1
        for k, v in res.items():
            acts[k][v] += 1
            by_band[bd][k][v] += 1
        if res['M0 현재'] != res['M2 이론']:
            flip['M2'] += 1; nb[bd] += 1
        if res['M0 현재'] != res['M1 제거']:
            flip['M1'] += 1

    n = max(1, sum(acts['M0 현재'].values()))
    print('# gto.mdf 반사실 — BB 디펜스 %d회\n' % n)
    print('%-10s %8s %8s %8s %8s' % ('변종', '폴드', '콜', '3벳', '쇼브'))
    for k in ('M0 현재', 'M1 제거', 'M2 이론'):
        c = acts[k]
        print('%-10s %7.1f%% %7.1f%% %7.1f%% %7.1f%%'
              % (k, 100*c['fold']/n, 100*c['call']/n, 100*c['3bet']/n, 100*c['shove']/n))
    print()
    print('M0 대비 행동이 바뀐 상황:  M1 제거 %.1f%%   M2 이론 %.1f%%'
          % (100*flip['M1']/n, 100*flip['M2']/n))
    print()
    print('오픈 크기대별 방어율 (M0 / M1 / M2)  — M2 와의 차이가 핵심')
    print('%-10s %7s %10s %10s %10s %10s' %
          ('구간', 'n', 'M0', 'M1', 'M2', 'M0−M2'))
    for bd in ('≤3bb', '3~6bb', '6~12bb', '>12bb'):
        t = tot_by_band[bd]
        if not t: continue
        d = lambda k: 100*(t - by_band[bd][k]['fold'])/t
        print('%-10s %7d %9.1f%% %9.1f%% %9.1f%% %+9.1f%%p'
              % (bd, t, d('M0 현재'), d('M1 제거'), d('M2 이론'),
                 d('M0 현재') - d('M2 이론')))
    print()
    print('M2 로 바뀐 상황의 구간 분포:', dict(nb))


if __name__ == '__main__':
    main()
