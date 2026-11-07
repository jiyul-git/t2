# -*- coding: utf-8 -*-
"""④ has_sd 변형 A/B/C 비교. 생산 코드 수정 없음.

`else` 블록(플랜 최종 폴백)에 도달한 intent 만 모집단으로 잡는다.
why 문자열로 식별한다 — 이 세 문구는 그 블록에서만 나온다.

  '쇼다운 가치 있음 → 팟 컨트롤'
  '쇼다운 가치 있음 → 체크다운(팟컨트롤 개념 ...)'
  '쇼다운 가치 없고 블러프 개념/조건 미달 → 포기'

A: has_sd = made >= 1 or eq >= 0.42 + 0.05*mw     (현재)
B: has_sd = made >= 1                              (보수적)
C: made == 0 을 나눌 별도 신호 — 존재 여부를 확인한다
"""
import json, os
from collections import Counter

ARCH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'hand_archive2_alt.jsonl')
MARK = ('쇼다운 가치 있음 → 팟 컨트롤',
        '쇼다운 가치 있음 → 체크다운',
        '쇼다운 가치 없고 블러프 개념/조건 미달 → 포기')
NB = {'flop': 3, 'turn': 4, 'river': 5}

rows, seen = [], set()
for ln in open(ARCH):
    r = json.loads(ln)
    for it in r.get('intents', []):
        if it.get('made') is None:
            continue
        w = ' | '.join(it.get('why') or [])
        hit = [m for m in MARK if (it['street'] + ': ' + m) in w or m in w]
        if not hit:
            continue
        # 이 스트리트에서 만들어진 계획만 (승계 제외)
        if it['street'] != it.get('street_made'):
            continue
        k = (r['hand_no'], it['street'], it['seat'], it['plan'], it['eq'])
        if k in seen:
            continue
        seen.add(k)
        mw = max(0, (it['n_opp'] or 1) - 1)
        if it['made'] >= 5: mw = 0
        elif it['made'] >= 3: mw = min(mw, 1)
        rows.append(dict(
            h=r['hand_no'], street=it['street'], seat=it['seat'],
            hole=''.join(r['hole'].get(str(it['seat']), [])),
            board=''.join(r['board'][:NB[it['street']]]),
            eq=it['eq'], rel=it['rel'], made=it['made'], outs=it['outs'],
            nadv=it['nut_adv'], radv=it['range_adv'], n_opp=it['n_opp'],
            blk=it.get('blocker'), plan=it['plan'], act=it.get('action'),
            A=(it['made'] >= 1 or it['eq'] >= 0.42 + 0.05*mw),
            B=(it['made'] >= 1)))

print('else 블록에서 생성된 계획 : %d건' % len(rows))
print('현재(A) 계획 분포 :', dict(Counter(x['plan'] for x in rows)))
print()

diff = [x for x in rows if x['A'] != x['B']]
print('A 와 B 가 갈리는 건수 : %d  (made==0 이면서 eq 문턱 통과)' % len(diff))
print('  → 이들의 현재 계획 :', dict(Counter(x['plan'] for x in diff)))
print('  → B 에서는 전부 giveup 이 된다')
print()
print('%-4s %-6s %-5s %-11s %-6s %-6s %-5s %-5s %-6s %-6s %-13s %s'
      % ('h', 'street', 'hole', 'board', 'eq', 'rel', 'outs', 'n_opp',
         'nadv', 'radv', '현재 plan', '행동'))
for x in sorted(diff, key=lambda y: (-y['outs'], -y['rel'])):
    print('%-4s %-6s %-5s %-11s %-6.3f %-6.2f %-5s %-5s %-6.2f %-6.2f %-13s %s'
          % (x['h'], x['street'], x['hole'], x['board'], x['eq'], x['rel'],
             x['outs'], x['n_opp'], x['nadv'], x['radv'], x['plan'], x['act']))

print()
print('--- B 가 깨뜨리는 것을 outs 로 나누면 ---')
for lab, g in (('outs >  0', [x for x in diff if x['outs'] > 0]),
               ('outs == 0', [x for x in diff if x['outs'] == 0])):
    if not g:
        print('%s : 0건' % lab); continue
    print('%s : %d건  rel %s  eq %s'
          % (lab, len(g), sorted(round(x['rel'], 2) for x in g),
             sorted(round(x['eq'], 3) for x in g)))

print()
print('--- C: made==0 을 나눌 후보 신호가 아카이브에 있는가 ---')
z = [x for x in rows if x['made'] == 0 and x['A']]
for f in ('rel', 'outs', 'nadv', 'radv', 'blk'):
    a = sorted(round(x[f], 2) for x in z if x['outs'] > 0)
    b = sorted(round(x[f], 2) for x in z if x['outs'] == 0)
    ov = (max(a) >= min(b) and max(b) >= min(a)) if (a and b) else None
    print('  %-6s  outs>0 %-28s outs==0 %-28s 겹침 %s'
          % (f, a, b, ov))
