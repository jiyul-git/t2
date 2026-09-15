#!/usr/bin/env python3
"""④ 본 측정 시드 수 역산 — 이론식 + 클러스터 부트스트랩 교차검증.

  python3 tools/seed_power.py --seeds 5000-5007

**설계 기준 (결과를 보기 전에 고정한다)**

  ① 검정 단위   축당 **하나의** 주가설. 한 축이 여러 지표에 나타나도
                (looseness → open_pct·defend_tot) 두 번 세지 않는다.
  ② PRIMARY     7축
  ③ 다중비교     Holm-Bonferroni, α=0.05. Holm 의 가장 엄격한 문턱이
                α/m 이므로 검정력 설계는 α/m 을 쓴다(보수적).
                CONDITIONAL·SECONDARY 는 이 family 에서 분리한다.
  ④ 최소 효과   |ρ| = 0.20.
                **"실제 효과가 0.20 일 것" 이라는 가정이 아니다.**
                "이보다 작은 효과는 이번 연구에서 primary evidence 로
                잡지 않는다" 는 설계 기준이다. 결과를 본 뒤 유리한
                효과크기를 고르는 post-hoc 설계를 막기 위해 미리 박는다.
  ⑤ 검정력      80% 기본, 90% 민감도.

**독립성.** 표본 단위는 (시드, 플레이어)다. 한 시드 안 24명은 같은
토너에서 서로 맞붙으므로 완전 독립이 아니다. 시드별 급내상관(ICC)을
실측해 설계효과 DEFF = 1 + (m-1)·ICC 로 유효 표본을 깎는다.

**축마다 eligible 비율이 다르다.** 시드당 기여 인원이 다르므로
필요 시드 수도 축마다 다르고, 가장 낮은 축이 병목이다.
"""
import os, sys, argparse, math, random, statistics as stat, collections
import multiprocessing as mp

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.dirname(os.path.abspath(__file__))
for _p in (D, T):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import f_trace as FT
import f_trace_layers as FL

# 축당 하나의 주가설. (축, 어느 도구, 지표키, 기대부호)
PRIMARY = [
    ('looseness',       'lay',  ['open_pct', 'defend_tot'], +1),
    ('aggression',      'lay',  ['defend_tp'],              +1),
    ('discipline',      'post', ['cbet_dev'],               -1),
    ('bluff',           'post', ['bluff'],                  +1),
    ('thin_value_turn', 'post', ['value'],                  +1),
    ('potcontrol',      'post', ['ROUTING'],                +1),
    ('cbet_flop',       'post', ['cbet_dev_flop'],          +1),
]

def ndtri(p):
    """표준정규 분위수 (Acklam 근사). scipy 없이 쓴다."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1-0.02425
    if p < pl:
        q = math.sqrt(-2*math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2*math.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p-0.5; r = q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def n_fisher(rho, alpha, power):
    """Fisher z 변환 기반 필요 표본."""
    za = ndtri(1 - alpha/2.0)
    zb = ndtri(power)
    return ((za+zb)/math.atanh(abs(rho)))**2 + 3


def spearman(a, b):
    n = len(a)
    if n < 4: return None
    def rank(x):
        o = sorted(range(n), key=lambda i: x[i]); r = [0.0]*n; i = 0
        while i < n:
            j = i
            while j+1 < n and x[o[j+1]] == x[o[i]]: j += 1
            for k in range(i, j+1): r[o[k]] = (i+j)/2.0 + 1
            i = j+1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = sum(ra)/n, sum(rb)/n
    num = sum((ra[i]-ma)*(rb[i]-mb) for i in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in ra)); db = math.sqrt(sum((x-mb)**2 for x in rb))
    return num/(da*db) if da and db else None


def icc_by_seed(groups):
    """시드별 급내상관. groups: {seed: [값…]}  일원배치 분산분석 추정."""
    ks = [k for k in groups if len(groups[k]) >= 2]
    if len(ks) < 2: return 0.0
    allv = [x for k in ks for x in groups[k]]
    gm = sum(allv)/len(allv)
    k_n = len(ks)
    ms_b = sum(len(groups[k])*(stat.mean(groups[k])-gm)**2 for k in ks)/max(1, k_n-1)
    ms_w = sum(sum((x-stat.mean(groups[k]))**2 for x in groups[k]) for k in ks) \
        / max(1, len(allv)-k_n)
    m = len(allv)/k_n
    if ms_b + (m-1)*ms_w <= 0: return 0.0
    return max(0.0, (ms_b - ms_w)/(ms_b + (m-1)*ms_w))


def collect(entries, hpl, stack, seeds, jobs, half_min):
    """8시드를 돌려 축별 (시드, pid, 축값, 평균f, 관측수) 를 만든다."""
    with mp.Pool(jobs) as pool:
        post = pool.map(FT.run_one, [(entries, hpl, stack, s, 3000) for s in seeds])
        lay = pool.map(FL.run_one, [(entries, hpl, stack, s, 3000) for s in seeds])

    out = collections.defaultdict(list)   # 축 -> [(seed, pid, axval, meanf, nobs)]
    for si, (rec, axv, _e) in enumerate(post):
        per = collections.defaultdict(lambda: collections.defaultdict(list))
        allpost = collections.defaultdict(list)
        for r in rec:
            if r['pid'] is None or r['f'] is None: continue
            per[r['branch']][r['pid']].append(r)
            allpost[r['pid']].append(r)
            if r['branch'] == 'cbet_dev' and r['street'] == 'flop':
                per['cbet_dev_flop'][r['pid']].append(r)
        for ax, src, keys, _sg in PRIMARY:
            if src != 'post': continue
            k = keys[0]
            if k == 'ROUTING':
                for pid, rs in allpost.items():
                    if len(rs) < half_min or pid not in axv: continue
                    y = sum(1 for z in rs if z['plan'] == 'pot_control')/len(rs)
                    out[ax].append((si, pid, axv[pid][ax], y, len(rs)))
            else:
                for pid, rs in per[k].items():
                    if len(rs) < half_min or pid not in axv: continue
                    out[ax].append((si, pid, axv[pid][ax], stat.mean(z['f'] for z in rs), len(rs)))
    for si, (rec, axv, _e) in enumerate(lay):
        per = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in rec:
            if r.get('pid') is None or r.get('v') is None: continue
            per[r['metric']][r['pid']].append(r['v'])
        for ax, src, keys, _sg in PRIMARY:
            if src != 'lay': continue
            k = keys[0]
            for pid, vs in per[k].items():
                if len(vs) < half_min or pid not in axv: continue
                out[ax].append((si, pid, axv[pid][ax], stat.mean(vs), len(vs)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5007')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--half-min', type=int, default=3)
    ap.add_argument('--rho', type=float, default=0.20)
    ap.add_argument('--alpha', type=float, default=0.05)
    ap.add_argument('--boot', type=int, default=2000)
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    m = len(PRIMARY)
    alpha_adj = a.alpha/m

    print('# ④ 시드 수 역산   entries=%d hpl=%d stack=%d   기준 >=%d'
          % (a.entries, a.hpl, a.stack, a.half_min))
    print()
    print('설계 기준 (결과를 보기 전에 고정)')
    print('  검정 단위   축당 하나의 주가설')
    print('  PRIMARY     %d축' % m)
    print('  다중비교     Holm-Bonferroni, α=%.2f → 설계는 가장 엄격한 α/m=%.5f'
          % (a.alpha, alpha_adj))
    print('  최소 효과   |ρ| = %.2f  — "실제 효과가 이만큼" 이 아니라' % a.rho)
    print('              "이보다 작으면 primary evidence 로 잡지 않는다"')
    print('  검정력      80%% 기본 / 90%% 민감도')
    print()
    print('이론 필요 표본 (Fisher z, 양측)')
    for pw in (0.80, 0.90):
        print('  power %.0f%%   보정 없음 α=%.2f → n=%.0f      Holm α/m=%.5f → n=%.0f'
              % (pw*100, a.alpha, n_fisher(a.rho, a.alpha, pw),
                 alpha_adj, n_fisher(a.rho, alpha_adj, pw)))
    print()

    data = collect(a.entries, a.hpl, a.stack, seeds, a.jobs, a.half_min)
    S = len(seeds)

    print('## 축별 eligible 과 시드당 기여')
    print('%-18s %7s %9s %9s %9s %9s' % ('축', 'n(8시드)', '시드당', 'ICC', 'DEFF', 'ρ(실측)'))
    print('-'*70)
    need80 = n_fisher(a.rho, alpha_adj, 0.80)
    need90 = n_fisher(a.rho, alpha_adj, 0.90)
    rows = []
    for ax, src, keys, sg in PRIMARY:
        d = data.get(ax) or []
        if len(d) < 8:
            print('%-18s %7d  (표본 부족)' % (ax, len(d))); continue
        per_seed = len(d)/S
        g = collections.defaultdict(list)
        for si, pid, xv, yv, nb in d: g[si].append(yv)
        icc = icc_by_seed(g)
        mbar = len(d)/max(1, len(g))
        deff = 1.0 + (mbar-1)*icc
        rho = spearman([x[2] for x in d], [x[3] for x in d])
        rows.append((ax, per_seed, deff, rho))
        print('%-18s %7d %9.1f %9.3f %9.2f %9s'
              % (ax, len(d), per_seed, icc, deff,
                 ('%+.3f' % rho) if rho is not None else '-'))
    print()
    print('## 필요 시드 수 (이론식)')
    print('%-18s %12s %12s' % ('축', 'power 80%', 'power 90%'))
    print('-'*44)
    worst = (None, 0, 0)
    for ax, per_seed, deff, rho in rows:
        s80 = math.ceil(need80*deff/per_seed)
        s90 = math.ceil(need90*deff/per_seed)
        print('%-18s %12d %12d' % (ax, s80, s90))
        if s80 > worst[1]: worst = (ax, s80, s90)
    print('-'*44)
    print('%-18s %12d %12d   ← 병목' % (worst[0], worst[1], worst[2]))
    print()

    # ---- 클러스터 부트스트랩: 필요 시드를 직접 탐색한다 ----
    #
    # **이론식 DEFF 는 결정에 쓰지 않는다.** DEFF = 1+(m-1)*ICC 는 군집
    # **평균**에 대한 공식인데, 여기서는 예측변수(축 값)가 군집 **안에서**
    # 변한다. within-cluster 예측변수에는 과보정이다. 위 표의 DEFF 열은
    # 참고용이고, 결정은 부트스트랩이 한다.
    #
    # 합성식:
    #   y = ρ·z(x) + sqrt(1-ρ²)·( sqrt(ICC)·b0 + sqrt(1-ICC)·ε )
    # z(x) 는 **그 축의 실측 평균·sd** 로 표준화한다. 앞서 (x-5.0)/2.2 로
    # 고정 상수를 박아 축마다 주입 상관이 달라졌다 — 검출력 순서가 축 sd
    # 순서와 정확히 일치해서 드러났다.
    # var(y)=1 이고 corr(x,y)=ρ 가 되도록 계수를 맞춘다.
    print('## 클러스터 부트스트랩 — 필요 시드 직접 탐색 (%d회/후보)' % a.boot)
    print('   시드 단위 복원추출. 축값은 실측 그대로, 결과변수만 목표 ρ=%.2f 로 합성.'
          % a.rho)
    print('   축 표준화는 그 축의 실측 평균·sd 를 쓴다.')
    print()
    print('%-18s %10s %10s %12s' % ('축', 'power80', 'power90', '이론(DEFF 미적용)'))
    print('-'*54)
    rng = random.Random(12345)
    crit = ndtri(1-alpha_adj/2.0)
    base = math.ceil(need80)
    out_rows = []
    for ax, per_seed, deff, rho_obs in rows:
        d = data[ax]
        by = collections.defaultdict(list)
        for si, pid, xv, yv, nb in d: by[si].append(xv)
        ks = list(by)
        g = {k: [y for _si, _p, _x, y, _n in d if _si == k] for k in ks}
        icc = max(0.0, min(0.95, icc_by_seed(g)))
        xs_all = [x[2] for x in d]
        mx = stat.mean(xs_all); sx = stat.pstdev(xs_all) or 1.0
        cb = math.sqrt(1.0-a.rho**2)

        def power_at(S, target_n=None):
            hit = 0
            for _ in range(a.boot):
                xs, ys = [], []
                for _s in range(S):
                    k = rng.choice(ks)
                    b0 = rng.gauss(0, 1)
                    for xv in by[k]:
                        z = (xv-mx)/sx
                        e = rng.gauss(0, 1)
                        xs.append(xv)
                        ys.append(a.rho*z + cb*(math.sqrt(icc)*b0
                                                + math.sqrt(1-icc)*e))
                r = spearman(xs, ys)
                if r is None: continue
                zz = math.atanh(max(-0.999999, min(0.999999, r)))*math.sqrt(len(xs)-3)
                if abs(zz) > crit: hit += 1
            return hit/float(a.boot)

        def search(target):
            lo_, hi_ = 2, 8
            while power_at(hi_) < target and hi_ < 4000:
                lo_, hi_ = hi_, hi_*2
            while lo_ + 1 < hi_:
                mid = (lo_+hi_)//2
                if power_at(mid) >= target: hi_ = mid
                else: lo_ = mid
            return hi_

        s80 = search(0.80)
        s90 = search(0.90)
        theo = math.ceil(need80/per_seed)
        out_rows.append((ax, s80, s90, theo))
        print('%-18s %10d %10d %12d' % (ax, s80, s90, theo))
    print('-'*54)
    w80 = max(out_rows, key=lambda r: r[1])
    w90 = max(out_rows, key=lambda r: r[2])
    print('병목  power80 : %s %d시드     power90 : %s %d시드'
          % (w80[0], w80[1], w90[0], w90[2]))
    print()
    print('시드당 테이블핸드 378 기준 → power80 약 %d 테이블핸드 (4코어 %.0f분)'
          % (w80[1]*378, w80[1]*378*0.10/4/60))
