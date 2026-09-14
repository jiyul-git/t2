#!/usr/bin/env python3
"""`refresh` / `update_plan` 반사실 — 턴·리버 계획 갱신을 해부한다.

  python3 tools/cf_refresh.py --n 300

**읽기 전용이다.** plan.py 를 고치지 않는다. `refresh` 를 건너뛴 변종은
실행 중인 소스에서 그 호출만 뺀 `update_plan` 을 메모리에 만들어 쓴다.

네 가지를 잰다.
  1) 계획 변경률 — 플랍 계획이 턴·리버에서 얼마나 바뀌나, 어느 분기로
  2) 성향 반응  — 플랍 계획을 **고정**하고 축만 1↔9 로 바꿔 턴 갱신
  3) refresh 우회 — 갱신을 통째로 건너뛰면 계획이 얼마나 달라지나
  4) 성향 생존  — 플랍에서 갈렸던 계획이 턴 갱신 뒤에도 남아 있나
"""
import argparse, copy, inspect, os, random, sys, textwrap
from collections import Counter, defaultdict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, plan as PL, persona as PS

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
PLACEBO = ['tilt_swing', 'tilt_stack']
AXES = ['aggression', 'looseness', 'discipline', 'gamble', 'bluff',
        'semibluff', 'potcontrol', 'board_texture', 'range_read',
        'outs', 'trap', 'blockbet']

REFRESH_CALL = """        st = refresh(st, hero, board, opp_range, profile, pot, stack, street,
                     n_opp, seed=seed, opp_est=opp_est, my_range=my_range)
        if _first:
            st.setdefault('refreshed', []).append(street)
"""


def variant_no_refresh():
    src = inspect.getsource(PL.update_plan)
    if REFRESH_CALL not in src:
        raise SystemExit('refresh 호출 블록을 못 찾았다 — plan.py 가 바뀌었다')
    src = src.replace(REFRESH_CALL, "        pass\n")
    src = src.replace('def update_plan(', 'def update_plan_norefresh(', 1)
    ns = PL.__dict__
    exec(compile(textwrap.dedent(src), '<변종:no_refresh>', 'exec'), ns)
    return ns['update_plan_norefresh']


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--seed', type=int, default=20260914)
    a = ap.parse_args()
    norefresh = variant_no_refresh()
    axes = AXES + PLACEBO
    rng = random.Random(a.seed)
    q = 0.78

    chg = Counter(); why_hit = Counter(); done = 0
    flip = Counter(); trans = defaultdict(Counter)
    nr_diff = Counter()
    surv = {'split': 0, 'kept': 0}
    plans = defaultdict(Counter)

    for i in range(a.n):
        d = DECK[:]; rng.shuffle(d)
        hero = d[:2]; b3 = d[2:5]; b4 = d[2:6]; b5 = d[2:7]
        prof = PS.make_player(rng, q, i)
        est = fake_read(rng)
        pot = rng.choice([600, 1200, 2400, 5000])
        stack = int(pot*rng.choice([2.0, 3.5, 6.0, 12.0]))
        s = rng.randrange(1 << 30)

        # **난수는 여기서 한 번만 뽑는다.** up() 안에서 뽑으면 변종마다
        # 상황이 달라져 축과 무관한 차이가 생긴다 (실제로 위약이 5% 나왔다).
        my_p, opp_p = rng.uniform(0.15, 0.40), rng.uniform(0.15, 0.45)
        oop_, init_ = rng.random() < 0.5, rng.random() < 0.5
        RG = {}
        for _b in (b3, b4, b5):
            _dead = hero + _b
            RG[len(_b)] = (bot.range_combos(my_p, _dead),
                           bot.range_combos(opp_p, _dead))

        def up(state, board, street, prev, p, fn=None, first=False):
            mr, orr = RG[len(board)]
            return (fn or PL.update_plan)(
                copy.deepcopy(state) if state else None, hero, board, mr, orr, p,
                pot, stack, street, s, 1, 0, prev, oop_, init_,
                opp_est=est, opp_stack_bb=60, first=first, bb_chips=max(1, pot//6))

        try:
            pf_ = up(None, b3, 'flop', None, prof, first=True)
            pt = up(pf_, b4, 'turn', b3, prof)
            pr = up(pt, b5, 'river', b4, prof)
        except Exception:
            continue
        done += 1
        plans['flop'][pf_['plan']] += 1
        plans['turn'][pt['plan']] += 1
        plans['river'][pr['plan']] += 1
        if pf_['plan'] != pt['plan']: chg['flop→turn'] += 1
        if pt['plan'] != pr['plan']: chg['turn→river'] += 1
        if pf_['plan'] != pr['plan']: chg['flop≠river'] += 1
        for stt, ws in (pt.get('why_by_street') or {}).items():
            for w in ws:
                body = w.split(':', 1)[1].strip()
                why_hit[body.split('(')[0].split('→')[0].strip()[:34]] += 1

        # 3) refresh 우회
        try:
            pt_nr = up(pf_, b4, 'turn', b3, prof, fn=norefresh)
            if pt['plan'] != pt_nr['plan']:
                nr_diff['turn'] += 1
                nr_diff['%s → %s' % (pt_nr['plan'], pt['plan'])] += 1
        except Exception:
            pass

        # 2) 성향 반응 — 플랍 계획 고정, 턴 갱신만 축을 바꾼다
        for ax in axes:
            try:
                lo = up(pf_, b4, 'turn', b3, perturb(prof, ax, 1.0))
                hi = up(pf_, b4, 'turn', b3, perturb(prof, ax, 9.0))
            except Exception:
                continue
            if lo['plan'] != hi['plan']:
                flip[ax] += 1
                trans[ax]['%s → %s' % (lo['plan'], hi['plan'])] += 1

        # 4) 플랍에서 갈린 성향이 턴 갱신 뒤에도 남나
        try:
            fl = up(None, b3, 'flop', None, perturb(prof, 'bluff', 1.0), first=True)
            fh = up(None, b3, 'flop', None, perturb(prof, 'bluff', 9.0), first=True)
            if fl['plan'] != fh['plan']:
                surv['split'] += 1
                tl = up(fl, b4, 'turn', b3, prof)     # 같은 기준 프로필로 갱신
                th = up(fh, b4, 'turn', b3, prof)
                if tl['plan'] != th['plan']:
                    surv['kept'] += 1
        except Exception:
            pass

    print('# refresh / update_plan 반사실 — 상황 %d개\n' % done)
    print('## 1. 계획이 얼마나 바뀌나')
    for k in ('flop→turn', 'turn→river', 'flop≠river'):
        print('  %-12s %4d / %d = %.1f%%' % (k, chg[k], done, 100*chg[k]/max(1, done)))
    print('\n  스트리트별 계획 분포')
    for stt in ('flop', 'turn', 'river'):
        print('    %-6s %s' % (stt, '  '.join('%s %d' % kv
                                              for kv in plans[stt].most_common(5))))
    print('\n  refresh 가 남긴 사유 (상위 8)')
    for k, v in why_hit.most_common(8):
        print('    %-36s %d' % (k, v))

    print('\n## 2. 성향 반응 — 플랍 계획 고정, 턴 갱신만')
    pl = max((flip[x] for x in PLACEBO), default=0)
    plr = 100*pl/max(1, done)
    print('  %-16s %7s %8s  %s' % ('축', '뒤집힘', '비율', '가장 흔한 전환'))
    for ax in sorted(axes, key=lambda x: -flip[x]):
        v = flip[ax]; r = 100*v/max(1, done)
        tag = '위약' if ax in PLACEBO else (
              '●' if r >= plr*2 and r >= 5 else ('△' if r > plr else '○'))
        top = trans[ax].most_common(1)
        print('  %-16s %7d %7.1f%%  %-4s %s'
              % (ax, v, r, tag, ('%s ×%d' % top[0] if top else '')))
    print('  위약 바닥값 %.1f%%' % plr)

    print('\n## 3. refresh 를 통째로 건너뛰면 (턴)')
    print('  계획이 달라진 상황 %d / %d = %.1f%%'
          % (nr_diff['turn'], done, 100*nr_diff['turn']/max(1, done)))
    for k, v in nr_diff.most_common(6):
        if k != 'turn': print('    %-34s %d' % (k, v))

    print('\n## 4. 플랍에서 갈린 성향이 턴 갱신 뒤에도 남나')
    print('  bluff 1↔9 로 플랍 계획이 갈린 경우  %d건' % surv['split'])
    if surv['split']:
        print('  그중 턴 갱신 뒤에도 계획이 다른 경우  %d건 (%.0f%%)'
              % (surv['kept'], 100*surv['kept']/surv['split']))
        print('  → 나머지 %.0f%% 는 턴에서 같은 계획으로 수렴했다'
              % (100*(surv['split']-surv['kept'])/surv['split']))


if __name__ == '__main__':
    main()
