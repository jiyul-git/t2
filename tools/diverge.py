#!/usr/bin/env python3
"""⑧ P1·P3 — 축별 경로 분화 관측. **채점하지 않는다.**

  python3 tools/diverge.py rows55b.jsonl.gz

설계는 CF_DESIGN_DIVERGE.md (커밋 3b1fea7). 그 설계대로만 낸다.
새 시뮬레이션 없음 — rows55b 만 읽는다.

  P1  D 팔에서 축별 Δp≠0 의 **분기 점유 분포**
      ⑦ 의 B(가짓수)와 다른 질문이다. B 를 다시 채점하지 않는다
  P3  M 팔에서 plan·src **전이 행렬** 원자료
      요약 통계로 압축하지 않는다

  P2 는 이 도구에서 내지 않는다. 설계 6절에 따라 P1 을 보고 판별 기준을
  별도 커밋으로 고정한 뒤에 한다.

분기 = normalize(src) = re.sub(r'\\(\\d+%\\)', '(N%)', src)
"""
import sys, gzip, json, re, collections

PCT = re.compile(r'\(\d+%\)')
A = ['aggression', 'discipline', 'bluff', 'thin_value_turn', 'cbet_flop']
OUT = ['potcontrol', 'looseness']


def norm(x):
    return PCT.sub('(N%)', str(x))


def aligned(r, arm):
    return all((not r['shift_%s_%s' % (arm, t)]) and r['inv_%s_%s' % (arm, t)]
               for t in ('lo', 'hi'))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'rows55b.jsonl.gz'
    op = gzip.open if path.endswith('.gz') else open

    occ = collections.defaultdict(collections.Counter)      # P1: axis -> branch -> n
    nz = collections.Counter()                              # axis -> Δp≠0 수
    srcdiff = collections.Counter()                         # D 팔 src_lo != src_hi
    srcpair = collections.defaultdict(collections.Counter)  # 그때의 (lo, hi)
    mplan = collections.defaultdict(collections.Counter)    # P3: axis -> (lo,hi) plan
    msrc = collections.defaultdict(collections.Counter)     # P3: axis -> (lo,hi) src
    mnz = collections.Counter()

    for line in op(path, 'rt', encoding='utf-8'):
        r = json.loads(line)
        if not r.get('attached_O'):
            continue
        ax = r['axis']
        # ---- P1 (D 팔) ----
        if aligned(r, 'D'):
            lo, hi = r['p_D_lo'], r['p_D_hi']
            if lo is not None and hi is not None and float(hi) - float(lo) != 0.0:
                nz[ax] += 1
                occ[ax][norm(r['src_O'])] += 1
                a, b = norm(r['src_D_lo']), norm(r['src_D_hi'])
                if a != b:
                    srcdiff[ax] += 1
                    srcpair[ax][(a, b)] += 1
        # ---- P3 (M 팔) ----
        if aligned(r, 'M'):
            lo, hi = r['p_M_lo'], r['p_M_hi']
            if lo is not None and hi is not None and float(hi) - float(lo) != 0.0:
                mnz[ax] += 1
                mplan[ax][(r['plan_M_lo'], r['plan_M_hi'])] += 1
                msrc[ax][(norm(r['src_M_lo']), norm(r['src_M_hi']))] += 1

    print('# ⑧ P1·P3 — %s' % path)
    print('  설계 3b1fea7. **채점하지 않는다.** P2 는 여기서 내지 않는다')
    print()

    # ================= P1 =================
    print('## P1 — D 팔, 축별 Δp≠0 의 분기 점유 분포')
    print()
    for ax in A + OUT:
        n = nz[ax]
        mark = '' if ax in A else '   (A 밖)'
        print('%-18s Δp≠0 %6d   분기 %d종%s' % (ax, n, len(occ[ax]), mark))
        if not n:
            continue
        for br, c in occ[ax].most_common():
            print('      %6d  %5.1f%%   %s' % (c, 100.0*c/n, br[:66]))
        print()

    print('### P1-b — 분기별로 본 같은 표 (어느 분기를 어느 축이 쓰는가)')
    print()
    allbr = collections.Counter()
    for ax in A:
        allbr.update(occ[ax])
    for br, tot in allbr.most_common():
        print('  %s' % br[:72])
        for ax in A:
            c = occ[ax].get(br, 0)
            if c:
                print('      %-18s %6d  (그 축 Δp≠0 의 %5.1f%%)'
                      % (ax, c, 100.0*c/nz[ax]))
        print()

    # ---- 설계 1-1 확인 ----
    print('### P1-c — 설계 1-1 확인: D 팔에서 src_lo != src_hi 인 건수')
    print()
    print('  설계는 "plan 이 안 바뀌므로 size==0 경우에만 갈린다" 고 추론했다.')
    print('  실측으로 확인한다.')
    print()
    for ax in A:
        print('  %-18s %6d / %6d' % (ax, srcdiff[ax], nz[ax]))
        for (a, b), c in srcpair[ax].most_common(4):
            print('        %5d   %s' % (c, ('%s  →  %s' % (a[:30], b[:30]))))
    print()

    # ================= P3 =================
    print('## P3 — M 팔, plan·src 전이 행렬 (원자료. 압축하지 않는다)')
    print()
    for ax in A + OUT:
        n = mnz[ax]
        mark = '' if ax in A else '   (A 밖)'
        print('%-18s Δp≠0 %6d%s' % (ax, n, mark))
        if not n:
            print()
            continue
        diag = sum(c for (a, b), c in mplan[ax].items() if a == b)
        print('    plan 전이   대각(변화 없음) %d / %d = %.1f%%'
              % (diag, n, 100.0*diag/n))
        off = [(k, c) for k, c in mplan[ax].items() if k[0] != k[1]]
        for (a, b), c in sorted(off, key=lambda x: -x[1]):
            print('        %6d   %-18s →  %s' % (c, a, b))
        if not off:
            print('        (비대각 없음)')
        dg = sum(c for (a, b), c in msrc[ax].items() if a == b)
        print('    src 전이    대각(변화 없음) %d / %d = %.1f%%'
              % (dg, n, 100.0*dg/n))
        of = [(k, c) for k, c in msrc[ax].items() if k[0] != k[1]]
        for (a, b), c in sorted(of, key=lambda x: -x[1])[:6]:
            print('        %6d   %-34s →  %s' % (c, a[:34], b[:34]))
        if len(of) > 6:
            print('        … 비대각 %d종 중 상위 6종' % len(of))
        if not of:
            print('        (비대각 없음)')
        print()
    print('  **flip 서열 채점에 M 팔을 쓰지 않는다** (설계 1-2·5절).')


if __name__ == '__main__':
    main()
