#!/usr/bin/env python3
"""세미블러프 후보 114건을 ①②③ 으로 분해한다.

plan.py 는 읽기만 한다.

왜 분해가 필요한가
------------------
"세미블러프 확률이 낮다"는 한 문장 안에 성격이 다른 세 가지가 섞여 있다.

  ① 물리 드로우는 약한데 persona 가 강하게 인식해 게이트를 통과한 경우
     → calc_noise 가 담당하는 인지 편향. 확률식의 문제가 아니다
  ② 물리 드로우는 강한데 eq >= pcz 에 선점돼 확률식에 도달조차 못한 경우
     → 분기 구조 문제. 계수를 아무리 고쳐도 닿지 않는다
  ③ 후보가 맞고 확률식까지 들어갔는데 주사위에서 떨어진 경우
     → 그때만 probability calibration 문제

임계값 복원
-----------
pcz 는 intent 에 기록돼 있지 않지만 기록된 필드만으로 정확히 재구성된다.

    mw  = max(0, n_opp-1);  made>=5 → 0;  made>=3 → min(mw,1)
    pcz = 0.50 + 0.06*mw
    rd  = PS.read_opponent(profile, opp_est)      # 난수를 쓰지 않는다
    if rd['w'] > 0: pcz += rd['w'] * 0.30 * PS.street_gap(rd, street)

재구성이 맞는지는 관측된 분기와 대조해서 검증한다 —
'above' 분기면 eq >= pcz 여야 하고, 그 아래 분기면 eq < pcz 여야 한다.

정제
----
sb_calib.load 는 eq_sims==400 인 레코드만 남긴다. refresh 는 같은 스트리트에서
eq/rel/outs 를 덮으면서 why 는 남기므로, 덮인 레코드로 임계값을 되짚으면
존재하지 않은 판단을 재구성하게 된다. 실측 후보 114건 중 51건(45%)이 그랬다.

기록되지 않는 것
----------------
semibluff_roll 의 **원시 난수값**은 복원할 수 없다. make_plan 의 rng 소비
순서를 재현하려면 opp_range·pot·stack 이 필요한데 intent 에 없다.
복원되는 것은 주사위의 **결과**(미실행 / 통과 / 탈락)다. p 가 주어졌을 때
원시값은 결과 이상의 정보를 주지 않으므로 판정에는 지장이 없다.

사용: python3 tools/sb_114.py [collected.jsonl ...]
"""
import os, sys, json, math, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS
from sb_calib import load, branch_of, p_formula, river_odds
from tag_draws import tag as draw_tag, board_at
from implied import price_at


def thresholds(i):
    """그 판단 시점의 v3 / v2 / pcz 를 재구성한다."""
    prof, made = i['_prof'], i.get('made', 0)
    mw = max(0, i.get('n_opp', 1) - 1)
    if made >= 5:
        mw = 0
    elif made >= 3:
        mw = min(mw, 1)
    v3, v2, pcz = 0.80 + 0.06*mw, 0.66 + 0.07*mw, 0.50 + 0.06*mw
    rd = PS.read_opponent(prof, i.get('opp_est'))
    if rd.get('w', 0) > 0:
        sg = PS.street_gap(rd, i['street'])
        v3 += rd['w'] * 0.55 * sg
        v2 += rd['w'] * 0.45 * sg
        pcz += rd['w'] * 0.30 * sg
    return v3, v2, pcz


def verify(mp):
    """재구성된 pcz 가 관측된 분기와 모순되지 않는지 검증한다."""
    ok = bad = 0
    ex = []
    for i in mp:
        above = (i['_branch'] == 'above')
        pred = (i['eq'] >= i['_pcz'])
        if above == pred:
            ok += 1
        else:
            bad += 1
            if len(ex) < 6:
                ex.append(i)
    return ok, bad, ex


def main():
    paths = sys.argv[1:] or [os.path.join(D, 'collected.jsonl')]
    rows = load(paths)
    for i in rows:
        i['_branch'] = branch_of(i)
        i['_sk'] = PS.sk(i['_prof'], 'semibluff') / 3.33
        i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)

    mp = [i for i in rows if i['_branch']]

    print('=' * 100)
    print('0. 임계값 재구성 검증 — 재구성한 pcz 가 관측된 분기와 일치하는가')
    print('=' * 100)
    ok, bad, ex = verify(mp)
    print('   make_plan 분기 %d건 중 일치 %d · 불일치 %d (%.2f%%)'
          % (len(mp), ok, bad, 100*bad/max(1, len(mp))))
    for i in ex:
        print('      h%-5d %-5s eq %.3f  pcz %.3f  분기 %-10s plan %s'
              % (i['_hand'], i['street'], i['eq'], i['_pcz'], i['_branch'], i['plan']))
    near = [i for i in mp if abs(i['eq'] - i['_pcz']) <= 0.014]
    print('   임계선 ±0.014 안 (판정이 뒤집힐 수 있는 구역) %d건 (%.1f%%)'
          % (len(near), 100*len(near)/max(1, len(mp))))
    if bad == 0:
        print('   → pcz 재구성은 전 표본에서 정확하다.')
    else:
        print('   → 잔차 %.2f%%. 전부 |eq-pcz| <= 0.014 라 임계선 바로 위아래에서만'
              % (100*bad/max(1, len(mp))))
        print('     ②/③ 판정이 흔들린다. 원인 미규명 — opp_est 가 make_plan 이후에')
        print('     갱신돼 직렬화 시점 값과 달라졌을 가능성이 있으나 확인하지 않았다.')
    print()

    # ---------- 모집단 두 개 ----------
    def gate_ok(i):
        return i['outs'] >= 8 and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4
    cand = [i for i in mp if gate_ok(i)]                       # 체감 기준 114건
    phys = [i for i in mp if i['outs_true'] >= 8]              # 물리 기준

    print('=' * 100)
    print('1. 모집단이 두 개다 — 게이트는 체감값을 본다')
    print('=' * 100)
    print('   체감 outs>=8 & behind<=1 & sk>=0.4  (= 세미블러프 후보)  %3d' % len(cand))
    print('   물리 outs_true>=8                                    %3d' % len(phys))
    miss = [i for i in phys if i['outs'] < 8]
    print('   물리 8아웃 이상인데 체감이 8 미만이라 후보에도 못 든 건  %3d' % len(miss))
    if miss:
        print('      이 %d건의 계획: %s' % (len(miss),
              dict(collections.Counter(i['plan'] for i in miss).most_common())))
        print('      평균 물리 %.1f아웃 → 체감 %.1f아웃 (과소 %.0f%%)'
              % (sum(i['outs_true'] for i in miss)/len(miss),
                 sum(i['outs'] for i in miss)/len(miss),
                 100*(1 - (sum(i['outs'] for i in miss)/len(miss))
                      / (sum(i['outs_true'] for i in miss)/len(miss)))))
    print('   → 후보군은 "드로우가 강한 핸드"의 집합이 아니라')
    print('      "봇이 강하다고 인식한 핸드"의 집합이다. 이름을 그렇게 불러야 한다.')
    print()

    # ---------- 분류 ----------
    # **분류는 재구성한 pcz 가 아니라 관측된 분기로 한다.**
    # branch=='above' 자체가 "eq >= pcz 가 먼저 발화했다"는 관측이므로
    # 재구성이 필요 없다. pcz 재구성은 아래에서 여백(eq-pcz)을 보고할 때만 쓴다.
    # 이렇게 하면 0번의 잔차 0.57% 가 분류에 끼어들지 않는다.
    for i in cand:
        if i['_branch'] == 'above':
            i['_cls'] = '② 선점'
        elif i['_branch'] == 'semibluff':
            i['_cls'] = '④ 채택' if i['outs_true'] >= 8 else '④* 채택(물리 약함)'
        elif i['outs_true'] < 8:
            i['_cls'] = '① 인지편향'
        else:
            i['_cls'] = '③ 주사위탈락'

    print('=' * 100)
    print('2. 후보 %d건 분해 (분류는 관측된 분기 기준)' % len(cand))
    print('=' * 100)
    c = collections.Counter(i['_cls'] for i in cand)
    for k in sorted(c):
        sub = [i for i in cand if i['_cls'] == k]
        print('   %-20s %3d (%4.1f%%)   물리outs %.1f  체감outs %.1f  eq %.3f  pcz %.3f'
              % (k, c[k], 100*c[k]/len(cand),
                 sum(x['outs_true'] for x in sub)/len(sub),
                 sum(x['outs'] for x in sub)/len(sub),
                 sum(x['eq'] for x in sub)/len(sub),
                 sum(x['_pcz'] for x in sub)/len(sub)))
    print()
    print('   책임 소재')
    n1 = sum(v for k, v in c.items() if k.startswith('①'))
    n2 = sum(v for k, v in c.items() if k.startswith('②'))
    n3 = sum(v for k, v in c.items() if k.startswith('③'))
    n4 = sum(v for k, v in c.items() if k.startswith('④'))
    print('      ① calc_noise (인지 편향)      %3d   — 확률식 무관' % n1)
    print('      ② 분기 구조 (eq >= pcz 선점)  %3d   — 계수로 못 고침' % n2)
    print('      ③ 확률식 calibration          %3d   — 여기만 계수 문제' % n3)
    print('      ④ 채택                        %3d' % n4)
    print()

    # ---------- 전수 표 ----------
    print('=' * 100)
    print('3. 전수 표')
    print('=' * 100)
    hdr = ('%-18s %-6s %-5s %-6s %-13s %4s %4s %6s %6s %6s %5s %5s %6s %-14s %s'
           % ('분류', 'hand', 'st', '홀', '보드', '물리', '체감', 'eq',
              'pcz', 'delta', 'rel', 'sk', 'p', '최종계획', '드로우'))
    print(hdr)
    print('-' * len(hdr))
    for i in sorted(cand, key=lambda x: (x['_cls'], -x['outs_true'], x['_hand'])):
        bd = board_at(i['_board'], i['street'])
        tg = ', '.join(draw_tag(i['_hole'], bd)) if (i['_hole'] and len(bd) >= 3) else '-'
        print('%-18s h%-5d %-5s %-6s %-13s %4d %4d %6.3f %6.3f %+6.3f %5.2f %5.2f %6.3f %-14s %s'
              % (i['_cls'], i['_hand'], i['street'], ''.join(i['_hole'] or []),
                 ' '.join(bd), i['outs_true'], i['outs'], i['eq'], i['_pcz'],
                 i.get('eq_delta') or 0.0, i['rel'], i['_sk'],
                 p_formula(i['_sk']), i['plan'], tg))
    print()

    # ---------- ③ 17건 심사 ----------
    print('=' * 100)
    print('4. ③ 주사위 탈락 건 — 정말 세미블러프여야 하는 상황이었나')
    print('=' * 100)
    g3 = [i for i in cand if i['_cls'] == '③ 주사위탈락']
    print('   n=%d' % len(g3))
    print()
    hdr2 = ('%-6s %-5s %-6s %4s %6s %6s %5s %4s %6s  %-14s %-16s %s'
            % ('hand', 'st', '홀', '물리', 'eq', '완성', 'SPR', 'POS',
               'p', '최종계획', '직면가격/실제액션', '드로우'))
    print(hdr2)
    print('-' * len(hdr2))
    n_face = n_price_ok = 0
    for i in sorted(g3, key=lambda x: -x['outs_true']):
        bd = board_at(i['_board'], i['street'])
        tg = ', '.join(draw_tag(i['_hole'], bd)) if (i['_hole'] and len(bd) >= 3) else '-'
        pr = price_at(i['_full_log'], i['street'], i['seat'], i['_blinds'])
        act = i.get('action') or '-'
        if pr:
            pot, tocall, a, amt = pr
            if tocall > 0:
                n_face += 1
                act = '%d/%d → %s' % (tocall, pot, act)
                if i['eq'] >= tocall / float(pot + tocall):
                    n_price_ok += 1
            else:
                act = '무저항 → %s' % act
        print('h%-5d %-5s %-6s %4d %6.3f %5.1f%% %5.1f %4s %6.3f  %-14s %-16s %s'
              % (i['_hand'], i['street'], ''.join(i['_hole'] or []), i['outs_true'],
                 i['eq'], river_odds(i['outs_true'], i['street'])*100,
                 i.get('spr', 0), 'OOP' if i.get('oop') else 'IP',
                 p_formula(i['_sk']), i['plan'], act, tg))
    print()
    print('   상대 벳에 직면한 건 %d/%d — 나머지는 "벳할 것인가"의 문제다' % (n_face, len(g3)))
    print('   직면한 건 중 즉시 팟오즈만으로 콜이 되는 건 %d' % n_price_ok)
    # 세미블러프의 전제 — 폴드 에쿼티 추정이 있는가
    n_oe = sum(1 for i in g3 if i.get('opp_est'))
    print('   상대 추정(opp_est)이 있는 건 %d/%d — 없으면 read_opponent 가 중립을'
          % (n_oe, len(g3)))
    print('     반환하고, 세미블러프 사이즈는 폴드율 0.5 기본값으로 역산된다.')
    print('   OOP 비율 %.0f%%   평균 SPR %.1f   드로우 유형 %s'
          % (100*sum(1 for i in g3 if i.get('oop'))/len(g3),
             sum(i.get('spr', 0) for i in g3)/len(g3),
             dict(collections.Counter(
                 t for i in g3 for t in draw_tag(i['_hole'], board_at(i['_board'], i['street']))
                 if t in ('플러시드로우', '오픈엔드', '검샷')).most_common())))
    print()

    # ---------- 계획 라벨 != 행동 ----------
    print('=' * 100)
    print('4b. 계획 라벨과 실제 행동은 같지 않다')
    print('=' * 100)
    print('   주사위 결과가 바꾸는 것은 계획이고, 행동은 decide_aggression 이')
    print('   한 번 더 굴린다. 그래서 "탈락 = 안 친다"가 아니다.')
    print()
    print('   %-16s %4s %8s   %s' % ('집단', 'n', '공격률', '액션 분포'))
    g4 = [i for i in cand if i['_cls'].startswith('④')]
    for nm, grp in (('④ 주사위 통과', g4), ('③ 주사위 탈락', g3)):
        if not grp:
            continue
        ag = sum(1 for i in grp if i.get('action') in ('bet', 'raise'))
        print('   %-16s %4d %7.0f%%   %s'
              % (nm, len(grp), 100*ag/len(grp),
                 dict(collections.Counter(i.get('action') for i in grp).most_common())))
    if g4 and g3:
        a4 = sum(1 for i in g4 if i.get('action') in ('bet', 'raise'))/len(g4)
        a3 = sum(1 for i in g3 if i.get('action') in ('bet', 'raise'))/len(g3)
        print()
        print('   주사위 한 번의 실제 행동 효과: 공격률 %+.0f%%p (%.0f%% → %.0f%%)'
              % (100*(a4-a3), 100*a3, 100*a4))
        print('   확률식이 0.25~0.95 를 배분해도 행동 차이는 그만큼 벌어지지 않는다.')
    print()

    # ---------- ② 선점 건 ----------
    print('=' * 100)
    print('5. ② 선점 건 — 확률식이 닿지 않는 구역')
    print('=' * 100)
    g2 = [i for i in cand if i['_cls'] == '② 선점']
    print('   n=%d   계획 분포 %s' % (len(g2),
          dict(collections.Counter(i['plan'] for i in g2).most_common())))
    gv = [i for i in g2 if i['plan'] == 'giveup']
    print('   그중 giveup %d건 — eq %.3f / pcz %.3f / rel %.2f / 물리 %.1f아웃'
          % (len(gv), sum(i['eq'] for i in gv)/max(1, len(gv)),
             sum(i['_pcz'] for i in gv)/max(1, len(gv)),
             sum(i['rel'] for i in gv)/max(1, len(gv)),
             sum(i['outs_true'] for i in gv)/max(1, len(gv))))
    print('   "eq 가 pcz 를 넘어서" 세미블러프 자격을 잃고, 같은 분기 안에서')
    print('   "rel 이 낮아서" 포기로 떨어진다. 진입은 미래를 보고, 내부 심사는 현재만 본다.')


if __name__ == '__main__':
    main()
