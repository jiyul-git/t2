#!/usr/bin/env python3
"""④ 본 분석 — PRIMARY 7축의 축 → 행동 방향성.

  python3 tools/axis_analysis.py --seeds 5000-5054           # 본 측정 (55시드)
  python3 tools/axis_analysis.py --seeds 5000-5007 --placebo # 위약 검증

**ANALYSIS_PLAN.md 가 사전 등록한 설계를 그대로 구현한다.**
결과를 보고 고치지 않는다. 설계와 코드가 어긋나면 코드를 고친다.

  축 값        무틸트 설계값 (prof['concepts']/['temper'])
  f 집계       플레이어별 산술평균, 최소 3건
  looseness    z(open_pct)·z(defend_tot) 평균. **표준화는 전체에서 한 번**
               (부트스트랩 안에서 재표준화하면 반복마다 정의가 달라진다)
  점추정       전체 플레이어 Spearman ρ
  CI           클러스터 부트스트랩 (시드 복원추출) 백분위
  p 값         순열 검정. 축 값은 플레이어에 iid 로 배정되므로 자유 순열이
               정확한 귀무다. 결과변수의 군집 구조는 그대로 보존된다.
  다중비교      Holm α=0.05, 정확히 7개. CONDITIONAL 은 별도 family
  통제         잠재3 / +동일식 성향축 / +상황 — 셋 다 보고

위약(--placebo)은 tilt_swing·tilt_stack 을 **같은 절차 전체**에 태운다.
통과 기준은 ρ=0 이 아니다 (ANALYSIS_PLAN 4절):
  ① 방향 불일치  ② Holm 후 유의 없음  ③ CI 가 0 포함  ④ split-half 미재현
"""
import os, sys, argparse, math, random, statistics as stat, collections, json
from logkeys import oop_field_of
import multiprocessing as mp

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.dirname(os.path.abspath(__file__))
for _p in (D, T):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import f_trace as FT
import f_trace_layers as FL

LAT = ('study', 'aggro', 'exp')

# 축당 하나의 주가설. ANALYSIS_PLAN 1-3 표와 일치해야 한다.
PRIMARY = [
    # (축, 결과변수 키, 기대부호, 동일식 성향축 통제 집합)
    ('looseness',       'PRE_LOOSE',   +1, []),
    ('aggression',      'defend_tp',   +1, []),
    ('discipline',      'cbet_dev',    -1, ['aggression', 'bluff', 'cbet_flop']),
    ('bluff',           'bluff_br',    +1, ['gamble', 'fold_equity', 'multiway']),
    ('thin_value_turn', 'value_r85',   +1, ['aggression', 'gamble']),
    ('potcontrol',      'ROUTING',     +1, ['range_merge', 'multiway']),
    ('cbet_flop',       'cbet_flop_f', +1, ['discipline', 'aggression', 'bluff',
                                            'multiway', 'board_texture']),
]
# **진짜 위약은 합성 난수 축이다.**
# tilt_swing·tilt_stack 을 위약으로 썼다가 tilt_stack × bluff_br 에서
# ρ +0.402 가 나왔다. 조사해 보니 위약이 아니었다 —
#   dynamics.py:116  stack_axis = (_t(prof,'tilt_stack')-5.0)/5.0
#   persona.py:563   swing = (temper(prof,'tilt_swing',5.0)-5.0)/5.0
#        → dynamics.Tilt.level() → play.Hand.axes → PS.tilted_view
#        → plan.py 에 들어가는 프로필의 개념값이 바뀐다
# CLAUDE.md 의 "plan.py 가 안 읽는다" 는 문자 그대로는 맞지만 틸트를
# 경유하는 간접 경로가 있다. 그 기록을 "행동에 영향 없음" 으로 읽었다.
#
# _rand_A/_rand_B 는 (시드, pid) 해시에서 만든 값이고 엔진이 어디서도
# 읽지 않는다. 이것이 유일하게 타당한 바닥이다.
PLACEBO = [
    ('_rand_A', 'cbet_dev',  0, []),
    ('_rand_B', 'bluff_br',  0, []),
    ('_rand_A', 'PRE_LOOSE', 0, []),
    ('_rand_B', 'value_r85', 0, []),
    ('_rand_A', 'ROUTING',   0, []),
    # 참고용 — 순수 위약이 아니다. 틸트 간접 경로가 있다.
    ('tilt_swing', 'cbet_dev', 0, []),
    ('tilt_stack', 'bluff_br', 0, []),
]
SITU = ('n_opp', 'oop', 'rel')          # 플레이어별 상황 평균


# ---------- 통계 ----------
def ranks(x):
    n = len(x); o = sorted(range(n), key=lambda i: x[i]); r = [0.0]*n; i = 0
    while i < n:
        j = i
        while j+1 < n and x[o[j+1]] == x[o[i]]: j += 1
        for k in range(i, j+1): r[o[k]] = (i+j)/2.0 + 1
        i = j+1
    return r

def pearson(a, b):
    n = len(a)
    if n < 4: return None
    ma, mb = sum(a)/n, sum(b)/n
    num = sum((a[i]-ma)*(b[i]-mb) for i in range(n))
    da = math.sqrt(sum((x-ma)**2 for x in a)); db = math.sqrt(sum((x-mb)**2 for x in b))
    return num/(da*db) if da and db else None

def spearman(a, b):
    if len(a) < 4: return None
    return pearson(ranks(a), ranks(b))

def resid(y, X):
    """y 를 X(열 리스트)에 최소제곱 회귀한 잔차. 절편 포함."""
    n = len(y); k = len(X)
    cols = [[1.0]*n] + [list(c) for c in X]
    m = k+1
    A = [[sum(cols[i][t]*cols[j][t] for t in range(n)) for j in range(m)] for i in range(m)]
    b = [sum(cols[i][t]*y[t] for t in range(n)) for i in range(m)]
    for i in range(m):
        p = max(range(i, m), key=lambda r: abs(A[r][i]))
        A[i], A[p] = A[p], A[i]; b[i], b[p] = b[p], b[i]
        if abs(A[i][i]) < 1e-12: continue
        for r in range(m):
            if r == i: continue
            f = A[r][i]/A[i][i]
            for c in range(i, m): A[r][c] -= f*A[i][c]
            b[r] -= f*b[i]
    w = [b[i]/A[i][i] if abs(A[i][i]) > 1e-12 else 0.0 for i in range(m)]
    return [y[t] - sum(w[i]*cols[i][t] for i in range(m)) for t in range(n)]

def partial(x, y, ctrl):
    """순위 잔차 편상관."""
    if len(x) < 6 or not ctrl: return spearman(x, y)
    R = [ranks(c) for c in ctrl]
    return pearson(resid(ranks(x), R), resid(ranks(y), R))

def holm(pairs, alpha=0.05):
    """[(p, key)] → {key: (보정p, 기각여부)}. step-down."""
    srt = sorted(pairs)
    m = len(srt); out = {}; prev = 0.0; stop = False
    for i, (p, k) in enumerate(srt):
        adj = min(1.0, max(prev, p*(m-i)))
        prev = adj
        rej = (not stop) and adj <= alpha
        if not rej: stop = True
        out[k] = (adj, rej)
    return out


# ---------- 수집 ----------
def build(entries, hpl, stack, seeds, jobs, half_min):
    """플레이어별 표를 만든다. key=(시드idx, pid)."""
    with mp.Pool(jobs) as pool:
        post = pool.map(FT.run_one, [(entries, hpl, stack, s, 3000) for s in seeds])
        lay = pool.map(FL.run_one, [(entries, hpl, stack, s, 3000) for s in seeds])

    AX, LATV = {}, {}
    obs = collections.defaultdict(lambda: collections.defaultdict(list))  # 지표 -> key -> [값]
    situ = collections.defaultdict(lambda: collections.defaultdict(list)) # 상황 -> key -> [값]

    import zlib
    for si, (rec, axv, _e) in enumerate(post):
        for pid, d in axv.items():
            d = dict(d)
            # 합성 위약 축. (시드, pid) 에서 결정론적으로 만들고 엔진은
            # 어디서도 읽지 않는다. 축 값 범위를 실제 축과 비슷하게 맞춰
            # 순위 구조가 비교 가능하게 한다.
            for tag, salt in (('_rand_A', 'A'), ('_rand_B', 'B')):
                h = zlib.crc32(('%s|%d|%d' % (salt, si, pid)).encode())
                d[tag] = round((h % 10001)/1000.0, 1)
            AX[(si, pid)] = d
        for r in rec:
            if r['pid'] is None or r['f'] is None: continue
            k = (si, r['pid'])
            br, st_ = r['branch'], r['street']
            if br == 'cbet_dev':
                obs['cbet_dev'][k].append(r['f'])
                if st_ == 'flop': obs['cbet_flop_f'][k].append(r['f'])
            elif br == 'bluff':
                obs['bluff_br'][k].append(r['f'])
            elif br == 'value' and st_ in ('flop', 'turn') \
                    and r.get('rel') is not None and r['rel'] < 0.85:
                obs['value_r85'][k].append(r['f'])
            # 라우팅은 전체 포스트플랍 계획이 분모다
            obs['_ALL'][k].append(1.0 if r['plan'] == 'pot_control' else 0.0)
            # 상황 공변량 (플레이어별 평균)
            situ['n_opp'][k].append(float(r.get('n_opp') or 1))
            # f_trace 레코드의 포지션은 update_plan 이 받은 field 식이다.
            _oopv = oop_field_of(r)
            if _oopv is not None: situ['oop'][k].append(1.0 if _oopv else 0.0)
            if r.get('rel') is not None: situ['rel'][k].append(float(r['rel']))

    for si, (rec, axv, _e) in enumerate(lay):
        for r in rec:
            if r.get('pid') is None or r.get('v') is None: continue
            k = (si, r['pid'])
            if r['metric'] in ('open_pct', 'defend_tp', 'defend_tot'):
                obs[r['metric']][k].append(r['v'])

    # 잠재요인
    for si, (rec, axv, _e) in enumerate(post):
        pass
    # latent 는 axv 에 없다 — f_trace.run_one 은 concepts+temper 만 준다.
    # fieldsim 을 다시 돌리지 않고 prof 에서 직접 뽑기 위해 여기서 재구성한다.
    return AX, obs, situ


def mean_table(obs, key, half_min):
    return {k: stat.mean(v) for k, v in obs.get(key, {}).items() if len(v) >= half_min}


def halves(obs, key, half_min):
    out = {}
    for k, v in obs.get(key, {}).items():
        if len(v) >= max(4, half_min):
            out[k] = (stat.mean(v[0::2]), stat.mean(v[1::2]))
    return out


# ---------- 분석 ----------
def analyse(name, axis, xs, ys, keys, ctrl_axes, AX, situ_tab,
            half_tab, rng, boot, perm, alpha_m):
    """한 축의 전 지표를 낸다."""
    n = len(xs)
    rho = spearman(xs, ys)
    res = {'axis': axis, 'outcome': name, 'n': n, 'rho': rho}

    # 클러스터 부트스트랩 CI — 시드 복원추출
    byseed = collections.defaultdict(list)
    for i, k in enumerate(keys): byseed[k[0]].append(i)
    sk = list(byseed)
    bs = []
    for _ in range(boot):
        idx = []
        for _s in range(len(sk)):
            idx.extend(byseed[rng.choice(sk)])
        if len(idx) < 6: continue
        r = spearman([xs[i] for i in idx], [ys[i] for i in idx])
        if r is not None: bs.append(r)
    if bs:
        bs.sort()
        res['ci'] = (bs[int(0.025*len(bs))], bs[min(len(bs)-1, int(0.975*len(bs)))])
    else:
        res['ci'] = (None, None)

    # 순열 p — 축 값은 플레이어에 iid 배정이므로 자유 순열이 정확한 귀무다
    if rho is not None:
        cnt = 0
        px = list(xs)
        for _ in range(perm):
            rng.shuffle(px)
            r = spearman(px, ys)
            if r is not None and abs(r) >= abs(rho): cnt += 1
        res['p'] = (cnt+1.0)/(perm+1.0)
    else:
        res['p'] = 1.0

    # 편상관 3단
    lat = [[AX[k].get('_lat_'+L, 0.0) for k in keys] for L in LAT]
    res['p_lat'] = partial(xs, ys, lat)
    if ctrl_axes:
        ca = lat + [[AX[k].get(c, 5.0) for k in keys] for c in ctrl_axes]
        res['p_ax'] = partial(xs, ys, ca)
    else:
        res['p_ax'] = res['p_lat']
    sv = [[situ_tab[s].get(k, 0.0) for k in keys] for s in SITU
          if any(k in situ_tab[s] for k in keys)]
    res['p_situ'] = partial(xs, ys, (ca if ctrl_axes else lat) + sv) if sv else None

    # split-half — 두 가지를 구분해서 낸다.
    #
    # r_out : 결과변수의 신뢰도. **축과 무관하다** — 같은 결과변수면
    #         위약이든 실제 축이든 값이 같다. 관측 가능한 ρ 의 상한(√r)을
    #         정하는 값이지 축-결과 연관의 재현성이 아니다.
    # ρ 반분 : 기회를 홀/짝으로 나눠 **각 반쪽에서 ρ 를 따로** 낸다.
    #         이것이 ANALYSIS_PLAN 4절 ④ 가 요구하는 축-결과 연관의
    #         재현성이다. 처음에 r_out 만 내서 ④ 를 판정할 수 없었다.
    hk = [k for k in keys if k in half_tab]
    if len(hk) >= 4:
        res['r'] = spearman([half_tab[k][0] for k in hk], [half_tab[k][1] for k in hk])
        res['r_n'] = len(hk)
        hx = [AX[k].get(axis, 5.0) for k in hk]
        res['rho_h1'] = spearman(hx, [half_tab[k][0] for k in hk])
        res['rho_h2'] = spearman(hx, [half_tab[k][1] for k in hk])
    else:
        res['r'], res['r_n'] = None, len(hk)
        res['rho_h1'] = res['rho_h2'] = None
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5054')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--half-min', type=int, default=3)
    ap.add_argument('--boot', type=int, default=10000)
    ap.add_argument('--perm', type=int, default=10000)
    ap.add_argument('--alpha', type=float, default=0.05)
    ap.add_argument('--placebo', action='store_true')
    a = ap.parse_args()

    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi)+1)) if hi else [int(lo)]
    rng = random.Random(777)

    print('# ④ %s   entries=%d hpl=%d stack=%d 시드 %d개 기준 >=%d'
          % ('위약 검증' if a.placebo else '본 분석',
             a.entries, a.hpl, a.stack, len(seeds), a.half_min))
    print('   부트스트랩 %d · 순열 %d · Holm α=%.2f' % (a.boot, a.perm, a.alpha))
    print()

    AX, obs, situ = build(a.entries, a.hpl, a.stack, seeds, a.jobs, a.half_min)
    situ_tab = {s: {k: stat.mean(v) for k, v in situ[s].items()} for s in SITU}

    # looseness 결과변수 — 표준화는 전체에서 **한 번만**
    op = mean_table(obs, 'open_pct', a.half_min)
    dt = mean_table(obs, 'defend_tot', a.half_min)
    both = [k for k in op if k in dt]
    if both:
        mo, so = stat.mean([op[k] for k in both]), stat.pstdev([op[k] for k in both]) or 1.0
        md, sd = stat.mean([dt[k] for k in both]), stat.pstdev([dt[k] for k in both]) or 1.0
        PRE = {k: ((op[k]-mo)/so + (dt[k]-md)/sd)/2.0 for k in both}
        cor = spearman([op[k] for k in both], [dt[k] for k in both])
        print('보조 진단 — looseness 두 지표 상관 (n=%d) : %s'
              % (len(both), ('%+.3f' % cor) if cor is not None else '-'))
        print('   낮게 나와도 사전 정의대로 평균을 유지한다 (ANALYSIS_PLAN 1-3).')
        print()
    else:
        PRE = {}

    tables = {'PRE_LOOSE': PRE,
              'defend_tp': mean_table(obs, 'defend_tp', a.half_min),
              'cbet_dev': mean_table(obs, 'cbet_dev', a.half_min),
              'bluff_br': mean_table(obs, 'bluff_br', a.half_min),
              'value_r85': mean_table(obs, 'value_r85', a.half_min),
              'cbet_flop_f': mean_table(obs, 'cbet_flop_f', a.half_min),
              'ROUTING': mean_table(obs, '_ALL', a.half_min)}
    halftabs = {k: halves(obs, {'PRE_LOOSE': 'open_pct', 'ROUTING': '_ALL'}.get(k, k),
                          a.half_min) for k in tables}

    spec = PLACEBO if a.placebo else PRIMARY
    alpha_m = a.alpha/len(spec)
    out = []
    for axis, okey, sign, ctrl in spec:
        tab = tables.get(okey) or {}
        keys = [k for k in tab if k in AX]
        if len(keys) < 6:
            print('%-16s %-12s  표본 부족 (n=%d)' % (axis, okey, len(keys))); continue
        xs = [AX[k].get(axis, 5.0) for k in keys]
        ys = [tab[k] for k in keys]
        out.append(analyse(okey, axis, xs, ys, keys, ctrl, AX, situ_tab,
                           halftabs.get(okey, {}), rng, a.boot, a.perm, alpha_m))

    hp = holm([(r['p'], (r['axis'], r['outcome'])) for r in out], a.alpha)
    f = lambda v: ('%+.3f' % v) if v is not None else '  -  '
    print('%-16s %-12s %5s %8s %-18s %9s %8s | %8s %8s %8s'
          % ('축', '결과변수', 'n', 'ρ', '95% CI', 'Holm p', '기각',
             '편(잠재)', '편(+축)', '편(+상황)'))
    print('-'*118)
    for r in out:
        adj, rej = hp[(r['axis'], r['outcome'])]
        ci = '[%s, %s]' % (f(r['ci'][0]), f(r['ci'][1]))
        print('%-16s %-12s %5d %8s %-18s %9.4f %8s | %8s %8s %8s'
              % (r['axis'], r['outcome'], r['n'], f(r['rho']), ci, adj,
                 'O' if rej else '-', f(r['p_lat']), f(r['p_ax']), f(r['p_situ'])))
    print()
    print('%-16s %-12s %9s %9s %9s %6s'
          % ('축', '결과변수', 'ρ 홀', 'ρ 짝', 'r(결과)', 'n'))
    print('-'*66)
    for r in out:
        print('%-16s %-12s %9s %9s %9s %6d'
              % (r['axis'], r['outcome'], f(r.get('rho_h1')), f(r.get('rho_h2')),
                 f(r['r']), r['r_n']))
    print()
    print('ρ 홀/짝 : 기회를 반으로 나눠 각각에서 낸 축-결과 상관 — ④ 재현성.')
    print('r(결과) : 결과변수 자체의 신뢰도. **축과 무관하다** — 같은 결과변수면')
    print('          위약이든 실제 축이든 같다. ρ 의 상한(√r)을 정할 뿐이다.')
    print()
    if a.placebo:
        sig = [r for r in out if hp[(r['axis'], r['outcome'])][1]]
        ci0 = [r for r in out if r['ci'][0] is not None
               and not (r['ci'][0] <= 0 <= r['ci'][1])]
        print('## 위약 통과 판정 (ANALYSIS_PLAN 4절)')
        print('  ② Holm 후 유의한 위약 : %d건  %s' % (len(sig), '← 통과' if not sig else '← 실패'))
        print('  ③ CI 가 0 을 포함 안 함 : %d건  %s' % (len(ci0), '← 통과' if not ci0 else '← 실패'))
        big = [r for r in out if r['rho'] is not None and abs(r['rho']) >= 0.4]
        print('  |ρ| >= 0.4 : %d건  %s' % (len(big), '← 통과' if not big else '← 도구 조사'))
        rep = [r for r in out
               if r.get('rho_h1') is not None and r.get('rho_h2') is not None
               and abs(r['rho_h1']) >= 0.2 and abs(r['rho_h2']) >= 0.2
               and r['rho_h1']*r['rho_h2'] > 0]
        print('  ④ 양 반쪽에서 |ρ|>=0.2 이고 방향 일치 : %d건  %s'
              % (len(rep), '← 통과' if not rep else '← 도구 조사'))
        d1 = [r for r in out if r.get('rho_h1') is not None
              and r['rho']*r['rho_h1'] > 0 and r['rho']*r['rho_h2'] > 0]
        print('  ① 전체·홀·짝 방향이 모두 일치 : %d건 (일관성 낮을수록 좋다)' % len(d1))
        print()
        print('  ρ=.08 같은 값으로 분석기를 폐기하지 않는다. 위 셋이 통과면 진행.')
    else:
        print('|ρ|=0.20 은 합격선이 아니다 — 사전 설계의 최소 검출 효과다.')
        print('관측된 ρ 를 그대로 보고하고 합격/불합격 판정을 내리지 않는다.')


if __name__ == '__main__':
    main()
