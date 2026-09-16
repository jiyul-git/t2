#!/usr/bin/env python3
"""⑦ — 축 서열이 경로의 어느 단계에서 생기는가. G1~G4 판별.

  python3 tools/path_test.py rows55b.jsonl.gz

**측정 정의는 CF_DESIGN_PATH.md 2-0-1 ~ 2-0-4 에서 측정 전에 잠갔다**
(커밋 2b768af). 이 파일은 그 정의를 그대로 구현한다. 새 시뮬레이션 없음.

  모집단  attached_O 이고 그 팔의 양쪽 tag 가 정렬·불변량 통과한 쌍
  팔      D (채점). M·T 는 참고 출력
  A       {aggression, discipline, bluff, thin_value_turn, cbet_flop}
          Δp≠0 이 0 인 축은 조건부 크기가 정의되지 않아 제외한다
  R       |Δp≠0| / |모집단|
  S       mean(|Δp|) given Δp≠0        ← median 아님. ⑥ 에서 퇴화했다
  T       |act_lo≠act_hi| / |Δp≠0|
  비      A 위에서의 max/min
  순서    순위 벡터가 flip 순위 벡터와 **완전히 같을 때만** 일치
"""
import sys, gzip, json, re, collections

ARMS = ('D', 'M', 'T')
SCORE_ARM = 'D'
A = ['aggression', 'discipline', 'bluff', 'thin_value_turn', 'cbet_flop']
# ⑥ 에서 고정된 관측 서열 (CF_RESULT_LEVEL1_EXT.md)
FLIP = {'aggression': 9.2, 'discipline': 4.3, 'bluff': 3.5,
        'thin_value_turn': 2.7, 'cbet_flop': 1.0}
PCT = re.compile(r'\(\d+%\)')
SORT_KEY = ('seed', 'hand', 'table', 'pid', 'street')


def ranks(d, keys):
    """큰 값이 1위. 동점은 같은 순위를 주지 않는다 — 있으면 경고한다."""
    vs = [d[k] for k in keys]
    if len(set(vs)) != len(vs):
        return None
    order = sorted(keys, key=lambda k: -d[k])
    return tuple(order)


def spearman(a, b):
    n = len(a)
    ra = {k: i for i, k in enumerate(a)}
    rb = {k: i for i, k in enumerate(b)}
    ks = list(ra)
    xa = [ra[k] for k in ks]; xb = [rb[k] for k in ks]
    ma = sum(xa)/n; mb = sum(xb)/n
    num = sum((x-ma)*(y-mb) for x, y in zip(xa, xb))
    da = sum((x-ma)**2 for x in xa) ** 0.5
    db = sum((y-mb)**2 for y in xb) ** 0.5
    return num/(da*db) if da and db else 0.0


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'rows55b.jsonl.gz'
    op = gzip.open if path.endswith('.gz') else open
    # [arm][axis] -> 집계
    St = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {'pop': 0, 'nz': 0, 'absum': 0.0, 'actne': 0,
                 'rows': [], 'allbr': set()}))
    for line in op(path, 'rt', encoding='utf-8'):
        r = json.loads(line)
        if not r.get('attached_O'):
            continue
        ax = r['axis']
        for arm in ARMS:
            if not all((not r['shift_%s_%s' % (arm, t)])
                       and r['inv_%s_%s' % (arm, t)] for t in ('lo', 'hi')):
                continue
            g = St[arm][ax]
            g['pop'] += 1
            p_lo, p_hi = r['p_%s_lo' % arm], r['p_%s_hi' % arm]
            if p_lo is None or p_hi is None:
                continue
            d = float(p_hi) - float(p_lo)
            if d == 0.0:
                continue
            g['nz'] += 1
            g['absum'] += abs(d)
            if r['act_%s_lo' % arm] != r['act_%s_hi' % arm]:
                g['actne'] += 1
            br = PCT.sub('(N%)', str(r.get('src_O')))
            g['allbr'].add(br)
            g['rows'].append((tuple(r[k] for k in SORT_KEY), br))

    print('# ⑦ G1~G4 판별 — %s' % path)
    print('  정의 고정 커밋 2b768af. 새 시뮬레이션 없음')
    print('  A = %s' % ', '.join(A))
    print('  flip 순서 = %s' % ' > '.join(sorted(FLIP, key=lambda k: -FLIP[k])))
    print()

    for arm in ARMS:
        tag = '  ← 채점' if arm == SCORE_ARM else '  (참고)'
        print('## %s 팔%s' % (arm, tag))
        h = ('%-18s %9s %8s %8s %10s %8s %8s %7s'
             % ('축', '모집단', 'Δp≠0', 'R', 'S', 'act≠', 'T', '전수br'))
        print(h); print('-'*len(h))
        for ax in sorted(St[arm], key=lambda k: (k not in A, k)):
            g = St[arm][ax]
            R = g['nz']/g['pop'] if g['pop'] else 0.0
            S = g['absum']/g['nz'] if g['nz'] else float('nan')
            T = g['actne']/g['nz'] if g['nz'] else float('nan')
            mark = '' if ax in A else '  (A 밖)'
            print('%-18s %9d %8d %7.3f%% %10.5f %8d %7.3f %7d%s'
                  % (ax, g['pop'], g['nz'], 100*R,
                     S if S == S else 0.0, g['actne'],
                     T if T == T else 0.0, len(g['allbr']), mark))
        print()

    g = St[SCORE_ARM]
    R = {ax: g[ax]['nz']/g[ax]['pop'] for ax in A}
    S = {ax: g[ax]['absum']/g[ax]['nz'] for ax in A}
    T = {ax: g[ax]['actne']/g[ax]['nz'] for ax in A}

    # --- G3: 동일 표본수 N, 결정론적 앞 N 개 ---
    N = min(g[ax]['nz'] for ax in A)
    B = {}
    for ax in A:
        rows = sorted(g[ax]['rows'], key=lambda x: x[0])[:N]
        B[ax] = len(set(b for _, b in rows))

    flip_order = tuple(sorted(FLIP, key=lambda k: -FLIP[k]))
    print('## 판별 통계량 (D 팔, A 다섯 축)')
    h = '%-18s %9s %10s %8s %8s   %6s' % ('축', 'R', 'S', 'T', 'B(N)', 'flip')
    print(h); print('-'*len(h))
    for ax in flip_order:
        print('%-18s %8.3f%% %10.5f %8.3f %8d   %5.1f%%'
              % (ax, 100*R[ax], S[ax], T[ax], B[ax], FLIP[ax]))
    print()
    print('  G3 공통 표본수 N = %d  (A 중 최소 Δp≠0 건수)' % N)
    print()

    def report(name, d):
        o = ranks(d, A)
        if o is None:
            # 동점이 있으면 **엄격 순서와 완전 일치할 수 없다** → 기준상 불일치.
            # 판정 기준(완전 일치)은 그대로다. 출력만 사유를 밝힌다.
            tie = collections.Counter(d[k] for k in A)
            dup = [v for v, c in tie.items() if c > 1]
            print('  %-6s 동점 %s → 엄격 순서와 완전 일치 불가   **어긋남**'
                  % (name, ', '.join('%g×%d' % (v, tie[v]) for v in sorted(dup))))
            print('  %-6s 값: %s' % ('', '  '.join('%s %g' % (k, d[k]) for k in flip_order)))
            return None, False
        ok = (o == flip_order)
        rho = spearman(o, flip_order)
        print('  %-6s %-62s %s   ρ=%+.3f'
              % (name, ' > '.join(o), '일치' if ok else '**어긋남**', rho))
        return o, ok

    print('## 순서 판정 — 완전 일치만 "일치"')
    print('  %-6s %s' % ('flip', ' > '.join(flip_order)))
    _, R_ok = report('R', R)
    _, S_ok = report('S', S)
    _, T_ok = report('T', T)
    _, B_ok = report('B', B)
    print()
    print('  ρ 는 n=5 라 참고 수치다. 판정에 쓰지 않는다')
    print()

    rt = lambda d: max(d.values())/min(d.values()) if min(d.values()) else float('inf')
    Rr, Sr, Tr = rt(R), rt(S), rt(T)
    print('## 비 (A 위 max/min)')
    print('  R 비 %.3f    S 비 %.3f    T 비 %.3f' % (Rr, Sr, Tr))
    print()

    print('## 채점')
    g1 = (Sr < 2.0) and bool(R_ok)
    g2 = (Rr < 2.0) and bool(S_ok)
    g3 = bool(B_ok)
    g4_rej = (Tr < 1.5)
    g4 = (not g4_rej) and bool(T_ok) and (R_ok is False)
    for nm, ok, why in (
        ('G1 도달 지배', g1, 'S비 %.3f < 2.0 : %s   R순서 일치 : %s'
            % (Sr, Sr < 2.0, R_ok)),
        ('G2 크기 지배', g2, 'R비 %.3f < 2.0 : %s   S순서 일치 : %s'
            % (Rr, Rr < 2.0, S_ok)),
        ('G3 분기 다양성', g3, 'B순서 일치 : %s' % B_ok),
        ('G4 하류 전달', g4, 'T비 %.3f >= 1.5 : %s   T순서 일치 : %s   R순서 불일치 : %s'
            % (Tr, not g4_rej, T_ok, R_ok is False)),
    ):
        print('  %-14s %-8s %s' % (nm, '잔존' if ok else '**기각**', why))
    print()
    print('  네 가설이 전부 기각될 수 있다. 그러면 그대로 기록한다 (설계 6절).')


if __name__ == '__main__':
    main()
