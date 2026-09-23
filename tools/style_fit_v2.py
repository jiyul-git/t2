#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_CALIB_V2 fitting — calibration 덤프에서 중심/스케일/모집단을 잡는다.

사전등록: STYLE_CALIB_V2_PREREG.md 3절. 규칙은 전부 그 문서에 먼저 박혀 있다.
숨은 archetype 라벨을 쓰지 않는다. 입력은 raw 공개행동 좌표뿐이다.

출력: style_params_v2.json (동결 대상) + MANIAC 진단 JSON.
"""
from __future__ import print_function

import argparse
import glob
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import style_params_v2 as SP

NAMES = SP.NAMES
MIN_HANDS = 6
K = 6
RESTART_SEEDS = tuple(range(777, 797))      # 20회
MAX_ITER = 100
SCALE_FLOOR = 0.5

# X 식의 항 (reads.style_shadow 와 같은 상수). 진단 전용.
X_TERMS = (
    ('pf_3bet', 0.22, 0.09, 0.06),
    ('pf_4bet', 0.16, 0.055, 0.04),
    ('barrel', 0.20, 0.52, 0.20),
    ('aggr', 0.18, 5.20, 1.80),
    ('sz_big', 0.14, 0.22, 0.18),
    ('sz_sd', 0.10, 0.28, 0.20),
)


def _hi(x, c, s):
    return max(0.0, math.tanh((float(x) - c) / s))


def load_samples(paths):
    pts, ests, meta = [], [], []
    seeds, bad = [], []
    for path in sorted(paths):
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        seeds.append(d['seed'])
        if d.get('engine_errors'):
            bad.append(d['seed'])
            continue
        for pr in d['pairs']:
            for win in ('w1', 'w2'):
                r = pr['raw'].get(win)
                if not r or int(r.get('hands', 0)) < MIN_HANDS:
                    continue
                pts.append((r['L'], r['A'], r['X']))
                ests.append(r['est'])
                meta.append((d['seed'], pr['key'], win, r['hands']))
    return np.asarray(pts, dtype=float), ests, meta, seeds, bad


def kmeanspp_init(Z, k, rng):
    n = Z.shape[0]
    idx = [rng.integers(n)]
    d2 = ((Z - Z[idx[0]]) ** 2).sum(axis=1)
    for _ in range(1, k):
        tot = d2.sum()
        if tot <= 0:
            idx.append(int(rng.integers(n)))
        else:
            r = rng.random() * tot
            j = int(np.searchsorted(np.cumsum(d2), r))
            idx.append(min(j, n - 1))
        d2 = np.minimum(d2, ((Z - Z[idx[-1]]) ** 2).sum(axis=1))
    return Z[idx].copy()


def kmeans(Z, k, seed):
    rng = np.random.default_rng(seed)
    C = kmeanspp_init(Z, k, rng)
    lab = None
    for _ in range(MAX_ITER):
        d = ((Z[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
        new = d.argmin(axis=1)
        if lab is not None and np.array_equal(new, lab):
            lab = new
            break
        lab = new
        for j in range(k):
            m = lab == j
            if not m.any():
                return None, None, float('inf')
            C[j] = Z[m].mean(axis=0)
    d = ((Z[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
    lab = d.argmin(axis=1)
    if len(set(lab.tolist())) < k:
        return None, None, float('inf')
    inertia = float(d[np.arange(Z.shape[0]), lab].sum())
    return C, lab, inertia


def assign_names(Cz):
    """사전등록 3-4 규칙. z 좌표만 본다."""
    left = list(range(Cz.shape[0]))
    out = {}

    def take(name, key):
        j = max(left, key=key)
        out[name] = j
        left.remove(j)

    take('MANIAC', lambda j: (Cz[j, 2], Cz[j, 1]))
    take('LAG', lambda j: Cz[j, 0] + Cz[j, 1])
    take('LOOSE_PASSIVE', lambda j: Cz[j, 0] - Cz[j, 1])
    take('TIGHT_PASSIVE', lambda j: -(Cz[j, 0] + Cz[j, 1]))
    take('NIT', lambda j: -Cz[j, 0])
    out['TAG'] = left.pop()
    return out


def consistency(centers, sizes, total, pop):
    c = centers
    checks = [
        ('C1 L(NIT)<L(TAG)<L(LAG)',
         c['NIT'][0] < c['TAG'][0] < c['LAG'][0]),
        ('C2 L(TIGHT_PASSIVE)<L(LOOSE_PASSIVE)',
         c['TIGHT_PASSIVE'][0] < c['LOOSE_PASSIVE'][0]),
        ('C3 A(TIGHT_PASSIVE)<A(NIT) and A(LOOSE_PASSIVE)<A(LAG)',
         c['TIGHT_PASSIVE'][1] < c['NIT'][1] and c['LOOSE_PASSIVE'][1] < c['LAG'][1]),
        ('C4 X(MANIAC)=max',
         all(c['MANIAC'][2] >= c[n][2] for n in NAMES)),
        ('C5 every cluster >=1% of samples',
         all(sizes[n] >= 0.01 * total for n in NAMES)),
        # Amendment A1. 보고 전용 — 깨져도 배정을 고치지 않는다.
        ('C6 MANIAC center above population mean on L and A',
         c['MANIAC'][0] >= pop[0] and c['MANIAC'][1] >= pop[1]),
    ]
    return [{'check': k, 'ok': bool(v)} for k, v in checks]


def nearest_top(P, centers, scales):
    """argmax posterior = 최근접 중심 (q>0 에서 d2 단조)."""
    C = np.asarray([centers[n] for n in NAMES], dtype=float)
    S = np.asarray(scales, dtype=float)
    d = (((P[:, None, :] - C[None, :, :]) / S[None, None, :]) ** 2).sum(axis=2)
    lab = d.argmin(axis=1)
    return lab, d


def maniac_diag(P, ests, centers_v2, scales_v2):
    out = {}
    # (a) 식 병목
    terms = {}
    hyp = 0.0
    for key, w, c, s in X_TERMS:
        vals = np.asarray([_hi(e[key], c, s) for e in ests])
        q = np.percentile(vals, [50, 90, 99])
        terms[key] = {
            'weight': w, 'center': c, 'scale': s,
            'mean': float(vals.mean()), 'median': float(q[0]),
            'p90': float(q[1]), 'p99': float(q[2]),
            'zero_frac': float((vals <= 0.0).mean()),
            'input_mean': float(np.mean([e[key] for e in ests])),
            'input_p99': float(np.percentile([e[key] for e in ests], 99)),
        }
        hyp += w * float(q[2])
    out['x_terms'] = terms
    out['x_if_all_terms_at_p99'] = 1.0 + 9.0 * hyp
    xs = P[:, 2]
    out['X_distribution'] = {
        'mean': float(xs.mean()), 'sd': float(xs.std(ddof=0)),
        'p50': float(np.percentile(xs, 50)), 'p90': float(np.percentile(xs, 90)),
        'p99': float(np.percentile(xs, 99)), 'max': float(xs.max()),
        'frac_ge_6': float((xs >= 6).mean()), 'frac_ge_7': float((xs >= 7).mean()),
        'frac_ge_8': float((xs >= 8).mean()),
    }
    # (b) 중심 병목
    Cm = np.asarray(SP.V1_CENTERS['MANIAC'], dtype=float)
    S1 = np.asarray(SP.V1_SCALES, dtype=float)
    dm = np.sqrt((((P - Cm) / S1) ** 2).sum(axis=1))
    out['v1_maniac_center_distance'] = {
        'min': float(dm.min()), 'p1': float(np.percentile(dm, 1)),
        'median': float(np.percentile(dm, 50)),
    }
    lab1, _ = nearest_top(P, SP.V1_CENTERS, SP.V1_SCALES)
    n_v1 = int((lab1 == NAMES.index('MANIAC')).sum())
    # (c) 스케일만 교체
    lab2, _ = nearest_top(P, SP.V1_CENTERS, scales_v2)
    n_scale = int((lab2 == NAMES.index('MANIAC')).sum())
    lab3, _ = nearest_top(P, centers_v2, scales_v2)
    n_v2 = int((lab3 == NAMES.index('MANIAC')).sum())
    out['maniac_argmax_counts'] = {
        'total_samples': int(P.shape[0]),
        'v1_centers_v1_scales': n_v1,
        'v1_centers_v2_scales': n_scale,
        'v2_centers_v2_scales': n_v2,
    }
    out['top_counts_v1'] = {NAMES[i]: int((lab1 == i).sum()) for i in range(len(NAMES))}
    out['top_counts_v2'] = {NAMES[i]: int((lab3 == i).sum()) for i in range(len(NAMES))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dumps', nargs='+', required=True)
    ap.add_argument('--out', default='style_params_v2.json')
    ap.add_argument('--diag', default='style_calib_v2_diag.json')
    a = ap.parse_args()

    paths = []
    for g in a.dumps:
        paths.extend(glob.glob(g) if any(ch in g for ch in '*?[') else [g])
    P, ests, meta, seeds, bad = load_samples(paths)
    if P.shape[0] < 200:
        print('FATAL: too few samples: %d' % P.shape[0])
        return 2

    pop = P.mean(axis=0)
    sd = P.std(axis=0, ddof=0)
    sd_safe = np.maximum(sd, 1e-6)
    cov = np.cov(P.T, ddof=0)
    Z = (P - pop) / sd_safe

    best = (None, None, float('inf'), None)
    tried = []
    for s in RESTART_SEEDS:
        C, lab, inertia = kmeans(Z, K, s)
        tried.append({'seed': s, 'inertia': (None if math.isinf(inertia) else inertia)})
        if inertia < best[2]:
            best = (C, lab, inertia, s)
    Cz, lab, inertia, bseed = best
    if Cz is None:
        print('FATAL: every restart degenerated')
        return 2

    names_by_cluster = assign_names(Cz)
    centers = {}
    sizes = {}
    for name, j in names_by_cluster.items():
        centers[name] = tuple(float(x) for x in (Cz[j] * sd_safe + pop))
        sizes[name] = int((lab == j).sum())

    # pooled within-cluster per-axis sd
    resid = P - (Cz[lab] * sd_safe + pop)
    within = np.sqrt((resid ** 2).mean(axis=0))
    scales = tuple(float(max(SCALE_FLOOR, x)) for x in within)

    checks = consistency(centers, sizes, P.shape[0], pop)
    diag = maniac_diag(P, ests, centers, scales)

    params = {
        'version': 'STYLE_CALIB_V2',
        'prereg': 'STYLE_CALIB_V2_PREREG.md',
        'centers': {n: list(centers[n]) for n in NAMES},
        'scales': list(scales),
        'pop': [float(x) for x in pop],
        'pop_sd': [float(x) for x in sd],
        'pop_cov': [[float(v) for v in row] for row in cov],
        'fit': {
            'n_samples': int(P.shape[0]),
            'n_seeds': len(seeds),
            'seeds': sorted(seeds),
            'invalid_seeds': sorted(bad),
            'min_hands': MIN_HANDS,
            'k': K,
            'best_restart_seed': int(bseed),
            'inertia': inertia,
            'cluster_sizes': sizes,
            'restarts': tried,
        },
        'consistency': checks,
    }
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(params, fh, ensure_ascii=False, indent=1, sort_keys=True)
    with open(a.diag, 'w', encoding='utf-8') as fh:
        json.dump(diag, fh, ensure_ascii=False, indent=1, sort_keys=True)

    print('FIT samples=%d seeds=%d invalid=%s inertia=%.4f (restart seed %d)'
          % (P.shape[0], len(seeds), bad or '[]', inertia, bseed))
    print('POP_V2    = (%.4f, %.4f, %.4f)   sd = (%.4f, %.4f, %.4f)'
          % (tuple(pop) + tuple(sd)))
    print('SCALES_V2 = (%.4f, %.4f, %.4f)' % scales)
    for n in NAMES:
        print('  %-14s (%.3f, %.3f, %.3f)  n=%d' % ((n,) + centers[n] + (sizes[n],)))
    for c in checks:
        print('  %-48s %s' % (c['check'], 'OK' if c['ok'] else 'VIOLATED'))
    print('MANIAC argmax: v1c/v1s=%d  v1c/v2s=%d  v2c/v2s=%d  (n=%d)'
          % (diag['maniac_argmax_counts']['v1_centers_v1_scales'],
             diag['maniac_argmax_counts']['v1_centers_v2_scales'],
             diag['maniac_argmax_counts']['v2_centers_v2_scales'],
             diag['maniac_argmax_counts']['total_samples']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
