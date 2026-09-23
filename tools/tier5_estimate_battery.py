#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ESTIMATE 단계 전용 배터리. 읽기 전용.

v7_num_battery 의 QX_E 는 `opp_est` 를 완성된 dict 로 받아 넘긴다. 그래서
reads.estimate / _shrink / obs_from_profile 를 **한 번도 부르지 않는다**
(계측으로 확인). 즉 기능 6단계 중 1~3단계(관찰 기록 · 기억 · 표본 충분성)가
QX_E 에서 통째로 빠져 있다.

이 배터리는 합성 Book 을 만들어 perceived_profile 을 거치게 한다.
  관측된 빈도와 표본 크기를 격자로 흔들고
  관찰자가 만든 추정치가 **실제 생성 빈도**를 얼마나 따라가는지 잰다.
oracle 은 내가 Book 을 만들 때 쓴 생성 빈도다 — target 의 hidden profile 이
아니라 합성 표본의 성질이다. 관찰자는 이 값을 못 본다.

점수 이름은 QX_S 로 따로 둔다. **사전등록한 QX_E 에 섞지 않는다.**
"""
from __future__ import print_function

import argparse
import copy
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import reads as RD
import v7_num_battery as B

TRUE_RATES = (0.25, 0.40, 0.55, 0.70, 0.85)
SAMPLES = (4, 10, 25, 60)
REPS = 6
OBS_ID, TGT_ID = 1, 2


def make_book(n, rate):
    """관측 장부를 직접 만든다. 관찰자 능력과 무관하게 동일한 기록이다
    (Book.observe_* 가 관찰자를 구분하지 않는 것과 같다)."""
    bk = RD.Book()
    r = bk.rec(OBS_ID, TGT_ID)
    r['hands'] = n
    r['facing_bet'] = n
    r['fold_to_bet'] = int(round(n * rate))
    for st in ('flop', 'turn', 'river'):
        r['fb_' + st] = n
        r['f2b_' + st] = int(round(n * rate))
    r['vpip'] = int(round(n * 0.26))
    r['pfr'] = int(round(n * 0.15))
    r['cbet_opp'] = n
    r['cbet'] = int(round(n * 0.55))
    r['barrel_opp'] = n
    r['barrel'] = int(round(n * 0.42))
    return bk


def qx_s(prof):
    """추정치가 실제 생성 빈도를 얼마나 따라가는가."""
    xs, ys = [], []
    i = 0
    for rate in TRUE_RATES:
        for n in SAMPLES:
            bk = make_book(n, rate)
            tot = 0.0
            for rep in range(REPS):
                rng = random.Random(B.SEED + i * 977 + rep)
                est = RD.perceived_profile(bk, OBS_ID, TGT_ID, prof, rng)
                tot += float(est.get('ftb') or RD.PRIOR['fold_to_bet'])
            ys.append(tot / REPS)
            xs.append(rate)
            i += 1
    return B.pearson(xs, ys), ys


def evaluate(prof):
    r, ys = qx_s(prof)
    return {'QX_S': r, 'vector': [round(v, 9) for v in ys],
            'level': float(np.mean(ys))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='910001-910004')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--axes', default='consistency,attention,adaptability,'
                                      'range_read,sizing_tell,potodds,spr,blocker')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    import json
    import persona as PS
    import v7_num_intervention as IV
    lo, hi = (int(x) for x in a.seeds.split('-'))
    profs = IV.base_profiles(range(lo, hi + 1), a.entries, a.n)
    print('기저 프로필 %d개' % len(profs))
    base = [evaluate(p)['QX_S'] for p in profs]
    print('QX_S 자연분포: mean %+.4f  sd %.4f  min %+.4f  max %+.4f'
          % (float(np.mean(base)), float(np.std(base)),
             float(np.min(base)), float(np.max(base))))

    res = {}
    for ax in [x for x in a.axes.split(',') if x]:
        in_temper = ax in PS.TEMPER
        dS, chg = [], []
        for prof in profs:
            def mut(v):
                q = copy.deepcopy(prof)
                (q['temper'] if in_temper else q['concepts'])[ax] = float(v)
                return q
            e1, e2 = evaluate(mut(2.0)), evaluate(mut(8.0))
            dS.append(e2['QX_S'] - e1['QX_S'])
            chg.append(sum(1 for x, y in zip(e1['vector'], e2['vector'])
                           if x != y) / float(len(e1['vector'])))
        ci = IV.boot_ci(dS)
        res[ax] = {'dS': float(np.mean(dS)), 'dS_ci': ci,
                   'frac_response_changed': float(np.mean(chg)),
                   'group': 'TEMPER' if in_temper else 'CALC'}
        print('%-14s dS %+.4f  95%%CI [%+.4f, %+.4f]   응답변화 %5.1f%%'
              % (ax, res[ax]['dS'], ci[0], ci[1],
                 100.0 * res[ax]['frac_response_changed']))
    if a.out:
        json.dump({'base_mean': float(np.mean(base)),
                   'base_sd': float(np.std(base)), 'axes': res},
                  open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
