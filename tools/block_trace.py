#!/usr/bin/env python3
"""block 발화 41건이 파이프라인 어디서 죽는지 전수 추적. plan.py 는 읽기만 한다.

묻는 것
-------
block 의 진짜 결함이 "계획이 죽는 것"인가, "발화 기준 자체가 틀린 것"인가.

파이프라인 (plan.py 실제 순서)
------------------------------
  [1] make_plan 447   if sk(blockbet)>=1 and rng < block_p:  plan='block'
  [2] make_plan 456~467  if/elif/else 가 **무조건** plan 을 재할당      ← 현재 병목
  [3] update_plan 1491   _allowed(profile, plan, rng)
                         block 은 원개념 s 에 대해
                           s < 1.5        → value_2street 로 강등
                           1.5 <= s < 3.5 → 확률 (s-1.5)/2 로 유지
                           s >= 3.5       → 유지
  [4] river_fix 1522     block 은 리버에서 thin_river 로 승격될 수 있다(made>=1)
  [5] revise_plan 1771   다음 스트리트에서 rel>=0.70 이면 승격
  [6] decide_aggression 903  block 전용 p = clamp(0.15, 0.92, 0.35+0.055*sk(blockbet))
      decide_response       block 전용 분기 없음 → calldown 경로
  [7] decide_size / SIZING['block'] = {flop .25, turn .28, river .30}

[2] 가 100% 이므로 [3] 이후는 **전부 반사실**이다. 관측으로는 확인할 수 없다.
이 도구는 [3] 을 확률로, [6] 을 결정적으로 계산해 "복구해도 어디서 또 죽는가"를 낸다.

난수는 새로 굴리지 않는다. decide_aggression 은 이 경로에서 rng 를 쓰지 않는다.

사용: python3 tools/block_trace.py [collected*.jsonl ...]
"""
import os, sys, glob, math, random, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS
import plan as PL
from sb_calib import load, branch_of
from init_gate import block_fired, block_p, fired, _street_why
from cf_block import aggr, now_aggr


def allowed_keep(prof):
    """_allowed 가 block 을 유지할 확률. 강등 대상은 value_2street."""
    if not prof.get('concepts'):
        return 1.0
    s = PS.sk(prof, 'blockbet')
    if s < 1.5:
        return 0.0
    if s < 3.5:
        return (s - 1.5) / 2.0
    return 1.0


def main():
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(D, 'collected_p*.jsonl')))
    allr = load(paths, pure=False)
    pure = load(paths)
    bf_all = [i for i in allr if block_fired(i)]
    bf = [i for i in pure if block_fired(i)]

    print('=' * 118)
    print('0. 진입 조건 검증 — 발화한 %d건이 정말 그 조건을 만족하는가' % len(bf_all))
    print('=' * 118)
    print('   plan.py:442  `if oop and not initiative and 0.25 <= rel <= 0.80:`')
    print('   oop=True      %d/%d' % (sum(1 for i in bf_all if i.get('oop')), len(bf_all)))
    print('   initiative=False %d/%d' % (sum(1 for i in bf_all if not i.get('init')), len(bf_all)))
    print('   0.25<=rel<=0.80 %d/%d'
          % (sum(1 for i in bf_all if 0.25 <= i['rel'] <= 0.80), len(bf_all)))
    print('   street 분포 %s' % dict(collections.Counter(i['street'] for i in bf_all).most_common()))
    print('   → 세 조건이 전건 참이면 발화 기준 자체는 의도대로 작동하고 있다는 뜻이다.')
    print()
    print('   street 가 flop 뿐인 것은 우연이 아니다 — block 은 make_plan 에서만')
    print('   세워지고, 턴·리버는 refresh/revise_plan 경로라 block 을 새로 만들지')
    print('   않는다. 즉 block 은 **플랍에서만 태어날 수 있다**.')
    print()

    print('=' * 118)
    print('1. 깔때기 — [2] 가 100%% 라 [3] 이후는 전부 반사실이다')
    print('=' * 118)
    surv = sum(1 for i in bf_all if i['plan'] == 'block')
    print('   [1] 발화                                  %3d' % len(bf_all))
    print('   [2] 456~467 이 덮음                        %3d  (%.0f%%)  ← 현재 병목'
          % (len(bf_all), 100.0))
    print('   [2] 통과해 살아남음                          %3d' % surv)
    print()
    print('   아래는 전부 "만약 [2] 가 없었다면" 이다.')
    keep = [allowed_keep(i['_prof']) for i in bf_all]
    print('   [3] _allowed 유지 기대           %5.1f / %d  (%.0f%%)'
          % (sum(keep), len(keep), 100*sum(keep)/len(keep)))
    hard = sum(1 for i in bf_all if PS.sk(i['_prof'], 'blockbet') < 1.5)
    prob = sum(1 for i in bf_all if 1.5 <= PS.sk(i['_prof'], 'blockbet') < 3.5)
    safe = sum(1 for i in bf_all if PS.sk(i['_prof'], 'blockbet') >= 3.5)
    print('         원개념 <1.5 무조건 강등   %2d' % hard)
    print('         1.5~3.5 확률 강등        %2d' % prob)
    print('         >=3.5 안전               %2d' % safe)
    print('   → [3] 은 두 번째 사망 지점이지만 %.0f%% 는 통과한다.'
          % (100*sum(keep)/len(keep)))
    print('     make_plan 게이트는 원개념 3.33(sk>=1)을 요구하는데 _allowed 는 3.5 를')
    print('     요구한다. 3.33~3.5 구간은 발화는 되는데 확률 강등에 걸린다 — 문턱 불일치.')
    print()

    print('=' * 118)
    print('2. 전수 — 요청하신 필드')
    print('=' * 118)
    h = ('%-6s %-5s %6s %5s %4s %6s %4s %4s %6s %5s %5s %7s %7s %7s %7s  %-14s %-6s'
         % ('hand', 'st', 'eq', 'rel', 'made', 'danger', 'pos', 'ini',
            'sk(bb)', 'aggr', 'bluff', 'block_p', '_allow', '현재p', 'CFp',
            '덮은 결과', '실제'))
    print(h); print('-' * len(h))
    for i in sorted(bf, key=lambda x: (x['street'], -x['rel'])):
        ch = [x for x in _street_why(i) if x.startswith(('중간강도(', '중간강도이나'))]
        over = ch[0].split('→')[-1].strip() if ch else '-'
        nw = now_aggr(i)
        cf = aggr(i, 'block')
        print('h%-5d %-5s %6.3f %5.2f %4d %6.2f %4s %4s %6.2f %5.1f %5.1f %7.3f %7.2f %7s %7.2f  %-14s %-6s'
              % (i['_hand'], i['street'], i['eq'], i['rel'], i.get('made', 0),
                 i.get('danger') or 0.0, 'OOP' if i.get('oop') else 'IP',
                 'Y' if i.get('init') else 'N',
                 PS.sk(i['_prof'], 'blockbet'), i['_prof'].get('aggr', 5),
                 i['_prof'].get('bluff', 5), block_p(i)[0], allowed_keep(i['_prof']),
                 ('%.2f' % nw) if nw is not None else '-', cf, over, i.get('action')))
    print()

    print('=' * 118)
    print('3. 네 그룹 — [2] 가 없었다면 최종적으로 어디에 도달하는가')
    print('=' * 118)
    print('   (현재는 3번이 100%. 1·2·4번은 반사실이다)')
    print()
    unres = [i for i in bf if (i.get('tocall') or 0) == 0]
    res = [i for i in bf if (i.get('tocall') or 0) > 0]
    # 그룹 1/2 — 무저항에서 block 이 살아남았을 때 bet/check 기대
    g1 = sum(allowed_keep(i['_prof']) * aggr(i, 'block') for i in unres)
    g2 = sum(allowed_keep(i['_prof']) * (1 - aggr(i, 'block')) for i in unres)
    g4 = sum(1 - allowed_keep(i['_prof']) for i in unres)
    print('   무저항 %d건' % len(unres))
    print('     1. block → bet                     기대 %5.2f건 (%.0f%%)'
          % (g1, 100*g1/max(1, len(unres))))
    print('     2. block → check                   기대 %5.2f건 (%.0f%%)'
          % (g2, 100*g2/max(1, len(unres))))
    print('     3. 456~467 이 덮음 (현재 실제)        %5d건 (100%%)' % len(unres))
    print('     4. _allowed 가 value_2street 로 강등  기대 %5.2f건 (%.0f%%)'
          % (g4, 100*g4/max(1, len(unres))))
    print()
    print('   저항 %d건 — decide_aggression 을 타지 않는다' % len(res))
    r4 = sum(1 - allowed_keep(i['_prof']) for i in res)
    print('     _allowed 강등 기대 %.2f건, 나머지는 calldown 경로(block 전용 분기 없음)' % r4)
    print()

    print('=' * 118)
    print('4. 결함의 성격 — "계획이 죽는다" vs "발화 기준이 틀렸다"')
    print('=' * 118)
    # 발화 기준이 맞는지: 발화군과 비발화군의 상태 비교
    cand = [i for i in pure
            if i.get('oop') and not i.get('init') and 0.25 <= i['rel'] <= 0.80
            and branch_of(i) == 'above' and PS.sk(i['_prof'], 'blockbet')/3.33 >= 1]
    nf = [i for i in cand if not block_fired(i)]
    ff = [i for i in cand if block_fired(i)]
    def ms(v):
        return (sum(v)/len(v)) if v else 0.0
    print('   같은 후보 조건·개념 게이트를 통과한 %d건 중 발화 %d / 비발화 %d'
          % (len(cand), len(ff), len(nf)))
    print('   %-10s %8s %8s' % ('', '발화', '비발화'))
    for nm, f in (('rel', lambda x: x['rel']), ('eq', lambda x: x['eq']),
                  ('made', lambda x: x.get('made', 0)),
                  ('danger', lambda x: x.get('danger') or 0.0),
                  ('sk(bb)', lambda x: PS.sk(x['_prof'], 'blockbet')),
                  ('block_p', lambda x: block_p(x)[0])):
        print('   %-10s %8.3f %8.3f' % (nm, ms([f(x) for x in ff]), ms([f(x) for x in nf])))
    print()
    print('   발화/비발화를 가르는 것은 block_p 하나뿐이고 block_p 는')
    print('   aggr·bluff·danger 만 본다. 위 표에서 rel·eq·made 가 두 집단에서')
    print('   거의 같은 것이 그 확인이다 (공식상 당연하지만, 공식을 제대로 읽었는지')
    print('   검산하는 의미가 있다).')
    print()
    print('   다만 "핸드 강도를 전혀 안 본다"고 말하면 과장이다 —')
    print('   진입 조건 `0.25 <= rel <= 0.80` 이 이미 강도 밴드로 거른다.')
    print('   정확히는 **밴드 안에서는 더 구분하지 않는다**.')
    print()
    print('   따라서 두 결함은 층이 다르다')
    print('     (i)  계획이 죽는다        — 456 덮어쓰기. 한 줄 문제. 100% 확정')
    print('     (ii) 발화 기준이 얇다      — rel 밴드로 거른 뒤 그 안에서는 강도를 안 본다.')
    print('          다만 이건 pot_control 의 _pc_p 와 같은 성질이고(그쪽도 rel·eq 무관),')
    print('          지금 데이터로 결함이라고 부를 근거는 없다. 설계 검토 대상으로 남긴다.')


if __name__ == '__main__':
    main()
