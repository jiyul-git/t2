#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V6 구조 조건의 축 불일치를 확인한다. 읽기 전용.

반사실 도구는 관찰자를 `observer_resolution_v4.detail_access` 로 bin 하는데,
V6 의 보간 파라미터는 채널별 `read_resolution` 값(see_freq/see_line/see_size)이다.

    detail_access = 0.30*see_freq + 0.45*see_line + 0.25*see_size

즉 bin 축은 see_line 이 가장 무겁다. freq 채널의 층 비중을 detail_access bin 으로
보면 축이 어긋난다. 그 어긋남의 크기를 실제 봇 모집단에서 잰다.
"""
from __future__ import print_function

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import persona as PS
import reads as RD


def bern(a):
    return ((1 - a) ** 2, 2 * a * (1 - a), a ** 2)


def binof(da):
    return 'LOW' if da < .34 else ('MID' if da < .67 else 'HIGH')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='850001-850012')
    ap.add_argument('--entries', type=int, default=100)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))

    rows = []
    for sd in range(lo, hi + 1):
        f = FS.Field(entries=a.entries, seed=sd, fmt='standard')
        for p in f.players.values():
            prof = p.get('prof')
            if not prof:
                continue
            r = PS.read_resolution(prof)
            d = RD.observer_resolution_v4(prof)
            rows.append((d['detail_access'], r['see_freq'], r['see_line'], r['see_size']))

    n = len(rows)
    print('observers sampled: %d (seeds %d-%d, entries %d)' % (n, lo, hi, a.entries))
    print()
    print('%-5s %6s | %-24s | %-24s | %-24s' %
          ('bin', 'n', 'see_freq  c / t / d', 'see_line  c / t / d', 'see_size  c / t / d'))
    for b in ('LOW', 'MID', 'HIGH'):
        sel = [r for r in rows if binof(r[0]) == b]
        if not sel:
            print('%-5s %6d | (empty)' % (b, 0))
            continue
        out = ['%-5s %6d' % (b, len(sel))]
        for i, _ in enumerate(('freq', 'line', 'size'), start=1):
            ws = [bern(r[i]) for r in sel]
            m = [sum(w[j] for w in ws) / len(ws) for j in range(3)]
            av = sum(r[i] for r in sel) / len(sel)
            out.append('a=%.3f %.3f/%.3f/%.3f' % (av, m[0], m[1], m[2]))
        print(' | '.join(out))
    print()
    print('=== 같은 모집단을 **각 채널 자신의 a** 로 bin 했을 때 ===')
    print('%-5s %-6s %6s %8s %8s %8s' % ('bin', 'axis', 'n', 'coarse', 'trait', 'detail'))
    for i, nm in enumerate(('freq', 'line', 'size'), start=1):
        for b in ('LOW', 'MID', 'HIGH'):
            sel = [r for r in rows if binof(r[i]) == b]
            if not sel:
                print('%-5s %-6s %6d   (empty)' % (b, nm, 0))
                continue
            ws = [bern(r[i]) for r in sel]
            m = [sum(w[j] for w in ws) / len(ws) for j in range(3)]
            print('%-5s %-6s %6d %8.4f %8.4f %8.4f' % (b, nm, len(sel), m[0], m[1], m[2]))
    print()
    print('bin 축은 see_line 에 0.45, see_freq 에 0.30 만 준다. '
          'freq 채널을 detail_access bin 으로 자르면 a=see_freq 가 bin 안에서 넓게 퍼진다.')
    for i, nm in enumerate(('see_freq', 'see_line', 'see_size'), start=1):
        xs = [r[0] for r in rows]
        ys = [r[i] for r in rows]
        mx = sum(xs) / n
        my = sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        sx = sum((x - mx) ** 2 for x in xs) ** 0.5
        sy = sum((y - my) ** 2 for y in ys) ** 0.5
        print('  corr(detail_access, %-8s) = %.4f' % (nm, cov / (sx * sy)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
