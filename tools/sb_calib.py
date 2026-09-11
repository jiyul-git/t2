#!/usr/bin/env python3
"""세미블러프 확률식 `min(0.95, 0.25 + 0.24*sk)` 의 실측 calibration.

plan.py 는 읽기만 한다. 수집된 intent 에서 아래를 잰다.

  1. 게이트 도달 표본을 복원한다
       분기 순서상 semibluff 테스트는 `eq >= pcz` 가 거짓일 때만 실행된다.
       why 의 **그 스트리트 접두사** 로 어느 분기가 발화했는지 식별해서
       semibluff 이하 분기(semibluff / bluff_2street / 최종 else)만 남긴다.
  2. 그중 `outs>=8 and behind<=1 and sk>=0.4` 를 만족한 건 = 주사위가
       실제로 굴려진 건이다 (파이썬 and 는 단락평가라 앞이 깨지면 안 굴린다).
  3. 예측 p 와 실측 P(plan=='semibluff') 를 sk 구간별 / outs 구간별로 비교한다.
  4. outs 가 식에 안 들어간다는 주장을 표본으로 확인한다 —
       채택군과 도달군의 outs 분포가 같아야 한다.

사용: python3 tools/sb_calib.py collected.jsonl [...]
"""
import os, sys, json, math, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
import persona as PS

# make_plan 각 분기가 남기는 사유 문자열의 지문.
# (CLAUDE.md 5 — why 는 스트리트를 넘어 누적되므로 접두사로 걸러야 한다)
ABOVE = ('3스트리트 밸류', '밸류 → 3스트리트', '지만 위험',
         '블락벳으로 가격 통제', '중간강도(', '중간강도이나')
SB     = '→ 세미블러프'
BLUFF  = '쇼다운 가치 없음 + 블로커'
ELSE_  = ('쇼다운 가치 있음 →', '쇼다운 가치 없고')


def street_why(i):
    """이 스트리트에 붙은 why 줄만."""
    pre = '%s: ' % i['street']
    w = i['why'] if isinstance(i['why'], list) else [i['why']]
    return [x[len(pre):] for x in w if x.startswith(pre)]


def branch_of(i):
    """make_plan 의 어느 분기에서 계획이 확정됐는지."""
    ws = street_why(i)
    for w in ws:
        if SB in w:
            return 'semibluff'
    for w in ws:
        if w.startswith(BLUFF):
            return 'bluff'
    for w in ws:
        if any(w.startswith(e) for e in ELSE_):
            return 'else'
    for w in ws:
        if any(a in w for a in ABOVE):
            return 'above'
    return None          # revise_plan/refresh 산물 — make_plan 이 아니다


def p_formula(sk):
    return min(0.95, 0.25 + 0.24 * sk)


def river_odds(outs, street):
    """물리적 완성 확률. 판단에 쓰는 값이 아니라 비교용 기준선."""
    left = 47 if street == 'flop' else 46
    n = 2 if street == 'flop' else 1
    q = 1.0
    for k in range(n):
        q *= float(left - k - outs) / (left - k)
    return 1.0 - max(0.0, q)


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0.0, c-h), min(1.0, c+h))


def load(paths, pure=True):
    """intent 를 읽는다.

    pure=True 면 `eq_sims == 400` 인 레코드만 남긴다. **이 필터가 없으면
    분석이 조용히 오염된다.**

    refresh(plan.py:1682) 는 같은 스트리트에서 `eq`·`rel`·`outs`·`made` 를
    덮어쓰면서 make_plan 이 남긴 `why` 는 그대로 둔다. 그래서 why 로 분기를
    식별하면 make_plan 의 판단이 맞게 잡히지만, 그 옆에 붙은 숫자는 **판단
    이후의 값**이다. 임계값(eq vs pcz)이나 게이트(outs>=8)를 그 숫자로
    되짚으면 존재하지 않은 판단을 재구성하게 된다.

    두 경로는 sims 로 구분된다 — make_plan 400, refresh 300.
    덮인 레코드는 `outs` 가 calc_noise 를 안 거친 날것이라 항상
    outs == outs_true 가 되고, 체감/물리 괴리가 인위적으로 0 이 된다.

    실측: 정제 전 후보 114건 중 51건(45%)이 덮인 레코드였다.
    """
    rows, dropped, rec = [], 0, 0
    for path in paths:
        for line in open(path):
            r = json.loads(line)
            rec += 1
            for i in r.get('intents', []):
                prof = r['profiles'].get(str(i['seat'])) or {}
                if not prof.get('concepts'):
                    continue                 # 개념 없는 봇은 sk() 경로가 다르다
                if pure and i.get('eq_sims') != 400:
                    dropped += 1
                    continue
                i['_prof'] = prof
                i['_hand'] = r['hand_no']
                i['_hole'] = r['hole'].get(str(i['seat']))
                i['_src'] = os.path.basename(path)
                # 핸드 단위 맥락은 **여기서 붙인다**. 나중에 (파일, hand_no) 로
                # 조인하면 안 된다 — 합본 파일은 토너먼트마다 hand_no 가 1 부터
                # 다시 시작해서 키가 충돌하고, 조용히 남의 보드가 붙는다.
                # (실측: 4x250 합본에서 전수표의 보드·드로우 태그가 통째로 틀렸다)
                i['_rec'] = rec
                i['_board'] = list(r.get('board') or [])
                i['_full_log'] = [tuple(x) for x in (r.get('full_log') or [])]
                i['_blinds'] = tuple(r.get('blinds') or (0, 0))
                rows.append(i)
    load.dropped = dropped
    return rows


def main():
    paths = sys.argv[1:] or [os.path.join(D, 'collected.jsonl')]
    rows = load(paths)
    for i in rows:
        i['_branch'] = branch_of(i)
        i['_sk'] = PS.sk(i['_prof'], 'semibluff') / 3.33

    mp = [i for i in rows if i['_branch']]
    print('intent %d건 (refresh 가 덮은 %d건 제외) · make_plan 분기 식별 %d건'
          % (len(rows), getattr(load, 'dropped', 0), len(mp)))
    c = collections.Counter(i['_branch'] for i in mp)
    for k in ('above', 'semibluff', 'bluff', 'else'):
        print('   %-10s %4d (%4.1f%%)' % (k, c[k], 100*c[k]/max(1, len(mp))))
    print()

    # ---- 1. 주사위가 실제로 굴려진 표본 ----
    below = [i for i in mp if i['_branch'] != 'above']
    rolled = [i for i in below
              if i['outs'] >= 8 and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4]
    print('=' * 78)
    print('1. 세미블러프 주사위가 굴려진 표본')
    print('=' * 78)
    print('eq < pcz 로 내려온 건            %d' % len(below))
    print('  중 outs>=8                     %d' % sum(1 for i in below if i['outs'] >= 8))
    print('  중 outs>=8 & behind<=1         %d' % sum(1 for i in below
                                                      if i['outs'] >= 8 and i.get('behind',0) <= 1))
    print('  중 + sk>=0.4  (= 주사위 실행)  %d' % len(rolled))
    took = [i for i in rolled if i['_branch'] == 'semibluff']
    exp = sum(p_formula(i['_sk']) for i in rolled)
    lo, hi = wilson(len(took), len(rolled))
    print()
    print('예측 채택수 Σp  %.1f  (평균 p %.3f)' % (exp, exp/max(1,len(rolled))))
    print('실측 채택수     %d    (실측률 %.3f, 95%% CI %.3f~%.3f)'
          % (len(took), len(took)/max(1,len(rolled)), lo, hi))
    print()

    # ---- 2. sk 축: 식이 의도한 대로 움직이는가 ----
    print('=' * 78)
    print('2. sk(개념) 축 — 식이 유일하게 반응하는 축')
    print('=' * 78)
    print('%-14s %5s %8s %8s %9s   %s' % ('sk(0~3)', 'n', '예측p', '실측p', '차이', '원개념'))
    print('-' * 78)
    bins = [(0.4, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.01)]
    for a, b in bins:
        sub = [i for i in rolled if a <= i['_sk'] < b]
        if not sub:
            continue
        pe = sum(p_formula(i['_sk']) for i in sub) / len(sub)
        k = sum(1 for i in sub if i['_branch'] == 'semibluff')
        po = k / len(sub)
        print('%-14s %5d %8.3f %8.3f %+9.3f   %.1f~%.1f'
              % ('%.1f~%.1f' % (a, b), len(sub), pe, po, po - pe, a*3.33, b*3.33))
    print()

    # ---- 3. outs 축: 식에 없는 축 ----
    print('=' * 78)
    print('3. outs(객관적 드로우 강도) 축 — 식에 들어가지 않는 축')
    print('=' * 78)
    # 완성확률은 여기 붙이지 않는다. 이 축은 **체감** outs 라서
    # 물리적 완성확률을 갖다 붙이면 존재하지 않는 확률이 된다.
    # 물리 기준 완성확률은 아래 10번(스트리트로 나눈 표)에 있다.
    print('%-7s %5s %8s %8s %9s %10s' % ('체감outs', 'n', '예측p', '실측p', '차이', '물리outs'))
    print('-' * 78)
    for o in sorted(set(i['outs'] for i in rolled)):
        sub = [i for i in rolled if i['outs'] == o]
        pe = sum(p_formula(i['_sk']) for i in sub) / len(sub)
        k = sum(1 for i in sub if i['_branch'] == 'semibluff')
        po = k / len(sub)
        ot = sum(i['outs_true'] for i in sub) / len(sub)
        print('%-7d %5d %8.3f %8.3f %+9.3f %10.1f'
              % (o, len(sub), pe, po, po - pe, ot))
    print()

    # ---- 4. 선택압 검정 ----
    print('=' * 78)
    print('4. 채택군 vs 도달군 — 드로우 강도에 선택압이 있는가')
    print('=' * 78)

    def ms(v):
        n = len(v)
        if n == 0:
            return (0.0, 0.0, 0)
        m = sum(v)/n
        sd = math.sqrt(sum((x-m)**2 for x in v)/max(1, n-1))
        return (m, sd, n)

    rej = [i for i in rolled if i['_branch'] != 'semibluff']
    for name, grp in (('채택(semibluff)', took), ('기각(그 외)', rej)):
        mo, so, n = ms([i['outs'] for i in grp])
        mk, sk_, _ = ms([i['_sk'] for i in grp])
        me, se, _ = ms([i['eq'] for i in grp])
        print('%-18s n=%-4d outs %.2f±%.2f   sk %.2f±%.2f   eq %.3f±%.3f'
              % (name, n, mo, so, mk, sk_, me, se))
    mo1, so1, n1 = ms([i['outs'] for i in took])
    mo2, so2, n2 = ms([i['outs'] for i in rej])
    if n1 > 1 and n2 > 1:
        se = math.sqrt(so1**2/n1 + so2**2/n2)
        print('  outs 차이 %+.3f  (t = %+.2f)' % (mo1-mo2, (mo1-mo2)/se if se else 0.0))
    mk1, sk1, _ = ms([i['_sk'] for i in took])
    mk2, sk2, _ = ms([i['_sk'] for i in rej])
    if n1 > 1 and n2 > 1:
        se = math.sqrt(sk1**2/n1 + sk2**2/n2)
        print('  sk   차이 %+.3f  (t = %+.2f)' % (mk1-mk2, (mk1-mk2)/se if se else 0.0))
    print()

    # ---- 5. 기각된 드로우가 어디로 갔는가 ----
    print('=' * 78)
    print('5. 주사위에서 기각된 드로우의 종착지')
    print('=' * 78)
    cc = collections.Counter((i['_branch'], i['plan']) for i in rej)
    for (b, p), v in cc.most_common():
        print('   %-8s → %-14s %4d (%4.1f%%)' % (b, p, v, 100*v/max(1, len(rej))))
    print()
    gv = [i for i in rej if i['plan'] == 'giveup']
    print('   기각 → giveup %d건의 outs 분포: %s'
          % (len(gv), dict(sorted(collections.Counter(i['outs'] for i in gv).items()))))
    print()

    # ---- 6. 두 축의 눈금 비교 ----
    print('=' * 78)
    print('6. 두 축의 눈금 — 어느 쪽이 확률을 더 많이 흔드는가')
    print('=' * 78)
    print('   개념 축 : p(sk=0.4)=%.3f → p(sk=3.0)=%.3f   배율 %.2f배'
          % (p_formula(0.4), p_formula(3.0), p_formula(3.0)/p_formula(0.4)))
    fl8, fl13 = river_odds(8, 'flop'), river_odds(13, 'flop')
    print('   드로우 축: 완성 %.3f(8아웃) → %.3f(13아웃)      배율 %.2f배  (식 반영 0배)'
          % (fl8, fl13, fl13/fl8))
    print()

    # ---- 8. 선점 인구조사 ----
    print('=' * 78)
    print('8. 선점(preemption) — 같은 드로우 조건에서 eq >= pcz 가 먼저 가져간 몫')
    print('=' * 78)
    cond = lambda i: (i['outs'] >= 8 and i.get('behind', 0) <= 1 and i['_sk'] >= 0.4)
    ab = [i for i in mp if i['_branch'] == 'above' and cond(i)]
    tot = len(ab) + len(rolled)
    print('   조건 충족 make_plan 건               %3d' % tot)
    print('   eq >= pcz 로 선점 (주사위 미실행)    %3d (%.1f%%)' % (len(ab), 100*len(ab)/max(1,tot)))
    print('   eq <  pcz 로 주사위 실행             %3d (%.1f%%)' % (len(rolled), 100*len(rolled)/max(1,tot)))
    if ab:
        print('   선점군 eq %.3f / outs_true %.2f   계획 %s'
              % (sum(i['eq'] for i in ab)/len(ab),
                 sum(i['outs_true'] for i in ab)/len(ab),
                 dict(collections.Counter(i['plan'] for i in ab).most_common())))
    print()

    # ---- 9. 게이트가 보는 outs 는 체감값이다 ----
    print('=' * 78)
    print('9. 게이트가 읽는 outs 는 calc_noise 를 거친 체감값이다')
    print('=' * 78)
    if rolled:
        m1 = sum(i['outs'] for i in rolled)/len(rolled)
        m2 = sum(i['outs_true'] for i in rolled)/len(rolled)
        print('   물리 outs_true 분포 %s' % dict(sorted(collections.Counter(
            i['outs_true'] for i in rolled).items())))
        print('   체감 outs      분포 %s' % dict(sorted(collections.Counter(
            i['outs'] for i in rolled).items())))
        print('   평균 체감 %.2f vs 물리 %.2f  (과대 +%.2f아웃, %.0f%%)'
              % (m1, m2, m1-m2, 100*(m1/max(1e-9, m2)-1)))
        print('   물리 outs_true < 8 인데 게이트를 통과한 건 %d'
              % sum(1 for i in rolled if i['outs_true'] < 8))
    print()

    # ---- 10. 스트리트로 나눈 물리 강도 ----
    print('=' * 78)
    print('10. 스트리트로 나눈 물리 드로우 강도 (플랍·턴 혼재 제거)')
    print('=' * 78)
    for st in ('flop', 'turn'):
        sub = [i for i in rolled if i['street'] == st]
        if not sub:
            continue
        print('-- %s  n=%d' % (st, len(sub)))
        print('   %-10s %4s %8s %8s %10s' % ('outs_true', 'n', '예측p', '실측p', '완성확률'))
        for o in sorted(set(i['outs_true'] for i in sub)):
            s2 = [i for i in sub if i['outs_true'] == o]
            pe = sum(p_formula(i['_sk']) for i in s2)/len(s2)
            k = sum(1 for i in s2 if i['_branch'] == 'semibluff')
            print('   %-10d %4d %8.3f %8.3f %9.1f%%'
                  % (o, len(s2), pe, k/len(s2), river_odds(o, st)*100))
    print()

    # ---- 11. 상관 ----
    print('=' * 78)
    print('11. 배정된 확률과 객관적 강도의 상관')
    print('=' * 78)

    def corr(xs, ys):
        n = len(xs)
        if n < 2:
            return 0.0
        mx, my = sum(xs)/n, sum(ys)/n
        sx = math.sqrt(sum((x-mx)**2 for x in xs))
        sy = math.sqrt(sum((y-my)**2 for y in ys))
        if sx == 0 or sy == 0:
            return 0.0
        return sum((x-mx)*(y-my) for x, y in zip(xs, ys))/(sx*sy)

    if rolled:
        ps = [p_formula(i['_sk']) for i in rolled]
        ro = [river_odds(i['outs_true'], i['street']) for i in rolled]
        print('   corr(p, 완성확률)   %+.3f   ← 식이 강도를 보지 않는다는 뜻' % corr(ps, ro))
        print('   corr(p, outs_true)  %+.3f' % corr(ps, [i['outs_true'] for i in rolled]))
        print('   corr(outs_true, sk) %+.3f   ← 개념 높은 봇이 더 강한 드로우를 들고 온다'
              % corr([i['outs_true'] for i in rolled], [i['_sk'] for i in rolled]))
        e8 = [p_formula(i['_sk']) for i in rolled if i['outs_true'] == 8]
        if e8:
            print('   물리 8아웃 %d건 안에서 p 범위 %.3f~%.3f (%.2f배) — 같은 드로우, 개념만으로'
                  % (len(e8), min(e8), max(e8), max(e8)/min(e8)))
    print()

    # ---- 7. 필드 전체의 sk 분포 ----
    print('=' * 78)
    print('7. 필드의 semibluff 개념 분포 → p 분포')
    print('=' * 78)
    seen, sks = set(), []
    for i in rows:
        key = (i['_src'], i['seat'], id(i['_prof']))
        t = i['_prof'].get('concepts', {}).get('semibluff')
        if t is None:
            continue
        sks.append(t)
    if sks:
        sks.sort()
        q = lambda f: sks[min(len(sks)-1, int(f*len(sks)))]
        print('   개념(0~10)  p10 %.1f  중앙 %.1f  p90 %.1f' % (q(.10), q(.50), q(.90)))
        print('   게이트(>=1.33) 통과 비율 %.1f%%'
              % (100*sum(1 for x in sks if x/3.33 >= 0.4)/len(sks)))
        for f in (0.10, 0.50, 0.90):
            print('   p(개념 %.1f) = %.3f' % (q(f), p_formula(q(f)/3.33)))


if __name__ == '__main__':
    main()
