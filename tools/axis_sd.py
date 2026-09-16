#!/usr/bin/env python3
"""H5-A — 축의 **입력 공간** 실재 분산.

  python3 tools/axis_sd.py --seeds 5000-5054 --entries 24

L1/L2 본측정과 같은 필드를 그대로 재구성한다. **핸드를 돌리지 않는다** —
fieldsim.Field 생성만 하면 persona.make_player 가 호출되고 거기서 멈춘다.
시뮬레이션이 아니다.

**이 도구는 입력 공간만 잰다.** 축별 sd 가 다르다는 것이 축별 행동 차이의
검증이 아니다. 행동 효과는 L1/L2 결과의 문제이고 별개다 (H5-B).

생성 구조 (persona.py:183 make_player)
  잠재 3   study = gauss(2.6 + 4.2q, 2.1)
           aggro = gauss(5.0, 2.4)
           exp   = gauss(3.0 + 3.8q, 2.2)
  concepts v = base + ws(study-5)1.05 + wa(aggro-5)0.85 + we(exp-5)0.85
               + gauss(0, SPREAD[k])        → _clamp(0,10) → round(,1)
  temper   축마다 따로. aggression = aggro + gauss(0, 0.8) 처럼 잠재에 직접 붙는다

**해석을 어렵게 하는 것 셋**
  1  _clamp(0, 10) 가 양 끝을 자른다 — 경계에 쌓이면 sd 가 줄어든다
  2  round(x, 1) 이 이산화한다
  3  skill_bounds 밖이면 **최대 6회 재추첨**한다 (persona.py:234) — 절단
     표본이라 생성식의 모수 sd 와 실측 sd 가 다르다
"""
import os, sys, argparse, statistics as stat, collections

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if D not in sys.path:
    sys.path.insert(0, D)

LO, HI = 1.0, 9.0          # 반사실 개입에 쓴 두 값


def _corr(x, y):
    n = len(x); mx = sum(x)/n; my = sum(y)/n
    sx = sum((a-mx)**2 for a in x) ** 0.5
    sy = sum((b-my)**2 for b in y) ** 0.5
    if not sx or not sy: return 0.0
    return sum((a-mx)*(b-my) for a, b in zip(x, y))/(sx*sy)


def _ols(X, y):
    """절편 포함 최소제곱. 정규방정식을 가우스 소거로 푼다. R2 만 쓴다."""
    n = len(y); k = len(X) + 1
    cols = [[1.0]*n] + [list(map(float, c)) for c in X]
    A = [[sum(cols[i][t]*cols[j][t] for t in range(n)) for j in range(k)]
         + [sum(cols[i][t]*y[t] for t in range(n))] for i in range(k)]
    for i in range(k):
        piv = max(range(i, k), key=lambda r: abs(A[r][i]))
        A[i], A[piv] = A[piv], A[i]
        if abs(A[i][i]) < 1e-12: return [0.0]*k, 0.0
        for r in range(k):
            if r == i: continue
            f = A[r][i]/A[i][i]
            for c in range(i, k+1): A[r][c] -= f*A[i][c]
    b = [A[i][k]/A[i][i] for i in range(k)]
    my = sum(y)/n
    sst = sum((v-my)**2 for v in y)
    pred = [sum(b[j]*cols[j][t] for j in range(k)) for t in range(n)]
    sse = sum((y[t]-pred[t])**2 for t in range(n))
    return b, (1.0 - sse/sst if sst else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='5000-5054')
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--axes', default='potcontrol,aggression,bluff,'
                                      'thin_value_turn,discipline,looseness,cbet_flop')
    a = ap.parse_args()
    lo, _, hi = a.seeds.partition('-')
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    focus = [x for x in a.axes.split(',') if x]

    import fieldsim as FS
    FS.Field.BOT_LOG = 0
    vals = collections.defaultdict(list)
    hero = collections.defaultdict(list)
    lat = collections.defaultdict(list)      # study / aggro / exp
    nfield = 0
    fq = None
    for s in seeds:
        f = FS.Field(entries=a.entries, start_stack=a.stack, hero_pid=0,
                     seed=s, hands_per_level=a.hpl)
        fq = f.field_q
        nfield += 1
        for pid, rec in f.players.items():
            p = rec['prof']
            tgt = hero if pid == f.hero_pid else vals
            for k, v in (p.get('concepts') or {}).items(): tgt[k].append(v)
            for k, v in (p.get('temper') or {}).items():   tgt[k].append(v)
            if pid != f.hero_pid:
                for k, v in (p.get('latent') or {}).items(): lat[k].append(v)

    axes = sorted(vals)
    n = len(vals[axes[0]]) if axes else 0
    print('# H5-A 입력 공간 분산 — 핸드를 돌리지 않았다')
    print('  필드 %d개 (시드 %s)  entries=%d  field_quality=%.4f'
          % (nfield, a.seeds, a.entries, fq))
    print('  히어로(pid 0)는 q=0.9 고정이라 **제외**한다 (fieldsim.py:70)')
    print('  표본 %d명 = %d필드 × %d명' % (n, nfield, a.entries - 1))
    print()
    hdr = ('%-18s %6s %6s %6s %6s %6s %7s %7s   %8s'
           % ('축', '평균', 'sd', '5%', '95%', 'min', 'max', '경계%', '1↔9 = ?sd'))
    print(hdr); print('-' * len(hdr))

    def row(ax, xs, star=''):
        xs = sorted(xs)
        m = stat.mean(xs); sd = stat.pstdev(xs)
        q = lambda p_: xs[min(len(xs)-1, int(p_*len(xs)))]
        edge = 100.0*sum(1 for x in xs if x <= 0.05 or x >= 9.95)/len(xs)
        span = (HI - LO)/sd if sd else float('inf')
        print('%-18s %6.2f %6.3f %6.1f %6.1f %6.1f %7.1f %6.1f%%   %8.2f%s'
              % (ax, m, sd, q(0.05), q(0.95), xs[0], xs[-1], edge, span, star))

    for ax in focus:
        if ax in vals: row(ax, vals[ax], '  ←')
    print('   ' + '-'*(len(hdr)-3))
    for ax in axes:
        if ax not in focus: row(ax, vals[ax])
    print()
    print('  1↔9 = ?sd   반사실 개입 폭 8.0 이 그 축의 실재 sd 몇 배인가')
    print('  경계%        0 또는 10 에 붙은 비율. 높으면 clamp 가 sd 를 깎았다')
    print()
    print('## 잠재 3요인이 설명하는 몫')
    print()
    print('  축 분산의 상당 부분은 study·aggro·exp 공유분이다. 반사실 스왑은')
    print('  잠재를 그대로 두고 축만 1 또는 9 로 바꾸므로, **잠재와 어긋난')
    print('  조합**(예: aggro 3 인데 aggression 9)을 만든다. 필드에 실재하는')
    print('  조합이 아니다. 잔차 sd 는 잠재를 고정했을 때 그 축이 실제로')
    print('  흔들리는 폭이다.')
    print()
    L = [lat['study'], lat['aggro'], lat['exp']]
    h2 = '%-18s %7s %7s %7s %7s %8s %9s   %9s' % (
        '축', 'r:study', 'r:aggro', 'r:exp', 'R2', 'sd', '잔차sd', '1↔9=?잔차sd')
    print(h2); print('-' * len(h2))
    for ax in focus:
        if ax not in vals: continue
        y = vals[ax]
        b, r2 = _ols(L, y)
        sd = stat.pstdev(y)
        res = sd * ((1.0 - r2) ** 0.5)
        print('%-18s %7.3f %7.3f %7.3f %7.3f %8.3f %9.3f   %9.2f'
              % (ax, _corr(L[0], y), _corr(L[1], y), _corr(L[2], y), r2, sd, res,
                 (HI - LO)/res if res else float('inf')))
    print()
    print('  R2 는 study·aggro·exp 셋을 한꺼번에 넣은 선형 설명력이다.')
    print('  **이 표도 입력 공간만 잰다.** 축별 sd 차이를 행동 차이로 읽지 않는다.')


if __name__ == '__main__':
    main()
