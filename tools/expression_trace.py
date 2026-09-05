"""개인차가 어디서 압축되는지 추적한다. **수정 없이 측정만.**

    python3 tools/expression_trace.py

배경: 생성 단계에서는 서로 다른 사람을 만드는데(aggression 2~9),
행동으로 나올 때는 라벨별 aggr 이 2.98~4.37 로 좁혀졌다. 관찰 모델을 아무리
고쳐도 신호 자체가 없으면 답이 안 나온다.

  정상:  A→A' B→B' C→C' (행동에 개인차가 있고 관찰자가 불완전하게 복원)
  현재:  A,B,C → 비슷한 행동 (관찰할 정보 자체가 부족)

단계마다 개인차가 얼마나 남는지 본다. 척도는 **변동계수(sd/mean)**와
사분위 범위로, 단계 간 비교가 되도록 정규화한다.

  ① 잠재요인      study / aggro / exp
  ② 기질          aggression / looseness / discipline
  ③ 개념          bluff / cbet_flop / potodds
  ④ 계획 분포     공격적 계획 비율
  ⑤ 행동          VPIP / PFR / 공격률
"""
import sys, os, math, statistics, collections, random

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import persona as PS   # noqa: E402
import tourney as T    # noqa: E402

SEEDS = (21001, 21002, 21003, 21004, 21005, 21006)
HANDS = 45
AGG = ('bet', 'raise', 'allin')


def spread(vals):
    """개인차 크기. (sd, sd/평균, 10~90 분위 폭)"""
    if len(vals) < 3:
        return (0.0, 0.0, 0.0)
    m = statistics.mean(vals)
    sd = statistics.pstdev(vals)
    a = sorted(vals)
    lo = a[max(0, int(len(a)*0.10))]
    hi = a[min(len(a)-1, int(len(a)*0.90))]
    return (sd, (sd/m if m else 0.0), hi-lo)


def main():
    gen = collections.defaultdict(list)     # 생성 단계 (엔진 통과 전)
    beh = collections.defaultdict(list)     # 행동 단계
    plan_agg = []
    per = {}

    rng = random.Random(4242)
    for i in range(4000):
        p = PS.make_player(rng, field_quality=0.6, pid=i)
        gen['latent.aggro'].append(p['latent']['aggro'])
        gen['latent.study'].append(p['latent']['study'])
        gen['temper.aggression'].append(p['temper']['aggression'])
        gen['temper.looseness'].append(p['temper']['looseness'])
        for k in ('bluff', 'cbet_flop', 'potodds'):
            gen['concept.' + k].append(p['concepts'].get(k, 5.0))

    for sd in SEEDS:
        t = T.Tournament(entries=60, seed=sd, fmt='standard', hero_seat=7)
        for _ in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            while st and not st.get('done') and g < 250:
                st = t.submit('fold')
                g += 1
            h = getattr(t.run, 'h', None)
            if h is None:
                continue
            # 계획 분포 — 공격적 계획 비율
            for _k, v in (getattr(h, 'plans', {}) or {}).items():
                pl = v.get('plan')
                if pl:
                    plan_agg.append(1.0 if pl.startswith(('value', 'bluff',
                                                          'semibluff')) else 0.0)
            for seat, pr in (h.prof or {}).items():
                if not pr.get('concepts'):
                    continue
                # table_id 가 None 이라 전 시드가 'T0_n' 으로 겹친다.
                # 시드를 키에 넣지 않으면 8명분만 남는다.
                key = '%d|T%s_%s' % (sd, getattr(h, 'table_id', 0), seat)
                d = per.setdefault(key, {'aggr_t': pr['temper']['aggression'],
                                         'loose_t': pr['temper']['looseness'],
                                         'hands': 0, 'vpip': 0, 'pfr': 0,
                                         'ag': 0, 'pa': 0})
        # 장부에서 행동 집계. 예전에는 이 블록이 시드 루프 안쪽이면서도
        # h 가 마지막 핸드의 것만 남아 표본이 7명으로 줄었다.
        for k, r in ((getattr(t.run, 'h', None).book.d
                      if getattr(t.run, 'h', None) else {}) or {}).items():
            _o, tg = k.split('>')
            tg = '%d|%s' % (sd, tg)
            if tg not in per or r.get('hands', 0) < 20:
                continue
            d = per[tg]
            if d['hands']:
                continue
            d['hands'] = r['hands']
            d['vpip'] = r['vpip']
            d['pfr'] = r['pfr']
            d['ag'] = r.get('agg_actions', 0)
            d['pa'] = r.get('passive_actions', 0)

    for k, d in per.items():
        if not d['hands']:
            continue
        beh['behavior.vpip'].append(d['vpip']/d['hands'])
        beh['behavior.pfr'].append(d['pfr']/d['hands'])
        tot = d['ag'] + d['pa']
        if tot:
            beh['behavior.aggr'].append(10.0*d['ag']/tot)
        beh['_temper.aggression'].append(d['aggr_t'])
        beh['_temper.looseness'].append(d['loose_t'])

    print('개인차 크기 — 단계별 (변동계수 sd/mean 이 클수록 개인차가 크다)')
    print('%-24s %6s %7s %7s %8s' % ('단계', 'n', 'mean', 'sd', 'sd/mean'))
    for k in sorted(gen):
        s = spread(gen[k])
        print('%-24s %6d %7.2f %7.2f %8.2f'
              % ('[생성] ' + k, len(gen[k]), statistics.mean(gen[k]), s[0], s[1]))
    if plan_agg:
        m = statistics.mean(plan_agg)
        print('%-24s %6d %7.2f %7s %8s'
              % ('[계획] 공격계획비율', len(plan_agg), m, '-', '-'))
    for k in sorted(beh):
        if k.startswith('_'):
            continue
        s = spread(beh[k])
        print('%-24s %6d %7.3f %7.3f %8.2f'
              % ('[행동] ' + k, len(beh[k]), statistics.mean(beh[k]), s[0], s[1]))

    # 기질 → 행동 상관: 개인차가 실제로 행동으로 전달되는가
    def corr(x, y):
        if len(x) < 3:
            return 0.0
        mx, my = statistics.mean(x), statistics.mean(y)
        num = sum((a-mx)*(b-my) for a, b in zip(x, y))
        den = math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))
        return num/den if den else 0.0

    print()
    print('기질 → 행동 전달 (상관이 낮으면 그 구간에서 개인차가 사라진 것)')
    n = min(len(beh['_temper.aggression']), len(beh.get('behavior.aggr', [])))
    if n >= 5:
        print('  aggression → 공격률   corr %+.2f (n=%d)'
              % (corr(beh['_temper.aggression'][:n], beh['behavior.aggr'][:n]), n))
    n2 = min(len(beh['_temper.looseness']), len(beh['behavior.vpip']))
    if n2 >= 5:
        print('  looseness  → VPIP     corr %+.2f (n=%d)'
              % (corr(beh['_temper.looseness'][:n2], beh['behavior.vpip'][:n2]), n2))
        print('  aggression → PFR      corr %+.2f (n=%d)'
              % (corr(beh['_temper.aggression'][:n2], beh['behavior.pfr'][:n2]), n2))


if __name__ == '__main__':
    main()
