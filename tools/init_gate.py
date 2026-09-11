#!/usr/bin/env python3
"""initiative=False · rel>=0.5 · made==0 집단에서 pot_control/block 이
어느 단계에서 사라졌는지 역추적한다.

plan.py 는 읽기만 한다. 새 계측을 추가하지 않는다 —
필요한 값(init·oop·rel·made·danger·n_opp·profile·trace)은 이미 전부 기록된다.

전제: rel 이 높다고 공격하거나 팟컨트롤해야 한다는 뜻이 아니다.
     묻는 것은 "이 핸드가 후보로 평가될 정보가 있었는데 어느 단계에서
     그 가능성이 사라졌나" 하나다.

검사하는 관문 (plan.py 의 실제 순서)
------------------------------------
make_plan · eq >= pcz 분기 안
  [B] block        oop and not initiative and 0.25 <= rel <= 0.80
                   block_p = clamp(0, 0.42, (0.12+0.05*aggr-0.03*bluff)*(1+0.4*dang))
                   fish 원형이면 ×0.25
                   발동: sk('blockbet') >= 1 and rng < block_p
  [P] pot_control  _pc_p = min(0.75, pc*0.8+0.12+0.18*mw) * max(0.35, 1-0.22*_mg)
                   pc = clamp(0,1,(icm + (10-gamble) + (10-aggr))/30)
                   발동: sk('potcontrol') >= 1 and rng < _pc_p
  [V] 얇은 밸류    rel >= max(0.28, 0.52-0.080*_mg) and made >= 1
  [F] 402 폴백     showdown if made>=1 else giveup

decide_aggression
  [G] giveup/showdown 분기  `if not initiative: return 0.0`  ← 하드 게이트

initiative 가 하드 게이트인 분기는 [G] 하나뿐이다. 이 도구가 그것도 센다.

난수는 굴리지 않는다. 확률값과 게이트 통과 여부까지만 낸다.

사용: python3 tools/init_gate.py [collected*.jsonl ...]
"""
import os, sys, glob, collections, math

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot, archetypes as A
import persona as PS
import plan as PL
from sb_calib import load, branch_of
from sb_114 import thresholds
from tag_draws import board_at



def fired(i):
    """eq>=pcz 분기 **안에서** 어느 관문이 실제로 발화했는지 why 로 읽는다.

    최종 plan 으로 세면 안 된다 — _allowed(plan.py:1491)가 뒤에서
    block → value_2street, pot_control → showdown 으로 강등할 수 있어서
    발화한 관문이 최종 라벨에서 사라진다.
    """
    pre = '%s: ' % i['street']
    w = [x[len(pre):] for x in (i['why'] if isinstance(i['why'], list) else [i['why']])
         if x.startswith(pre)]
    for x in w:
        if '블락벳으로 가격 통제' in x:
            return 'block'
        if x.startswith('중간강도(') and '팟 컨트롤' in x:
            return 'pot_control'
        if x.startswith('중간강도(') and '얇은 밸류' in x:
            return 'thin_value'
        if x.startswith('중간강도이나'):
            return 'fallback402'
    return None


def block_p(i):
    """plan.py:441 의 block_p 를 그대로 재현."""
    prof = i['_prof']
    if not (i.get('oop') and not i.get('init') and 0.25 <= i['rel'] <= 0.80):
        return 0.0, '진입조건 불충족'
    p = 0.12 + 0.05*prof['aggr'] - 0.03*prof.get('bluff', 5)
    p *= (1 + 0.4*(i.get('danger') or 0.0))
    tag = A.ARCHETYPES.get(prof.get('type'), (0,)*6 + ('reg', ''))
    if len(tag) > 6 and tag[6] == 'fish':
        p *= 0.25
    return max(0.0, min(0.42, p)), 'ok'


def pc_p(i):
    """plan.py:455 의 _pc_p 를 그대로 재현."""
    prof = i['_prof']
    pc = max(0.0, min(1.0, (prof['icm'] + (10-prof['gamble']) + (10-prof['aggr']))/30.0))
    made = i.get('made', 0)
    mw = max(0, i.get('n_opp', 1) - 1)
    if made >= 5:
        mw = 0
    elif made >= 3:
        mw = min(mw, 1)
    mg = PS.sk(prof, 'range_merge')/3.33
    return min(0.75, pc*0.8 + 0.12 + 0.18*mw) * max(0.35, 1.0 - 0.22*mg)


def cf_no_gate(i):
    """[G] 의 `if not initiative: return 0.0` 이 없었다면 나왔을 p.

    그 뒤 코드는 cbet_freq × 규율 이다. cbet_freq 의 docstring 은
    '**이니셔티브 보유자의** 지속벳 빈도'라고 못박고 있으므로,
    이 수치는 '기존 함수가 뱉을 값'이지 '옳은 값'이 아니다. 그대로 적는다.
    """
    prof = i['_prof']
    bd = board_at(i['_board'], i['street'])
    cf = PL.cbet_freq(prof, bd, i.get('n_opp', 1), i['street'], bool(i.get('oop')),
                      i['rel'], i.get('opp_est'), range_adv=i.get('range_adv') or 0.0)
    if prof.get('concepts'):
        cf *= max(0.05, 1.0 - 0.085*PS.temper(prof, 'discipline', 5.0))
    return max(0.0, min(0.9, cf))


def main():
    paths = sys.argv[1:]
    if not paths:
        paths = sorted(glob.glob(os.path.join(D, 'collected_p*.jsonl'))) \
                or [os.path.join(D, 'collected.jsonl')]
    rows = load(paths)
    for i in rows:
        i['_branch'] = branch_of(i)
        i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)
    mp = [i for i in rows if i['_branch']]
    print('표본: %d파일 · make_plan 원본 %d건 (refresh 가 덮은 %d건 제외)'
          % (len(paths), len(mp), getattr(load, 'dropped', 0)))
    print()

    # ---------- 1. 모집단 ----------
    pop = [i for i in mp if (not i.get('init')) and i['rel'] >= 0.5
           and i.get('made', 0) == 0]
    print('=' * 104)
    print('1. 모집단  initiative=False · rel>=0.5 · made==0')
    print('=' * 104)
    print('   n = %d  (make_plan 원본의 %.1f%%)' % (len(pop), 100*len(pop)/max(1, len(mp))))
    print('   계획 분포 %s' % dict(collections.Counter(i['plan'] for i in pop).most_common()))
    print('   실제 액션 %s' % dict(collections.Counter(i.get('action') for i in pop).most_common()))
    print('   OOP %d / IP %d'
          % (sum(1 for i in pop if i.get('oop')), sum(1 for i in pop if not i.get('oop'))))
    print('   물리 outs 분포 %s'
          % dict(sorted(collections.Counter(i['outs_true'] for i in pop).items())))
    print()
    # eq>=pcz 로 들어온 것만이 [B]/[P] 관문을 지난다
    inpcz = [i for i in pop if i['_branch'] == 'above']
    print('   그중 eq >= pcz 분기로 들어간 건 %d — [B]/[P] 관문을 지난 것은 이들뿐'
          % len(inpcz))
    print('   나머지 %d건은 애초에 다른 분기(semibluff/bluff/최종 else)로 갔다'
          % (len(pop) - len(inpcz)))
    print()


    # ---------- 2-0. block 은 도달 가능한가 ----------
    print('=' * 104)
    print('2-0. [B] block 이 make_plan 을 살아서 나오는가')
    print('=' * 104)
    print('   plan.py:447 은 **독립된 if** 다. elif 체인의 일부가 아니다.')
    print('       447  if sk(blockbet) >= 1 and rng.random() < block_p:')
    print("       448      plan = 'block'; why.append('OOP 중간강도 → 블락벳으로...')")
    print('       449~455  (주석과 _mg/_pc_p 계산)')
    print('       456  if sk(potcontrol) >= 1 and rng.random() < _pc_p:')
    print("       457      plan = 'pot_control'")
    print('       458  elif rel >= ... and made >= 1:')
    print("       459      plan = 'value_2street'")
    print('       461  else:')
    print("       465      plan = 'showdown' if made >= 1 else 'giveup'")
    print('   456~467 의 if/elif/else 는 **무조건 실행되고 무조건 plan 을 재할당**한다.')
    print('   따라서 448 의 plan = "block" 은 항상 덮인다.')
    print()
    # 전수 확인 — 정제 전 원본으로 본다(발화 자체는 refresh 와 무관하다)
    allr = load(paths, pure=False)
    nfire = nboth = nraw = 0
    over = collections.Counter()
    final = collections.Counter()
    for i in allr:
        wall = i['why'] if isinstance(i['why'], list) else [i['why']]
        if any('블락벳으로 가격 통제' in x for x in wall):
            nraw += 1
        pre = '%s: ' % i['street']
        w = [x[len(pre):] for x in
             (i['why'] if isinstance(i['why'], list) else [i['why']])
             if x.startswith(pre)]
        if not any('블락벳으로 가격 통제' in x for x in w):
            continue
        nfire += 1
        final[i['plan']] += 1
        ch = [x for x in w if x.startswith(('중간강도(', '중간강도이나'))]
        if ch:
            nboth += 1
            over[ch[0].split('→')[-1].strip()] += 1
    nb = sum(1 for i in allr if i['plan'] == 'block')
    print('   전 intent %d건 (정제 전)' % len(allr))
    print('   block 발화(그 스트리트 why 기준)            %d건' % nfire)
    print('   그중 같은 스트리트에 456 체인 why 가 함께 붙음 %d건 (%.0f%%)'
          % (nboth, 100*nboth/max(1, nfire)))
    print('   덮어쓴 결과 %s' % dict(over.most_common()))
    print('   최종 plan 분포 %s' % dict(final.most_common()))
    print('   **전 표본에서 plan == "block" 인 intent: %d건**' % nb)
    print()
    if nb == 0 and nfire > 0:
        print('   → block 은 도달 불가 분기다. PLANS·SIZING·_allowed·decide_aggression 에')
        print('     각각 전용 처리가 있지만 make_plan 을 살아서 나오지 못한다.')
        print('     "확률이 작아서 안 나온다"가 아니라 **나왔다가 지워진다**.')
        print('     이 집단(oop·not initiative·중간강도)을 위해 만든 분기가')
        print('     그 집단에서 한 번도 실행되지 않는다.')
    print()
    print('   주의 — 위 집계는 반드시 스트리트 접두사로 걸러야 한다.')
    print('     걸르지 않으면 block why 가 다음 스트리트 기록에 승계돼')
    print('     발화 건수가 부풀려진다 (같은 입력에서 미필터 %d건 vs 필터 %d건).'
          % (nraw, nfire))
    print()

    # ---------- 2. block 관문 ----------
    print('=' * 104)
    print('2. [B] block — 진입 조건이 `oop and not initiative` 라 이 집단을 위한 분기다')
    print('=' * 104)
    elig, noelig = [], collections.Counter()
    for i in inpcz:
        if not i.get('oop'):
            noelig['IP 라 진입 불가'] += 1
        elif not (0.25 <= i['rel'] <= 0.80):
            noelig['rel %.2f 이 0.25~0.80 밖' % i['rel']] += 1
        else:
            elig.append(i)
    print('   진입 가능 %d / 불가 %d' % (len(elig), sum(noelig.values())))
    for k, v in noelig.most_common(6):
        print('      %-28s %d' % (k, v))
    if elig:
        gate = [i for i in elig if PS.sk(i['_prof'], 'blockbet')/3.33 >= 1]
        print('   진입 가능 %d건 중 sk(blockbet)>=1 통과 %d (%.0f%%)'
              % (len(elig), len(gate), 100*len(gate)/len(elig)))
        ps = [block_p(i)[0] for i in gate]
        if ps:
            ps.sort()
            print('   그 %d건의 block_p  중앙 %.3f  최소 %.3f  최대 %.3f  (상한 0.42)'
                  % (len(ps), ps[len(ps)//2], ps[0], ps[-1]))
            print('   기대 발동 건수 Σp = %.2f / %d' % (sum(ps), len(gate)))
            got = sum(1 for i in gate if fired(i) == 'block')
            fin = sum(1 for i in gate if i['plan'] == 'block')
            print('   실측 block 발화 %d건 (최종 라벨이 block 인 것은 %d건 —'
                  % (got, fin))
            print('     차이가 나면 _allowed 가 value_2street 으로 강등한 것이다)')
            q = 1.0
            for x in ps:
                q *= (1 - x)
            print('   0건이 나올 확률 = ∏(1-p_i) = %.3f' % q)
            print('     (Σp 만으로 포아송 근사하면 %.3f 이 나온다. 개별 p 가 다르므로'
                  % math.exp(-sum(ps)))
            print('      정확값은 위의 곱이다. 아래 2-0 을 보면 이 계산 자체가 무의미하다)')
    print()

    # ---------- 3. pot_control 관문 ----------
    print('=' * 104)
    print('3. [P] pot_control — 개념 게이트에서 떨어졌나, 확률에서 떨어졌나')
    print('=' * 104)
    g = [i for i in inpcz if PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1]
    ng = [i for i in inpcz if PS.sk(i['_prof'], 'potcontrol')/3.33 < 1]
    print('   sk(potcontrol)>=1 (원개념 3.33) 통과 %d / 탈락 %d' % (len(g), len(ng)))
    if ng:
        print('      탈락군 원개념 중앙 %.2f'
              % sorted(PS.sk(i['_prof'], 'potcontrol') for i in ng)[len(ng)//2])
    if g:
        ps = sorted(pc_p(i) for i in g)
        print('   통과군 %d건의 _pc_p  중앙 %.3f  최소 %.3f  최대 %.3f  (상한 0.75)'
              % (len(g), ps[len(ps)//2], ps[0], ps[-1]))
        print('   기대 발동 Σp = %.2f / %d   실측 발화 %d건 (최종 라벨 %d건)'
              % (sum(ps), len(g), sum(1 for i in g if fired(i) == 'pot_control'),
                 sum(1 for i in g if i['plan'] == 'pot_control')))
        print()
        print('   _pc_p 를 구성 요소로 분해 (평균 기여)')
        pcv = [max(0.0, min(1.0, (i['_prof']['icm'] + (10-i['_prof']['gamble'])
                                  + (10-i['_prof']['aggr']))/30.0)) for i in g]
        mgv = [PS.sk(i['_prof'], 'range_merge')/3.33 for i in g]
        mwv = [max(0, i.get('n_opp', 1)-1) for i in g]
        print('      pc  (icm·gamble·aggr)  평균 %.3f → 기여 0.8×pc = %.3f'
              % (sum(pcv)/len(pcv), 0.8*sum(pcv)/len(pcv)))
        print('      상수항                                    +0.120')
        print('      mw  (다인원)           평균 %.2f → 기여 %.3f'
              % (sum(mwv)/len(mwv), 0.18*sum(mwv)/len(mwv)))
        print('      머징 감쇠 max(0.35, 1-0.22*mg)  mg 평균 %.2f → ×%.3f'
              % (sum(mgv)/len(mgv), max(0.35, 1-0.22*sum(mgv)/len(mgv))))
        print('      → rel 도 eq 도 들어가지 않는다. 핸드 강도와 무관한 확률이다.')
    print()

    # ---------- 4. decide_aggression 하드 게이트 ----------
    print('=' * 104)
    print('4. [G] decide_aggression 의 initiative 하드 게이트')
    print('=' * 104)
    print('   initiative 를 읽는 분기 전수 (plan.py:836~931)')
    print('      giveup/showdown   `if not initiative: return 0.0`      ← 하드 게이트')
    print('      bluff/semibluff   `if not initiative and oop:` 연속 감쇠 + probe 개념')
    print('      trap              항상 0.0 (initiative 무관)')
    print('      block             읽지 않음')
    print('      pot_control       읽지 않음')
    print('      value             읽지 않음')
    print('   → initiative 가 **하드 게이트인 분기는 giveup/showdown 하나뿐**이다.')
    print('     블러프 계획에는 동크 억제와 probe 개념이라는 연속 처리가 있는데')
    print('     포기 계획에는 그 대응물이 없다.')
    print()
    hit = [i for i in pop if i['plan'] in ('giveup', 'showdown')
           and (i.get('tocall') or 0) == 0]
    print('   이 게이트에 실제로 걸린 건(무저항 · 계획 giveup/showdown) %d건' % len(hit))
    if hit:
        print('     실제 액션 %s' % dict(collections.Counter(i.get('action') for i in hit).most_common()))
        print('     OOP %d / IP %d' % (sum(1 for i in hit if i.get('oop')),
                                       sum(1 for i in hit if not i.get('oop'))))
        print('     probe 개념(원개념) 중앙 %.2f'
              % sorted(PS.sk(i['_prof'], 'probe') for i in hit)[len(hit)//2])
        cf = sorted(cf_no_gate(i) for i in hit)
        print()
        print('   반사실 CF-I1: `if not initiative: return 0.0` 만 제거했다면')
        print('     기존 코드가 그다음 줄에서 계산했을 p')
        print('       중앙 %.3f  최소 %.3f  최대 %.3f' % (cf[len(cf)//2], cf[0], cf[-1]))
        print('       기대 벳 건수 Σp = %.2f / %d  (현재는 0)' % (sum(cf), len(hit)))
        print('     **주의** — 그 줄은 cbet_freq 다. docstring 이 "이니셔티브')
        print('     보유자의 지속벳 빈도"라고 못박은 함수다. 이니셔티브가 없는')
        print('     자리에 그대로 쓰는 것은 의미가 맞지 않는다. 위 수치는')
        print('     "기존 함수가 뱉을 값"이지 "옳은 값"이 아니다.')
    print()

    # ---------- 5. 관문별 소실 회계 ----------
    print('=' * 104)
    print('5. 어느 단계에서 가능성이 사라졌는가 — 회계')
    print('=' * 104)
    acct = collections.Counter()
    for i in inpcz:
        f = fired(i)
        if f == 'block':
            acct['[B] block 발화'] += 1
        elif f == 'pot_control':
            acct['[P] pot_control 발화'] += 1
        elif f == 'thin_value':
            acct['[V] 얇은 밸류 발화'] += 1
        else:
            bp, why = block_p(i)
            bg = PS.sk(i['_prof'], 'blockbet')/3.33 >= 1
            pg = PS.sk(i['_prof'], 'potcontrol')/3.33 >= 1
            if not bg and not pg:
                acct['개념 게이트 둘 다 탈락'] += 1
            elif why != 'ok' and not pg:
                acct['block 진입불가 + potcontrol 개념 탈락'] += 1
            elif why != 'ok':
                acct['block 진입불가 → pot_control 확률 탈락'] += 1
            elif not pg:
                acct['block 확률 탈락 + potcontrol 개념 탈락'] += 1
            else:
                acct['block·pot_control 둘 다 확률에서 탈락'] += 1
    tot = sum(acct.values())
    for k, v in acct.most_common():
        print('   %-42s %3d (%4.1f%%)' % (k, v, 100*v/max(1, tot)))
    print()
    dg = [i for i in inpcz if fired(i) and fired(i) != 'fallback402'
          and i['plan'] != {'block': 'block', 'pot_control': 'pot_control',
                            'thin_value': 'value_2street'}[fired(i)]]
    print('   _allowed 강등 실측: 발화한 관문과 최종 라벨이 다른 건 %d' % len(dg))
    for i in dg:
        print('      h%-5d %-5s %s 발화 → 최종 %s' % (i['_hand'], i['street'],
                                                   fired(i), i['plan']))
    print()
    print('   → 개념을 갖고도 확률에서 떨어진 것과, 개념 자체가 없는 것은')
    print('     성격이 다르다. 전자는 calibration, 후자는 필드 분포 문제다.')


if __name__ == '__main__':
    main()
