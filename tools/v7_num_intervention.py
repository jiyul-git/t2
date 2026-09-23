#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NUMERIC_BUNDLE_V7 paired intervention. 읽기 전용.

사전등록 3-A. 같은 기저 프로필에서 concept 하나만 2.0 <-> 8.0 으로 바꾸고
나머지는 전부 고정한다. 같은 배터리·같은 RNG 시드로 QX_E / QX_G 를 잰다.

2.0 / 8.0 은 read_resolution._see 의 양 끝 앵커다. 새 값이 아니다.
"""
from __future__ import print_function

import argparse
import copy
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import fieldsim as FS
import reads as RD
import v7_num_battery as B

LOW, HIGH = 2.0, 8.0
BOOT = 2000


def base_profiles(seeds, entries, k):
    profs = []
    for sd in seeds:
        f = FS.Field(entries=entries, seed=sd, fmt='standard')
        for pid, p in sorted(f.players.items()):
            if pid == 0:
                continue
            if p.get('prof', {}).get('concepts'):
                profs.append(p['prof'])
    rng = random.Random(B.SEED)
    idx = sorted(rng.sample(range(len(profs)), min(k, len(profs))))
    return [profs[i] for i in idx]


def with_concept(prof, c, v):
    q = copy.deepcopy(prof)
    q['concepts'][c] = float(v)
    return q


def boot_ci(diffs, seed=B.SEED, iters=BOOT):
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(iters):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return means[int(0.025 * iters)], means[int(0.975 * iters)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='910001-910004')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--concept', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))
    profs = base_profiles(range(lo, hi + 1), a.entries, a.n)
    print('base profiles: %d  (seeds %s, entries %d)' % (len(profs), a.seeds, a.entries))

    res = {}
    todo = (a.concept,) if a.concept else RD.TIER_V7_NUMERIC
    for c in todo:
        dE, dG, dLvl, chg = [], [], [], []
        dfam = {k: [] for k in B.FAMILIES_ALL}
        for prof in profs:
            a_lo = B.evaluate(with_concept(prof, c, LOW))
            a_hi = B.evaluate(with_concept(prof, c, HIGH))
            # 응답 자체가 바뀌기는 하는가 — 도달은 했는데 출력이 불변인지 가른다
            v_lo, v_hi = a_lo['vector'], a_hi['vector']
            chg.append(sum(1 for x, y in zip(v_lo, v_hi) if x != y) / float(len(v_lo)))
            dE.append(a_hi['QX_E'] - a_lo['QX_E'])
            dG.append(a_hi['QX_G'] - a_lo['QX_G'])
            dLvl.append(a_hi['level'] - a_lo['level'])
            for k in B.FAMILIES_ALL:
                dfam[k].append(a_hi['families'][k] - a_lo['families'][k])
        n = len(dE)
        mE, mG = sum(dE) / n, sum(dG) / n
        ciE, ciG = boot_ci(dE), boot_ci(dG)
        res[c] = {
            'dE': mE, 'dE_ci': ciE, 'dG': mG, 'dG_ci': ciG,
            'd_level': sum(dLvl) / n,
            'by_family': {k: sum(v) / n for k, v in dfam.items()},
            'frac_response_changed': sum(chg) / n,
            'n_pairs': n,
        }
        print('%-14s dE %+.4f [%+.4f,%+.4f]  dG %+.4f [%+.4f,%+.4f]  dlevel %+.4f'
              '  응답변화 %.1f%%'
              % (c, mE, ciE[0], ciE[1], mG, ciG[0], ciG[1], res[c]['d_level'],
                 100.0 * res[c]['frac_response_changed']))
        print('   %s' % {k: round(v, 4) for k, v in res[c]['by_family'].items()})
    if a.out:
        json.dump({'low': LOW, 'high': HIGH, 'n': len(profs),
                   'seeds': a.seeds, 'entries': a.entries, 'result': res},
                  open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
