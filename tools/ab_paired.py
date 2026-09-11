#!/usr/bin/env python3
"""A/B 짝지은 상세 비교. plan.py 는 읽기만 한다.

    python3 tools/ab_paired.py A0,A1,... B0,B1,...

묻는 것
-------
가설: "block 확률이 rel 을 무시해서 **강한 밸류**가 block 으로 샌다."
그러면 B(rel>=0.65)에서 변화가 나타나고 A(rel<0.65)에는 불필요한 변화가
거의 없어야 설득력이 있다.

짝짓기의 한계 — 반드시 먼저 읽을 것
-----------------------------------
tourney.next_hand 는 핸드마다 self.rng 에서 시드를 하나 뽑는다(121줄).
그런데 tourney:199 가 **새 플레이어를 앉힐 때 같은 rng 를 소비**한다.
탈락·착석 패턴은 결과에 의존하므로, 코드가 바뀌면 어느 시점부터 딜 자체가
갈라진다. 이 도구는 (파일, hand_no) 로 짝지어 **보드가 실제로 같은 핸드가
몇 %인지 먼저 재고**, 그 부분집합에서만 "동일 핸드 행동 변화"를 센다.
"""
import os, sys, json, math, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import persona as PS


def load(paths):
    """(파일, 토너먼트 순번, hand_no) 로 키를 만든다.

    **(파일, hand_no) 로 키를 잡으면 안 된다** — collect.py 는 히어로가
    파산하면 새 토너먼트를 시작하고 hand_no 가 1 부터 다시 시작한다.
    그래서 한 파일 안에서 hand_no 가 반복되고, 6,000핸드가 541개 키로
    뭉개진다(실측). 토너먼트 경계는 hand_no 가 줄어드는 지점으로 찾는다.

    A/B 는 같은 --seed0 를 같은 순서로 쓰므로 k번째 토너먼트끼리 대응한다.
    대응이 실제로 맞는지는 아래 0번에서 보드 일치율로 검증한다.
    """
    out = {}
    for p in paths:
        suf = os.path.basename(p).split('_')[-1]
        tno, prev = 0, None
        for l in open(p):
            r = json.loads(l)
            hn = r['hand_no']
            if prev is not None and hn <= prev:
                tno += 1
            prev = hn
            out[(suf, tno, hn)] = r
    return out


def flop_intents(r):
    """좌석 → 플랍 intent (첫 번째)."""
    d = {}
    for i in r.get('intents', []):
        if i.get('street') == 'flop' and i.get('seat') is not None:
            d.setdefault(int(i['seat']), i)
    return d


def won_of(r):
    seats = [str(s) for s in (r.get('seats') or [])]
    bf, af = r.get('stacks_before') or {}, r.get('stacks_after') or {}
    d = {k: af.get(k, 0) - bf.get(k, 0) for k in seats}
    return d if sum(d.values()) == 0 else None      # 칩 주입 핸드는 제외


def stat(v):
    if not v:
        return (float('nan'),) * 3 + (0,)
    v = sorted(v)
    n = len(v)
    m = sum(v) / n
    med = v[n // 2] if n % 2 else (v[n//2 - 1] + v[n//2]) / 2
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / max(1, n - 1))
    return m, med, sd, n


def main():
    if len(sys.argv) < 3:
        print(__doc__); return
    A = load(sys.argv[1].split(','))
    B = load(sys.argv[2].split(','))
    common = sorted(set(A) & set(B))
    print('=' * 96)
    print('0. 짝짓기가 어디까지 성립하는가')
    print('=' * 96)
    print('   A %d핸드 · B %d핸드 · 공통 키 %d' % (len(A), len(B), len(common)))
    same_board = [k for k in common if A[k].get('board') == B[k].get('board')]
    same_hole = [k for k in same_board if A[k].get('hole') == B[k].get('hole')]
    print('   보드가 같은 핸드   %5d (%.1f%%)' % (len(same_board), 100*len(same_board)/max(1, len(common))))
    print('   홀카드까지 같은 핸드 %5d (%.1f%%)' % (len(same_hole), 100*len(same_hole)/max(1, len(common))))
    print('   → 아래 6번(동일 핸드 행동 변화)은 홀카드까지 같은 %d핸드에서만 센다.'
          % len(same_hole))
    print('     나머지는 애초에 다른 게임이라 비교 대상이 아니다.')
    print()

    # ---------- 1~4 : 계획별 손익 ----------
    def by_plan(S):
        d = collections.defaultdict(list)
        for r in S.values():
            w = won_of(r)
            if w is None:
                continue
            for s, i in flop_intents(r).items():
                if str(s) in w:
                    d[i.get('plan')].append(w[str(s)])
        return d

    def v2_split(S):
        """value_2street 를 rel 0.65 로 가른다 (decide_aggression 이 쓰는 값)."""
        out = {'value_2street 전체': [], 'B rel>=0.65': [], 'A rel<0.65': []}
        for r in S.values():
            w = won_of(r)
            if w is None:
                continue
            for s, i in flop_intents(r).items():
                if i.get('plan') != 'value_2street' or str(s) not in w:
                    continue
                out['value_2street 전체'].append(w[str(s)])
                (out['B rel>=0.65'] if i.get('rel', 0) >= 0.65
                 else out['A rel<0.65']).append(w[str(s)])
        return out

    pa, pb = by_plan(A), by_plan(B)
    va, vb = v2_split(A), v2_split(B)

    print('=' * 96)
    print('1~3. value_2street 전체 / B(rel>=0.65) / A(rel<0.65) 의 좌석 손익')
    print('=' * 96)
    print('%-20s %10s %10s %8s | %10s %10s %8s | %10s'
          % ('집단', 'A 평균', 'A 중앙', 'A n', 'B 평균', 'B 중앙', 'B n', '평균차'))
    print('-' * 96)
    for k in ('value_2street 전체', 'B rel>=0.65', 'A rel<0.65'):
        m1, d1, s1, n1 = stat(va[k])
        m2, d2, s2, n2 = stat(vb[k])
        print('%-20s %10.0f %10.0f %8d | %10.0f %10.0f %8d | %+10.0f'
              % (k, m1, d1, n1, m2, d2, n2, m2 - m1))
    print()
    print('   가설이 맞다면 B 집단에서 변화가 나타나고 A 집단은 거의 그대로여야 한다.')
    print()

    print('=' * 96)
    print('4. 계획별 좌석 손익 — 평균/중앙값')
    print('=' * 96)
    print('%-16s %9s %9s %7s | %9s %9s %7s | %9s'
          % ('플랍 계획', 'A 평균', 'A 중앙', 'A n', 'B 평균', 'B 중앙', 'B n', '평균차'))
    print('-' * 96)
    for k in sorted(set(pa) | set(pb), key=lambda x: -(len(pa.get(x, [])) + len(pb.get(x, [])))):
        if k is None:
            continue
        m1, d1, s1, n1 = stat(pa.get(k, []))
        m2, d2, s2, n2 = stat(pb.get(k, []))
        print('%-16s %9.0f %9.0f %7d | %9.0f %9.0f %7d | %+9.0f'
              % (k, m1, d1, n1, m2, d2, n2,
                 (m2 - m1) if n1 and n2 else float('nan')))
    print()

    # ---------- 5 : bet/check ----------
    print('=' * 96)
    print('5. bet/check 빈도 변화 (플랍 intent 기준)')
    print('=' * 96)

    def acts(S):
        c = collections.Counter()
        for r in S.values():
            for s, i in flop_intents(r).items():
                c[i.get('action')] += 1
        return c
    ca, cb = acts(A), acts(B)
    keys = ['bet', 'raise', 'call', 'check', 'fold']
    ta, tb = sum(ca[k] for k in keys), sum(cb[k] for k in keys)
    print('%-10s %9s %8s | %9s %8s | %8s' % ('액션', 'A', 'A %', 'B', 'B %', '%p 차'))
    print('-' * 62)
    for k in keys:
        print('%-10s %9d %7.1f%% | %9d %7.1f%% | %+7.1f%%p'
              % (k, ca[k], 100*ca[k]/max(1, ta), cb[k], 100*cb[k]/max(1, tb),
                 100*cb[k]/max(1, tb) - 100*ca[k]/max(1, ta)))
    print()

    # ---------- 6 : 동일 핸드 행동 변화 ----------
    print('=' * 96)
    print('6. 동일 핸드(홀카드까지 일치)에서 행동이 실제로 달라진 비율')
    print('=' * 96)
    n_seat = n_diff = 0
    n_plan = 0
    bycur = collections.Counter()
    for k in same_hole:
        fa, fb = flop_intents(A[k]), flop_intents(B[k])
        for s in set(fa) & set(fb):
            n_seat += 1
            if fa[s].get('plan') != fb[s].get('plan'):
                n_plan += 1
            if fa[s].get('action') != fb[s].get('action'):
                n_diff += 1
                bycur[(fa[s].get('plan'), fb[s].get('plan'))] += 1
    print('   비교한 좌석-핸드 %d' % n_seat)
    print('   플랍 계획이 달라진 비율 %.2f%% (%d)' % (100*n_plan/max(1, n_seat), n_plan))
    print('   실제 액션이 달라진 비율 %.2f%% (%d)' % (100*n_diff/max(1, n_seat), n_diff))
    if bycur:
        print()
        print('   액션이 달라진 건의 계획 전이 (상위 10)')
        for (a, b), v in bycur.most_common(10):
            print('     %-15s → %-15s %3d' % (a, b, v))



    # ---------- 7 : 짝지은 검정 ----------
    print()
    print('=' * 96)
    print('7. 짝지은 검정 — 같은 딜의 같은 좌석에서 손익 차이')
    print('=' * 96)
    print('   비짝지음 비교(위 1~4)는 칩 분산이 커서 n 수백으로는 아무것도 못 가른다.')
    print('   같은 홀카드·같은 보드의 같은 좌석을 직접 빼면 분산이 크게 준다.')
    print()
    d_all, d_chg, d_v2b, d_v2a = [], [], [], []
    for k in same_hole:
        wa, wb = won_of(A[k]), won_of(B[k])
        if wa is None or wb is None:
            continue
        fa, fb = flop_intents(A[k]), flop_intents(B[k])
        for s in set(fa) & set(fb):
            if str(s) not in wa or str(s) not in wb:
                continue
            d = wb[str(s)] - wa[str(s)]
            d_all.append(d)
            if fa[s].get('plan') != fb[s].get('plan'):
                d_chg.append(d)
            if fa[s].get('plan') == 'value_2street':
                (d_v2b if fa[s].get('rel', 0) >= 0.65 else d_v2a).append(d)
    def rep(nm, v):
        if not v:
            print('   %-26s n=0' % nm); return
        m, med, sd, n = stat(v)
        se = sd / math.sqrt(n) if n > 1 else float('nan')
        tt = m / se if se and not math.isnan(se) and se > 0 else float('nan')
        print('   %-26s n=%-5d 평균 %+9.0f  중앙 %+8.0f  SE %8.0f  t=%+.2f  %s'
              % (nm, n, m, med, se, tt,
                 '유의' if (not math.isnan(tt) and abs(tt) > 1.96) else '유의하지 않음'))
    rep('전체 좌석-핸드', d_all)
    rep('계획이 바뀐 좌석만', d_chg)
    rep('value_2street B(rel>=.65)', d_v2b)
    rep('value_2street A(rel<.65)', d_v2a)
    print()
    nz = sum(1 for x in d_all if x != 0)
    print('   전체 %d 중 손익이 실제로 달라진 좌석 %d (%.2f%%)'
          % (len(d_all), nz, 100*nz/max(1, len(d_all))))
    print('   → 나머지는 A·B 가 완전히 같은 결과를 냈다. 위 1~4 의 평균차는')
    print('     대부분 갈라진 게임(홀카드 불일치 %.1f%%)에서 온 잡음이다.'
          % (100 - 100*len(same_hole)/max(1, len(common))))


if __name__ == '__main__':
    main()
