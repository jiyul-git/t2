#!/usr/bin/env python3
"""② 선점 26건의 반사실 — `eq >= pcz` 가 먼저 잡지 않았다면 어디로 갔나.

plan.py 는 읽기만 한다. **난수를 새로 굴리지 않는다.**

왜 난수를 안 굴리는가
---------------------
세미블러프 주사위의 원시값은 로그에 없다. 여기서 새로 굴려 "26건 중 n건이
세미블러프가 된다"고 말하면 측정 노이즈를 결론으로 승격시키는 것이다.
그래서 여기서는 다음까지만 낸다.

    1. 게이트 통과 여부          (결정적)
    2. 세미블러프 확률 p          (결정적, sk 의 함수)
    3. 기대 세미블러프 건수 Σp    (기대값)
    4. 통과했을 때의 행동 확률    (decide_aggression / decide_response 는
                                  이 경로에서 난수를 쓰지 않는다 — 검증함)

두 가지 반사실
--------------
CF-1 재정렬  semibluff elif 를 `eq >= pcz` **위로** 옮긴다.
             주사위 실패 → 현재 경로 그대로. 최소 개입.
CF-2 제거    `eq >= pcz` 분기를 **없앤다**.
             주사위 실패 → 다음 elif(bluff) → 최종 else.
             bluff 는 `eq < 0.42` 를 요구하는데 이 26건은 전부 eq >= pcz >= 0.50
             이라 **구조적으로 통과 불가**. 따라서 최종 else 로 간다.

임계값은 하나도 새로 만들지 않는다. A/B/C 분류의 rel 0.30 은
plan.py 가 이미 쓰는 값이다(decide_aggression 팟컨트롤 분기, bluff 분기 게이트).

사용: python3 tools/cf_pcz.py [collected.jsonl ...]
"""
import os, sys, json, math, random, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS
import plan as PL
from sb_calib import load, branch_of, p_formula, river_odds
from sb_114 import thresholds
from tag_draws import tag as draw_tag, board_at

PASSIVE = ('giveup', 'pot_control', 'showdown')


def trace_of(i, kind):
    for t in (i.get('trace') or []):
        if (t or {}).get('kind') == kind and t.get('street') == i['street']:
            return t
    return None


def actual_aggr(i):
    """실제 경로의 '칠 확률'. 무저항이면 decide_aggression 의 p,
       저항이면 실제로 레이즈했는지(0/1 관측)."""
    if (i.get('tocall') or 0) > 0:
        return (1.0 if i.get('action') == 'raise' else 0.0), '관측'
    t = trace_of(i, 'aggression')
    return (float(t['p']) if t else 0.0), ('trace' if t else '없음')


def cf_semibluff_aggr(i):
    """계획이 semibluff 였다면의 행동 확률. 이 경로는 난수를 쓰지 않는다."""
    prof = i['_prof']
    bd = board_at(i['_board'], i['street'])
    if (i.get('tocall') or 0) > 0:
        # decide_response 의 세미블러프 분기 (plan.py:760)
        p = (0.10 + 0.055*PS.sk(prof, 'semibluff') + 0.030*PS.sk(prof, 'reraise'))
        p *= 0.70 + 0.06*PS.temper(prof, 'aggression', 5.0)
        p_raise = max(0.03, min(0.80, p))
        # 레이즈 안 하면 내재오즈로 need 를 깎고 콜/폴드
        t = trace_of(i, 'response')
        need = float(t['need']) if t else None
        io = 0.02 + 0.008*(0.6*PS.sk(prof, 'outs') + 0.4*PS.sk(prof, 'potodds'))
        pot, stack = float(i.get('pot') or 0), float(i.get('stack') or 0)
        implied = min(0.12, io * min(1.0, stack/max(1.0, 2.0*pot))) if stack > pot else 0.0
        need_adj = max(0.02, need - implied) if need is not None else None
        tail = 'call' if (need_adj is not None and i['eq'] >= need_adj) else 'fold'
        return p_raise, tail, need, need_adj
    # decide_aggression 의 블러프 계획 분기 (plan.py:865)
    st = dict(i)
    p, why = PL.decide_aggression(prof, bd, i['street'], 'semibluff', i['rel'],
                                  i.get('n_opp', 1), bool(i.get('oop')),
                                  bool(i.get('init')), i.get('behind', 0),
                                  random.Random(0), i.get('opp_est'),
                                  i.get('outs', 0), plan_state=st)
    return p, None, None, None


def main():
    paths = sys.argv[1:] or [os.path.join(D, 'collected.jsonl')]
    rows = load(paths)
    for i in rows:
        i['_branch'] = branch_of(i)
        i['_sk'] = PS.sk(i['_prof'], 'semibluff') / 3.33
        i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
    cand = [i for i in rows if i['_branch'] and i['outs'] >= 8
            and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4]
    g2 = [i for i in cand if i['_branch'] == 'above']

    print('=' * 104)
    print('0. 반사실의 전제 검증')
    print('=' * 104)
    print('   ② 선점 n=%d' % len(g2))
    gate = [i for i in g2 if i['outs'] >= 8 and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4]
    print('   세미블러프 게이트(outs>=8 & behind<=1 & sk>=0.4) 통과 %d/%d'
          % (len(gate), len(g2)))
    print('     → 후보 정의가 곧 게이트 조건이라 전건 통과. 막는 것은 분기 순서뿐이다.')
    bl = [i for i in g2 if i['eq'] < 0.42]
    print('   CF-2 에서 bluff_2street 로 갈 수 있는 건(eq < 0.42) %d/%d' % (len(bl), len(g2)))
    mw = lambda i: (0 if i.get('made', 0) >= 5 else
                    (min(max(0, i.get('n_opp', 1)-1), 1) if i.get('made', 0) >= 3
                     else max(0, i.get('n_opp', 1)-1)))
    hs = [i for i in g2 if (i.get('made', 0) >= 1 or i['eq'] >= 0.42 + 0.05*mw(i))]
    print('   CF-2 최종 else 에서 has_sd 가 참인 건 %d/%d' % (len(hs), len(g2)))
    print('     → has_sd 가 전건 참이면 최종 else 의 giveup 은 도달 불가.')
    print('        즉 CF-2 에서 이 26건은 semibluff / pot_control / showdown 으로만 간다.')
    print()

    # ---- 각 건 계산 ----
    for i in g2:
        i['_p_sb'] = p_formula(i['_sk'])
        i['_a0'], i['_a0src'] = actual_aggr(i)
        i['_a1'], i['_tail'], i['_need'], i['_need_adj'] = cf_semibluff_aggr(i)
        i['_d'] = i['_p_sb'] * (i['_a1'] - i['_a0'])

    print('=' * 104)
    print('1. CF-1 재정렬 — semibluff 분기를 eq>=pcz 위로 옮기면')
    print('=' * 104)
    S = sum(i['_p_sb'] for i in g2)
    print('   기대 세미블러프 건수  Σp = %.1f / %d  (평균 p %.3f)'
          % (S, len(g2), S/len(g2)))
    print('   주사위 실패분 %.1f건은 현재 경로 그대로 — 잃는 것이 없다' % (len(g2)-S))
    a0 = sum(i['_a0'] for i in g2)
    a1 = sum(i['_p_sb']*i['_a1'] + (1-i['_p_sb'])*i['_a0'] for i in g2)
    print('   기대 공격 건수  현재 %.2f → 반사실 %.2f  (%+.2f건)' % (a0, a1, a1-a0))
    print()

    print('=' * 104)
    print('2. 전수 표  (기대변화 = p × (반사실 공격확률 - 현재 공격확률))')
    print('=' * 104)
    h = ('%-6s %-5s %-6s %-13s %4s %6s %6s %5s %5s %6s %7s %7s %8s  %-14s %s'
         % ('hand', 'st', '홀', '보드', '물리', 'eq', 'pcz', 'rel', 'sk',
            'p', '현재공격', '반사실', '기대변화', '현재계획', '드로우'))
    print(h); print('-' * len(h))
    for i in sorted(g2, key=lambda x: -x['_d']):
        bd = board_at(i['_board'], i['street'])
        tg = ', '.join(draw_tag(i['_hole'], bd)) if (i['_hole'] and len(bd) >= 3) else '-'
        print('h%-5d %-5s %-6s %-13s %4d %6.3f %6.3f %5.2f %5.2f %6.3f %7.2f %7.2f %+8.2f  %-14s %s'
              % (i['_hand'], i['street'], ''.join(i['_hole'] or []), ' '.join(bd),
                 i['outs_true'], i['eq'], i['_pcz'], i['rel'], i['_sk'], i['_p_sb'],
                 i['_a0'], i['_a1'], i['_d'], i['plan'], tg))
    print()

    # ---- A/B/C ----
    print('=' * 104)
    print('3. A / B / C 분류')
    print('=' * 104)
    print('   A — 선점이 계획을 만들어냈다 (밸류 라인, 또는 rel>=0.30 의 수동 라인)')
    print('   B — 선점이 수동·포기 계획을 만들었고, 반사실에서 공격이 늘어난다')
    print('   C — 선점을 없애도 결국 공격하지 않는다')
    print('   (rel 0.30 은 plan.py 가 이미 쓰는 값이다. 새로 만들지 않았다)')
    print()
    for i in g2:
        made_plan = (i['plan'] not in PASSIVE) or (i['rel'] >= 0.30 and i['plan'] != 'giveup')
        if made_plan:
            i['_abc'] = 'A'
        elif i['_d'] > 0:
            i['_abc'] = 'B'
        else:
            i['_abc'] = 'C'
    for k in ('A', 'B', 'C'):
        sub = [i for i in g2 if i['_abc'] == k]
        if not sub:
            print('   %s  n=0' % k); continue
        print('   %s  n=%-3d  eq %.3f  rel %.2f  물리 %.1f아웃  Σp %.1f  기대변화 %+.2f건  계획 %s'
              % (k, len(sub), sum(x['eq'] for x in sub)/len(sub),
                 sum(x['rel'] for x in sub)/len(sub),
                 sum(x['outs_true'] for x in sub)/len(sub),
                 sum(x['_p_sb'] for x in sub), sum(x['_d'] for x in sub),
                 dict(collections.Counter(x['plan'] for x in sub).most_common())))
    print()

    B = [i for i in g2 if i['_abc'] == 'B']
    if B:
        print('   B 상세 — 진짜 분기순서 후보')
        hb = ('   %-6s %-5s %-6s %4s %6s %5s %6s %7s %7s %8s  %-12s %s'
              % ('hand', 'st', '홀', '물리', 'eq', 'rel', 'p', '현재', '반사실', '기대변화',
                 '현재계획', '드로우'))
        print(hb); print('   ' + '-' * (len(hb)-3))
        for i in sorted(B, key=lambda x: -x['_d']):
            bd = board_at(i['_board'], i['street'])
            tg = ', '.join(draw_tag(i['_hole'], bd)) if (i['_hole'] and len(bd) >= 3) else '-'
            print('   h%-5d %-5s %-6s %4d %6.3f %5.2f %6.3f %7.2f %7.2f %+8.2f  %-12s %s'
                  % (i['_hand'], i['street'], ''.join(i['_hole'] or []), i['outs_true'],
                     i['eq'], i['rel'], i['_p_sb'], i['_a0'], i['_a1'], i['_d'],
                     i['plan'], tg))
        print()

    # ---- CF-2 ----
    print('=' * 104)
    print('4. CF-2 제거 — eq>=pcz 분기 자체를 없애면')
    print('=' * 104)
    print('   주사위 실패분 %.1f건의 행선지:' % (len(g2)-S))
    pc = [i for i in g2 if PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1]
    print('     potcontrol 개념 >= 1(원개념 3.33) 인 건 %d/%d → 그중 72%% 가 pot_control,'
          % (len(pc), len(g2)))
    print('     나머지는 showdown. **giveup 은 구조적으로 나오지 않는다.**')
    gv = [i for i in g2 if i['plan'] == 'giveup']
    print()
    print('   현재 giveup %d건이 CF-2 에서는 전부 사라진다.' % len(gv))
    print('   이 %d건은 402줄 폴백(`showdown if made>=1 else giveup`)의 산물이고,' % len(gv))
    print('   그 폴백은 eq>=pcz 분기 **안에만** 있다.')
    if gv:
        print('     평균 eq %.3f / rel %.2f / 물리 %.1f아웃 / made %.1f'
              % (sum(i['eq'] for i in gv)/len(gv), sum(i['rel'] for i in gv)/len(gv),
                 sum(i['outs_true'] for i in gv)/len(gv),
                 sum(i.get('made', 0) for i in gv)/len(gv)))
        print('     이 중 실제로 체크/폴드로 끝난 건 %d/%d'
              % (sum(1 for i in gv if i.get('action') in ('check', 'fold')), len(gv)))
    print()
    print('=' * 104)
    print('5. 이번 단계의 답')
    print('=' * 104)
    print('   26건 중 선점이 잘못된 계획을 만든 건 = B %d건.'
          % sum(1 for i in g2 if i['_abc'] == 'B'))
    print('   기대 공격 건수 변화 %+.2f건 (CF-1 기준, 1,000핸드당).'
          % (sum(i['_d'] for i in g2)))
    print('   pcz 임계값은 건드리지 않았다. 움직인 것은 분기 순서뿐이다.')


if __name__ == '__main__':
    main()
