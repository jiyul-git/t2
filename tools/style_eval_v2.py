#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STYLE_CALIB_V2 holdout 평가 — 동결 파라미터로 안정성·예측력·게이트를 잰다.

사전등록: STYLE_CALIB_V2_PREREG.md 4절.
덤프는 중심/스케일에 의존하지 않으므로 같은 덤프로 V1 과 V2 를 나란히 잰다.
게이트 기준은 V2 이고 V1 수치는 참고다. 이 도구는 파라미터를 수정하지 않는다.
"""
from __future__ import print_function

import argparse
import glob
import json
import math
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import style_params_v2 as SP

NAMES = SP.NAMES
CUTS = (10, 20, 30, 40)
MIN_BELIEF_HANDS = 4
MIN_FUTURE_HANDS = 6


def eval_dump(d, par):
    centers, scales, pop = par['centers'], par['scales'], par['pop']
    per_cut = {}
    post = {}          # cut -> key -> posterior
    for cut in CUTS:
        certs, ents = [], []
        tops = Counter()
        pc = {}
        for pr in d['pairs']:
            b = pr['belief'].get(str(cut))
            if not b or int(b.get('hands', 0)) < MIN_BELIEF_HANDS:
                continue
            po = SP.posterior(b['L'], b['A'], b['X'], b['q'], centers, scales)
            pc[pr['key']] = po
            certs.append(po['certainty'])
            ents.append(po['entropy'])
            tops[po['top']] += 1
        post[cut] = pc
        per_cut[str(cut)] = {
            'pairs': len(pc),
            'mean_certainty': (sum(certs) / len(certs)) if certs else 0.0,
            'mean_entropy': (sum(ents) / len(ents)) if ents else 0.0,
            'top_counts': {n: tops.get(n, 0) for n in NAMES},
        }

    flips = {}
    for a, b in ((10, 20), (20, 30), (30, 40)):
        aa, bb = post.get(a, {}), post.get(b, {})
        ks = sorted(set(aa) & set(bb))
        nf = sum(1 for k in ks if aa[k]['top'] != bb[k]['top'])
        flips['%d-%d' % (a, b)] = {
            'pairs': len(ks), 'flips': nf, 'rate': nf / float(max(1, len(ks))),
            'mean_cert_delta': ((sum(bb[k]['certainty'] - aa[k]['certainty'] for k in ks) / len(ks))
                                if ks else 0.0),
            'mean_entropy_delta': ((sum(bb[k]['entropy'] - aa[k]['entropy'] for k in ks) / len(ks))
                                   if ks else 0.0),
        }

    ss = {'style': 0.0, 'population': 0.0, 'direct': 0.0, 'population_v1const': 0.0}
    n_pred = 0
    fut_top = Counter()
    by_key = {pr['key']: pr for pr in d['pairs']}
    for key, po in post.get(20, {}).items():
        pr = by_key[key]
        w2 = pr['raw'].get('w2')
        if not w2 or int(w2.get('hands', 0)) < MIN_FUTURE_HANDS:
            continue
        actual = (w2['L'], w2['A'], w2['X'])
        b = pr['belief']['20']
        ss['style'] += SP.sqerr(SP.weighted_center(po['probs'], centers), actual)
        ss['population'] += SP.sqerr(pop, actual)
        ss['direct'] += SP.sqerr((b['L'], b['A'], b['X']), actual)
        ss['population_v1const'] += SP.sqerr(SP.V1_POP, actual)
        n_pred += 1
        fut_top[SP.posterior(w2['L'], w2['A'], w2['X'], 1.0, centers, scales)['top']] += 1

    return {'seed': d['seed'], 'engine_errors': d.get('engine_errors', 0),
            'cuts': per_cut, 'flips': flips, 'ss': ss, 'n_pred': n_pred,
            'future_top_counts': {n: fut_top.get(n, 0) for n in NAMES}}


def pool(rows):
    ss = {k: 0.0 for k in ('style', 'population', 'direct', 'population_v1const')}
    n = 0
    for r in rows:
        for k in ss:
            ss[k] += r['ss'][k]
        n += r['n_pred']
    rm = {k: math.sqrt(v / max(1, n)) for k, v in ss.items()}
    g1 = bool(n and rm['style'] <= 0.90 * rm['population'])
    g2 = bool(n and rm['style'] <= 1.10 * rm['direct'])
    return {
        'pairs': n, 'rmse': rm,
        'style_over_population': (rm['style'] / rm['population']) if rm['population'] else None,
        'style_over_direct': (rm['style'] / rm['direct']) if rm['direct'] else None,
        'style_over_population_v1const': (rm['style'] / rm['population_v1const'])
                                         if rm['population_v1const'] else None,
        'G1_pass_vs_population_0p90': g1,
        'G2_pass_vs_direct_1p10': g2,
        'both_pass': bool(g1 and g2),
    }


def merge_cuts(rows):
    out = {}
    for cut in CUTS:
        tot = 0
        cs = es = 0.0
        tops = Counter()
        for r in rows:
            c = r['cuts'][str(cut)]
            tot += c['pairs']
            cs += c['mean_certainty'] * c['pairs']
            es += c['mean_entropy'] * c['pairs']
            for n in NAMES:
                tops[n] += c['top_counts'][n]
        out[str(cut)] = {'pairs': tot,
                         'mean_certainty': cs / max(1, tot),
                         'mean_entropy': es / max(1, tot),
                         'top_counts': {n: tops[n] for n in NAMES}}
    return out


def merge_flips(rows):
    out = {}
    for k in ('10-20', '20-30', '30-40'):
        p = f = 0
        for r in rows:
            p += r['flips'][k]['pairs']
            f += r['flips'][k]['flips']
        out[k] = {'pairs': p, 'flips': f, 'rate': f / float(max(1, p))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dumps', nargs='+', required=True)
    ap.add_argument('--params', required=True)
    ap.add_argument('--label', default='holdout')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    paths = []
    for g in a.dumps:
        paths.extend(glob.glob(g) if any(ch in g for ch in '*?[') else [g])
    dumps, invalid = [], []
    for p in sorted(paths):
        with open(p, encoding='utf-8') as fh:
            d = json.load(fh)
        (invalid if d.get('engine_errors') else dumps).append(d)

    par_v2 = SP.load_params(a.params)
    par_v1 = SP.v1_params()
    res = {'label': a.label, 'params_version': par_v2['version'],
           'n_seeds': len(dumps), 'seeds': sorted(x['seed'] for x in dumps),
           'invalid_seeds': sorted(x['seed'] for x in invalid)}
    for tag, par in (('V2', par_v2), ('V1', par_v1)):
        rows = [eval_dump(d, par) for d in dumps]
        res[tag] = {
            'cuts': merge_cuts(rows),
            'flips': merge_flips(rows),
            'prediction': pool(rows),
            'future_top_counts': {n: sum(r['future_top_counts'][n] for r in rows)
                                  for n in NAMES},
            'per_seed_gate': {str(r['seed']): pool([r]) for r in rows},
        }
    with open(a.out, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, sort_keys=True)

    for tag in ('V2', 'V1'):
        pr = res[tag]['prediction']
        ns = sum(1 for v in res[tag]['per_seed_gate'].values() if v['both_pass'])
        print('[%s %s] pairs=%d  style=%.5f pop=%.5f direct=%.5f  '
              'ratio_pop=%.5f ratio_direct=%.5f  G1=%s G2=%s  per-seed both=%d/%d'
              % (a.label, tag, pr['pairs'], pr['rmse']['style'], pr['rmse']['population'],
                 pr['rmse']['direct'], pr['style_over_population'], pr['style_over_direct'],
                 pr['G1_pass_vs_population_0p90'], pr['G2_pass_vs_direct_1p10'],
                 ns, len(res[tag]['per_seed_gate'])))
    print('cuts(V2):', json.dumps(res['V2']['cuts']['40'], ensure_ascii=False))
    if invalid:
        print('INVALID seeds excluded: %s' % res['invalid_seeds'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
