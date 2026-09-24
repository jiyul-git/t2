#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SYNTH_CHANNEL_SPLIT — QX_EV 합성 대조의 READ 집계를 채널로 가른다. 읽기 전용.

사전등록 SYNTH_CHANNEL_SPLIT_PREREG.md 2·3절.

**새 측정이 아니다.** qx_ev_validate.synth_control 과 똑같은 계산을
수비(D)/공격(A)/pooled 셋으로 다르게 묶기만 한다. fixture 와 make_arms 는
수정하지 않는다 — 재현이 거기 걸려 있다.
"""
from __future__ import print_function

import argparse
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import qx_ev_fixture as FX
import qx_ev_validate as QV
import tier5_axis_validate as T5
import v7_num_intervention as IV

FLOOR = 0.002
# QX_EV_VALIDATION_RESULT.md 3-4 에 기록된 값. G2 관문의 대조 기준이다.
RECORDED = {'calc_only': 0.06074, 'pipe_only': 0.06032, 'diff': 0.00042}


def per_state_regret(prof, states, evs):
    """상태별 regret. synth_control 과 **완전히 같은 호출**이다."""
    return {s.sid: FX.regret_of(
        s, FX.bot_action(s, prof, random.Random(FX.FIX_SEED + s.sid))[0],
        evs[s.sid]) for s in states}


def collect(profs, states, evs):
    read = [s for s in states if s.group == 'READ']
    groups = {'D': [s for s in read if s.channel == 'D'],
              'A': [s for s in read if s.channel == 'A'],
              'pooled': read}
    acc = {k: {'calc': [], 'pipe': []} for k in groups}
    for prof in profs:
        c_only, p_only = T5.make_arms(prof)
        for arm, key in ((c_only, 'calc'), (p_only, 'pipe')):
            r = per_state_regret(arm, read, evs)
            for g, ss in groups.items():
                acc[g][key].append(float(np.mean([r[s.sid] for s in ss])))
    return acc, {k: len(v) for k, v in groups.items()}


def summarize(acc, counts):
    out = {}
    for g in ('D', 'A', 'pooled'):
        ca, pi = acc[g]['calc'], acc[g]['pipe']
        d = [x - y for x, y in zip(ca, pi)]          # CALC − PIPE
        ci = IV.boot_ci(d)
        out[g] = {'calc_only': float(np.mean(ca)),
                  'pipe_only': float(np.mean(pi)),
                  'diff': float(np.mean(d)), 'ci': list(ci),
                  'n_states': counts[g],
                  'sig': bool(ci[0] > 0 or ci[1] < 0)}
    return out


def verdict(res, g1, g2):
    if not (g1 and g2):
        return 'INCONCLUSIVE'
    dD, dA, dP = res['D'], res['A'], res['pooled']
    opposite = (dD['diff'] > 0) != (dA['diff'] > 0)
    both_sig = dD['sig'] and dA['sig']
    if opposite and both_sig:
        if (max(abs(dD['diff']), abs(dA['diff'])) >= FLOOR
                and abs(dP['diff']) < min(abs(dD['diff']), abs(dA['diff']))):
            return 'CHANNEL_CANCELLATION_CONFIRMED'
        if abs(dD['diff']) < FLOOR and abs(dA['diff']) < FLOOR:
            return 'CHANNEL_CANCELLATION_WEAK'
    return 'NO_CHANNEL_CANCELLATION'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='940001-940010')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=400)
    # 150 이다. 120 은 qx_ev_validate 의 argparse 기본값이고, 기록을 만든
    # 실행은 150 이었다 (QX_EV_VALIDATION_RESULT.md 1-4 "150쌍").
    # 근거·확인은 Amendment C1.
    ap.add_argument('--synth-n', type=int, default=150)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))

    states = FX.build_states()
    evs = {s.sid: s.ev_actions() for s in states}
    profs = IV.base_profiles(range(lo, hi + 1), a.entries, a.n)[:a.synth_n]
    print('상태 %d (READ D %d / READ A %d)   합성 프로필 %d'
          % (len(states),
             sum(1 for s in states if s.group == 'READ' and s.channel == 'D'),
             sum(1 for s in states if s.group == 'READ' and s.channel == 'A'),
             len(profs)))

    acc, counts = collect(profs, states, evs)
    res = summarize(acc, counts)

    # ---- G1: 원본 synth_control 과 부동소수점까지 같은가 ----
    print('\n--- G1 재현 관문: 원본 synth_control 직접 호출 ---')
    orig = QV.synth_control(profs, states, evs)
    p = res['pooled']
    g1 = (orig['calc_only'] == p['calc_only']
          and orig['pipe_only'] == p['pipe_only']
          and orig['diff'] == p['diff'])
    print('  원본 %.10f / %.10f      분리도구 pooled %.10f / %.10f'
          % (orig['calc_only'], orig['pipe_only'],
             p['calc_only'], p['pipe_only']))
    print('  G1 -> %s' % ('OK (부동소수점 일치)' if g1 else 'FAIL'))

    # ---- G2: 기록된 값과 일치하는가 ----
    g2 = all(abs(p[k] - RECORDED[k]) < 5e-6 for k in RECORDED)
    print('--- G2 기록 대조 (QX_EV_VALIDATION_RESULT.md 3-4) ---')
    for k in ('calc_only', 'pipe_only', 'diff'):
        print('  %-10s 기록 %.5f   재현 %.5f   차 %+.7f'
              % (k, RECORDED[k], p[k], p[k] - RECORDED[k]))
    print('  G2 -> %s' % ('OK' if g2 else 'FAIL'))

    # ---- 분리 결과 ----
    print('\n=== 채널 분리 (CALC − PIPE, 양수 = PIPE 가 낫다) ===')
    print('%-8s %6s %10s %10s %10s %24s'
          % ('채널', '상태', 'CALC', 'PIPE', 'diff', '95%CI'))
    for g, nm in (('D', '수비'), ('A', '공격'), ('pooled', '합침')):
        r = res[g]
        print('%-8s %6d %10.5f %10.5f %+10.5f   [%+.5f, %+.5f]  %s'
              % (nm, r['n_states'], r['calc_only'], r['pipe_only'],
                 r['diff'], r['ci'][0], r['ci'][1],
                 '유의' if r['sig'] else '유의하지 않음'))
    v = verdict(res, g1, g2)
    print('\n========== 판정: %s ==========' % v)
    out = {'result': res, 'verdict': v, 'g1': bool(g1), 'g2': bool(g2),
           'floor': FLOOR, 'recorded': RECORDED, 'n_profiles': len(profs)}
    if a.out:
        json.dump(out, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
