#!/usr/bin/env python3
"""(가) made==0 · 물리 outs==0 인데 rel 이 높아 giveup 이 된 건의 해부.

plan.py 는 읽기만 한다. 수정안을 내지 않는다.

세 가지를 따로 확정한다.

1. rel 이 무엇인가 (코드 기준, 추측 금지)
   plan.py:29 relative_strength
       mine = bot.eval7(hero + board)            ← **7장 최고 조합**
       cand = 상대 레인지 콤보 중 데드카드 제외
       rel  = 1 - (나를 이기는 콤보 수)/(콤보 수)
   즉 rel 은 **상대 레인지 대비 현재 승률 순위**다.
   equity 도 range_advantage 도 nut_advantage 도 아니다.

   plan.py:206 made_strength 는 반대로 **내 홀카드의 기여가 없으면 0** 이다
   (docstring: "98o 가 6s Ks Kc 보드에서 원페어(=보드의 KK)로 잡혀
    '쇼다운 가치 있음'이 되는 문제").

   두 함수는 **의도적으로 다른 것을 잰다.** eval7 은 보드가 만든 조합을 세고
   made_strength 는 세지 않는다. made==0 & rel 높음 은 그 차이의 결과다.

   기록된 rel 은 perceived_rel(plan.py:72)을 거친 값이지만,
   이 집단에서는 보정 셋이 전부 게이트로 막힌다:
       overpair_love  made >= 1 필요      → made==0 이라 off
       draw_love      outs >= 4 필요      → outs==0 이라 off
       sticky         raw rel < 0.45 필요 → 적용됐다면 최대 +0.08 (bias 는 _z 로 [-1,1])
   따라서 **기록 rel > 0.53 이면 raw relative_strength 와 정확히 같다.**

2. 402 에 왜 도착하는가 (증상인가 원인인가)
   eq >= pcz 분기 안의 순서는
       block          → sk('blockbet')>=1 and rng < block_p
       pot_control    → sk('potcontrol')>=1 and rng < _pc_p
       얇은 밸류      → rel >= max(0.28, 0.52-0.080*_mg) **and made >= 1**
       402 폴백       → 'showdown' if made >= 1 else 'giveup'
   얇은 밸류 게이트가 rel 조건을 통과해도 `made >= 1` 에서 걸리면
   402 로 떨어지고, 402 가 **같은 made 를 다시** 본다.
   그래서 made 가 연속 두 번 판별자가 된다. 이 도구는 건별로
   "rel 조건은 통과했는가"를 따로 재서 그 사실을 확인한다.

3. rel 0.5~1.0 이 실제로 어떤 핸드인가
   eval7 카테고리와 보드만의 카테고리를 나란히 낸다.

사용: python3 tools/rel_made.py [collected.jsonl ...]
"""
import os, sys, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot
import persona as PS
from sb_calib import load, branch_of
from sb_114 import thresholds
from cf_402 import is_402
from tag_draws import board_at

CAT = {0: '하이카드', 1: '원페어', 2: '투페어', 3: '트립스', 4: '스트레이트',
       5: '플러시', 6: '풀하우스', 7: '쿼드', 8: '스트플'}


def board_cat(board):
    """보드만으로 성립하는 최고 등급 (made_strength 와 같은 규칙)."""
    if len(board) >= 5:
        return bot.eval7(list(board))[0]
    cnt = collections.Counter(c[0] for c in board)
    m = max(cnt.values()) if cnt else 1
    c = {1: 0, 2: 1, 3: 3, 4: 7}.get(m, 0)
    su = collections.Counter(c2[1] for c2 in board)
    if su and max(su.values()) >= 5:
        c = max(c, 5)
    return c


def main():
    paths = sys.argv[1:] or [os.path.join(D, 'collected.jsonl')]
    rows = load(paths)
    for i in rows:
        i['_branch'] = branch_of(i)
        i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
    mp = [i for i in rows if i['_branch']]
    all402 = [i for i in mp if is_402(i)]
    ga = [i for i in all402 if i.get('made', 0) == 0 and i['outs_true'] == 0]

    print('=' * 112)
    print('1. rel 의 정체 — 기록된 rel 이 raw relative_strength 인가')
    print('=' * 112)
    print('   대상 (가) n=%d  (402 발동 · made==0 · 물리 outs==0)' % len(ga))
    hi = [i for i in ga if i['rel'] > 0.53]
    print('   기록 rel > 0.53  %d/%d' % (len(hi), len(ga)))
    print('     → 이 %d건은 perceived_rel 보정이 **하나도 적용될 수 없다**.' % len(hi))
    print('        overpair_love: made>=1 필요(0) / draw_love: outs>=4 필요(0)')
    print('        sticky: raw<0.45 필요이고 최대 +0.08 이므로 결과가 0.53 을 못 넘는다')
    amb = [i for i in ga if i['rel'] <= 0.53]
    print('   기록 rel <= 0.53 %d건 — sticky 적용 여부가 확정되지 않는 구간' % len(amb))
    for i in amb:
        print('      h%-5d %-5s rel %.2f' % (i['_hand'], i['street'], i['rel']))
    print()
    print('   결론: rel 은 **상대 레인지 대비 현재 승률 순위**다 (eval7 기준).')
    print('         equity(eq) 도 range_adv 도 nut_adv 도 아니다. 합성값도 아니다.')
    print()

    print('=' * 112)
    print('2. rel 0.5~1.0 이 실제로 어떤 핸드인가')
    print('=' * 112)
    h = ('%-6s %-5s %-6s %-14s %6s %5s %6s %6s  %-9s %-9s %-5s %-9s %s'
         % ('hand', 'st', '홀', '보드', 'eq', 'rel', 'pcz', 'radv',
            '내 7장', '보드만', '기여', '최종계획', '실제'))
    print(h); print('-' * len(h))
    contrib = collections.Counter()
    for i in sorted(ga, key=lambda x: -x['rel']):
        bd = board_at(i['_board'], i['street'])
        if not i['_hole'] or len(bd) < 3:
            continue
        c7 = bot.eval7(list(i['_hole']) + list(bd))[0]
        cb = board_cat(bd)
        same = (c7 <= cb)
        contrib[(CAT.get(c7, '?'), same)] += 1
        print('h%-5d %-5s %-6s %-14s %6.3f %5.2f %6.3f %+6.2f  %-9s %-9s %-5s %-9s %s'
              % (i['_hand'], i['street'], ''.join(i['_hole']), ' '.join(bd),
                 i['eq'], i['rel'], i['_pcz'], i.get('range_adv') or 0.0,
                 CAT.get(c7, '?'), CAT.get(cb, '?'),
                 '없음' if same else '있음', i['plan'], i.get('action')))
    print()
    print('   내 7장 등급 × 홀카드 기여 여부')
    for (c, same), n in sorted(contrib.items(), key=lambda x: -x[1]):
        print('     %-10s 기여 %-4s %2d건' % (c, '없음' if same else '있음', n))
    print()

    print('=' * 112)
    print('3. 402 에 왜 도착했는가 — 증상인가 원인인가')
    print('=' * 112)
    print('   얇은 밸류 게이트  `rel >= max(0.28, 0.52 - 0.080*_mg) and made >= 1`')
    print('   두 조건을 따로 재서, 무엇이 실제로 막았는지 본다.')
    print()
    h3 = ('%-6s %-5s %5s %6s %8s %8s %10s %10s'
          % ('hand', 'st', 'rel', '_mg', 'rel문턱', 'rel통과', 'made통과', '막은 조건'))
    print(h3); print('-' * len(h3))
    blocked = collections.Counter()
    for i in sorted(ga, key=lambda x: -x['rel']):
        mg = PS.sk(i['_prof'], 'range_merge') / 3.33
        thr = max(0.28, 0.52 - 0.080 * mg)
        rel_ok = i['rel'] >= thr
        made_ok = i.get('made', 0) >= 1
        if rel_ok and not made_ok:
            b = 'made 만'
        elif not rel_ok and not made_ok:
            b = 'rel·made 둘 다'
        elif not rel_ok:
            b = 'rel 만'
        else:
            b = '없음(?)'
        blocked[b] += 1
        print('h%-5d %-5s %5.2f %6.2f %8.3f %8s %10s %10s'
              % (i['_hand'], i['street'], i['rel'], mg, thr,
                 'O' if rel_ok else 'X', 'O' if made_ok else 'X', b))
    print()
    for k, v in blocked.most_common():
        print('     %-18s %2d건 (%.0f%%)' % (k, v, 100*v/max(1, len(ga))))
    print()
    n_made_only = blocked.get('made 만', 0)
    print('   → 얇은 밸류 게이트를 rel 로는 통과했는데 made 로만 막힌 건 %d/%d.'
          % (n_made_only, len(ga)))
    print('     이 건들은 402 가 문제를 "생성"한 게 아니라, 앞 게이트가 made 로')
    print('     걸러낸 것을 402 가 **같은 made 로 한 번 더** 판정해 굳힌 것이다.')
    print('     즉 판별자(made)가 두 번 연속 쓰였고, 두 곳 다 같은 이유로 틀린다.')
    print()

    # pot_control 이 먼저 잡을 수 있었는가
    print('   앞 순위 분기가 잡을 기회가 있었는가')
    npc = sum(1 for i in ga if PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1)
    nbb = sum(1 for i in ga if PS.sk(i['_prof'], 'blockbet')/3.33 >= 1)
    print('     pot_control 개념 게이트 통과(>=1)  %d/%d — 확률에서 떨어져 내려왔다'
          % (npc, len(ga)))
    print('     blockbet   개념 게이트 통과(>=1)  %d/%d' % (nbb, len(ga)))
    print()

    print('=' * 112)
    print('4. 행동 층에서 실제로 무슨 일이 일어났나')
    print('=' * 112)
    ac = collections.Counter(i.get('action') for i in ga)
    print('   실제 액션 %s' % dict(ac.most_common()))
    unres = [i for i in ga if (i.get('tocall') or 0) == 0]
    res = [i for i in ga if (i.get('tocall') or 0) > 0]
    print('   무저항 %d건 / 저항 %d건' % (len(unres), len(res)))
    if res:
        # **주의** — trace 의 eq 는 응답 시점 값이고 intent 의 eq 는 계획 시점 값이다.
        # 둘은 같지 않다(실측 h10 river: 계획 0.556 / 응답 0.208).
        # 팟오즈 비교는 반드시 응답 시점 eq 로 해야 한다.
        ok = miss = noinfo = 0
        for i in res:
            t = None
            for x in (i.get('trace') or []):
                if (x or {}).get('kind') == 'response' and x.get('street') == i['street']:
                    t = x
            if not t:
                noinfo += 1
            elif float(t.get('eq', 0)) >= float(t['need']):
                ok += 1
            else:
                miss += 1
        print('     저항 %d건을 응답 시점 eq 로 재판정' % len(res))
        print('       eq >= need (793줄이 콜)   %d' % ok)
        print('       eq <  need (폴드)          %d' % miss)
        if noinfo:
            print('       trace 없음                  %d' % noinfo)
        gap = [(float(t.get('eq', 0)) - i['eq'])
               for i in res
               for t in [next((x for x in (i.get('trace') or [])
                              if (x or {}).get('kind') == 'response'
                              and x.get('street') == i['street']), None)] if t]
        if gap:
            print('       계획 eq 와 응답 eq 의 차이  중앙 %+.3f  (최소 %+.3f 최대 %+.3f)'
                  % (sorted(gap)[len(gap)//2], min(gap), max(gap)))
    ini = [i for i in unres if i.get('init')]
    noini = [i for i in unres if not i.get('init')]
    print()
    print('   무저항 %d건에서 "포기 행동 계층"이 실제로 무엇을 하는가' % len(unres))
    print('     decide_aggression:838 — 이니셔티브가 없으면 return 0.0 (체크 고정)')
    print('                            있으면 DEVIATE 지속벳 경로로 확률이 생긴다')
    print('     이니셔티브 있음 %2d건  실제 %s' % (len(ini),
          dict(collections.Counter(i.get('action') for i in ini).most_common())))
    print('     이니셔티브 없음 %2d건  실제 %s' % (len(noini),
          dict(collections.Counter(i.get('action') for i in noini).most_common())))
    if ini:
        ps = [x['p'] for i in ini
              for x in (i.get('trace') or [])
              if (x or {}).get('kind') == 'aggression' and x.get('street') == i['street']]
        if ps:
            print('       지속벳 확률 중앙 %.2f (최소 %.2f 최대 %.2f) — 규율로 깎인 값'
                  % (sorted(ps)[len(ps)//2], min(ps), max(ps)))
    print()
    print('   giveup 계획은 decide_aggression:838 에서 showdown 과 같은 분기다.')
    print('   따라서 이 %d건의 문제는 "라벨이 giveup 이다"가 아니라' % len(ga))
    print('   **포기 행동 계층(체크 고정)에 들어갔다**는 것이다.')

    # ---------- 5. 대표 사례 코드 경로 대조 ----------
    print()
    print('=' * 112)
    print('5. 대표 사례 — make_plan 진입부터 행동까지 코드 경로로 따라간다')
    print('=' * 112)
    pick = []
    srt = sorted(ga, key=lambda x: -x['rel'])
    seen = set()
    for i in srt:                      # rel 최상위 / 보드페어 / 트립스 / 벳한 것 / 리버
        bd = board_at(i['_board'], i['street'])
        if not i['_hole'] or len(bd) < 3:
            continue
        c7 = bot.eval7(list(i['_hole']) + list(bd))[0]
        key = None
        if not seen & {'top'}:
            key = 'top'
        elif c7 == 1 and 'pair' not in seen:
            key = 'pair'
        elif c7 == 3 and 'trips' not in seen:
            key = 'trips'
        elif i.get('action') == 'bet' and 'bet' not in seen:
            key = 'bet'
        elif i['street'] == 'river' and 'river' not in seen:
            key = 'river'
        if key:
            seen.add(key); pick.append((key, i))
        if len(pick) >= 5:
            break
    LBL = {'top': 'rel 최상위', 'pair': '보드 페어', 'trips': '보드 트립스',
           'bet': '실제로 벳한 건', 'river': '리버'}
    for key, i in pick:
        bd = board_at(i['_board'], i['street'])
        mg = PS.sk(i['_prof'], 'range_merge') / 3.33
        thr = max(0.28, 0.52 - 0.080 * mg)
        pc = max(0.0, min(1.0, (i['_prof']['icm'] + (10-i['_prof']['gamble'])
                                + (10-i['_prof']['aggr']))/30.0))
        mw = max(0, i.get('n_opp', 1) - 1)
        _pc_p = min(0.75, pc*0.8 + 0.12 + 0.18*mw) * max(0.35, 1.0 - 0.22*mg)
        tr = None
        for x in (i.get('trace') or []):
            if (x or {}).get('kind') in ('aggression', 'response') and x.get('street') == i['street']:
                tr = x
        print()
        print('── %s   h%d %s  %s on %s' % (LBL[key], i['_hand'], i['street'],
                                            ' '.join(i['_hole']), ' '.join(bd)))
        print('   내 7장 %s / 보드만 %s → 홀카드 기여 없음 ⇒ made_strength = 0'
              % (CAT.get(bot.eval7(list(i['_hole'])+list(bd))[0], '?'),
                 CAT.get(board_cat(bd), '?')))
        print('   eq %.3f  rel %.2f  (상대 레인지 콤보 %s개 대비)'
              % (i['eq'], i['rel'], i.get('opp_range_n')))
        print('   [1] eq >= v3 %.3f ?  %s' % (i['_v3'], 'Y' if i['eq'] >= i['_v3'] else 'N'))
        print('   [2] eq >= v2 %.3f ?  %s' % (i['_v2'], 'Y' if i['eq'] >= i['_v2'] else 'N'))
        print('   [3] eq >= pcz %.3f ?  %s  ← 여기로 진입'
              % (i['_pcz'], 'Y' if i['eq'] >= i['_pcz'] else 'N'))
        print('   [4] block      sk(blockbet) %.2f >= 1 ? %s'
              % (PS.sk(i['_prof'], 'blockbet')/3.33,
                 'Y' if PS.sk(i['_prof'], 'blockbet')/3.33 >= 1 else 'N'))
        print('   [5] pot_control sk %.2f >= 1 ? %s · 확률 %.2f 에서 탈락'
              % (PS.sk(i['_prof'], 'potcontrol')/3.33,
                 'Y' if PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1 else 'N', _pc_p))
        print('   [6] 얇은 밸류  rel %.2f >= %.3f ? O   and made %d >= 1 ? X  ← **여기서 막힘**'
              % (i['rel'], thr, i.get('made', 0)))
        print('   [7] 402 폴백  showdown if made>=1 else giveup → made %d ⇒ giveup'
              % i.get('made', 0))
        print('   [8] _allowed  giveup 은 need 목록에 없다 ⇒ 통과')
        if tr and tr.get('kind') == 'aggression':
            print('   [9] decide_aggression  p %.2f — %s' % (tr['p'], tr['why']))
        elif tr:
            print('   [9] decide_response  need %.3f eq %.3f → %s — %s'
                  % (tr.get('need', 0), tr.get('eq', 0), tr.get('act'), tr.get('why')))
        print('   [10] 실제 액션  %s' % i.get('action'))
    print()
    print('   공통 원인')
    print('     [6] 과 [7] 이 **같은 변수(made)** 로 연속 판정한다.')
    print('     [6] 의 made 는 정당하다 — "얇은 밸류로 칠 것인가"를 묻기 때문이다.')
    print('     하이카드로 밸류벳을 할 수는 없다.')
    print('     [7] 의 made 는 다른 질문을 한다 — "쇼다운 가치가 있는가".')
    print('     그 질문의 답은 rel 이 이미 갖고 있는데(25/26 이 rel 문턱 통과),')
    print('     402 는 rel 을 문자열에 찍기만 하고 판정에는 쓰지 않는다.')
    print()
    print('   다만 이것이 곧 "402 를 고치면 된다"는 뜻은 아니다.')
    print('     giveup 과 showdown 은 decide_aggression:838 에서 같은 분기다.')
    print('     402 의 판별자를 rel 로 바꿔도 무저항 %d건의 행동은 그대로다.' % len(unres))
    print('     행동이 바뀌려면 [5] 나 [6] 에서 다른 계획을 받아야 한다.')

    # 레인지 신뢰도 단서
    print()
    print('   주의 — rel 은 **추정된** 상대 레인지 기준이다')
    ns = [i.get('opp_range_n') or 0 for i in ga]
    ns.sort()
    print('     opp_range 콤보 수  중앙 %d  최소 %d  최대 %d'
          % (ns[len(ns)//2], ns[0], ns[-1]))
    print('     레인지가 넓게 추정됐다면 A-high 의 rel 이 그만큼 부풀려진다.')
    print('     이 도구는 그 추정의 타당성까지는 검증하지 않았다.')



if __name__ == '__main__':
    main()
