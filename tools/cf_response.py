#!/usr/bin/env python3
"""응답 반사실 — 상대 벳에 직면했을 때 성향이 폴드/콜/레이즈를 바꾸는가.

  python3 tools/cf_response.py --n 300
  python3 tools/cf_response.py --n 300 --street turn
  python3 tools/cf_response.py --n 300 --reads

**읽기 전용이다.** plan.py 를 수정하지 않는다.

방법
  1) 기준 프로필로 make_plan 을 돌려 plan_state 를 만든다. **이걸 고정한다.**
     계획 라벨이 바뀌면 응답 차이인지 계획 차이인지 섞인다.
  2) 축 하나만 1.0 ↔ 9.0 으로 바꾼 프로필로 act_with_plan 을 부른다.
     act_with_plan 이 실제 호출부다 — eq(perceived_range)·need(calldown_need)·
     decide_response 를 전부 거치므로 재구성 오차가 없다.
  3) 최종 액션(fold/call/raise)이 달라지면 그 축이 응답을 뒤집은 것이다.

  plan_state 는 호출마다 깊은 사본을 준다 (act_with_plan 이 변형한다).

위약 축(tilt_swing/tilt_stack)으로 난수 스트림 어긋남의 바닥값을 잰다.
"""
import argparse, copy, os, random, sys
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, plan as PL, persona as PS

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
PLACEBO = ['tilt_swing', 'tilt_stack']
DEFAULT_AXES = ['aggression', 'discipline', 'looseness', 'gamble',
                'bluff', 'reraise', 'semibluff', 'potodds', 'outs',
                'bluffcatch_river', 'range_read', 'sizing_tell',
                'stackoff', 'icm', 'potcontrol']
BOARD_N = {'flop': 3, 'turn': 4, 'river': 5}


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
            'range_read': rng.uniform(1, 9), 'sz_mean': rng.uniform(0.4, 0.9),
            'type': None}


def situation(rng, street):
    d = DECK[:]; rng.shuffle(d)
    hero = d[:2]; board = d[2:2+BOARD_N[street]]
    dead = hero + board
    opp_range = bot.range_combos(rng.uniform(0.15, 0.45), dead)
    my_range = bot.range_combos(rng.uniform(0.15, 0.40), dead)
    pot = rng.choice([600, 1200, 2400, 5000, 9000])
    # 상대가 팟의 40~110% 를 쳤다. pot 은 그 벳이 포함된 값이다(호출부 규약).
    frac = rng.choice([0.40, 0.55, 0.66, 0.75, 1.0, 1.1])
    tocall = int(pot*frac)
    pot_live = pot + tocall
    stack = int(pot * rng.choice([1.0, 2.0, 3.5, 6.0, 12.0]))
    return dict(hero=hero, board=board, my_range=my_range, opp_range=opp_range,
                pot=pot_live, tocall=tocall, stack=stack, street=street,
                n_opp=1, to_act_behind=rng.choice([0, 0, 1]),
                oop=rng.random() < 0.5, initiative=rng.random() < 0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--street', default='flop', choices=list(BOARD_N))
    ap.add_argument('--reads', action='store_true')
    ap.add_argument('--read', action='store_true',
                    help='배팅라인 리딩(read_val)을 같이 넘긴다. 이게 없으면 '
                         'calldown_need 의 trust 블록(range_read/bluffcatch/'
                         'sizing_tell)이 통째로 꺼진다.')
    ap.add_argument('--axes', default=','.join(DEFAULT_AXES))
    ap.add_argument('--lo', type=float, default=1.0)
    ap.add_argument('--hi', type=float, default=9.0)
    ap.add_argument('--seed', type=int, default=20260914)
    a = ap.parse_args()
    axes = [x.strip() for x in a.axes.split(',') if x.strip()] + PLACEBO
    rng = random.Random(a.seed)
    q = 0.78
    flips = Counter(); trans = defaultdict(Counter)
    lo_fold = Counter(); hi_fold = Counter()
    lo_raise = Counter(); hi_raise = Counter()
    base_act = Counter(); base_plan = Counter(); done = 0
    by_plan = defaultdict(Counter)

    for i in range(a.n):
        sit = situation(rng, a.street)
        prof = PS.make_player(rng, q, i)
        est = fake_read(rng) if a.reads else None
        # session.py:501 의 read_val — line_bluff_prior 가 내는 0~1 스칼라
        rv = rng.uniform(0.10, 0.70) if a.read else None
        s = rng.randrange(1 << 30)
        try:
            ps = PL.make_plan(sit['hero'], sit['board'], sit['my_range'],
                              sit['opp_range'], prof, sit['pot'], sit['stack'],
                              sit['street'], seed=s, n_opp=1,
                              to_act_behind=sit['to_act_behind'],
                              oop_vs_aggr=sit['oop'], initiative=sit['initiative'],
                              opp_est=est)
        except Exception:
            continue

        def run(p):
            (act, _amt), _eq, _need = PL.act_with_plan(
                sit['hero'], sit['board'], p, copy.deepcopy(ps),
                sit['pot'], sit['tocall'], sit['stack'], sit['street'],
                initiative=sit['initiative'],
                opp_range=sit['opp_range'], seed=s, n_opp=1,
                to_act_behind=sit['to_act_behind'], opp_est=est, read=rv)
            return act

        try:
            b = run(prof)
        except Exception:
            continue
        base_act[b] += 1; base_plan[ps['plan']] += 1; done += 1
        for ax in axes:
            try:
                x = run(perturb(prof, ax, a.lo))
                y = run(perturb(prof, ax, a.hi))
            except Exception:
                continue
            if x == 'fold': lo_fold[ax] += 1
            if y == 'fold': hi_fold[ax] += 1
            if x == 'raise': lo_raise[ax] += 1
            if y == 'raise': hi_raise[ax] += 1
            if x != y:
                flips[ax] += 1
                trans[ax]['%s → %s' % (x, y)] += 1
                by_plan[ax][ps['plan']] += 1

    print('# 응답 반사실 — %s, 상황 %d개, 축을 %.0f ↔ %.0f 로'
          % (a.street, done, a.lo, a.hi))
    print('# 상대 추정 opp_est: %s   배팅라인 리딩 read: %s   (계획 라벨은 고정)\n'
          % ('있음' if a.reads else '없음', '있음' if a.read else '없음'))
    pl = max((flips[x] for x in PLACEBO), default=0)
    plr = 100*pl/max(1, done)
    print('%-18s %7s %8s %9s %9s  %s'
          % ('축', '뒤집힘', '비율', '폴드율차', '레이즈율차', '가장 흔한 전환'))
    for ax in sorted(axes, key=lambda x: -flips[x]):
        v = flips[ax]; r = 100*v/max(1, done)
        df = 100*(hi_fold[ax]-lo_fold[ax])/max(1, done)
        dr = 100*(hi_raise[ax]-lo_raise[ax])/max(1, done)
        tag = '위약' if ax in PLACEBO else (
              '●' if r >= plr*2 and r >= 5 else ('△' if r > plr else '○'))
        top = trans[ax].most_common(1)
        print('%-18s %7d %7.1f%% %+8.1f%%p %+8.1f%%p %-4s %s'
              % (ax, v, r, df, dr, tag, ('%s ×%d' % top[0] if top else '')))
    print('\n위약 바닥값 %.1f%%' % plr)
    print('폴드율차/레이즈율차 = (축 9일 때) − (축 1일 때). 부호가 방향이다.')
    print('\n기준 행동 / 계획 분포')
    for k, v in base_act.most_common():
        print('  %-8s %5d %6.1f%%' % (k, v, 100*v/max(1, done)))
    print('  계획: ' + '  '.join('%s %d' % (k, v) for k, v in base_plan.most_common(6)))
    top_ax = [x for x in sorted(axes, key=lambda x: -flips[x]) if x not in PLACEBO][:3]
    print('\n뒤집힘이 어느 계획에서 나왔나 (상위 3축)')
    for ax in top_ax:
        if not by_plan[ax]: continue
        print('  %-18s %s' % (ax, '  '.join('%s %d' % kv for kv in by_plan[ax].most_common(5))))


if __name__ == '__main__':
    main()
