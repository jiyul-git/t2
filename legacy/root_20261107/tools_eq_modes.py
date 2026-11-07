# -*- coding: utf-8 -*-
"""1단계 — eq 를 두 모드로 분해해 아카이브 전체에 계산한다. 분석 전용.

    eq_runout   현재 코드와 같은 계산. 남은 보드를 리버까지 돌린 뒤 쇼다운.
    eq_current  보드를 돌리지 않는다. 지금 쇼다운했다면.
    delta_eq    eq_runout - eq_current. 남은 카드가 만드는 변화량.

**중대한 한계**: 아카이브에 opp_range 가 없다. 코드가 실제로 쓴
추정 레인지를 복원할 수 없어, 양쪽 모두 bot.range_combos(0.35) 로
계산한다. 따라서 절대값은 기록된 eq 와 다르다. 비교 대상은
같은 레인지로 계산한 두 모드의 **차이**뿐이다.
기록된 eq 와의 격차를 아래에 같이 출력해 그 한계를 노출한다.
"""
import sys, os, json, random, statistics as st
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot

ARCH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'hand_archive2_alt.jsonl')
NB = {'flop': 3, 'turn': 4, 'river': 5}
SIMS = 1500


def eq_two_modes(hero, board, n_opp):
    dead = set(hero) | set(board)
    pool = bot.range_combos(0.35, dead)
    pools = [pool] * max(1, n_opp)
    ru = bot.equity_vs_pools(hero, board, pools, sims=SIMS, seed=11)
    # 같은 함수를 쓰되 보드를 돌리지 않는다
    rng = random.Random(11)
    hs = bot.eval7(hero + board)
    win = tie = run = 0
    ps = [[c for c in p if c[0] not in dead and c[1] not in dead] for p in pools]
    for _ in range(SIMS):
        used = set(dead); opps = []; ok = True
        for p in ps:
            for _t in range(40):
                c = rng.choice(p)
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
    cur = (win + tie*0.5) / max(1, run)
    return ru, cur


rows, seen = [], set()
for ln in open(ARCH):
    r = json.loads(ln)
    for it in r.get('intents', []):
        if it.get('made') is None or it['street'] not in NB:
            continue
        hero = r['hole'].get(str(it['seat']))
        if not hero:
            continue
        board = r['board'][:NB[it['street']]]
        k = (tuple(hero), tuple(board), it['n_opp'])
        if k in seen:
            continue
        seen.add(k)
        rows.append(dict(h=r['hand_no'], street=it['street'], seat=it['seat'],
                         hole=hero, board=board, n_opp=it['n_opp'],
                         eq_rec=it['eq'], rel=it['rel'], made=it['made'],
                         outs=it['outs'], plan=it['plan']))

print('고유 (핸드, 보드, 인원) 조합 : %d  (sims=%d)' % (len(rows), SIMS))
for x in rows:
    x['ru'], x['cur'] = eq_two_modes(x['hole'], x['board'], x['n_opp'])
    x['d'] = x['ru'] - x['cur']

gap = [abs(x['ru'] - x['eq_rec']) for x in rows]
print('기록된 eq 와 eq_runout(0.35 근사)의 절대 격차: 중앙 %.3f  평균 %.3f  최대 %.3f'
      % (st.median(gap), sum(gap)/len(gap), max(gap)))
print('→ 절대값은 신뢰하지 말 것. delta_eq 만 본다.')
print()

print('--- delta_eq 의 부호 분포 ---')
print('  전체 %d건   양수 %d  음수 %d  |delta|<0.02 %d'
      % (len(rows), sum(1 for x in rows if x['d'] > 0.02),
         sum(1 for x in rows if x['d'] < -0.02),
         sum(1 for x in rows if abs(x['d']) <= 0.02)))
print()

print('--- made / outs 별 delta_eq ---')
print('%-22s %-5s %-9s %-9s %-9s %s' % ('군', 'n', 'delta중앙', 'delta최소', 'delta최대', 'eq_current 중앙'))
groups = [
    ('A made0 outs>0', lambda x: x['made'] == 0 and x['outs'] > 0),
    ('B made0 outs=0', lambda x: x['made'] == 0 and x['outs'] == 0),
    ('C made>=1 outs>0', lambda x: x['made'] >= 1 and x['outs'] > 0),
    ('D made>=1 outs=0', lambda x: x['made'] >= 1 and x['outs'] == 0),
]
for lab, f in groups:
    g = [x for x in rows if f(x)]
    if not g:
        print('%-22s 0' % lab); continue
    d = [x['d'] for x in g]
    print('%-22s %-5d %+9.3f %+9.3f %+9.3f %.3f'
          % (lab, len(g), st.median(d), min(d), max(d),
             st.median([x['cur'] for x in g])))

print()
print('--- 높은 eq(기록 >= 0.42) 구간만 ---')
hi = [x for x in rows if x['eq_rec'] >= 0.42]
print('%-22s %-5s %-11s %s' % ('군', 'n', 'delta 범위', 'eq_current 범위'))
for lab, f in groups:
    g = [x for x in hi if f(x)]
    if not g:
        print('%-22s 0' % lab); continue
    print('%-22s %-5d %+.3f ~ %+.3f  %.3f ~ %.3f'
          % (lab, len(g), min(x['d'] for x in g), max(x['d'] for x in g),
             min(x['cur'] for x in g), max(x['cur'] for x in g)))

print()
print('--- outs 가 같아도 delta 가 갈리는가 (outs>=8 전수) ---')
print('%-4s %-6s %-5s %-11s %-5s %-6s %-6s %-9s %-9s %-9s %s'
      % ('h', 'street', 'hole', 'board', 'outs', 'made', 'rel',
         'eq_rec', 'eq_cur', 'delta', 'plan'))
for x in sorted([y for y in rows if y['outs'] >= 8], key=lambda y: -y['d']):
    print('%-4s %-6s %-5s %-11s %-5s %-6s %-6.2f %-9.3f %-9.3f %+-9.3f %s'
          % (x['h'], x['street'], ''.join(x['hole']), ''.join(x['board']),
             x['outs'], x['made'], x['rel'], x['eq_rec'], x['cur'], x['d'], x['plan']))

out = os.path.join(os.path.dirname(ARCH), 'eq_decomp.json')
json.dump([{k: (list(v) if isinstance(v, tuple) else v)
            for k, v in x.items()} for x in rows],
          open(out, 'w'), ensure_ascii=False)
print()
print('저장:', out)
