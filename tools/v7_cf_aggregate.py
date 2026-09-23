#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V7 반사실 집계. 읽기 전용. V7_CF_JSON 줄을 모아 구간별로 합친다."""
from __future__ import print_function

import argparse
import glob
import json
import sys

NB = ('n<6', '6-11', '12-29', 'n>=30')


def load(pat):
    recs = []
    for p in sorted(glob.glob(pat)):
        for line in open(p, encoding='utf-8'):
            if line.startswith('V7_CF_JSON='):
                recs.append(json.loads(line.split('=', 1)[1]))
    return recs


def report(recs, label):
    print('=== %s : %d seeds ===' % (label, len(recs)))
    print('%-8s %-18s %-18s %5s %5s %6s %6s %6s %s'
          % ('seed', 'control', 'v7', 'dH', 'dE', 'indep', 'chain', 'preD',
             'first_divergence'))
    tot = dict(dH=0, dE=0, ind=0, chain=0, err=0, indh=0)
    for r in sorted(recs, key=lambda x: x['seed']):
        print('%-8s %-18s %-18s %5d %5d %6d %6d %6s %s'
              % (r['seed'], r['control_hash'], r['v7_hash'], r['diff_hands'],
                 r['diff_entries'], r['independent_entries'],
                 r['chain_entries'], r['pre_state_first_diff_hand'],
                 json.dumps(r['first_diff']) if r['first_diff'] else '-'))
        tot['dH'] += r['diff_hands']; tot['dE'] += r['diff_entries']
        tot['ind'] += r['independent_entries']; tot['chain'] += r['chain_entries']
        tot['err'] += r['engine_errors']; tot['indh'] += len(r['independent_hands'])
    print('TOTAL diff_hands=%d diff_entries=%d  independent: %d hands / %d entries'
          '  chain: %d entries  engine_errors=%d'
          % (tot['dH'], tot['dE'], tot['indh'], tot['ind'], tot['chain'], tot['err']))

    agg = {str(t): {'calls': 0, 'wpos': 0, 'sw': 0.0, 'ss': 0.0, 'sd': 0.0,
                    'sm': 0.0, 'bn': [{'calls': 0, 'sd': 0.0, 'sm': 0.0}
                                      for _ in NB]}
           for t in range(1, 6)}
    for r in recs:
        for t, st in r['tier_stats'].items():
            a = agg[t]
            a['calls'] += st['calls']; a['wpos'] += st['w_positive']
            a['sw'] += st['sum_w']; a['ss'] += st['sum_s']
            a['sd'] += st['sum_data']; a['sm'] += st['sum_mag']
            for i, b in enumerate(st['by_n']):
                a['bn'][i]['calls'] += b['calls']
                a['bn'][i]['sd'] += b['sum_data']
                a['bn'][i]['sm'] += b['sum_mag']
    total = sum(agg[str(t)]['calls'] for t in range(1, 6))
    print('\n%-3s %-22s %8s %7s %7s %7s %7s %9s'
          % ('#', 'tier', 'calls', 'share', 'w>0%', 'mean_s', 'mean_w', 'mean|ch|'))
    names = ['NO_EXPLOIT', 'IMPRESSION', 'STYLE_EXPLOIT', 'QUALITATIVE_REG',
             'QUANTITATIVE_EXPERT']
    for t in range(1, 6):
        a = agg[str(t)]
        c = a['calls'] or 1
        print('%-3d %-22s %8d %6.2f%% %6.1f%% %7.4f %7.4f %9.4f'
              % (t, names[t - 1], a['calls'], 100.0 * a['calls'] / max(1, total),
                 100.0 * a['wpos'] / c, a['ss'] / c, a['sw'] / c, a['sm'] / c))
    print('\n증거 비중(data)과 채널 크기의 n 의존 — 4·5단계')
    print('%-3s %-10s %8s %9s %9s' % ('#', 'n bucket', 'calls', 'mean_data', 'mean|ch|'))
    for t in (4, 5):
        for i, nb in enumerate(NB):
            b = agg[str(t)]['bn'][i]
            if not b['calls']:
                print('%-3d %-10s %8d %9s %9s' % (t, nb, 0, '-', '-'))
                continue
            print('%-3d %-10s %8d %9.4f %9.4f'
                  % (t, nb, b['calls'], b['sd'] / b['calls'], b['sm'] / b['calls']))
    print()
    return agg, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--main', required=True)
    ap.add_argument('--supp')
    a = ap.parse_args()
    report(load(a.main), 'MAIN (preregistered, entries 100)')
    if a.supp:
        report(load(a.supp), 'SUPPLEMENTARY (entries 400, tier-5 coverage)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
