#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V7 — 모집단에서 5단계 분포를 재고 c5 를 적합한다.

사전등록: HIERARCHICAL_READ_V7_PREREG.md 3·4절.
읽기 전용. 핸드를 돌리지 않고 선수 생성분포만 본다.

  fit     860001..860050 (400인 필드) 에서 c5 = Q 의 (1 - 3.5/400) 분위수
  verify  870001..870020 에서 필드별 5단계 인원수. 적합에 쓰지 않는다

field.field_quality 가 entries 에 의존하므로 비율은 **400인 필드 기준**이다.
hero(pid 0)는 make_player(rng, 0.9, ...) 로 따로 만들어지므로 제외한다.
"""
from __future__ import print_function

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import reads as RD

TARGET_PER_400 = 3.5          # 사전등록 목표 구간 3~4명의 한가운데
TARGET_LO, TARGET_HI = 3, 4


def draw(seed, entries, hero_pid=0):
    f = FS.Field(entries=entries, seed=seed, fmt='standard')
    out = []
    for pid, p in f.players.items():
        if pid == hero_pid:
            continue                      # hero 는 별도 품질로 생성된다
        prof = p.get('prof')
        if prof:
            out.append(RD.exploit_tier_v7(prof))
    return out, f.field_q


def span(text):
    lo, hi = (int(x) for x in text.split('-'))
    return range(lo, hi + 1)


def tier_counts(rows, c5):
    c1, c2, c3 = RD.TIER_V7_CUTS
    cnt = [0] * 5
    for r in rows:
        if c5 is not None and r['Q'] >= c5:
            t = 5
        elif r['E'] >= c3:
            t = 4
        elif r['E'] >= c2:
            t = 3
        elif r['E'] >= c1:
            t = 2
        else:
            t = 1
        cnt[t - 1] += 1
    return cnt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fit-seeds', default='860001-860050')
    ap.add_argument('--verify-seeds', default='870001-870020')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--out', default='v7_tier_params.json')
    ap.add_argument('--extra', action='append', default=[],
                    metavar='SEEDS:ENTRIES',
                    help='추가 서술 표. 예: 880001-880012:100')
    ap.add_argument('--c5', type=float)
    a = ap.parse_args()

    fit_rows, fq = [], None
    per_field_fit = []
    for sd in span(a.fit_seeds):
        rows, fq = draw(sd, a.entries)
        per_field_fit.append(len(rows))
        fit_rows.extend(rows)
    n = len(fit_rows)
    print('fit pool: %d fields x %d bots = %d  (entries=%d, field_q=%.4f)'
          % (len(per_field_fit), per_field_fit[0] if per_field_fit else 0, n,
             a.entries, fq))

    # c5 없이 본 구간 분포 (5단계가 아직 없는 상태)
    base = tier_counts(fit_rows, None)
    print('\n=== c5 적합 전 (구간 4 가 상한) ===')
    for i, nm in enumerate(RD.TIER_V7_NAMES):
        print('  %d %-22s %6d  %6.2f%%  (400명당 %5.1f)'
              % (i + 1, nm, base[i], 100.0 * base[i] / n, 400.0 * base[i] / n))

    qs = sorted((r['Q'] for r in fit_rows), reverse=True)
    frac = TARGET_PER_400 / 400.0
    k = max(1, int(round(frac * n)))
    c5 = a.c5 if a.c5 is not None else qs[k - 1]
    ge = sum(1 for q in qs if q >= c5)
    print('\nc5 적합: 목표 %.1f / 400  -> 상위 %d / %d,  c5 = %.6f  (>= c5 인 인원 %d)'
          % (TARGET_PER_400, k, n, c5, ge))
    print('Q 분위수  p50 %.4f  p90 %.4f  p99 %.4f  p99.125 %.4f  max %.4f'
          % (qs[int(0.50 * n)], qs[int(0.10 * n)], qs[int(0.01 * n)],
             c5, qs[0]))

    fitted = tier_counts(fit_rows, c5)
    print('\n=== c5 적합 후 (적합 표본, in-sample) ===')
    for i, nm in enumerate(RD.TIER_V7_NAMES):
        print('  %d %-22s %6d  %6.2f%%  (400명당 %5.2f)'
              % (i + 1, nm, fitted[i], 100.0 * fitted[i] / n, 400.0 * fitted[i] / n))

    # ---- 검증 표본 ----
    vcnt = []
    vtot = [0] * 5
    vn = 0
    for sd in span(a.verify_seeds):
        rows, _ = draw(sd, a.entries)
        c = tier_counts(rows, c5)
        vcnt.append(c[4])
        vn += len(rows)
        for i in range(5):
            vtot[i] += c[i]
    inrange = sum(1 for x in vcnt if TARGET_LO <= x <= TARGET_HI)
    print('\n=== 검증 표본 %s (적합에 안 쓴 시드) ===' % a.verify_seeds)
    print('  필드별 5단계 인원: %s' % vcnt)
    print('  평균 %.2f명 / 필드,  3~4명 구간에 든 필드 %d/%d (%.0f%%)'
          % (sum(vcnt) / float(len(vcnt)), inrange, len(vcnt),
             100.0 * inrange / len(vcnt)))
    for i, nm in enumerate(RD.TIER_V7_NAMES):
        print('  %d %-22s %6d  %6.2f%%  (400명당 %5.2f)'
              % (i + 1, nm, vtot[i], 100.0 * vtot[i] / vn, 400.0 * vtot[i] / vn))

    empty = [RD.TIER_V7_NAMES[i] for i in range(5) if vtot[i] == 0]
    print('\n빈 구간: %s' % (empty if empty else '없음'))

    extras = {}
    for spec in a.extra:
        sd_txt, ent_txt = spec.rsplit(':', 1)
        ent = int(ent_txt)
        tot = [0] * 5
        nn = 0
        per = []
        fq2 = None
        for sd in span(sd_txt):
            rows, fq2 = draw(sd, ent)
            c = tier_counts(rows, c5)
            per.append(c[4])
            nn += len(rows)
            for i in range(5):
                tot[i] += c[i]
        extras[spec] = {'counts': tot, 'n_bots': nn,
                        'per_field_level5': per, 'field_q': fq2}
        print('\n=== 서술 표: seeds %s, entries %d (field_q %.4f) ==='
              % (sd_txt, ent, fq2))
        for i, nm in enumerate(RD.TIER_V7_NAMES):
            print('  %d %-22s %6d  %6.2f%%  (필드당 %5.2f)'
                  % (i + 1, nm, tot[i], 100.0 * tot[i] / nn,
                     float(tot[i]) / len(per)))
        print('  필드별 5단계 인원: %s' % per)

    params = {
        'version': 'HIERARCHICAL_READ_V7',
        'prereg': 'HIERARCHICAL_READ_V7_PREREG.md',
        'cuts_E': list(RD.TIER_V7_CUTS),
        'c5': c5,
        'fit': {
            'seeds': a.fit_seeds, 'entries': a.entries, 'field_q': fq,
            'n_bots': n, 'target_per_400': TARGET_PER_400,
            'rank_used': k, 'in_sample_counts': fitted,
        },
        'verify': {
            'seeds': a.verify_seeds, 'n_bots': vn,
            'per_field_level5': vcnt, 'counts': vtot,
            'fields_in_target': inrange, 'fields': len(vcnt),
        },
        'extra': extras,
    }
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(params, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
