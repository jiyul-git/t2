#!/usr/bin/env python3
"""BB 방어 반사실 — 성향을 바꾸면 폴드/콜/3벳이 뒤집히는가. **읽기 전용이다.**

  python3 tools/cf_defend.py --n 3000
  python3 tools/cf_defend.py --n 3000 --reads
  python3 tools/cf_defend.py --gto            기준 폭(gto.defend_pct)만 찍는다

cf_profile.py 와 같은 방법이다. 같은 핸드·같은 오픈·같은 스택·같은 seed 로
preflop.defend_decision 을 두 번 부른다. 축 하나만 1.0 ↔ 9.0 으로 놓고.

위약 축(plan/preflop 이 안 읽는 tilt_swing/tilt_stack)을 같이 돌려
난수 스트림 어긋남의 바닥값을 잰다.
"""
import argparse, math, os, random, sys
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import preflop as pf, persona as PS, gto as G

RANKS = '23456789TJQKA'
SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
PLACEBO = ['tilt_swing', 'tilt_stack']
DEFAULT_AXES = ['pf_defend', 'looseness', 'aggression', 'pf_range',
                'potodds', 'discipline', 'gamble', 'thin_value', 'icm']
OPENERS = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB']


def perturb(prof, axis, val):
    p = {'concepts': dict(prof['concepts']), 'temper': dict(prof['temper']),
         'latent': dict(prof.get('latent') or {}), 'id': prof.get('id')}
    if axis in p['temper']: p['temper'][axis] = float(val)
    elif axis in p['concepts']: p['concepts'][axis] = float(val)
    else: raise KeyError(axis)
    p.update(PS.derive(p))
    return p


def fake_read(rng):
    ftb = rng.uniform(0.30, 0.75)
    return {'confidence': rng.uniform(0.4, 0.9), 'n': rng.randint(15, 60),
            'ftb': ftb, 'fold': ftb, 'bluff': rng.uniform(2, 8),
            'aggr': rng.uniform(2, 8), 'ftb_flop': ftb, 'ftb_turn': ftb,
            'ftb_river': ftb, 'sizing_tell': rng.uniform(1, 9),
            'range_read': rng.uniform(1, 9), 'type': None}


def situation(rng):
    d = DECK[:]
    rng.shuffle(d)
    # 실측 분포에 맞춘다 — 봇 오픈의 중앙이 2.5bb 였다 (REVIEW_2.md 8절)
    return dict(hand=d[:2], opener_pos=rng.choice(OPENERS),
                open_bb=rng.choice([2.0, 2.2, 2.5, 2.5, 2.5, 3.0]),
                stack_bb=rng.choice([20, 25, 35, 50, 80, 120]),
                n_callers=0 if rng.random() < 0.8 else 1)


def call_defend(prof, sit, est, seed, bb=100.0):
    return pf.defend_decision(
        prof, 'BB', sit['opener_pos'], sit['hand'], bb,
        sit['open_bb'], sit['n_callers'], random.Random(seed),
        raise_level=1, stack_bb=sit['stack_bb'], exploit=est)[0]


def show_gto():
    print('gto.defend_pct — BB 기준 폭 (성향 없음)\n')
    print('  %-8s %8s %8s %8s' % ('오프너', '2.0bb', '2.5bb', '3.0bb'))
    for op in OPENERS:
        print('  %-8s %7.1f%% %7.1f%% %7.1f%%' % (
            op, 100*G.defend_pct('BB', op, 8, 100.0, True, 2.0),
            100*G.defend_pct('BB', op, 8, 100.0, True, 2.5),
            100*G.defend_pct('BB', op, 8, 100.0, True, 3.0)))
    print('\n  이 값이 defend_thresholds 의 base_tot 다. 성향은 여기서')
    print('  **얼마나 벗어나는가**만 정한다 (아래 참조).')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=2000)
    ap.add_argument('--reads', action='store_true')
    ap.add_argument('--axes', default=','.join(DEFAULT_AXES))
    ap.add_argument('--lo', type=float, default=1.0)
    ap.add_argument('--hi', type=float, default=9.0)
    ap.add_argument('--seed', type=int, default=20260914)
    ap.add_argument('--gto', action='store_true')
    a = ap.parse_args()
    if a.gto: return show_gto()

    axes = [x.strip() for x in a.axes.split(',') if x.strip()] + PLACEBO
    rng = random.Random(a.seed)
    q = 0.78
    flips = Counter(); trans = defaultdict(Counter)
    base_act = Counter(); done = 0
    lo_def = Counter(); hi_def = Counter()     # 축별 lo/hi 에서의 방어율
    for i in range(a.n):
        sit = situation(rng)
        prof = PS.make_player(rng, q, i)
        est = fake_read(rng) if a.reads else None
        s = rng.randrange(1 << 30)
        try:
            b = call_defend(prof, sit, est, s)
        except Exception:
            continue
        base_act[b] += 1; done += 1
        for ax in axes:
            try:
                x = call_defend(perturb(prof, ax, a.lo), sit, est, s)
                y = call_defend(perturb(prof, ax, a.hi), sit, est, s)
            except Exception:
                continue
            if x != 'fold': lo_def[ax] += 1
            if y != 'fold': hi_def[ax] += 1
            if x != y:
                flips[ax] += 1
                trans[ax]['%s → %s' % (x, y)] += 1

    print('# BB 방어 반사실 — 상황 %d개, 축을 %.0f ↔ %.0f 로' % (done, a.lo, a.hi))
    print('# 상대 읽기: %s\n' % ('있음' if a.reads else '없음'))
    pl = max((flips[x] for x in PLACEBO), default=0)
    plr = 100*pl/max(1, done)
    print('%-14s %7s %8s %9s %9s %8s  %s'
          % ('축', '뒤집힘', '비율', '방어율(1)', '방어율(9)', '차이', '가장 흔한 전환'))
    for ax in sorted(axes, key=lambda x: -flips[x]):
        v = flips[ax]; r = 100*v/max(1, done)
        dl = 100*lo_def[ax]/max(1, done); dh = 100*hi_def[ax]/max(1, done)
        tag = '위약' if ax in PLACEBO else (
              '●' if r >= plr*2 and r >= 5 else ('△' if r > plr else '○'))
        top = trans[ax].most_common(1)
        print('%-14s %7d %7.1f%% %8.1f%% %8.1f%% %+7.1f%%p %-4s %s'
              % (ax, v, r, dl, dh, dh-dl, tag,
                 ('%s ×%d' % top[0] if top else '')))
    print('\n위약 바닥값 %.1f%% — 이보다 높아야 의미가 있다.' % plr)
    print('**방어율(1) / 방어율(9) 차이가 핵심이다.** 뒤집힘 비율이 높아도')
    print('방어율이 안 움직이면 그 축은 방향이 아니라 진폭만 바꾸는 것이다.')
    print('\n기준 행동 분포')
    for k, v in base_act.most_common():
        print('  %-8s %5d %6.1f%%' % (k, v, 100*v/max(1, done)))
    print('  → 방어율 %.1f%%' % (100*(done-base_act['fold'])/max(1, done)))


if __name__ == '__main__':
    main()
