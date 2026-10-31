#!/usr/bin/env python3
"""Threshold variant (2026-10-30 size-approx experiment): only anchor data is used.
Fold share F(x) linear through the two anchors (x = price or bb); hand classes are ranked by the second anchor's
EV(best continue) - EV(fold); the weakest classes fold until F is reached (one class partly); continuing classes keep the second anchor's
continue mix renormalised. Compared with the computed held-out size (combo-weighted TV distance per class).
    python3 tools/gto_spot/size_approx_threshold.py <out.json> <label>:<size_a>:<rec_a>:<size_b>:<rec_b>:<size_test>:<rec_test> ..."""
import json
import sys

from size_approx_fit import GROUPS, group, price, root


def margins(path):
    d = json.load(open(path))
    n = [x for x in d['nodes'] if x['actor'] == 'BB' and len(x['path']) == 8][0]
    return {h: max(e for a, e in v['ev_bb'].items() if a != 'Fold') - v['ev_bb']['Fold'] for h, v in n['hands'].items()}


def run(sa, ra, sb, rb, st, rt):
    A, B, T = root(ra)[0], root(rb)[0], root(rt)[0]
    m = margins(rb)
    W = sum(v[0] for v in T.values())
    fs = lambda R: sum(v[0] * v[1]['fold'] for v in R.values()) / W
    fa, fb, ft = fs(A), fs(B), fs(T)
    out = {'fold_share': {'a': fa, 'b': fb, 'test': ft}}
    for model, xs in (('price', (price(sa), price(sb), price(st))), ('bb', (sa, sb, st))):
        F = min(1.0, max(0.0, fb + (fb - fa) * (xs[2] - xs[1]) / (xs[1] - xs[0])))
        left, pred = F * W, {}
        for h in sorted(B, key=lambda h: m[h]):
            w, g, _ = B[h]
            f = min(1.0, max(0.0, left / w)); left -= f * w
            cont = {k: g[k] for k in GROUPS if k != 'fold'}; s = sum(cont.values())
            if s <= 0:
                cont = {'call': 1.0, '3bet': 0.0, 'jam': 0.0}; s = 1.0
            pred[h] = {'fold': f, **{k: (1 - f) * v / s for k, v in cont.items()}}
        tv = {h: 0.5 * sum(abs(pred[h][k] - T[h][1][k]) for k in GROUPS) for h in T}
        worst = sorted(tv, key=lambda h: -tv[h])
        out[model] = {'fold_share_pred': F, 'tv_mean_combo_weighted': sum(T[h][0] * tv[h] for h in T) / W, 'tv_max': tv[worst[0]],
                      'classes_tv_over_0.10': sum(v > 0.10 for v in tv.values()), 'classes_tv_over_0.25': sum(v > 0.25 for v in tv.values()),
                      'abs_err_mean_by_action': {k: sum(T[h][0] * abs(pred[h][k] - T[h][1][k]) for h in T) / W for k in GROUPS},
                      'aggregate_pred': {k: sum(T[h][0] * pred[h][k] for h in T) / W for k in GROUPS},
                      'worst': [(h, round(tv[h], 3), {k: round(T[h][1][k], 2) for k in GROUPS}) for h in worst[:10]]}
    return out


if __name__ == '__main__':
    res = {}
    for arg in sys.argv[2:]:
        lab, sa, ra, sb, rb, st, rt = arg.split(':')
        res[lab] = r = run(float(sa), ra, float(sb), rb, float(st), rt)
        print(lab, {k: round(v, 3) for k, v in r['fold_share'].items()})
        for mo in ('price', 'bb'):
            x = r[mo]; print(' ', mo, 'F', round(x['fold_share_pred'], 3), 'tv mean', round(x['tv_mean_combo_weighted'], 3), 'max', round(x['tv_max'], 2),
                             '>0.10', x['classes_tv_over_0.10'], '>0.25', x['classes_tv_over_0.25'], {k: round(v, 3) for k, v in x['aggregate_pred'].items()})
            print('   worst', x['worst'][:6])
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
