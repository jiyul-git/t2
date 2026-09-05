"""belief 파이프라인의 병목을 단계별로 끊어서 본다.

    python3 tools/belief_diag.py

최종 결과(corr ~= 0)만 보면 어디서 정보가 사라지는지 알 수 없다. 세 단계로 나눈다.

  ① 행동으로 라벨을 구별할 수 있는가        — 행동 5지표 → 실제 라벨 예측 정확도
  ② 라벨/행동으로 어떤 개념을 추정할 수 있는가 — 개념별 MAE/RMSE/bias/corr
  ③ 관찰력이 그 정확도를 실제로 높이는가      — 관찰자 A/B

②가 핵심이다. **라벨을 맞히는 것과 개념을 추정하는 것은 별개다.** TAG 라는
걸 정확히 알아도 range_read 까지 알 수 있다는 보장은 없다. 행동에 간접적으로만
드러나는 개념은 관찰로 식별 불가능할 수 있고, 그건 실패가 아니라 결과다 —
식별 가능한 개념과 불가능한 개념을 구분해야 한다는 뜻이다.

테스트 시드는 캘리브레이션 시드와 분리한다.
"""
import sys, os, math, random, statistics, collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'tools'))
import tourney as T          # noqa: E402
import reads as RD           # noqa: E402
import calibrate as CB       # noqa: E402

TEST_SEEDS = tuple(range(700001, 700001 + 12))   # 캘리브레이션과 분리
KEYS = ('range_read', 'bluff', 'potodds', 'spr', 'board_texture', 'icm')


def _obs(att, rr, stl):
    return {'temper': {'attention': att, 'adaptability': 5, 'consistency': 5},
            'concepts': {'range_read': rr, 'sizing_tell': stl}}


OBSERVERS = {'예리': _obs(9, 9, 9), '보통': _obs(5, 5, 5), '둔감': _obs(1, 1, 1)}


def corr(x, y):
    if len(x) < 3:
        return 0.0
    mx, my = statistics.mean(x), statistics.mean(y)
    num = sum((a-mx)*(b-my) for a, b in zip(x, y))
    den = math.sqrt(sum((a-mx)**2 for a in x) * sum((b-my)**2 for b in y))
    return num/den if den else 0.0


def collect():
    """테스트 토너먼트에서 (실제 라벨, 행동, 실제 개념, 장부키)를 모은다."""
    out = []
    for sd in TEST_SEEDS:
        t = T.Tournament(entries=60, seed=sd, fmt='standard', hero_seat=7)
        for _ in range(55):
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
        info = {}
        for seat, pr in (h.prof or {}).items():
            if pr.get('concepts'):
                key = 'T%s_%s' % (getattr(h, 'table_id', 0), seat)
                info[key] = (CB.base_style(pr.get('type')), pr['concepts'])
        seen = set()
        for k, r in h.book.d.items():
            o, tg = k.split('>')
            if tg in seen or tg not in info or r.get('hands', 0) < 25:
                continue
            seen.add(tg)
            hn = float(r['hands'])
            beh = {'vpip': r['vpip']/hn, 'pfr': r['pfr']/hn,
                   'cbet': (r['cbet']/r['cbet_opp']) if r.get('cbet_opp') else None,
                   'ftb': (r['fold_to_bet']/r['facing_bet']) if r.get('facing_bet') else None,
                   'aggr': (10.0*r['agg_actions'] /
                            max(1, r['agg_actions']+r['passive_actions']))}
            lab, cs = info[tg]
            if lab:
                out.append({'label': lab, 'beh': beh, 'concepts': cs,
                            'book': h.book, 'obs': o, 'tgt': tg})
    return out


def stage1(rows):
    """행동으로 라벨을 구별할 수 있는가 — 최근접 서명 분류 정확도."""
    print('① 행동 → 라벨 구별 가능성')
    sig = RD.STYLE_SIG
    labs = collections.Counter(r['label'] for r in rows)
    hit = 0
    n = 0
    for r in rows:
        best, bd = None, 1e9
        for name, s in sig.items():
            d = 0.0
            for kk, v in s.items():
                o = r['beh'].get(kk)
                if o is None:
                    continue
                d += ((o - v) / RD._sig_scale(name, kk)) ** 2
            if d < bd:
                best, bd = name, d
        n += 1
        hit += 1 if best == r['label'] else 0
    base = max(labs.values())/max(1, sum(labs.values()))
    print('   표본 %d / 라벨 %d종  최빈 라벨 비율(기준선) %.2f'
          % (n, len(labs), base))
    print('   행동 최근접 분류 정확도 %.2f' % (hit/max(1, n)))
    print('   라벨 분포:', dict(labs.most_common(6)))
    print()


def stage2(rows):
    """개념별로 추정이 되는가 — 관찰자 '보통' 기준."""
    print('② 개념별 추정 가능성 (관찰자=보통)')
    print('   %-14s %6s %6s %7s %7s' % ('개념', 'MAE', 'RMSE', 'bias', 'corr'))
    acc = collections.defaultdict(lambda: ([], []))
    for r in rows:
        b = RD.opponent_belief(r['book'], r['obs'], r['tgt'],
                               OBSERVERS['보통'], random.Random(1))
        for kk in KEYS:
            e = b['concept_belief'].get(kk)
            a = r['concepts'].get(kk)
            if e is None or a is None:
                continue
            acc[kk][0].append(e)
            acc[kk][1].append(a)
    for kk in KEYS:
        e, a = acc[kk]
        if not e:
            continue
        d = [x-y for x, y in zip(e, a)]
        print('   %-14s %6.2f %6.2f %+7.2f %+7.2f'
              % (kk, statistics.mean(map(abs, d)),
                 math.sqrt(statistics.mean([x*x for x in d])),
                 statistics.mean(d), corr(e, a)))
    print()


def stage3(rows):
    """관찰력이 정확도를 높이는가."""
    print('③ 관찰력 효과 (range_read 기준)')
    print('   %-6s %6s %6s %7s %7s %8s' % ('관찰자', 'MAE', 'RMSE', 'bias', 'corr', '스타일확신'))
    for name, prof in OBSERVERS.items():
        e, a, c = [], [], []
        for r in rows:
            b = RD.opponent_belief(r['book'], r['obs'], r['tgt'], prof,
                                   random.Random(1))
            v = b['concept_belief'].get('range_read')
            t = r['concepts'].get('range_read')
            if v is None or t is None:
                continue
            e.append(v); a.append(t); c.append(b['style_certainty'])
        if not e:
            continue
        d = [x-y for x, y in zip(e, a)]
        print('   %-6s %6.2f %6.2f %+7.2f %+7.2f %8.2f'
              % (name, statistics.mean(map(abs, d)),
                 math.sqrt(statistics.mean([x*x for x in d])),
                 statistics.mean(d), corr(e, a), statistics.mean(c)))


def stage4(rows):
    """④ 행동을 건너뛰고 **실제 라벨**을 넣었을 때 개념 추정이 맞는가.

    ①~③ 은 행동→라벨에서 이미 정보가 망가졌을 수 있어 어느 화살표가
    문제인지 모른다. 여기서는 라벨을 정답으로 주고 라벨→개념 경로만 본다.

      corr < 0  라벨을 개념의 대리변수로 쓰는 것 자체가 잘못 (경로 제거)
      corr ~ 0  라벨이 개념을 설명하는 축이 아님 (경로 제거 쪽)
      corr > 0  경로엔 정보가 있고 행동→라벨 분류기가 병목 (분류기 교체)
    """
    import reads as RD
    print()
    print('④ 실제 라벨 → 개념 (행동 경로 우회)')
    print('   %-14s %6s %7s %7s %7s' % ('개념', 'n', 'corr', 'MAE', 'bias'))
    acc = collections.defaultdict(lambda: ([], []))
    for r in rows:
        pri = RD.STYLE_CONCEPT_PRIOR.get(r['label'])
        if not pri:
            continue
        for kk in KEYS:
            e = pri.get(kk)
            a = r['concepts'].get(kk)
            if e is None or a is None:
                continue
            acc[kk][0].append(e)
            acc[kk][1].append(a)
    for kk in KEYS:
        e, a = acc[kk]
        if len(e) < 10:
            continue
        d = [x-y for x, y in zip(e, a)]
        print('   %-14s %6d %+7.2f %7.2f %+7.2f'
              % (kk, len(e), corr(e, a), statistics.mean(map(abs, d)),
                 statistics.mean(d)))
    print()
    print('   라벨 내부 분산 — 라벨을 알아도 개념을 좁힐 수 있는가')
    print('   %-12s %5s %-24s %-24s'
          % ('라벨', 'n', 'range_read(실제)', 'bluff(실제)'))
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        for kk in KEYS:
            v = r['concepts'].get(kk)
            if v is not None:
                by[r['label']][kk].append(v)
    for lab in sorted(by, key=lambda x: -len(by[x].get('range_read', []))):
        rr = by[lab].get('range_read', [])
        bl = by[lab].get('bluff', [])
        if len(rr) < 5:
            continue
        print('   %-12s %5d mean %.2f sd %.2f       mean %.2f sd %.2f'
              % (lab, len(rr), statistics.mean(rr),
                 statistics.pstdev(rr) if len(rr) > 1 else 0,
                 statistics.mean(bl) if bl else 0,
                 statistics.pstdev(bl) if len(bl) > 1 else 0))


def _predict(beh, sig):
    import reads as RD
    best, bd = None, 1e9
    for name, s in sig.items():
        d = 0.0
        for kk, v in s.items():
            o = beh.get(kk)
            if o is None:
                continue
            d += ((o - v) / RD._sig_scale(name, kk)) ** 2
        if d < bd:
            best, bd = name, d
    return best


def stage5(rows):
    """혼동행렬 · 스타일 간 행동 거리 · 관찰 가능한 family 로 묶었을 때 성능.

    정확도 0.18 하나로는 '10개 라벨이 무의미한 것'과 '가까운 라벨끼리는
    구분되는데 너무 잘게 쪼갠 것'을 구별할 수 없다.
    """
    import reads as RD
    print()
    print('⑤ 행동 → 스타일 혼동행렬 (행=실제, 열=예측 top1)')
    labs = sorted({r['label'] for r in rows})
    cm = collections.defaultdict(collections.Counter)
    for r in rows:
        cm[r['label']][_predict(r['beh'], RD.STYLE_SIG)] += 1
    hdr = ''.join('%-11s' % l[:10] for l in labs)
    print('   %-12s%s' % ('', hdr))
    for a in labs:
        row = ''.join('%-11d' % cm[a][b] for b in labs)
        print('   %-12s%s' % (a[:11], row))

    print()
    print('⑥ 스타일 간 행동 거리 (작을수록 구분 불가)')
    keys = ('vpip', 'pfr', 'aggr', 'cbet', 'ftb')
    pairs = []
    for i, a in enumerate(labs):
        for b in labs[i+1:]:
            sa, sb = RD.STYLE_SIG.get(a), RD.STYLE_SIG.get(b)
            if not sa or not sb:
                continue
            d = 0.0
            for kk in keys:
                if kk in sa and kk in sb:
                    d += ((sa[kk]-sb[kk]) / RD._sig_scale(a, kk)) ** 2
            pairs.append((math.sqrt(d), a, b))
    pairs.sort()
    print('   가장 가까운 쌍 8개')
    for d, a, b in pairs[:8]:
        print('     %-12s %-12s  거리 %.2f' % (a, b, d))
    print('   가장 먼 쌍 3개')
    for d, a, b in pairs[-3:]:
        print('     %-12s %-12s  거리 %.2f' % (a, b, d))

    print()
    print('⑦ 관찰 가능한 family 로 묶었을 때')
    FAM = {'TAG_TIGHT': '타이트', 'ROCK': '타이트', 'NIT': '타이트',
           'TAG': '중간', 'STATION': '중간', 'TAG_AGGRO': '중간',
           'LOOSE_REG': '중간', 'FISH': '루즈', 'LAG': '루즈',
           'MANIAC': '루즈'}
    hit = n = 0
    famc = collections.Counter()
    for r in rows:
        p = _predict(r['beh'], RD.STYLE_SIG)
        fa, fp = FAM.get(r['label']), FAM.get(p)
        if fa is None or fp is None:
            continue
        n += 1
        famc[fa] += 1
        hit += 1 if fa == fp else 0
    base = max(famc.values())/max(1, sum(famc.values())) if famc else 0
    print('   family 3종 기준선 %.2f / 분류 정확도 %.2f (n=%d)'
          % (base, hit/max(1, n), n))
    print('   실제 family 분포:', dict(famc))


def stage8(rows):
    """⑧ 행동 → 개념 **직접** 추정 (스타일/라벨 완전 우회).

    ①~⑦ 은 행동 → 라벨 → 개념 경로였고 라벨 단계가 병목이었다. 여기서는
    라벨을 아예 빼고 estimate_concepts(행동 → 잠재요인 → 개념)만 단독으로
    쓴다. **style_belief 는 호출하지 않는다.**

      전부 양수    라벨이 병목 — 직접 경로를 주 경로로
      일부만 양수  개념마다 관찰 가능성이 다름 — identifiability 부여
      전부 0 근처  행동으로 cognition 을 직접 알 수는 없다는 모델 채택
    """
    import reads as RD
    print()
    print('⑧ 행동 → 개념 직접 추정 (스타일 우회)')
    print('   %-14s %6s %6s %6s %7s %7s' % ('개념', 'n', 'MAE', 'RMSE', 'bias', 'corr'))
    acc = collections.defaultdict(lambda: ([], []))
    for r in rows:
        est = RD.perceived_profile(r['book'], r['obs'], r['tgt'],
                                   OBSERVERS['보통'], random.Random(1))
        ec = RD.estimate_concepts(est, OBSERVERS['보통'], random.Random(1))
        for kk in KEYS:
            e = ec['concepts'].get(kk)
            a = r['concepts'].get(kk)
            if e is None or a is None:
                continue
            acc[kk][0].append(e)
            acc[kk][1].append(a)
    for kk in KEYS:
        e, a = acc[kk]
        if len(e) < 10:
            continue
        d = [x-y for x, y in zip(e, a)]
        print('   %-14s %6d %6.2f %6.2f %+7.2f %+7.2f'
              % (kk, len(e), statistics.mean(map(abs, d)),
                 math.sqrt(statistics.mean([x*x for x in d])),
                 statistics.mean(d), corr(e, a)))

    # 관찰자 능력이 직접 경로에서는 효과가 있는가
    print()
    print('   관찰자별 (직접 경로, range_read)')
    for name, prof in OBSERVERS.items():
        e, a = [], []
        for r in rows:
            est = RD.perceived_profile(r['book'], r['obs'], r['tgt'], prof,
                                       random.Random(1))
            ec = RD.estimate_concepts(est, prof, random.Random(1))
            v = ec['concepts'].get('range_read')
            t = r['concepts'].get('range_read')
            if v is None or t is None:
                continue
            e.append(v); a.append(t)
        if len(e) >= 10:
            d = [x-y for x, y in zip(e, a)]
            print('     %-6s MAE %.2f  bias %+.2f  corr %+.2f'
                  % (name, statistics.mean(map(abs, d)),
                     statistics.mean(d), corr(e, a)))


def main():
    rows = collect()
    if not rows:
        print('표본 없음')
        return
    stage1(rows)
    stage2(rows)
    stage3(rows)
    stage4(rows)
    stage5(rows)
    stage8(rows)


if __name__ == '__main__':
    main()




