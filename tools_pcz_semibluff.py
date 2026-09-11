# -*- coding: utf-8 -*-
"""② eq >= pcz 분기가 semibluff 후보를 가로채는가. 분석 전용.

주의: 아카이브에 opp_est 가 없어 pcz 의 read_opponent 보정
(`pcz += w*0.30*street_gap`)을 복원할 수 없다. 기본값
`pcz = 0.50 + 0.06*mw` 만 쓴다. 실제 pcz 는 이보다 높을 수 있으므로
'pcz 밴드'로 잡힌 건이 실제로는 아래 분기로 갔을 수 있다.
"""
import sys, os, json, random
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS, bot

ARCH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'hand_archive2_alt.jsonl')
NB = {'flop': 3, 'turn': 4, 'river': 5}


def eq_frozen(hero, board, pools, sims=2500, seed=7):
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


rows, seen = [], set()
for ln in open(ARCH):
    r = json.loads(ln)
    for it in r.get('intents', []):
        if it.get('made') is None or (it.get('outs') or 0) < 8:
            continue
        mw = max(0, (it['n_opp'] or 1) - 1)
        if it['made'] >= 5: mw = 0
        elif it['made'] >= 3: mw = min(mw, 1)
        pcz = 0.50 + 0.06*mw
        if it['eq'] < pcz:
            continue
        k = (r['hand_no'], it['street'], it['seat'], it['plan'], it['eq'])
        if k in seen:
            continue
        seen.add(k)
        prof = r['profiles'].get(str(it['seat']), {})
        sb = PS.sk(prof, 'semibluff')/3.33 if prof.get('concepts') else 2.0
        rows.append(dict(
            h=r['hand_no'], street=it['street'], seat=it['seat'],
            hole=r['hole'].get(str(it['seat']), []),
            board=r['board'][:NB[it['street']]],
            eq=it['eq'], pcz=pcz, rel=it['rel'], made=it['made'], outs=it['outs'],
            n_opp=it['n_opp'], init=bool(it['init']), behind=it.get('behind'),
            sb=sb, sb_p=min(0.95, 0.25 + 0.24*sb),
            plan=it['plan'], act=it.get('action'),
            fresh=(it['street'] == it.get('street_made'))))

print('eq >= pcz(기본값) ∧ outs >= 8 :  %d건' % len(rows))
print()
print('%-4s %-6s %-3s %-5s %-11s %-6s %-6s %-6s %-5s %-5s %-5s %-6s %-6s %-6s %-14s %-6s %s'
      % ('h', 'street', 'st', 'hole', 'board', 'eq', 'pcz', 'rel', 'made',
         'outs', 'n_op', 'init', 'behd', 'sb개념', 'plan', '행동', '생성'))
for x in sorted(rows, key=lambda y: (y['made'], -y['eq'])):
    print('%-4s %-6s %-3s %-5s %-11s %-6.3f %-6.2f %-6.2f %-5s %-5s %-5s %-6s %-6s %-6.2f %-14s %-6s %s'
          % (x['h'], x['street'], x['seat'], ''.join(x['hole']), ''.join(x['board']),
             x['eq'], x['pcz'], x['rel'], x['made'], x['outs'], x['n_opp'],
             x['init'], x['behind'], x['sb'], x['plan'], x['act'],
             '생성' if x['fresh'] else '승계'))

print()
print('--- made 별 ---')
for lab, g in (('made == 0', [x for x in rows if x['made'] == 0]),
               ('made >= 1', [x for x in rows if x['made'] >= 1])):
    print('%s : %d건  %s' % (lab, len(g), dict(Counter(x['plan'] for x in g))))

print()
print('--- rel 구간 ---')
for lo, hi, lab in ((0, .30, 'rel <.30'), (.30, .50, '.30~.50'),
                    (.50, .70, '.50~.70'), (.70, 9, '>= .70')):
    g = [x for x in rows if lo <= x['rel'] < hi]
    if g:
        print('%-10s %d건  made %s  plan %s'
              % (lab, len(g), sorted(x['made'] for x in g),
                 dict(Counter(x['plan'] for x in g))))

print()
print('--- semibluff 게이트를 통과했을까 (결정론 부분만) ---')
print('%-4s %-6s %-6s %-6s %-8s %-8s %s'
      % ('h', 'street', 'outs', 'behind', 'sb개념', '롤확률', '결정론 게이트'))
for x in rows:
    ok = (x['outs'] >= 8 and (x['behind'] or 0) <= 1 and x['sb'] >= 0.4)
    print('%-4s %-6s %-6s %-6s %-8.2f %-8.2f %s'
          % (x['h'], x['street'], x['outs'], x['behind'], x['sb'], x['sb_p'],
             '통과' if ok else '탈락'))

print()
print('--- eq 분해 (runout vs frozen, 0.35 근사 레인지 공통) ---')
print('%-4s %-6s %-5s %-11s %-9s %-9s %-9s %s'
      % ('h', 'street', 'hole', 'board', 'runout', 'frozen', '드로우분', 'plan'))
for x in rows:
    dead = set(x['hole']) | set(x['board'])
    pool = bot.range_combos(0.35, dead)
    n = max(1, x['n_opp'])
    ru = bot.equity_vs_pools(x['hole'], x['board'], [pool]*n, sims=2500, seed=7)
    fz = eq_frozen(x['hole'], x['board'], [pool]*n)
    print('%-4s %-6s %-5s %-11s %-9.3f %-9.3f %+-9.3f %s'
          % (x['h'], x['street'], ''.join(x['hole']), ''.join(x['board']),
             ru, fz, ru - fz, x['plan']))
