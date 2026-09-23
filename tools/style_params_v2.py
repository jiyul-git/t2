#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_CALIB_V2 공용 — posterior 기하만 교체 가능한 형태로 다시 계산한다.

사전등록: STYLE_CALIB_V2_PREREG.md 2절.

L/A/X 산출식은 건드리지 않는다. `reads.style_shadow` 가 낸 (L, A, X, q) 를
그대로 받아서 중심/스케일만 바꿔 posterior 를 다시 만든다. 따라서 좌표는
shipped SHADOW 코드와 비트 단위로 같다. production 은 이 모듈을 모른다.
"""
from __future__ import print_function

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import reads as RD

NAMES = RD.STYLE_V1_NAMES

V1_CENTERS = {k: tuple(v) for k, v in RD.STYLE_V1_CENTERS.items()}
V1_SCALES = (1.7, 1.7, 2.2)
V1_POP = (5.0, 5.0, 1.0)

# 평가 지표 정규화 상수. 사전등록으로 고정 — calibration 대상이 아니다.
METRIC_SCALES = (1.7, 1.7, 2.2)

_LOG_K = math.log(len(NAMES))


def posterior(L, A, X, q, centers, scales):
    """style_shadow 의 posterior 를 중심/스케일만 갈아끼워 재계산."""
    sl, sa, sx = (float(s) for s in scales)
    raw = {}
    for name in NAMES:
        lc, ac, xc = centers[name]
        d2 = ((L - lc) / sl) ** 2 + ((A - ac) / sa) ** 2 + ((X - xc) / sx) ** 2
        raw[name] = math.exp(-0.5 * q * d2)
    tot = sum(raw.values()) or 1.0
    probs = {n: raw[n] / tot for n in NAMES}
    H = -sum(p * math.log(max(p, 1e-300)) for p in probs.values())
    cert = max(0.0, min(1.0, q * (1.0 - H / _LOG_K)))
    top = max(NAMES, key=lambda k: probs[k])
    return {'probs': probs, 'top': top, 'entropy': H, 'certainty': cert}


def weighted_center(probs, centers):
    L = A = X = 0.0
    for name, p in probs.items():
        lc, ac, xc = centers[name]
        L += p * lc
        A += p * ac
        X += p * xc
    return (L, A, X)


def sqerr(pred, actual, scales=METRIC_SCALES):
    return sum(((pred[i] - actual[i]) / scales[i]) ** 2 for i in range(3)) / 3.0


def load_params(path):
    with open(path, encoding='utf-8') as fh:
        d = json.load(fh)
    centers = {k: tuple(float(x) for x in d['centers'][k]) for k in NAMES}
    return {
        'version': d.get('version'),
        'centers': centers,
        'scales': tuple(float(x) for x in d['scales']),
        'pop': tuple(float(x) for x in d['pop']),
        'raw': d,
    }


def v1_params():
    return {'version': 'V1', 'centers': dict(V1_CENTERS),
            'scales': V1_SCALES, 'pop': V1_POP, 'raw': {}}


def _selftest():
    """V1 중심/스케일을 넣으면 reads.style_shadow 와 같은 확률이 나와야 한다."""
    import random
    rng = random.Random(4242)
    worst = 0.0
    for _ in range(500):
        est = {
            'vpip': rng.uniform(0.02, 0.85), 'pfr': rng.uniform(0.0, 0.6),
            'rfi_rel': rng.uniform(0.1, 2.5), 'pf_limp': rng.uniform(0.0, 0.5),
            'pf_3bet': rng.uniform(0.0, 0.3), 'pf_4bet': rng.uniform(0.0, 0.2),
            'aggr': rng.uniform(1.0, 10.0), 'cbet': rng.uniform(0.0, 1.0),
            'barrel': rng.uniform(0.0, 1.0), 'ftb': rng.uniform(0.0, 1.0),
            'bluff': rng.uniform(1.0, 9.0), 'sz_mean': rng.uniform(0.2, 1.5),
            'sz_sd': rng.uniform(0.0, 0.8), 'sz_big': rng.uniform(0.0, 0.9),
            'confidence': rng.uniform(0.0, 1.0), 'n': rng.randrange(0, 120),
        }
        sh = RD.style_shadow(est)
        po = posterior(sh['L'], sh['A'], sh['X'], sh['q'], V1_CENTERS, V1_SCALES)
        for n in NAMES:
            worst = max(worst, abs(po['probs'][n] - sh['probs'][n]))
        worst = max(worst, abs(po['certainty'] - sh['certainty']))
    ok = worst <= 2e-6      # style_shadow 가 6자리 반올림해서 내보낸다
    print('selftest V1-equivalence max_abs_diff=%.3e %s' % (worst, 'PASS' if ok else 'FAIL'))

    # negative control: 중심을 옮기면 반드시 달라져야 한다 (검사가 공허하지 않음)
    moved = dict(V1_CENTERS)
    moved['TAG'] = (9.9, 0.1, 9.9)
    est = {'vpip': 0.3, 'pfr': 0.2, 'aggr': 5.0, 'confidence': 1.0, 'n': 60}
    sh = RD.style_shadow(est)
    a = posterior(sh['L'], sh['A'], sh['X'], sh['q'], V1_CENTERS, V1_SCALES)
    b = posterior(sh['L'], sh['A'], sh['X'], sh['q'], moved, V1_SCALES)
    moved_ok = abs(a['probs']['TAG'] - b['probs']['TAG']) > 1e-6
    print('selftest center-sensitivity %s' % ('PASS' if moved_ok else 'FAIL'))
    return 0 if (ok and moved_ok) else 1


if __name__ == '__main__':
    raise SystemExit(_selftest())
