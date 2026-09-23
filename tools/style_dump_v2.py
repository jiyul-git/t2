#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_CALIB_V2 덤프 — 시드 하나를 돌려 pair×cut 좌표를 떨군다.

사전등록: STYLE_CALIB_V2_PREREG.md 1·3-1·4 절.

harness 는 V1 자연상태 측정(tools/style_shadow_natural.py)의 MeasuredField 를
그대로 재사용한다. 모든 Hand 가 하나의 Book 을 공유해 pid 기준 관찰이 누적된다.
production 은 수정하지 않는다.

이 도구는 posterior 를 계산하지 않는다. 중심/스케일에 의존하는 값(top, probs,
certainty, entropy)은 전부 하류에서 만든다. 덤프는 calibration 과 holdout 에
같은 형태로 쓰인다.
"""
from __future__ import print_function

import argparse
import copy
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import fieldsim as FS
import reads as RD
import style_shadow_natural as NAT

CUTS = NAT.CUTS                      # (10, 20, 30, 40)
EST_KEYS = ('vpip', 'pfr', 'rfi_rel', 'pf_limp', 'pf_3bet', 'pf_4bet',
            'aggr', 'cbet', 'barrel', 'ftb', 'sz_mean', 'sz_sd', 'sz_big')


def _coords_from_est(est):
    sh = RD.style_shadow(est)
    out = {'L': sh['L'], 'A': sh['A'], 'X': sh['X'], 'q': sh['q'],
           'conf': sh['confidence'], 'n': sh['n']}
    return out


def _raw_entry(rec):
    """Book counter 구간 하나 → raw 좌표 + 입력 행동값."""
    hands = int((rec or {}).get('hands', 0) or 0)
    if hands <= 0:
        return None
    est = NAT.raw_est(rec)
    out = _coords_from_est(est)
    out['hands'] = hands
    out['est'] = {k: float(est[k]) for k in EST_KEYS}
    return out


def run(seed, rounds, entries):
    t0 = time.time()
    old = getattr(FS.Field, 'BOT_LOG', None)
    FS.Field.BOT_LOG = 0
    f = NAT.MeasuredField(entries=entries, seed=seed, fmt='standard')
    snaps = {}
    try:
        for rnd in range(1, rounds + 1):
            if f.remaining() <= 8:
                break
            f.hand_no += 1
            f.advance_level()
            for tb in list(f.tables.values()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
            if rnd in CUTS:
                snaps[rnd] = copy.deepcopy(f.shared_book.d)
    finally:
        if old is not None:
            FS.Field.BOT_LOG = old

    keys = set()
    for d in snaps.values():
        keys |= set(d)

    pairs = []
    d20 = snaps.get(20, {})
    d40 = snaps.get(40, {})
    for key in sorted(keys):
        rowb = {}
        for cut in CUTS:
            d = snaps.get(cut)
            if not d or key not in d:
                continue
            # 관찰자 노이즈/shrink 를 거친 belief. V1 과 같은 결정적 RNG.
            sh = NAT.style_for_pair(f, d, key, seed, cut)
            if sh is None:
                continue
            rowb[str(cut)] = {'L': sh['L'], 'A': sh['A'], 'X': sh['X'],
                              'q': sh['q'], 'conf': sh['confidence'],
                              'n': sh['n'],
                              'hands': int(d[key].get('hands', 0) or 0)}
        raw = {}
        w1 = _raw_entry(d20.get(key))
        if w1:
            raw['w1'] = w1
        if key in d20 and key in d40:
            w2 = _raw_entry(NAT.delta_rec(d20[key], d40[key]))
            if w2:
                raw['w2'] = w2
        if not rowb and not raw:
            continue
        pairs.append({'key': key, 'belief': rowb, 'raw': raw})

    return {
        'schema': 'style_dump_v2',
        'seed': seed,
        'rounds_done': max(snaps) if snaps else 0,
        'remaining': f.remaining(),
        'entries': entries,
        'engine_errors': len(f.errors),
        'errors': f.errors[:20],
        'elapsed_sec': round(time.time() - t0, 1),
        'pairs': pairs,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--rounds', type=int, default=40)
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = run(a.seed, a.rounds, a.entries)
    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, sort_keys=True)
    print('DUMP seed=%d pairs=%d rounds=%d errors=%d elapsed=%.1fs -> %s'
          % (out['seed'], len(out['pairs']), out['rounds_done'],
             out['engine_errors'], out['elapsed_sec'], a.out))
    return 0 if out['engine_errors'] == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
