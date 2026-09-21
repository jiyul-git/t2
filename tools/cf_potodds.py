#!/usr/bin/env python3
"""팟오즈 식 수정(FIX_PLAN 1-A)의 행동 영향. **읽기 전용이다.**

  python3 tools/cf_potodds.py --n 400 --street flop
  python3 tools/cf_potodds.py --n 400 --bf 2.2

현재 소스(수정본)에서 `need_true` 분모만 예전 식으로 되돌린 변종을
메모리에 만들어(`inspect.getsource` → 문자열 교체 → `exec`) 같은 상황·같은
seed 로 비교한다. plan.py 는 건드리지 않는다.

  현재 : need_true = (tocall*bf)/(pot + tocall)     ← 교과서
  예전 : need_true = (tocall*bf)/pot                ← 분모에 내 콜 빠짐

**`_sz_seen` 덮어쓰기(FIX_PLAN 2-A)는 양쪽 다 그대로 있다.** 이 측정은
팟오즈 식 하나만 가른다.

결정성 확인(위약에 해당): 같은 코드를 두 번 돌려 0.0% 가 나오는지 본다.
"""
import argparse, copy, inspect, os, random, sys, textwrap
from collections import Counter

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, plan as PL, persona as PS

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
BOARD_N = {'flop': 3, 'turn': 4, 'river': 5}

NEW = "    need_true = (tocall*bf)/max(1.0, float(pot) + float(tocall))\n"
OLD = "    need_true = (tocall*bf)/max(1.0, float(pot))\n"


def variant_old():
    src = inspect.getsource(PL.calldown_need)
    if NEW not in src:
        raise SystemExit('현재 소스에 수정본 식이 없다 — 1-A 가 적용됐는지 확인할 것')
    src = src.replace(NEW, OLD).replace('def calldown_need(', 'def calldown_need_old(', 1)
    ns = PL.__dict__
    exec(compile(textwrap.dedent(src), '<변종:old_potodds>', 'exec'), ns)
    return ns['calldown_need_old']


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
    pot = rng.choice([600, 1200, 2400, 5000, 9000])
    frac = rng.choice([0.40, 0.55, 0.66, 0.75, 1.0, 1.1])
    tocall = int(pot*frac)
    return dict(hero=hero, board=board,
                my_range=bot.range_combos(rng.uniform(0.15, 0.40), dead),
                opp_range=bot.range_combos(rng.uniform(0.15, 0.45), dead),
                pot=pot+tocall, tocall=tocall,
                stack=int(pot*rng.choice([1.0, 2.0, 3.5, 6.0, 12.0])),
                street=street, to_act_behind=rng.choice([0, 0, 1]),
                oop=rng.random() < 0.5, initiative=rng.random() < 0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--street', default='flop', choices=list(BOARD_N))
    ap.add_argument('--bf', type=float, default=1.0)
    ap.add_argument('--reads', action='store_true', default=True)
    ap.add_argument('--seed', type=int, default=20260914)
    a = ap.parse_args()
    old_fn = variant_old()
    cur_fn = PL.calldown_need
    rng = random.Random(a.seed)
    q = 0.78
    acts = {'현재(교과서)': Counter(), '예전(분모 부족)': Counter()}
    flip = Counter(); det = 0; done = 0
    needs = {'cur': [], 'old': []}
    ow_fired = 0

    for i in range(a.n):
        sit = situation(rng, a.street)
        prof = PS.make_player(rng, q, i)
        est = fake_read(rng) if a.reads else None
        rv = rng.uniform(0.10, 0.70)
        s = rng.randrange(1 << 30)
        try:
            ps = PL.make_plan(sit['hero'], sit['board'], sit['my_range'],
                              sit['opp_range'], prof, sit['pot'], sit['stack'],
                              sit['street'], seed=s, n_opp=1,
                              to_act_behind=sit['to_act_behind'],
                              oop=sit['oop'], initiative=sit['initiative'],
                              opp_est=est)
        except Exception:
            continue

        def run():
            (act, _), _eq, need = PL.act_with_plan(
                sit['hero'], sit['board'], prof, copy.deepcopy(ps),
                sit['pot'], sit['tocall'], sit['stack'], sit['street'],
                initiative=sit['initiative'],
                opp_range=sit['opp_range'], seed=s, n_opp=1, bf=a.bf,
                to_act_behind=sit['to_act_behind'], opp_est=est, read=rv)
            return act, need

        try:
            PL.calldown_need = cur_fn
            cur, ncur = run()
            det_a, _ = run()                       # 결정성 확인
            PL.calldown_need = old_fn
            old, nold = run()
        except Exception:
            continue
        finally:
            PL.calldown_need = cur_fn
        done += 1
        acts['현재(교과서)'][cur] += 1
        acts['예전(분모 부족)'][old] += 1
        if det_a != cur: det += 1
        if ncur is not None: needs['cur'].append(ncur)
        if nold is not None: needs['old'].append(nold)
        if cur != old:
            flip['총'] += 1
            flip['%s → %s' % (old, cur)] += 1
        # 덮어쓰기(2-A)가 걸렸는가 — 이 측정과 무관하게 여전히 존재한다
        _szt = sit['tocall']/max(1.0, float(sit['pot']) - sit['tocall'])
        _rd = PS.read_opponent(prof, est)
        if abs(PS.size_read(prof, PS.opp_size_norm(_rd, _szt, sit['street'])) - _szt) > 1e-9:
            ow_fired += 1

    import statistics as ST
    print('# 팟오즈 식 수정 — %s, 상황 %d개, bf=%.1f\n' % (a.street, done, a.bf))
    print('결정성 확인(같은 코드 두 번): 불일치 %d건  %s'
          % (det, '← 0 이어야 한다' if det == 0 else '← 문제!'))
    print()
    print('%-18s %8s %8s %8s' % ('', '폴드', '콜', '레이즈'))
    for k in ('예전(분모 부족)', '현재(교과서)'):
        c = acts[k]; n = max(1, sum(c.values()))
        print('%-18s %7.1f%% %7.1f%% %7.1f%%'
              % (k, 100*c['fold']/n, 100*c['call']/n, 100*c['raise']/n))
    d = acts['현재(교과서)']; o = acts['예전(분모 부족)']
    n = max(1, done)
    print('%-18s %+7.1f%%p %+7.1f%%p %+7.1f%%p'
          % ('차이', 100*(d['fold']-o['fold'])/n, 100*(d['call']-o['call'])/n,
             100*(d['raise']-o['raise'])/n))
    print()
    print('행동이 바뀐 상황 %d / %d = %.1f%%' % (flip['총'], done, 100*flip['총']/n))
    for k, v in flip.most_common():
        if k != '총': print('   %-22s %d' % (k, v))
    if needs['cur'] and needs['old']:
        print()
        print('need 중앙  예전 %.3f → 현재 %.3f  (%+.3f)'
              % (ST.median(needs['old']), ST.median(needs['cur']),
                 ST.median(needs['cur']) - ST.median(needs['old'])))
    print()
    print('참고: `_sz_seen` 덮어쓰기(FIX_PLAN 2-A)는 **양쪽 다 그대로 있다.**')
    print('      이 표본에서 발동한 비율 %.1f%% — 이 측정은 그것과 무관하게'
          % (100*ow_fired/n))
    print('      팟오즈 식 하나만 가른 것이다.')


if __name__ == '__main__':
    main()
