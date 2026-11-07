# -*- coding: utf-8 -*-
"""④-A: eq 의 출처를 분해한다. 생산 코드 수정 없음.

plan.py 의 eq 는 bot.equity_vs_combos → equity_vs_pools 이고,
남은 보드를 리버까지 **다 돌린 뒤** 쇼다운을 평가한다.
즉 미래 개선분이 전부 포함된 all-in equity 다.

비교군으로 '지금 핸드가 끝났다면' 승률(frozen)을 같은 레인지로 계산한다.
보드를 더 돌리지 않고 현재 보드에서만 평가한다.

    eq_runout - eq_frozen  =  드로우가 만들어낸 지분
"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot, plan as PL

ARCH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'hand_archive2_alt.jsonl')


def eq_frozen(hero, board, pools, sims=3000, seed=7):
    """보드를 더 돌리지 않는다. 현재 보드에서 쇼다운했다면?"""
    rng = random.Random(seed)
    dead = set(hero) | set(board)
    hs = bot.eval7(hero + board)
    win = tie = run = 0
    pools = [[c for c in p if c[0] not in dead and c[1] not in dead] for p in pools]
    for _ in range(sims):
        used = set(dead); opps = []; ok = True
        for pool in pools:
            for _t in range(40):
                c = rng.choice(pool)
                if c[0] not in used and c[1] not in used:
                    used.add(c[0]); used.add(c[1]); opps.append(list(c)); break
            else:
                ok = False; break
        if not ok:
            continue
        run += 1
        best = max(bot.eval7(o + board) for o in opps)
        if hs > best: win += 1
        elif hs == best: tie += 1
    return (win + tie*0.5) / max(1, run)


TARGETS = [(34, 'flop', 2), (61, 'flop', 3), (37, 'flop', 6),
           (44, 'flop', 6), (58, 'flop', 6), (56, 'turn', 7)]
NB = {'flop': 3, 'turn': 4, 'river': 5}

print('%-4s %-6s %-5s %-11s %-6s %-5s %-5s %-9s %-9s %-9s %s'
      % ('h', 'street', 'hole', 'board', 'made', 'outs', 'rel',
         'eq(코드)', 'eq_frozen', '드로우분', 'plan'))

for hno, street, seat in TARGETS:
    for ln in open(ARCH):
        r = json.loads(ln)
        if r['hand_no'] != hno:
            continue
        hero = r['hole'][str(seat)]
        board = r['board'][:NB[street]]
        its = [i for i in r['intents'] if i['seat'] == seat and i['street'] == street]
        it = its[0]
        # 상대 레인지 원본이 아카이브에 없다 → 코드가 폴백에 쓰는
        # 비율 근사(0.35)로 동일 조건 비교한다. 절대값이 아니라
        # runout 과 frozen 의 '차이'를 보는 게 목적이다.
        dead = set(hero) | set(board)
        pool = bot.range_combos(0.35, dead)
        n = max(1, it['n_opp'])
        ru = bot.equity_vs_pools(hero, board, [pool]*n, sims=3000, seed=7)
        fz = eq_frozen(hero, board, [pool]*n)
        print('%-4s %-6s %-5s %-11s %-6s %-5s %-5.2f %-9.3f %-9.3f %-9.3f %s'
              % (hno, street, ''.join(hero), ''.join(board), it['made'],
                 it['outs'], it['rel'], ru, fz, ru - fz, it['plan']))
        break
