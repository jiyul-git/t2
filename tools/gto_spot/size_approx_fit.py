#!/usr/bin/env python3
"""Open-size approximation test (2026-10-30): BB defence vs one open, fitted from two anchor open sizes, checked on a held-out size.
Per hand class and action group (fold / call / 3-bet / jam): linear in x through the two anchors, clipped to [0, 1], renormalised.
x = 'price' (BB required equity call / (pot + call), pot incl. blinds + ante) or 'bb' (open size); 'clamp' = nearest anchor unchanged.
    python3 tools/gto_spot/size_approx_fit.py <out.json> <label>:<size_a>:<rec_a>:<size_b>:<rec_b>:<size_test>:<rec_test> ...
"""
import json
import sys

ANTE_TOTAL = 1.0          # 9 x 1/9
GROUPS = ('fold', 'call', '3bet', 'jam')


def price(o):
    call = o - 1.0
    return call / (o + 0.5 + 1.0 + ANTE_TOTAL + call)


def group(a):
    if a == 'Fold':
        return 'fold'
    if a.startswith('Call'):
        return 'call'
    if a.startswith('3-bet'):
        return '3bet'
    if a.startswith('All-in'):
        return 'jam'
    raise ValueError(a)


def root(path):
    d = json.load(open(path))
    n = [x for x in d['nodes'] if x['actor'] == 'BB' and len(x['path']) == 8]
    assert len(n) == 1, path
    out = {}
    for h, v in n[0]['hands'].items():
        g = dict.fromkeys(GROUPS, 0.0)
        for a, f in v['freq'].items():
            g[group(a)] += f
        out[h] = (v['combos'], g, v.get('unstable_across_steps', False))
    return out, d['id'], d['method'], d.get('final_step'), d.get('stopped_at_step_cap')


def predict(ga, gb, xa, xb, xt):
    p = {k: min(1.0, max(0.0, ga[k] + (gb[k] - ga[k]) * (xt - xa) / (xb - xa))) for k in GROUPS}
    s = sum(p.values())
    return {k: v / s for k, v in p.items()} if s > 0 else dict(gb)


def compare(A, B, T, sa, sb, st):
    xs = {'price': (price(sa), price(sb), price(st)), 'bb': (sa, sb, st)}
    res = {}
    for model in ('price', 'bb', 'clamp'):
        rows, agg_p, agg_t, wsum = [], dict.fromkeys(GROUPS, 0.0), dict.fromkeys(GROUPS, 0.0), 0.0
        for h, (w, gt, unst) in T.items():
            ga, gb = A[h][1], B[h][1]
            gp = dict(gb) if model == 'clamp' else predict(ga, gb, *xs[model])
            err = {k: abs(gp[k] - gt[k]) for k in GROUPS}
            tv = 0.5 * sum(err.values())
            rows.append({'hand': h, 'combos': w, 'tv': tv, 'err': err, 'pred': gp, 'test': gt, 'a': ga, 'b': gb, 'unstable_test': unst})
            for k in GROUPS:
                agg_p[k] += w * gp[k]; agg_t[k] += w * gt[k]
            wsum += w
        rows.sort(key=lambda r: -r['tv'])
        res[model] = {
            'tv_mean_combo_weighted': sum(r['combos'] * r['tv'] for r in rows) / wsum,
            'tv_max': rows[0]['tv'], 'tv_max_hand': rows[0]['hand'],
            'abs_err_mean_by_action': {k: sum(r['combos'] * r['err'][k] for r in rows) / wsum for k in GROUPS},
            'abs_err_max_by_action': {k: max(r['err'][k] for r in rows) for k in GROUPS},
            'classes_tv_over_0.10': sum(r['tv'] > 0.10 for r in rows), 'classes_tv_over_0.25': sum(r['tv'] > 0.25 for r in rows),
            'aggregate_pred': {k: v / wsum for k, v in agg_p.items()}, 'aggregate_test': {k: v / wsum for k, v in agg_t.items()},
            'worst': [{k: (round(v, 4) if isinstance(v, float) else ({a: round(b, 3) for a, b in v.items()} if isinstance(v, dict) else v))
                       for k, v in r.items()} for r in rows[:12]],
        }
    # boundary / bend flags: the class's dominant action changes between anchors or between the second anchor and the test size
    dom = lambda g: max(GROUPS, key=lambda k: g[k])
    flags = []
    for h, (w, gt, unst) in T.items():
        ga, gb = A[h][1], B[h][1]
        if len({dom(ga), dom(gb), dom(gt)}) > 1 or max(abs(gb[k] - ga[k]) for k in GROUPS) > 0.1 and \
                any((gb[k] - ga[k]) * (gt[k] - gb[k]) < -1e-3 for k in GROUPS):
            flags.append({'hand': h, 'combos': w, 'dominant': [dom(ga), dom(gb), dom(gt)], 'unstable_test': unst})
    res['boundary_flags'] = flags
    res['x'] = {m: [round(v, 4) for v in xs[m]] for m in xs}
    return res


def main():
    out = {'schema': 'size_approx_experiment_v1', 'model': 'per class x action group, linear through 2 anchors, clip [0,1], renormalise',
           'price_def': 'BB required equity = (open - 1) / (open + 0.5 + 1 + 1 ante + open - 1)', 'spots': {}}
    for arg in sys.argv[2:]:
        lab, sa, ra, sb, rb, st, rt = arg.split(':')
        A, B, T = root(ra), root(rb), root(rt)
        r = compare(A[0], B[0], T[0], float(sa), float(sb), float(st))
        r['records'] = {s: {'id': x[1], 'method': x[2], 'final_step': x[3], 'stopped_at_step_cap': x[4]} for s, x in ((sa, A), (sb, B), (st, T))}
        out['spots'][lab] = r
        print(lab, {m: (round(r[m]['tv_mean_combo_weighted'], 4), round(r[m]['tv_max'], 3), r[m]['tv_max_hand']) for m in ('price', 'bb', 'clamp')})
        for m in ('price', 'bb', 'clamp'):
            print(' ', m, 'pred', {k: round(v, 3) for k, v in r[m]['aggregate_pred'].items()}, 'test', {k: round(v, 3) for k, v in r[m]['aggregate_test'].items()})
        print('  flags', len(r['boundary_flags']))
    json.dump(out, open(sys.argv[1], 'w'), indent=1)


if __name__ == '__main__':
    main()
