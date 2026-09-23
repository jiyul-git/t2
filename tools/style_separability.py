#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""행동공간 L/A/X 에 6개로 갈라질 구조가 실제로 있는지 잰다. 읽기 전용.

k-means 의 설명분산만 보면 아무 구름에서나 높게 나온다. 그래서 같은 평균·
공분산을 가진 **단일 정규분포 귀무표본**에 같은 절차를 돌린 값을 대조군으로
같이 낸다. 실루엣은 부분표본으로 잰다.
"""
from __future__ import print_function

import argparse
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import style_params_v2 as SP

K = 6
NULL_SEED = 31337
SIL_N = 4000


def load(paths):
    pts = []
    for p in sorted(paths):
        d = json.load(open(p, encoding='utf-8'))
        if d.get('engine_errors'):
            continue
        for pr in d['pairs']:
            for w in ('w1', 'w2'):
                r = pr['raw'].get(w)
                if r and int(r.get('hands', 0)) >= 6:
                    pts.append((r['L'], r['A'], r['X']))
    return np.asarray(pts, dtype=float)


def lloyd(Z, C):
    for _ in range(100):
        d = ((Z[:, None, :] - C[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1)
        new = np.stack([Z[lab == j].mean(0) if (lab == j).any() else C[j]
                        for j in range(C.shape[0])])
        if np.allclose(new, C):
            C = new
            break
        C = new
    d = ((Z[:, None, :] - C[None, :, :]) ** 2).sum(2)
    lab = d.argmin(1)
    return lab, float(d[np.arange(Z.shape[0]), lab].sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dumps', nargs='+', required=True)
    ap.add_argument('--params', default='style_params_v2.json')
    a = ap.parse_args()
    paths = []
    for g in a.dumps:
        paths.extend(glob.glob(g) if any(ch in g for ch in '*?[') else [g])
    P = load(paths)
    par = SP.load_params(a.params)
    pop = np.asarray(par['pop'])
    sd = np.asarray(par['raw']['pop_sd'])
    Z = (P - pop) / sd
    Cz = (np.asarray([par['centers'][n] for n in SP.NAMES]) - pop) / sd

    d = ((Z[:, None, :] - Cz[None, :, :]) ** 2).sum(2)
    lab = d.argmin(1)
    inertia = float(d[np.arange(Z.shape[0]), lab].sum())
    total = float((Z ** 2).sum())
    ev = 1.0 - inertia / total

    rng = np.random.default_rng(NULL_SEED)
    G = rng.multivariate_normal(Z.mean(0), np.cov(Z.T), size=Z.shape[0])
    _, gi = lloyd(G, G[rng.choice(G.shape[0], K, replace=False)].copy())
    ev_null = 1.0 - gi / float((G ** 2).sum())

    idx = rng.choice(Z.shape[0], min(SIL_N, Z.shape[0]), replace=False)
    Zs, ls = Z[idx], lab[idx]
    D = np.sqrt(((Zs[:, None, :] - Zs[None, :, :]) ** 2).sum(2))
    sil = []
    for i in range(Zs.shape[0]):
        same = ls == ls[i]
        same[i] = False
        if not same.any():
            continue
        aa = D[i][same].mean()
        bb = min(D[i][ls == j].mean() for j in range(K)
                 if j != ls[i] and (ls == j).any())
        sil.append((bb - aa) / max(aa, bb))

    print('n=%d  explained_variance(k=%d)=%.4f  gaussian_null=%.4f  '
          'silhouette(n=%d)=%.4f'
          % (Z.shape[0], K, ev, ev_null, len(idx), float(np.mean(sil))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
