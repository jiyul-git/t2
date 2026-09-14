#!/usr/bin/env python3
"""반사실 evaluator — 성향을 바꾸면 계획 라벨이 실제로 뒤집히는가.

  python3 tools/cf_profile.py --n 400
  python3 tools/cf_profile.py --n 400 --reads        상대 읽기가 있는 조건
  python3 tools/cf_profile.py --n 400 --street turn
  python3 tools/cf_profile.py --n 200 --axes aggression,bluff,potcontrol

**읽기 전용이다.** plan.py 를 수정하지 않는다. make_plan 을 그대로 부른다.

방법
  같은 상황·같은 seed 로 make_plan 을 두 번 부른다. 한 번은 축을 1.0 으로,
  한 번은 9.0 으로 놓고. 라벨이 달라지면 그 축이 그 상황에서 계획을
  뒤집은 것이다. 상관분석보다 강한 증거다 — 상황이 완전히 통제된다.

**위약 축(placebo)이 반드시 필요하다.**
  make_plan 은 `sk(...) >= 1 and rng.random() < p` 처럼 단축평가를 쓴다.
  게이트가 막히면 rng.random() 이 호출되지 않아 **난수 스트림이 어긋난다.**
  그러면 축과 무관한 이유로도 라벨이 바뀐다. plan.py 가 한 번도 읽지 않는
  축(tilt_swing, tilt_stack)을 같이 돌려 그 바닥값을 잰다.
  **어떤 축의 뒤집힘 비율은 위약보다 유의하게 높아야 의미가 있다.**

한계
  - 상황은 합성이다. 실제 대국의 상황 분포와 정확히 같지 않다.
    사다리 칸 분포를 같이 찍으니 아카이브(REVIEW_2.md 2절)와 대조할 것.
  - 라벨이 안 바뀌어도 사이즈·빈도는 바뀔 수 있다. 여기서 재는 것은
    **라벨** 하나다.
"""
import argparse, itertools, os, random, sys
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, plan as PL, persona as PS

RANKS = '23456789TJQKA'
SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]

# plan.py 가 한 번도 읽지 않는 축. 스트림 어긋남의 바닥값을 잰다.
PLACEBO = ['tilt_swing', 'tilt_stack']

DEFAULT_AXES = ['aggression', 'looseness', 'discipline', 'gamble',
                'bluff', 'semibluff', 'potcontrol', 'trap', 'range_merge',
                'stackoff', 'blocker', 'spr', 'board_texture', 'icm']

BOARD_N = {'flop': 3, 'turn': 4, 'river': 5}


def perturb(prof, axis, val):
    """축 하나만 바꾼 사본. temper/concepts 어느 쪽이든 찾아서 바꾸고
    derive 를 다시 돌린다 (aggr/bluff/type 등 파생값이 따라가야 한다)."""
    p = {'concepts': dict(prof['concepts']), 'temper': dict(prof['temper']),
         'latent': dict(prof.get('latent') or {}), 'id': prof.get('id')}
    if axis in p['temper']:
        p['temper'][axis] = float(val)
    elif axis in p['concepts']:
        p['concepts'][axis] = float(val)
    else:
        raise KeyError('그런 축이 없다: %s' % axis)
    p.update(PS.derive(p))
    return p


def situation(rng, street):
    """합성 상황 하나. 실제 엔진의 인자 모양을 그대로 맞춘다."""
    d = DECK[:]
    rng.shuffle(d)
    hero = d[:2]
    board = d[2:2+BOARD_N[street]]
    dead = hero + board
    opp_pct = rng.uniform(0.15, 0.45)
    my_pct = rng.uniform(0.15, 0.40)
    opp_range = bot.range_combos(opp_pct, dead)
    my_range = bot.range_combos(my_pct, dead)
    pot = rng.choice([300, 600, 1200, 2400, 5000, 9000])
    s = rng.choice([1.0, 1.8, 3.0, 5.0, 8.0, 14.0, 22.0])
    n_opp = 1 if rng.random() < 0.72 else (2 if rng.random() < 0.85 else 3)
    return dict(hero=hero, board=board, my_range=my_range, opp_range=opp_range,
                pot=pot, stack=int(pot*s), street=street, n_opp=n_opp,
                to_act_behind=rng.choice([0, 0, 1, 2]),
                oop=rng.random() < 0.5, initiative=rng.random() < 0.7,
                opp_stack_bb=rng.choice([20, 35, 60, 100]),
                bb_chips=max(1, pot//6))


def fake_read(rng):
    """상대 읽기가 쌓인 조건. read_opponent 가 쓰는 키만 채운다."""
    ftb = rng.uniform(0.30, 0.75)
    return {'confidence': rng.uniform(0.4, 0.9), 'n': rng.randint(15, 60),
            'ftb': ftb, 'fold': ftb, 'bluff': rng.uniform(2.0, 8.0),
            'aggr': rng.uniform(2.0, 8.0),
            'ftb_flop': ftb, 'ftb_turn': ftb, 'ftb_river': ftb,
            'sizing_tell': rng.uniform(1.0, 9.0),
            'range_read': rng.uniform(1.0, 9.0), 'type': None}


def run(n, street, use_reads, axes, lo, hi, seed):
    rng = random.Random(seed)
    q = 0.78
    axes = axes + PLACEBO
    flips = Counter(); trans = defaultdict(Counter); base_labels = Counter()
    done = 0
    for i in range(n):
        sit = situation(rng, street)
        prof = PS.make_player(rng, q, i)
        est = fake_read(rng) if use_reads else None
        s = rng.randrange(1 << 30)
        common = dict(sit, seed=s, opp_est=est)
        try:
            base = PL.make_plan(profile=prof, **common)['plan']
        except Exception:
            continue
        base_labels[base] += 1
        done += 1
        for ax in axes:
            try:
                a = PL.make_plan(profile=perturb(prof, ax, lo), **common)['plan']
                b = PL.make_plan(profile=perturb(prof, ax, hi), **common)['plan']
            except Exception:
                continue
            if a != b:
                flips[ax] += 1
                trans[ax]['%s → %s' % (a, b)] += 1
    return done, flips, trans, base_labels, axes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--street', default='flop', choices=list(BOARD_N))
    ap.add_argument('--reads', action='store_true', help='상대 읽기가 쌓인 조건')
    ap.add_argument('--axes', default=','.join(DEFAULT_AXES))
    ap.add_argument('--lo', type=float, default=1.0)
    ap.add_argument('--hi', type=float, default=9.0)
    ap.add_argument('--seed', type=int, default=20260914)
    a = ap.parse_args()
    axes = [x.strip() for x in a.axes.split(',') if x.strip()]
    done, flips, trans, base, used = run(a.n, a.street, a.reads, axes,
                                         a.lo, a.hi, a.seed)
    print('# 반사실 — %s, 상황 %d개, 축을 %.0f ↔ %.0f 로'
          % (a.street, done, a.lo, a.hi))
    print('# 상대 읽기: %s\n' % ('있음' if a.reads else '없음'))

    pl = max((flips[x] for x in PLACEBO), default=0)
    plr = 100*pl/max(1, done)
    print('%-16s %7s %8s   %s' % ('축', '뒤집힘', '비율', '가장 흔한 전환'))
    for ax in sorted(used, key=lambda x: -flips[x]):
        v = flips[ax]; r = 100*v/max(1, done)
        tag = '위약' if ax in PLACEBO else (
              '●' if r >= plr*2 and r >= 5 else ('△' if r > plr else '○'))
        top = trans[ax].most_common(1)
        print('%-16s %7d %7.1f%%  %-4s %s' % (
            ax, v, r, tag, ('%s ×%d' % top[0] if top else '')))
    print('\n위약 바닥값 %.1f%% — 이보다 높아야 의미가 있다.' % plr)
    print('● 위약의 2배 이상이고 5%% 이상   △ 위약보다 높음   ○ 위약 이하')

    print('\n기준 계획 분포 (합성 상황이 실제와 비슷한지 대조용)')
    for k, v in base.most_common():
        print("  %-16s %5d %6.1f%%" % (k, v, 100*v/max(1, done)))


if __name__ == '__main__':
    main()
