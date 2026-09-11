#!/usr/bin/env python3
"""block 이 덮어써지지 않았다면 — 행동 반사실. plan.py 는 읽기만 한다.

block 은 도달 불가 분기다(tools/init_gate.py 2-0 참조).
plan.py:447 이 독립 if 라서 456~467 의 if/elif/else 가 무조건 plan 을 덮는다.

여기서 묻는 것은 하나다.
    "block 이 코드상 죽어 있다"와
    "그 때문에 봇의 실제 플레이가 왜곡돼 있다"는 **별개의 명제**다.
    후자가 얼마인가.

난수를 새로 굴리지 않는다
-------------------------
decide_aggression 은 이 경로들에서 rng 를 **한 번도 소비하지 않는다**
(plan.py:836~931 전수 확인). 계획만 바뀌고 rng 스트림의 위치는 같으므로
attach_intent 의 `_roll = rng.random()` 은 **같은 난수**다.
따라서 행동이 갈릴 확률은 정확히

    P(행동 변경) = |p_cf - p_now|

이다. 독립 시행으로 보고 p_cf(1-p_now)+p_now(1-p_cf) 로 계산하면 안 된다 —
같은 난수를 쓰므로 그건 과대 계산이다.

사이즈
------
decide_size 는 rng 를 소비한다(TX.perceived 등). 최종 사이즈는 기록된
rng 스트림 없이는 복원되지 않는다. 그래서 **기본 표 SIZING 만** 비교한다.

저항 상황
---------
decide_aggression 을 타지 않는다. decide_response 의 계획 의존 분기는
    made>=5                                   넛 레이즈 (계획 무관)
    value_3street/value_2street/trap           밸류 레이즈 (eq > need+0.15)
    bluff_2street/semibluff/river_bluff        블러프 레이즈
    semibluff (outs>=8)                        세미블러프 레이즈/내재오즈
    giveup                                     이탈 블러프 레이즈 → 순수 팟오즈 조기 return
    그 외 (block·pot_control·showdown)         calldown 경로
block 은 마지막에 속한다. 그래서 계획별로 갈리는 지점이 다르다.

사용: python3 tools/cf_block.py [collected*.jsonl ...]
"""
import os, sys, glob, math, random, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS
import plan as PL
from sb_calib import load, branch_of
from sb_114 import thresholds
from init_gate import block_p, block_fired, fired, _street_why
from tag_draws import board_at

# decide_response 에서 그 계획이 타는 분기
RESP = {'value_2street': '밸류 레이즈 가능 → calldown',
        'value_3street': '밸류 레이즈 가능 → calldown',
        'pot_control': 'calldown',
        'showdown': 'calldown',
        'giveup': '순수 팟오즈 조기 return(793)',
        'block': 'calldown'}


def aggr(i, plan):
    """그 계획이었다면의 '칠 확률'. 이 경로는 rng 를 안 쓴다."""
    bd = board_at(i['_board'], i['street'])
    p, _ = PL.decide_aggression(i['_prof'], bd, i['street'], plan, i['rel'],
                                i.get('n_opp', 1), bool(i.get('oop')),
                                bool(i.get('init')), i.get('behind', 0),
                                random.Random(0), i.get('opp_est'),
                                i.get('outs', 0), plan_state=dict(i))
    return p


def now_aggr(i):
    for x in (i.get('trace') or []):
        if (x or {}).get('kind') == 'aggression' and x.get('street') == i['street']:
            return float(x['p'])
    return None


def main():
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(D, 'collected_p*.jsonl')))
    pure = load(paths)
    allr = load(paths, pure=False)
    for i in pure:
        i['_branch'] = branch_of(i)
        i['_v3'], i['_v2'], i['_pcz'] = thresholds(i)

    bf_all = [i for i in allr if block_fired(i)]
    bf = [i for i in pure if block_fired(i)]
    print('=' * 112)
    print('0. 표본')
    print('=' * 112)
    print('   block 발화  전체 %d건 / 정제(eq_sims=400) %d건' % (len(bf_all), len(bf)))
    print('   행동 반사실은 정제 %d건으로만 한다 — refresh 가 덮은 레코드는' % len(bf))
    print('   eq/rel/outs 가 판단 이후 값이라 decide_aggression 재계산이 성립하지 않는다.')
    print('   살아남은 block: %d건' % sum(1 for i in bf_all if i['plan'] == 'block'))
    print()

    for i in bf:
        i['_bp'] = block_p(i)[0]
        i['_now'] = now_aggr(i)
        i['_cf'] = aggr(i, 'block')
        i['_res'] = (i.get('tocall') or 0) > 0
        i['_d'] = (None if i['_now'] is None else abs(i['_cf'] - i['_now']))

    unres = [i for i in bf if not i['_res']]
    res = [i for i in bf if i['_res']]

    # ---------- 전수 표 ----------
    print('=' * 112)
    print('1. 전수 — 무저항 %d건' % len(unres))
    print('=' * 112)
    h = ('%-6s %-5s %6s %5s %3s %6s %6s  %-14s %7s %7s %8s  %6s %6s %-6s'
         % ('hand', 'st', 'eq', 'rel', 'mw', 'sk(bb)', 'block_p',
            '현재 plan', '현재p', 'CF p', '변경확률', '현사이즈', 'CF표', '실제'))
    print(h); print('-' * len(h))
    for i in sorted(unres, key=lambda x: -(x['_d'] or 0)):
        print('h%-5d %-5s %6.3f %5.2f %3d %6.2f %6.3f  %-14s %7s %7.2f %8s  %6s %6.2f %-6s'
              % (i['_hand'], i['street'], i['eq'], i['rel'],
                 max(0, i.get('n_opp', 1)-1), PS.sk(i['_prof'], 'blockbet'), i['_bp'],
                 i['plan'],
                 ('%.2f' % i['_now']) if i['_now'] is not None else '-',
                 i['_cf'],
                 ('%.2f' % i['_d']) if i['_d'] is not None else '-',
                 ('%.2f' % i['intent_size']) if i.get('intent_size') else '-',
                 PL.SIZING['block'].get(i['street'], 0.0),
                 i.get('action')))
    print()

    # ---------- 덮어쓴 대상별 ----------
    print('=' * 112)
    print('2. 덮어쓴 대상별 — "block 이 죽어서 실제 플레이가 얼마나 망가졌나"')
    print('=' * 112)
    print('   행동 변경 기대건수 = Σ|p_cf - p_now|  (같은 난수를 공유하므로 이게 정확값)')
    print()
    print('   %-16s %5s %10s %10s %8s   %s'
          % ('현재 결과', 'n', '변경 기대', '동일 기대', '비율', '사이즈 기본표 (플랍)'))
    print('   ' + '-' * 92)
    tot_n = tot_ch = 0
    for pl in ('value_2street', 'pot_control', 'giveup'):
        sub = [i for i in unres if i['plan'] == pl and i['_d'] is not None]
        if not sub:
            continue
        ch = sum(i['_d'] for i in sub)
        tot_n += len(sub); tot_ch += ch
        print('   %-16s %5d %10.2f %10.2f %7.0f%%   %.2f → 0.25'
              % (pl, len(sub), ch, len(sub)-ch, 100*ch/len(sub),
                 PL.SIZING.get(pl, {}).get('flop', 0.0)))
    if tot_n:
        print('   ' + '-' * 92)
        print('   %-16s %5d %10.2f %10.2f %7.0f%%'
              % ('합계(무저항)', tot_n, tot_ch, tot_n-tot_ch, 100*tot_ch/tot_n))
    print()

    # ---------- 방향 ----------
    print('=' * 112)
    print('3. 변경의 방향 — 공격이 늘어나는가 줄어드는가')
    print('=' * 112)
    up = [i for i in unres if i['_d'] is not None and i['_cf'] > i['_now']]
    dn = [i for i in unres if i['_d'] is not None and i['_cf'] < i['_now']]
    sm = [i for i in unres if i['_d'] is not None and abs(i['_cf'] - i['_now']) < 1e-9]
    print('   CF 가 더 침  %2d건  Σ(p_cf-p_now) = %+.2f' % (len(up), sum(i['_cf']-i['_now'] for i in up)))
    print('   CF 가 덜 침  %2d건  Σ(p_cf-p_now) = %+.2f' % (len(dn), sum(i['_cf']-i['_now'] for i in dn)))
    print('   동일         %2d건' % len(sm))
    print()
    for pl in ('value_2street', 'pot_control', 'giveup'):
        sub = [i for i in unres if i['plan'] == pl and i['_d'] is not None]
        if not sub:
            continue
        print('   %-14s 현재 p 중앙 %.2f → CF p 중앙 %.2f   실제 액션 %s'
              % (pl,
                 sorted(i['_now'] for i in sub)[len(sub)//2],
                 sorted(i['_cf'] for i in sub)[len(sub)//2],
                 dict(collections.Counter(i.get('action') for i in sub).most_common())))
    print()

    # ---------- 저항 ----------
    print('=' * 112)
    print('4. 저항 %d건 — decide_aggression 을 타지 않는다' % len(res))
    print('=' * 112)
    print('   계획이 바뀌면 decide_response 의 분기가 바뀌는 경우만 행동이 달라진다.')
    print()
    h4 = ('   %-6s %-5s %6s %5s  %-14s %-26s %-12s %-6s %s'
          % ('hand', 'st', 'eq', 'rel', '현재 plan', '현재 분기', 'CF(block)',
             '실제', '발동 조건 (응답 시점 eq)'))
    print(h4); print('   ' + '-' * (len(h4)-3))
    same = diff = latent = 0
    for i in sorted(res, key=lambda x: x['plan']):
        cur = RESP.get(i['plan'], 'calldown')
        tr = None
        for x in (i.get('trace') or []):
            if (x or {}).get('kind') == 'response' and x.get('street') == i['street']:
                tr = x
        # 응답 시점 eq/need 로 판정한다. 계획 시점 eq 로 하면 틀린다.
        req = ''
        if i['plan'] in ('value_2street', 'value_3street', 'trap'):
            if tr:
                ok = float(tr.get('eq', 0)) > float(tr['need']) + 0.15
                req = 'eq %.3f > need+0.15 %.3f ? %s' % (
                    float(tr.get('eq', 0)), float(tr['need'])+0.15, 'O' if ok else 'X')
            else:
                ok = None
                req = 'trace 없음'
            if ok:
                diff += 1; mark = '**다름**'
            else:
                latent += 1; mark = '조건 미충족'
        elif cur == RESP['block']:
            same += 1; mark = '동일'
        else:
            diff += 1; mark = '**다름**'
        print('   h%-5d %-5s %6.3f %5.2f  %-14s %-26s %-12s %-6s %s'
              % (i['_hand'], i['street'], i['eq'], i['rel'], i['plan'], cur, mark,
                 i.get('action'), req))
    print()
    print('   분기가 같아 바뀔 수 없음 %d / 분기는 다르나 발동 조건 미충족 %d / 실제로 바뀔 수 있음 %d'
          % (same, latent, diff))
    if diff:
        print('   바뀔 수 있는 건의 성격:')
        print('     value_2street → block : 밸류 레이즈 기회를 잃는다 (eq > need+0.15 일 때만)')
        print('     giveup        → block : 순수 팟오즈 조기 return(793) 대신 calldown 경로')
    print()

    # ---------- 결론 ----------
    print('=' * 112)
    print('5. 두 명제의 분리')
    print('=' * 112)
    print('   (a) block 은 코드상 도달 불가다 — 전 표본 %d건 발화 · 생존 0건. 확정.'
          % len(bf_all))
    if tot_n:
        print('   (b) 그 때문에 실제 플레이가 바뀌는 양 — 무저항 %d건에서 기대 %.2f건'
              % (tot_n, tot_ch))
        print('       봇 대전 6,000핸드 기준. 저항 %d건 중 실제로 달라질 수 있는 것은 %d건.'
              % (len(res), diff))
    print('   사이즈는 별개 축이다. 기본표에서 value_2street 0.50 → block 0.25 로 절반이고,')
    print('   giveup 0.00 → block 0.25 는 "칠 수단이 없음"에서 "친다"로 바뀐다.')
    print('   다만 decide_size 가 rng 를 소비하므로 최종 사이즈는 복원하지 않았다.')


if __name__ == '__main__':
    main()
