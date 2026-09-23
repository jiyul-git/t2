#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V7 구조 전수 검사. 읽기 전용.

사전등록 HIERARCHICAL_READ_V7_PREREG.md 8절 "구조" 항목을 그대로 검사한다.
각 검사에는 **음성 대조**가 붙는다 — 일부러 깨뜨린 변종에서 반드시 실패해야
검사가 공허하지 않다.
"""
from __future__ import print_function

import argparse
import itertools
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import reads as RD

TOL = 1e-9


def make_ests(rng, k):
    out = []
    for _ in range(k):
        n = rng.choice([1, 3, 6, 12, 25, 60, 140])
        out.append({
            'vpip': rng.uniform(0.05, 0.75), 'pfr': rng.uniform(0.0, 0.55),
            'rfi_rel': rng.uniform(0.2, 2.2), 'pf_limp': rng.uniform(0.0, 0.40),
            'pf_3bet': rng.uniform(0.0, 0.25), 'pf_4bet': rng.uniform(0.0, 0.15),
            'aggr': rng.uniform(1.0, 10.0), 'cbet': rng.uniform(0.1, 0.95),
            'barrel': rng.uniform(0.05, 0.95), 'ftb': rng.uniform(0.1, 0.9),
            'bluff': rng.uniform(1.0, 9.0), 'sz_mean': rng.uniform(0.25, 1.4),
            'sz_sd': rng.uniform(0.0, 0.7), 'sz_big': rng.uniform(0.0, 0.8),
            'sz_n': rng.choice([0, 3, 9, 25]),
            'pf_fold_to_3bet': rng.uniform(0.2, 0.9),
            'pf_fold_to_4bet': rng.uniform(0.2, 0.9),
            'sz_river': rng.uniform(0.2, 1.5),
            'confidence': rng.uniform(0.05, 1.0), 'n': n,
        })
    return out


def collect_profiles(seeds, entries):
    profs = {t: [] for t in range(1, 6)}
    for sd in seeds:
        f = FS.Field(entries=entries, seed=sd, fmt='standard')
        for pid, p in f.players.items():
            if pid == 0:
                continue
            pr = p.get('prof')
            if not pr:
                continue
            t = RD.exploit_tier_v7(pr)['tier']
            if len(profs[t]) < 60:
                profs[t].append(pr)
    return profs


def grid_points(k):
    lo, hi = RD.V7_RANGES[k]
    step = (hi - lo) / float(RD.V7_QUAL_STEPS - 1)
    return [lo + j * step for j in range(RD.V7_QUAL_STEPS)]


def run_checks(read_fn, profs, ests, label):
    fails = []
    seen_tiers = set()
    mags = {t: [0.0, 0] for t in range(1, 6)}
    for t, plist in profs.items():
        for prof in plist:
            for est in ests:
                o = read_fn(prof, est)
                tier = o.get('tier')
                seen_tiers.add(tier)

                # C1 1단계는 모든 채널 0 (size_river 는 중립값), w 도 0
                if tier == 1:
                    if abs(o.get('w', 0.0)) > TOL:
                        fails.append(('C1 tier1 w!=0', tier, o.get('w')))
                    for k in RD.V7_ALL_KEYS:
                        base = RD.V7_NEUTRAL_SIZE_RIVER if k == 'size_river' else 0.0
                        if abs(o.get(k, 0.0) - base) > TOL:
                            fails.append(('C1 tier1 channel nonzero', k, o.get(k)))

                # C2 1~3단계에서 정밀 채널 9개가 중립
                if tier <= 3:
                    for k in RD.V7_PRECISE:
                        base = RD.V7_NEUTRAL_SIZE_RIVER if k == 'size_river' else 0.0
                        if abs(o.get(k, 0.0) - base) > TOL:
                            fails.append(('C2 precise leak', tier, k, o.get(k)))

                # C3 2단계는 인상 두 채널만
                if tier == 2:
                    for k in RD.V7_ALL_KEYS:
                        if k in RD.V7_IMPRESSION or k == 'size_river':
                            continue
                        if abs(o.get(k, 0.0)) > TOL:
                            fails.append(('C3 tier2 extra channel', k, o.get(k)))

                # C4 4단계의 evidence 가 5점 격자 위에만 있다
                if tier == 4:
                    ev = o.get('evidence') or {}
                    for k, v in ev.items():
                        if min(abs(v - g) for g in grid_points(k)) > 1e-6:
                            fails.append(('C4 tier4 evidence off-grid', k, v))

                # C5 5단계만 연속 원값 — evidence == detail
                if tier == 5:
                    ev = o.get('evidence') or {}
                    det = (o.get('layer_sources') or {}).get('detail') or {}
                    for k, v in ev.items():
                        if abs(v - float(det.get(k, 0.0))) > 1e-6:
                            fails.append(('C5 tier5 evidence != detail', k, v))

                # C6 혼합 가중이 1 이고 같은 채널을 두 번 더하지 않는다
                if tier >= 2:
                    d = o.get('data', 0.0) if tier >= 4 else 0.0
                    s = o.get('s', 0.0)
                    pr = o.get('prior') or {}
                    ev = o.get('evidence') or {}
                    for k in RD.V7_ALL_KEYS:
                        if k == 'size_river':
                            continue
                        lo, hi = RD.V7_RANGES[k]
                        want = max(lo, min(hi, (1.0 - d) * s * pr.get(k, 0.0)
                                           + d * ev.get(k, 0.0)))
                        if abs(want - o.get(k, 0.0)) > 1e-6:
                            fails.append(('C6 mixture mismatch', tier, k,
                                          want, o.get(k)))

                if tier:
                    m = sum(abs(o.get(k, 0.0)) for k in RD.V7_ALL_KEYS
                            if k != 'size_river')
                    mags[tier][0] += m
                    mags[tier][1] += 1

    means = {t: (mags[t][0] / mags[t][1] if mags[t][1] else None)
             for t in range(1, 6)}
    print('[%s] tiers exercised: %s' % (label, sorted(seen_tiers)))
    print('[%s] mean sum|channel| by tier: %s' % (label, {
        t: (round(v, 4) if v is not None else None) for t, v in means.items()}))
    return fails, means, seen_tiers


def broken_read(prof, est):
    """음성 대조 — 2단계에서 정밀 채널을 흘리는 변종."""
    o = RD.hierarchical_read_v7(prof, est)
    if o.get('tier') == 2:
        o = dict(o)
        o['size_gap'] = 0.3
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='870001-870030')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--ests', type=int, default=8)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))
    seeds = range(lo, hi + 1)

    profs = collect_profiles(seeds, a.entries)
    print('profiles per tier: %s' % {t: len(v) for t, v in profs.items()})
    ests = make_ests(random.Random(20260923), a.ests)

    fails, means, seen = run_checks(RD.hierarchical_read_v7, profs, ests, 'V7')

    # C7 hidden target 정보 0 — 입력이 observer prof 와 opp_est 뿐이라 구조적이다.
    #     공허하지 않음을 위해 opp_est 를 바꾸면 반드시 출력이 바뀌어야 한다.
    p4 = (profs[4] or profs[3] or profs[2])[0]
    o1 = RD.hierarchical_read_v7(p4, ests[0])
    o2 = RD.hierarchical_read_v7(p4, ests[1])
    if all(abs(o1.get(k, 0.0) - o2.get(k, 0.0)) <= TOL for k in RD.V7_ALL_KEYS):
        fails.append(('C7 est-insensitive (vacuous check)',))

    # C8 단조: 구간이 올라갈수록 채널 크기 평균이 커진다
    seq = [means[t] for t in range(1, 6) if means[t] is not None]
    if any(seq[i] >= seq[i + 1] for i in range(len(seq) - 1)):
        fails.append(('C8 magnitude not monotone', [round(x, 4) for x in seq]))

    # 음성 대조 — 깨진 변종은 반드시 실패해야 한다
    bfails, _, _ = run_checks(broken_read, profs, ests, 'BROKEN(negative control)')
    neg_ok = any(f[0].startswith('C2') for f in bfails)

    print('\nV7 failures: %d' % len(fails))
    for f in fails[:20]:
        print('  ', f)
    print('negative control caught the injected leak: %s' % neg_ok)
    ok = (not fails) and neg_ok and seen == {1, 2, 3, 4, 5}
    print('\nSTRUCTURE %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
