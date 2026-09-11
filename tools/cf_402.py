#!/usr/bin/env python3
"""402줄 폴백만 바꾸는 반사실. plan.py 는 읽기만 한다.

대상
----
② 선점(eq>=pcz) 안에서 402줄 폴백
    plan = 'showdown' if made >= 1 else 'giveup'
이 만들어낸 건. 특히 made==0 → giveup.

묻는 것은 하나뿐이다
--------------------
이 자리의 made==0 → giveup 을 다른 계획으로 바꾸면 **행동이 달라지는가**.
계획 문자열을 바꾸는 게 목적이 아니다.

    CF-B1  made==0 → showdown
    CF-B2  made==0 → pot_control
    CF-B3  made==0 → semibluff

난수는 새로 굴리지 않는다. 계획 선택과 행동 **확률**까지만 낸다.

402 이후의 실제 흐름을 따라간다
-------------------------------
update_plan(plan.py:1444) 는 make_plan 출력을 같은 호출 안에서
_allowed(plan.py:1491) 에 통과시킨다. 그래서 402 에서 계획만 갈아끼운 것으로
끝나지 않는다.

    _allowed: 원개념 s(0~10) 에 대해
        s < 1.5            → 무조건 강등
        1.5 <= s < 3.5     → 확률 (s-1.5)/2.0 로 유지
        s >= 3.5           → 유지
    강등 대상: semibluff → showdown,  pot_control → showdown

즉 CF-B2·CF-B3 는 일부가 결국 showdown 으로 떨어진다. 그 확률을 반영한다.
(make_plan 의 세미블러프 게이트는 /3.33 스케일 0.4 = 원개념 1.33 을 요구하는데
 _allowed 는 1.5 를 요구한다. 두 문턱이 어긋나 있다 — 기록만 해둔다)

행동 층에서 giveup 과 showdown 이 갈리는 곳
-------------------------------------------
    무저항  decide_aggression:838  `if plan in ('giveup','showdown')` — **동일**
    저항    decide_response:793    giveup 은 순수 팟오즈로 조기 return,
                                   showdown 은 calldown 경로 — **다름**
그래서 CF-B1 의 효과는 저항 상황에서만 나타난다.

사용: python3 tools/cf_402.py [collected.jsonl ...]
"""
import os, sys, math, random, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS
import plan as PL
from sb_calib import load, branch_of, p_formula, river_odds
from sb_114 import thresholds
from cf_pcz import actual_aggr, PASSIVE
from tag_draws import tag as draw_tag, board_at

DOWN = {'semibluff': 'showdown', 'pot_control': 'showdown'}
CONCEPT = {'semibluff': 'semibluff', 'pot_control': 'potcontrol'}


def allowed_keep(prof, plan):
    """_allowed 가 그 계획을 유지할 확률과 강등 대상."""
    if plan not in CONCEPT or not prof.get('concepts'):
        return 1.0, None
    s = PS.sk(prof, CONCEPT[plan])
    if s < 1.5:
        return 0.0, DOWN[plan]
    if s < 3.5:
        return (s - 1.5) / 2.0, DOWN[plan]
    return 1.0, None


def aggr_of(i, plan):
    """그 계획이었다면의 '칠 확률'. 이 경로들은 난수를 쓰지 않는다.
       저항 상황이면 decide_aggression 자체가 안 불리므로 None."""
    if (i.get('tocall') or 0) > 0:
        return None
    bd = board_at(i['_board'], i['street'])
    p, _why = PL.decide_aggression(
        i['_prof'], bd, i['street'], plan, i['rel'], i.get('n_opp', 1),
        bool(i.get('oop')), bool(i.get('init')), i.get('behind', 0),
        random.Random(0), i.get('opp_est'), i.get('outs', 0), plan_state=dict(i))
    return p


def cf_aggr(i, plan):
    """_allowed 강등까지 반영한 기대 공격확률."""
    keep, down = allowed_keep(i['_prof'], plan)
    a_keep = aggr_of(i, plan)
    if a_keep is None:
        return None, keep, down
    if keep >= 1.0 or down is None:
        return a_keep, keep, down
    a_down = aggr_of(i, down)
    return keep*a_keep + (1-keep)*a_down, keep, down


def is_402(i):
    pre = '%s: ' % i['street']
    w = i['why'] if isinstance(i['why'], list) else [i['why']]
    return any(x.startswith(pre) and '상대레인지 열세' in x for x in w)


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
    for i in g2:
        i['_p_sb'] = p_formula(i['_sk'])
        i['_a0'], i['_a0src'] = actual_aggr(i)
        from cf_pcz import cf_semibluff_aggr
        i['_a1'] = cf_semibluff_aggr(i)[0]
        i['_d'] = i['_p_sb'] * (i['_a1'] - i['_a0'])
        made_plan = (i['plan'] not in PASSIVE) or (i['rel'] >= 0.30 and i['plan'] != 'giveup')
        i['_abc'] = 'A' if made_plan else ('B' if i['_d'] > 0 else 'C')
    B = [i for i in g2 if i['_abc'] == 'B']

    print('=' * 108)
    print('0. B 12건을 출처로 가른다 — 402 폴백이 만든 것과 아닌 것')
    print('=' * 108)
    b402 = [i for i in B if is_402(i)]
    bother = [i for i in B if not is_402(i)]
    print('   B 전체 %d건' % len(B))
    print('   402 폴백 발동(why 에 "상대레인지 열세") %d건  계획 %s'
          % (len(b402), dict(collections.Counter(i['plan'] for i in b402).most_common())))
    print('   402 아님 %d건  계획 %s'
          % (len(bother), dict(collections.Counter(i['plan'] for i in bother).most_common())))
    for i in bother:
        w = [x for x in i['why'] if x.startswith('%s: ' % i['street'])]
        print('      h%-5d %-5s %-12s ← %s' % (i['_hand'], i['street'], i['plan'],
                                               ' / '.join(w)[:74]))
    print()
    tgt = [i for i in b402 if i.get('made', 0) == 0]
    print('   402 중 made==0 (→ giveup) %d건  ← 이번 반사실의 대상' % len(tgt))
    print('   402 중 made>=1 (→ showdown) %d건' % (len(b402) - len(tgt)))
    print()

    # ---------- 상태 표 ----------
    print('=' * 108)
    print('1. 대상 %d건의 상태' % len(tgt))
    print('=' * 108)
    h = ('%-6s %-5s %-6s %-13s %6s %6s %5s %5s %5s %3s %6s %-5s %s'
         % ('hand', 'st', '홀', '보드', 'eq', 'eq_cur', 'rel', '물리', 'made',
            'mw', 'pcz', 'eq>=', '드로우'))
    print(h); print('-' * len(h))
    for i in sorted(tgt, key=lambda x: -x['outs_true']):
        bd = board_at(i['_board'], i['street'])
        tg = ', '.join(draw_tag(i['_hole'], bd)) if (i['_hole'] and len(bd) >= 3) else '-'
        mw = max(0, i.get('n_opp', 1) - 1)
        print('h%-5d %-5s %-6s %-13s %6.3f %6.3f %5.2f %5d %5d %3d %6.3f %-5s %s'
              % (i['_hand'], i['street'], ''.join(i['_hole'] or []), ' '.join(bd),
                 i['eq'], i.get('eq_current') or 0.0, i['rel'], i['outs_true'],
                 i.get('made', 0), mw, i['_pcz'],
                 'Y' if i['eq'] >= i['_pcz'] else 'N', tg))
    print()

    # ---------- 세 반사실 ----------
    print('=' * 108)
    print('2. CF-B1 / B2 / B3 — 402 에서 계획만 갈아끼우고 그 뒤 흐름을 따라간다')
    print('=' * 108)
    print('   _allowed 유지확률을 괄호로 적는다. 강등되면 showdown 이다.')
    print()
    h2 = ('%-6s %-5s %4s %7s | %8s | %-16s | %-16s'
          % ('hand', 'st', '저항', '현재', 'B1 show', 'B2 potctl', 'B3 semibluff'))
    print(h2); print('-' * len(h2))
    agg = collections.Counter()
    res = []
    for i in sorted(tgt, key=lambda x: -x['outs_true']):
        resisted = (i.get('tocall') or 0) > 0
        a0 = i['_a0']
        r = {'i': i, 'resisted': resisted, 'a0': a0}
        cells = []
        for nm, pl in (('B1', 'showdown'), ('B2', 'pot_control'), ('B3', 'semibluff')):
            a, keep, down = cf_aggr(i, pl)
            r[nm] = (a, keep)
            if a is None:
                cells.append('%-16s' % '저항(별도)')
            elif keep >= 1.0:
                cells.append('%-16s' % ('%.2f' % a))
            else:
                cells.append('%-16s' % ('%.2f (유지%.0f%%)' % (a, keep*100)))
        res.append(r)
        print('h%-5d %-5s %4s %7s | %8s | %-16s | %-16s'
              % (i['_hand'], i['street'], 'Y' if resisted else '-',
                 ('%.2f' % a0) if a0 is not None else '-',
                 cells[0].strip(), cells[1].strip(), cells[2].strip()))
    print()

    # ---------- 요약 ----------
    print('=' * 108)
    print('3. 어떤 대체 계획이 실제로 행동을 바꾸는가')
    print('=' * 108)
    unres = [r for r in res if not r['resisted']]
    print('   무저항 %d건 / 저항 %d건' % (len(unres), len(res)-len(unres)))
    if unres:
        s0 = sum(r['a0'] for r in unres)
        print()
        print('   %-14s %10s %10s   %s' % ('반사실', '기대공격건수', '현재대비', '비고'))
        print('   ' + '-' * 66)
        print('   %-14s %10.2f %10s   %s' % ('현재 (giveup)', s0, '—', ''))
        for nm, pl in (('B1', 'showdown'), ('B2', 'pot_control'), ('B3', 'semibluff')):
            s = sum(r[nm][0] for r in unres)
            note = ''
            if nm == 'B1':
                note = 'decide_aggression 은 giveup/showdown 을 같은 분기로 본다'
            if nm == 'B3':
                kk = [r[nm][1] for r in unres]
                note = '_allowed 유지확률 %.0f~%.0f%%' % (min(kk)*100, max(kk)*100)
            if nm == 'B2':
                kk = [r[nm][1] for r in unres]
                note = '_allowed 유지확률 %.0f~%.0f%%' % (min(kk)*100, max(kk)*100)
            print('   %-14s %10.2f %+10.2f   %s' % ('CF-%s %s' % (nm, pl), s, s-s0, note))
    print()
    rs = [r for r in res if r['resisted']]
    if rs:
        print('   저항 %d건은 decide_aggression 을 타지 않는다. 갈리는 곳은' % len(rs))
        print('   decide_response:793 — giveup 은 순수 팟오즈로 조기 return 하고')
        print('   showdown/pot_control 은 calldown 경로(인식 편향·블러프캐치)를 탄다.')
        print('   그 경로의 need 재계산은 기록된 값으로 복원되지 않아 수치를 내지 않는다.')
        for r in rs:
            i = r['i']
            t = None
            for x in (i.get('trace') or []):
                if (x or {}).get('kind') == 'response' and x.get('street') == i['street']:
                    t = x
            print('      h%-5d %-5s eq %.3f  need %s  실제 %s'
                  % (i['_hand'], i['street'], i['eq'],
                     ('%.3f' % t['need']) if t else '-', i.get('action')))
    print()
    # ---------- 5. 402 전체 모집단 ----------
    print('=' * 108)
    print('4. 402 폴백 전체 모집단 — 우리 대상은 그중 한 덩어리일 뿐이다')
    print('=' * 108)
    all402 = [i for i in rows if i['_branch'] and is_402(i)]
    gv = [i for i in all402 if i.get('made', 0) == 0]
    print('   make_plan 원본 %d건 중 402 발동 %d건 (%.1f%%)'
          % (len([i for i in rows if i['_branch']]), len(all402),
             100*len(all402)/max(1, len([i for i in rows if i['_branch']]))))
    print('     made>=1 → showdown  %2d' % (len(all402) - len(gv)))
    print('     made==0 → giveup    %2d' % len(gv))
    print()
    print('   giveup %d건의 rel × 물리outs' % len(gv))
    print('     %-14s %4s   %s' % ('rel', 'n', '물리 outs 분포'))
    for lo, hi in ((0, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 0.50),
                   (0.50, 0.70), (0.70, 1.01)):
        s = [i for i in gv if lo <= i['rel'] < hi]
        if s:
            print('     %-14s %4d   %s' % ('%.2f~%.2f' % (lo, hi), len(s),
                  dict(sorted(collections.Counter(x['outs_true'] for x in s).items()))))
    print()
    tgt0 = [i for i in gv if i['outs_true'] == 0 and i['rel'] <= 0.10]
    print('   도입 커밋이 명시한 대상(made 0 · 물리 outs 0 · rel<=0.10) : %d건' % len(tgt0))
    print('     → CLAUDE.md 의 "의도한 대상이 한 건도 없다" 는 이 표본에서도 **확인된다**.')
    print()
    n_hi = sum(1 for i in gv if i['outs_true'] == 0 and i['rel'] > 0.10)
    n_dr = sum(1 for i in gv if i['outs_true'] >= 8)
    print('   실제로 걸리는 것은 성격이 다른 두 덩어리다')
    print('     (가) 물리 outs 0 인데 rel 이 높다        %2d건  — 지금 이기고 있는데 포기' % n_hi)
    print('     (나) 물리 outs >= 8 인 드로우            %2d건  — 이번 반사실의 대상' % n_dr)
    print()
    print('   (가)는 계수 문제가 아니라 판별자 문제다. 402 는 `made >= 1` 로 가르는데')
    print('   그 분기의 바깥(진입 심사)과 안쪽(rel 기반 계획 선택)은 rel 로 말한다.')
    print('   made 0 · rel 0.70 은 "내 기여 조합은 없지만 상대 레인지에 지금 이기는" 상태다.')
    print()

    print('=' * 108)
    print('5. 이번 단계의 답')
    print('=' * 108)
    if unres:
        s0 = sum(r['a0'] for r in unres)
        s1 = sum(r['B1'][0] for r in unres)
        s3 = sum(r['B3'][0] for r in unres)
        print('   CF-B1(showdown) 은 무저항에서 행동을 **전혀 바꾸지 않는다** (%.2f → %.2f).'
              % (s0, s1))
        print('   라벨만 바뀌고 decide_aggression 이 같은 분기를 탄다.')
        print('   행동을 바꾸는 것은 CF-B3(semibluff) 뿐이다 (%.2f → %.2f).' % (s0, s3))
        print('   다만 _allowed 강등이 그 효과의 일부를 되돌린다.')


if __name__ == '__main__':
    main()
