#!/usr/bin/env python3
"""`need` 경로의 두 의심점이 실제 행동을 얼마나 바꾸는가. **읽기 전용이다.**

  python3 tools/cf_needpath.py --n 400                  플랍
  python3 tools/cf_needpath.py --n 400 --street river

**plan.py 를 고치지 않는다.** 대신 실행 중인 소스에서 문제 블록만 뺀
변종 함수를 메모리에 만들어(`inspect.getsource` → 문자열 제거 → `exec`)
호출부 `act_with_plan` 의 전역 조회에 잠시 끼워 넣는다. 디스크의 plan.py 는
그대로이고, 측정이 끝나면 원래 함수로 되돌린다. 소스에서 파생하므로
재구현 표류가 없다 — plan.py 가 바뀌면 여기도 자동으로 따라간다.

A. `need` 덮어쓰기 (plan.py:668-671)
     need *= call_bias(...)
     if abs(_sz_seen - _sz_true) > 1e-9:
         need = (_sz_seen*_p0)/max(1.0, _p0 + 2*_sz_seen*_p0)    # ← 대입
   이 세 줄을 뺀 변종과 비교한다.

B. `station`/`bluff_fear` 이중 적용
   `calldown_need` 의 `call_bias` 와 `decide_response` 마지막 블록이
   같은 계수(0.22, 0.30)를 두 번 곱한다. 뒤쪽(=decide_response) 한 번을
   뺀 변종과 비교한다.

상황·프로필·seed 는 세 조건이 완전히 같다.
"""
import argparse, copy, inspect, os, random, sys, textwrap
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, plan as PL, persona as PS

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
BOARD_N = {'flop': 3, 'turn': 4, 'river': 5}

OVERWRITE = """        # 오독한 사이즈로 팟오즈를 다시 계산한다 (인식이 곧 판단 근거다)
        if abs(_sz_seen - _sz_true) > 1e-9:
            _p0 = float(pot) - tocall
            need = (_sz_seen*_p0)/max(1.0, _p0 + 2*_sz_seen*_p0)
"""

# C: 팟오즈 식 자체를 교과서식으로 바꾸고 덮어쓰기는 뺀다.
#    need_true = tocall/pot_live 는 분모에서 **내 콜**을 뺐다.
#    교과서: 필요승률 = tocall/(벳전팟 + 상대벳 + 내콜) = tocall/(pot_live + tocall)
#    덮어쓰기식 sz/(1+2sz) 가 바로 그 값이다.
POTODDS_OLD = "    need_true = (tocall*bf)/max(1.0, float(pot))\n"
POTODDS_NEW = "    need_true = (tocall*bf)/max(1.0, float(pot) + float(tocall))\n"

DOUBLE = """    if has_c:
        sz = tocall/max(1.0, float(pot) - tocall)
        # 스테이션: 문턱을 낮춰 넓게 콜한다.
        need_seen *= max(0.55, 1.0 - 0.22*max(0.0, PS.bias(profile, 'station')))
        # 블러프 공포: 큰 벳일수록, 후반 스트리트일수록 문턱을 올린다.
        _bf_w = min(1.0, sz/0.9) * (1.0 if street == 'river' else 0.65)
        need_seen *= 1.0 + 0.30*max(0.0, PS.bias(profile, 'bluff_fear'))*_bf_w
        # 히어로콜: 가볍게 받아준다. 큰 벳에서 더 크게 작동한다.
        need_seen *= max(0.60, 1.0 - 0.18*max(0.0, PS.bias(profile, 'hero_call'))*_bf_w)
        need_seen = max(0.02, min(0.97, need_seen))
"""


def variant(fn, remove, new_name, swap=None):
    """실행 중인 소스에서 한 블록만 빼고 다시 컴파일한다.
    plan 모듈의 전역을 그대로 쓰므로 안의 이름 해석이 원본과 같다."""
    src = inspect.getsource(fn)
    if remove not in src:
        raise SystemExit('대상 블록을 못 찾았다 — plan.py 가 바뀌었다면 '
                         'cf_needpath.py 의 상수를 맞춰야 한다: %s' % new_name)
    src = src.replace(remove, '')
    if swap:
        old, new = swap
        if old not in src:
            raise SystemExit('교체 대상을 못 찾았다: %s' % new_name)
        src = src.replace(old, new)
    src = src.replace('def %s(' % fn.__name__, 'def %s(' % new_name, 1)
    ns = PL.__dict__
    exec(compile(textwrap.dedent(src), '<변종:%s>' % new_name, 'exec'), ns)
    return ns[new_name]


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
    ap.add_argument('--seed', type=int, default=20260914)
    ap.add_argument('--dump', type=int, default=0,
                    help='C 에서 뒤집힌 상황을 이 개수만큼 표로 찍는다')
    a = ap.parse_args()

    noov = variant(PL.calldown_need, OVERWRITE, 'calldown_need_noov')
    fixed = variant(PL.calldown_need, OVERWRITE, 'calldown_need_fixed',
                    swap=(POTODDS_OLD, POTODDS_NEW))
    single = variant(PL.decide_response, DOUBLE, 'decide_response_single')
    orig_cn, orig_dr = PL.calldown_need, PL.decide_response

    rng = random.Random(a.seed)
    q = 0.78
    acts = {k: Counter() for k in ('현재', 'A 덮어쓰기 없음', 'B 편향 한 번',
                                   'C 팟오즈 교정 + 성향 보존')}
    flip = Counter(); trans = defaultdict(Counter); by_plan = defaultdict(Counter)
    need_gap = []
    done = 0
    hi_station = {'n': 0, 'flipB': 0}
    rowsC = []

    for i in range(a.n):
        sit = situation(rng, a.street)
        prof = PS.make_player(rng, q, i)
        est = fake_read(rng)                 # 덮어쓰기는 opp_est 가 있어야 발동한다
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
                opp_range=sit['opp_range'], seed=s, n_opp=1,
                to_act_behind=sit['to_act_behind'], opp_est=est, read=rv)
            return act, need, _eq

        try:
            PL.calldown_need, PL.decide_response = orig_cn, orig_dr
            base, need0, _eqv = run()
            PL.calldown_need = noov
            av, needA, _ = run()
            PL.calldown_need = fixed
            cv, needC, _ = run()
            PL.calldown_need = orig_cn
            PL.decide_response = single
            bv, _, _ = run()
        except Exception:
            continue
        finally:
            PL.calldown_need, PL.decide_response = orig_cn, orig_dr

        # --- C 뒤집힘 분해용 중간값. persona 함수는 순수라 바깥에서 같은 값이 나온다 ---
        _sz_true = sit['tocall']/max(1.0, float(sit['pot']) - sit['tocall'])
        _rd = PS.read_opponent(prof, est)
        _sz_norm = PS.opp_size_norm(_rd, _sz_true, sit['street'])
        _sz_seen = PS.size_read(prof, _sz_norm)
        _made = bot.made_strength(sit['hero'], sit['board'])
        _draw = bot.draw_strength(sit['hero'], sit['board'])
        _cb = PS.call_bias(prof, sit['street'], _sz_seen, _made, _draw)
        _nt_old = sit['tocall']/max(1.0, float(sit['pot']))
        _nt_new = sit['tocall']/max(1.0, float(sit['pot']) + float(sit['tocall']))

        done += 1
        acts['현재'][base] += 1
        acts['A 덮어쓰기 없음'][av] += 1
        acts['B 편향 한 번'][bv] += 1
        acts['C 팟오즈 교정 + 성향 보존'][cv] += 1
        if base != cv:
            flip['C'] += 1; trans['C']['%s → %s' % (base, cv)] += 1
            by_plan['C'][ps['plan']] += 1
            rowsC.append(dict(street=sit['street'], plan=ps['plan'],
                              pot=sit['pot'], tocall=sit['tocall'],
                              sz=_sz_true, sz_seen=_sz_seen, cb=_cb,
                              nt_old=_nt_old, nt_new=_nt_new,
                              need0=need0, needC=needC, eq=_eqv,
                              fired=abs(_sz_seen - _sz_true) > 1e-9,
                              a0=base, aC=cv))
        if need0 is not None and needA is not None:
            need_gap.append(abs(needA - need0))
        if base != av:
            flip['A'] += 1; trans['A']['%s → %s' % (base, av)] += 1
            by_plan['A'][ps['plan']] += 1
        st_b = PS.bias(prof, 'station')
        if st_b > 0.3:
            hi_station['n'] += 1
            if base != bv: hi_station['flipB'] += 1
        if base != bv:
            flip['B'] += 1; trans['B']['%s → %s' % (base, bv)] += 1
            by_plan['B'][ps['plan']] += 1

    import statistics as ST
    print('# need 경로 반사실 — %s, 상황 %d개 (상대 추정치·리딩 모두 있음)\n'
          % (a.street, done))
    print('%-18s %8s %8s %8s' % ('조건', '폴드', '콜', '레이즈'))
    for k in ('현재', 'A 덮어쓰기 없음', 'B 편향 한 번', 'C 팟오즈 교정 + 성향 보존'):
        c = acts[k]; n = max(1, sum(c.values()))
        print('%-18s %7.1f%% %7.1f%% %7.1f%%'
              % (k, 100*c['fold']/n, 100*c['call']/n, 100*c['raise']/n))
    print()
    for k, name in (('A', 'A  need 덮어쓰기를 빼면'),
                    ('B', 'B  편향을 한 번만 적용하면'),
                    ('C', 'C  팟오즈를 고치고 성향을 보존하면')):
        v = flip[k]
        print('%-28s 행동이 바뀐 상황 %d / %d  = %.1f%%'
              % (name, v, done, 100*v/max(1, done)))
        if trans[k]:
            print('%-28s %s' % ('', '  '.join('%s ×%d' % t
                                              for t in trans[k].most_common(4))))
        if by_plan[k]:
            print('%-28s 계획별: %s' % ('', '  '.join('%s %d' % t
                                                     for t in by_plan[k].most_common(5))))
        print()
    if need_gap:
        need_gap.sort()
        print('A: need 자체가 얼마나 달라지나  중앙 %.3f  95%% %.3f  최대 %.3f'
              % (ST.median(need_gap), need_gap[int(len(need_gap)*.95)], need_gap[-1]))
    if rowsC:
        print()
        print('=== C 뒤집힘 분해 (%d건) ===' % len(rowsC))
        f2c = [r for r in rowsC if r['a0'] == 'fold' and r['aC'] == 'call']
        c2f = [r for r in rowsC if r['a0'] == 'call' and r['aC'] == 'fold']
        # 핵심 검증: call_bias 가 뒤집힘 방향을 예측하는가
        # call_bias < 1 = 넓게 콜하는 사람, > 1 = 과잉 폴드하는 사람
        def share(rs):
            if not rs: return '-'
            lo = sum(1 for r in rs if r['cb'] < 1.0)
            return '%d/%d (%.0f%%)' % (lo, len(rs), 100*lo/len(rs))
        print('  call_bias < 1 (넓게 콜하는 성향) 의 비율')
        print('    폴드 → 콜 로 뒤집힌 건  %s' % share(f2c))
        print('    콜 → 폴드 로 뒤집힌 건  %s' % share(c2f))
        allr = [r for r in rowsC if r['cb'] is not None]
        base_lo = sum(1 for r in allr if r['cb'] < 1.0)
        print('    (뒤집힌 전체에서는 %d/%d = %.0f%%)'
              % (base_lo, len(allr), 100*base_lo/max(1, len(allr))))
        # 덮어쓰기가 발동했는가로 가른다. 발동했으면 C 의 차이는 '체인 복원',
        # 안 했으면 '산수 교정' 이다. 둘은 성격이 다르다.
        fr = [r for r in rowsC if r['fired']]
        nf = [r for r in rowsC if not r['fired']]
        print()
        print('  덮어쓰기가 발동했던 상황  %d건 (%.0f%%)  → C 의 차이 = 체인 복원'
              % (len(fr), 100*len(fr)/max(1, len(rowsC))))
        print('  발동 안 했던 상황        %d건 (%.0f%%)  → C 의 차이 = 산수 교정'
              % (len(nf), 100*len(nf)/max(1, len(rowsC))))
        for nm, rs in (('  체인 복원', fr), ('  산수 교정', nf)):
            if not rs: continue
            _f2c = sum(1 for r in rs if r['a0'] == 'fold' and r['aC'] == 'call')
            _c2f = sum(1 for r in rs if r['a0'] == 'call' and r['aC'] == 'fold')
            _d = sum((r['needC'] or 0) - (r['need0'] or 0) for r in rs)/len(rs)
            print('%-12s 폴드→콜 %2d  콜→폴드 %2d   need 평균 변화 %+.3f'
                  % (nm, _f2c, _c2f, _d))
        print()
        print('  %-14s %8s %8s %8s %8s %8s %8s' %
              ('', 'sz', 'sz_seen', 'call_bias', 'need 현재', 'need C', 'eq'))
        for name, rs in (('폴드 → 콜', f2c), ('콜 → 폴드', c2f)):
            if not rs: continue
            g = lambda k: sum(r[k] for r in rs if r[k] is not None)/max(1, len(rs))
            print('  %-14s %8.2f %8.2f %8.2f %8.3f %8.3f %8.3f'
                  % (name + ' 평균', g('sz'), g('sz_seen'), g('cb'),
                     g('need0'), g('needC'), g('eq')))
        if a.dump:
            print()
            print('  %-6s %-14s %6s %6s %6s %7s %7s %7s %7s %6s %6s' %
                  ('스트','계획','sz','seen','c_bias','nt_old','nt_new','need0','needC','eq','전환'))
            for r in rowsC[:a.dump]:
                print('  %-6s %-14s %6.2f %6.2f %6.2f %7.3f %7.3f %7.3f %7.3f %6.3f  %s→%s'
                      % (r['street'], r['plan'], r['sz'], r['sz_seen'], r['cb'],
                         r['nt_old'], r['nt_new'], r['need0'] or 0, r['needC'] or 0,
                         r['eq'] or 0, r['a0'], r['aC']))
        print()
        print('  주의: 이 조건은 bf(버블팩터) = 1.0 고정이다. ICM 은 들어가지 않았다.')
    if hi_station['n']:
        print('B: station 편향 0.3 초과인 %d명만 보면 행동 변화 %.1f%%'
              % (hi_station['n'], 100*hi_station['flipB']/hi_station['n']))


if __name__ == '__main__':
    main()
