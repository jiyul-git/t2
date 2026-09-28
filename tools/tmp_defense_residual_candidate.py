#!/usr/bin/env python3
"""8-max MTT ante direct-vs-open defense: compact semantic base + defender-specific
hand residual (shrunk). Shadow only — production code is not modified.

Data: public 8-max MTT preflop charts (matthiola0/poker-hand-review, pinned in
chatgpt/gto-reference-20260928:data/gto_public/8max_mtt_matthiola.jsonl).
Pass the path with --data.

Models compared (all evaluated on identical rows):
  current      test@1a23123 preflop.defend_action_likelihoods (neutral GTO_ISH profile)
  compact      10-bin defender-specific monotone curves on pct/tp (attack) and
               pct/tot (continue) + ridge semantic attack residual.
               Same recipe as tmp/preflop-policy-shape-20260928
               tools/tmp_defend_policy_compact_semantic.py (reproduction checked).
  cand_def     compact + defender-specific hand residual on BOTH attack and continue,
               shrunk:  r(def,hand) = sum(d) / (n + kappa)
               kappa_attack / kappa_continue picked by leave-one-train-stack-out CV.
  cand_def_k0  same with kappa = 0 (no shrinkage) — overfit reference.
  cand_node    diagnostic: residual keyed by (node, hand) instead of (defender, hand).
  cand_node_logit  diagnostic: cand_logit keyed by (node, hand); tests whether the
               remaining BB contradictions come from pooling openers under one defender.
  cand_logit   defender residual where the CONTINUE correction is applied in logit
               space: cont = sigmoid(logit(cont_base) + r_c), targets clipped to
               [eps, 1-eps]. eps and kappa_continue picked by the same train-stack CV;
               kappa_attack reused from cand_def. Added after cand_def showed that an
               additive constant cannot follow a stack-dependent base error on
               pure-fold hands (82o: compact error 0.19 at 10-20bb, 0.55 at >=30bb).

Train stacks 10/20/50bb, holdout 15/30/100bb (same split as the earlier experiments).
Nothing is tuned on holdout.

Semantic gates are fixed in code before looking at results (see GATES).
"""
import argparse
import bisect
import collections
import json
import math
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import preflop  # noqa: E402

PCT = json.loads((ROOT / 'pf_rank.json').read_text())
TRAIN = {10, 20, 50}
HOLD = {15, 30, 100}
DIRECT = {
    'EP-vs-MP': (['UTG', 'UTG+1', 'LJ'], 'CO'),
    'EP-vs-BTN': (['UTG', 'UTG+1', 'LJ'], 'BTN'),
    'EP-vs-SB': (['UTG', 'UTG+1', 'LJ'], 'SB'),
    'EP-vs-BB': (['UTG', 'UTG+1', 'LJ'], 'BB'),
    'MP-vs-BTN': (['HJ', 'CO'], 'BTN'),
    'MP-vs-SB': (['HJ', 'CO'], 'SB'),
    'MP-vs-BB': (['HJ', 'CO'], 'BB'),
    'BTN-vs-SB': (['BTN'], 'SB'),
    'BTN-vs-BB': (['BTN'], 'BB'),
    'SB-vs-BB': (['SB'], 'BB'),
}
PROF = {'concepts': {'pf_defend': 10.0},
        'temper': {'looseness': 5.0, 'aggression': 5.0, 'slowplay_taste': 5.0},
        'type': 'GTO_ISH'}
RV = {r: i + 2 for i, r in enumerate('23456789TJQKA')}
EDGES10 = [0.0, 0.35, 0.55, 0.75, 0.90, 1.00, 1.15, 1.35, 1.65, 2.20, float('inf')]
LAMBDAS = [100.0, 300.0, 1000.0, 3000.0, 10000.0]
KAPPAS = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 64.0,
          float('inf')]
DEFENDERS = ['BB', 'SB', 'BTN', 'CO']

# Gates, fixed before results. "pure" = source frequency at the boundary.
GATES = {
    'pure_fold': 'source fold >= 0.999; contradiction if predicted fold < 0.5',
    'pure_continue': 'source fold <= 0.001; contradiction if predicted fold >= 0.5',
    'rule': ('candidate is rejected if, on holdout, it has more pure-fold or '
             'pure-continue contradictions than current, OR its worst (defender,hand) '
             'Brier exceeds current\'s worst, OR any all-stack pure-fold hand '
             '(e.g. BB 82o) is predicted to continue >= 0.5 at any stack'),
}


def combos(h):
    return 6 if len(h) == 2 else (4 if h.endswith('s') else 12)


def cards(h):
    if len(h) == 2:
        return [h[0] + 's', h[1] + 'h']
    return [h[0] + 's', h[1] + ('s' if h[2] == 's' else 'h')]


def targ(r):
    a = float(r.get('raise', 0)) + float(r.get('allin', 0))
    c = float(r.get('call', 0))
    f = float(r.get('fold', 0))
    return a, c, f, a + c


def load_items(path):
    rows = [json.loads(x) for x in open(path) if x.strip()]
    groups = collections.defaultdict(list)
    for r in rows:
        if r.get('scenario') == 'vs-open' and r.get('node') in DIRECT:
            groups[(int(r['stack_bb']), r['node'])].append(r)
    items = []
    for (stack, node), rs in sorted(groups.items()):
        ops, hero = DIRECT[node]
        ob = 3.0 if node == 'SB-vs-BB' else 2.5
        for r in rs:
            h = r['hand']
            ta, tc, tf, tcont = targ(r)
            vals = [preflop.defend_action_likelihoods(
                PROF, hero, op, cards(h), stack, ob, 0, raise_level=1,
                stack_bb=stack, exploit=None, bf=1.0, seats=8, ante=True,
                opener_allin=False, can_raise=True) for op in ops]
            k = float(len(vals))
            tp = sum(float(v['tp']) for v in vals) / k
            tot = sum(float(v['tot']) for v in vals) / k
            items.append({
                'stack': stack, 'node': node, 'hero': hero, 'hand': h,
                'w': combos(h), 'r': PCT[h],
                'za': PCT[h] / max(tp, 1e-9), 'zc': PCT[h] / max(tot, 1e-9),
                'ta': ta, 'tc': tc, 'tf': tf, 'tcont': tcont,
                'ca': sum(float(v['attack']) for v in vals) / k,
                'cc': sum(float(v['call']) for v in vals) / k,
                'cf': sum(float(v['fold']) for v in vals) / k})
    return items


# ---------------- compact base (reproduces the earlier 10-bin recipe) --------------

def pava_bins(sumy, sumw):
    n = len(sumw)
    sumy, sumw = list(sumy), list(sumw)
    vals = [None] * n
    for i in range(n):
        if sumw[i] > 0:
            vals[i] = sumy[i] / sumw[i]
    for i in range(n):
        if vals[i] is None:
            j = min((j for j in range(n) if vals[j] is not None), key=lambda j: abs(j - i))
            vals[i] = vals[j]
            sumw[i] = 1e-6
            sumy[i] = vals[i] * 1e-6
    blocks = []
    for i in range(n):
        blocks.append({'lo': i, 'hi': i, 'w': sumw[i], 'wy': sumy[i],
                       'mean': sumy[i] / sumw[i]})
        while len(blocks) >= 2 and blocks[-2]['mean'] < blocks[-1]['mean'] - 1e-15:
            b = blocks.pop()
            a = blocks.pop()
            w = a['w'] + b['w']
            blocks.append({'lo': a['lo'], 'hi': b['hi'], 'w': w, 'wy': a['wy'] + b['wy'],
                           'mean': (a['wy'] + b['wy']) / w})
    out = [0.0] * n
    for b in blocks:
        for i in range(b['lo'], b['hi'] + 1):
            out[i] = b['mean']
    return out


def _bin(z):
    nb = len(EDGES10) - 1
    return max(0, min(nb - 1, bisect.bisect_right(EDGES10, z) - 1))


def fit_bins(items, stacks):
    nb = len(EDGES10) - 1
    models = {}
    for hero in DEFENDERS:
        sub = [x for x in items if x['stack'] in stacks and x['hero'] == hero]
        m = {}
        for axis, yk, zk in (('attack', 'ta', 'za'), ('continue', 'tcont', 'zc')):
            sy = [0.0] * nb
            sw = [0.0] * nb
            for x in sub:
                i = _bin(x[zk])
                sy[i] += x['w'] * x[yk]
                sw[i] += x['w']
            m[axis] = pava_bins(sy, sw)
        models[hero] = m
    return models


def feats(h):
    pair = len(h) == 2
    suited = len(h) == 3 and h[2] == 's'
    off = len(h) == 3 and h[2] == 'o'
    r1, r2 = RV[h[0]], RV[h[1]]
    hi, lo = max(r1, r2), min(r1, r2)
    gap = abs(r1 - r2)
    ace, king, queen = hi == 14, hi == 13, hi == 12
    broad = hi >= 10 and lo >= 10
    return [1.0, float(pair), float(pair) * (hi - 2) / 12, float(suited), float(off),
            float(ace), float(ace and suited), float(ace and off),
            float(suited and ace and lo <= 5), float(king), float(king and suited),
            float(queen), float(broad), float(broad and suited),
            float(suited and gap == 1), float(suited and gap == 2),
            float(suited and gap == 1 and hi <= 9), float(pair and hi <= 6),
            float(pair and 7 <= hi <= 11), float(pair and hi >= 12),
            (hi - 2) / 12, (lo - 2) / 12, min(gap, 12) / 12]


FN = ['bias', 'pair', 'pair_rank', 'suited', 'offsuit', 'ace', 'ace_suited',
      'ace_offsuit', 'wheel_ace_suited', 'king', 'king_suited', 'queen_high',
      'broadway', 'broadway_suited', 'suited_connector', 'suited_onegap',
      'low_suited_connector', 'small_pair', 'mid_pair', 'premium_pair', 'hi_rank',
      'lo_rank', 'gap']


def solve(A, b):
    n = len(b)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda i: abs(M[i][col]))
        if abs(M[piv][col]) < 1e-12:
            continue
        M[col], M[piv] = M[piv], M[col]
        q = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= q
        for i in range(n):
            if i == col:
                continue
            q = M[i][col]
            if abs(q) < 1e-15:
                continue
            for j in range(col, n + 1):
                M[i][j] -= q * M[col][j]
    return [M[i][n] for i in range(n)]


def base_pred(models, x):
    cont = models[x['hero']]['continue'][_bin(x['zc'])]
    a = min(models[x['hero']]['attack'][_bin(x['za'])], cont)
    return a, cont


def fit_ridge(items, models, stacks, lam):
    p = len(FN)
    A = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for x in items:
        if x['stack'] not in stacks:
            continue
        ba, _ = base_pred(models, x)
        v = feats(x['hand'])
        y = x['ta'] - ba
        w = x['w']
        for i in range(p):
            b[i] += w * v[i] * y
            for j in range(p):
                A[i][j] += w * v[i] * v[j]
    for i, n in enumerate(FN):
        A[i][i] += 0.0 if n == 'bias' else lam
    return solve(A, b)


def compact_pred(fit, x):
    a, cont = base_pred(fit['models'], x)
    a = max(0.0, min(cont, a + sum(q * v for q, v in zip(fit['beta'], feats(x['hand'])))))
    return a, cont


# ---------------- residual ----------------------------------------------------------

def rkey(level, x):
    return (x['hero'], x['hand']) if level == 'defender' else (x['node'], x['hand'])


def residual_sums(items, fit, stacks, level):
    """Per key: sum of attack residual, sum of continue residual, chart count."""
    S = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for x in items:
        if x['stack'] not in stacks:
            continue
        a, cont = compact_pred(fit, x)
        s = S[rkey(level, x)]
        s[0] += x['ta'] - a
        s[1] += x['tcont'] - cont
        s[2] += 1
    return dict(S)


def shrunk(S, key, ka, kc):
    s = S.get(key)
    if not s:
        return 0.0, 0.0
    n = s[2]
    ra = 0.0 if math.isinf(ka) else s[0] / (n + ka)
    rc = 0.0 if math.isinf(kc) else s[1] / (n + kc)
    return ra, rc


def cand_pred(fit, S, level, ka, kc, x):
    a, cont = compact_pred(fit, x)
    ra, rc = shrunk(S, rkey(level, x), ka, kc)
    cont = max(0.0, min(1.0, cont + rc))
    a = max(0.0, min(cont, a + ra))
    return a, cont


EPSILONS = [0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]


def _lg(p, eps):
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))


def residual_sums_logit(items, fit, stacks, eps, level='defender'):
    S = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for x in items:
        if x['stack'] not in stacks:
            continue
        a, cont = compact_pred(fit, x)
        s = S[rkey(level, x)]
        s[0] += x['ta'] - a
        s[1] += _lg(x['tcont'], eps) - _lg(cont, eps)
        s[2] += 1
    return dict(S)


def cand_pred_logit(fit, S, ka, kc, eps, x, level='defender'):
    a, cont = compact_pred(fit, x)
    ra, rc = shrunk(S, rkey(level, x), ka, kc)
    cont = 1.0 / (1.0 + math.exp(-(_lg(cont, eps) + rc)))
    a = max(0.0, min(cont, a + ra))
    return a, cont


def pick_logit(items, lam, ka, level='defender'):
    grid = []
    for eps in EPSILONS:
        folds = []
        for hs in sorted(TRAIN):
            tr = TRAIN - {hs}
            fit = fit_compact(items, tr, lam)
            Sl = residual_sums_logit(items, fit, tr, eps, level)
            folds.append((hs, fit, Sl))
        for kc in KAPPAS:
            b = am = 0.0
            for hs, fit, Sl in folds:
                s = score(items, lambda x: cand_pred_logit(fit, Sl, ka, kc, eps, x, level),
                          {hs})['all']
                b += s['action_brier']
                am += s['attack_mae']
            grid.append({'eps': eps, 'kappa_continue': kc,
                         'brier': b / len(folds), 'attack_mae': am / len(folds)})
    return min(grid, key=lambda g: (g['brier'], g['attack_mae'])), grid


def fit_compact(items, stacks, lam):
    models = fit_bins(items, stacks)
    return {'models': models, 'beta': fit_ridge(items, models, stacks, lam), 'lam': lam}


# ---------------- scoring -----------------------------------------------------------

def score(items, predict, stacks):
    acc = collections.defaultdict(float)
    by_def = collections.defaultdict(lambda: collections.defaultdict(float))
    cell = collections.defaultdict(lambda: collections.defaultdict(float))
    pure = collections.Counter()
    for x in items:
        if x['stack'] not in stacks:
            continue
        a, cont = predict(x)
        c = max(0.0, cont - a)
        f = max(0.0, 1.0 - cont)
        w = x['w']
        ea, ec, ef = (a - x['ta']) ** 2, (c - x['tc']) ** 2, (f - x['tf']) ** 2
        vals = {'w': w, 'attack_brier': w * ea, 'call_brier': w * ec,
                'fold_brier': w * ef, 'action_brier': w * (ea + ec + ef) / 3,
                'attack_mae': w * abs(a - x['ta']),
                'continue_mae': w * abs(cont - x['tcont'])}
        for k, v in vals.items():
            acc[k] += v
            by_def[x['hero']][k] += v
            cell[(x['hero'], x['hand'])][k] += v
        if x['tf'] >= 0.999:
            pure['pure_fold_n'] += 1
            if f < 0.5:
                pure['pure_fold_contra'] += 1
        if x['tf'] <= 0.001:
            pure['pure_cont_n'] += 1
            if f >= 0.5:
                pure['pure_cont_contra'] += 1

    def norm(d):
        return {k: d[k] / d['w'] for k in d if k != 'w'}
    return {'all': norm(acc), 'by_defender': {k: norm(by_def[k]) for k in DEFENDERS},
            'cells': {'%s|%s' % k: norm(v) for k, v in cell.items()},
            'pure': dict(pure)}


def pick_lambda(items):
    cv = []
    for lam in LAMBDAS:
        fs = []
        for hs in sorted(TRAIN):
            fit = fit_compact(items, TRAIN - {hs}, lam)
            fs.append(score(items, lambda x: compact_pred(fit, x), {hs})['all'])
        cv.append({'lambda': lam,
                   'brier': sum(f['action_brier'] for f in fs) / len(fs),
                   'attack_mae': sum(f['attack_mae'] for f in fs) / len(fs)})
    return min(cv, key=lambda c: (c['brier'], c['attack_mae'])), cv


def pick_kappa(items, lam, level):
    """Leave-one-train-stack-out CV over (kappa_attack, kappa_continue)."""
    folds = []
    for hs in sorted(TRAIN):
        tr = TRAIN - {hs}
        fit = fit_compact(items, tr, lam)
        folds.append((hs, fit, residual_sums(items, fit, tr, level)))
    grid = []
    for ka in KAPPAS:
        for kc in KAPPAS:
            b = am = 0.0
            for hs, fit, S in folds:
                s = score(items, lambda x: cand_pred(fit, S, level, ka, kc, x), {hs})['all']
                b += s['action_brier']
                am += s['attack_mae']
            grid.append({'kappa_attack': ka, 'kappa_continue': kc,
                         'brier': b / len(folds), 'attack_mae': am / len(folds)})
    best = min(grid, key=lambda g: (g['brier'], g['attack_mae']))
    return best, grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default=str(ROOT / 'data' / 'gto_public'))
    a = ap.parse_args()
    items = load_items(a.data)
    print('items', len(items), flush=True)

    best_lam, lam_cv = pick_lambda(items)
    lam = best_lam['lambda']
    fit = fit_compact(items, TRAIN, lam)
    print('lambda', lam, flush=True)

    kdef, kdef_grid = pick_kappa(items, lam, 'defender')
    print('kappa defender', kdef, flush=True)
    knode, knode_grid = pick_kappa(items, lam, 'node')
    print('kappa node', knode, flush=True)
    klog, klog_grid = pick_logit(items, lam, kdef['kappa_attack'])
    print('logit', klog, flush=True)
    S_log = residual_sums_logit(items, fit, TRAIN, klog['eps'])
    klogn, _ = pick_logit(items, lam, knode['kappa_attack'], 'node')
    print('logit node', klogn, flush=True)
    S_logn = residual_sums_logit(items, fit, TRAIN, klogn['eps'], 'node')
    S_def = residual_sums(items, fit, TRAIN, 'defender')
    S_node = residual_sums(items, fit, TRAIN, 'node')

    preds = {
        'current': lambda x: (x['ca'], x['ca'] + x['cc']),
        'compact': lambda x: compact_pred(fit, x),
        'cand_def': lambda x: cand_pred(fit, S_def, 'defender',
                                        kdef['kappa_attack'], kdef['kappa_continue'], x),
        'cand_def_k0': lambda x: cand_pred(fit, S_def, 'defender', 0.0, 0.0, x),
        'cand_node': lambda x: cand_pred(fit, S_node, 'node',
                                         knode['kappa_attack'], knode['kappa_continue'], x),
        'cand_logit': lambda x: cand_pred_logit(fit, S_log, kdef['kappa_attack'],
                                                klog['kappa_continue'], klog['eps'], x),
        'cand_node_logit': lambda x: cand_pred_logit(
            fit, S_logn, knode['kappa_attack'], klogn['kappa_continue'], klogn['eps'], x,
            'node'),
    }
    res = {m: {'train': score(items, p, TRAIN), 'holdout': score(items, p, HOLD)}
           for m, p in preds.items()}

    # all-stack pure hands per node (e.g. 82o): must be predicted fold at every stack
    by_nh = collections.defaultdict(list)
    for x in items:
        by_nh[(x['node'], x['hand'])].append(x)
    inv = {}
    for m, p in preds.items():
        contra = []
        for (node, h), xs in by_nh.items():
            if len(xs) == 6 and all(x['tf'] >= 0.999 for x in xs):
                worst = max(p(x)[1] for x in xs)
                if worst >= 0.5:
                    contra.append({'node': node, 'hand': h, 'max_continue': worst})
        inv[m] = contra
    n_allpure = sum(1 for xs in by_nh.values()
                    if len(xs) == 6 and all(x['tf'] >= 0.999 for x in xs))

    # 82o direct check at every node / stack
    check82 = []
    for x in items:
        if x['hand'] == '82o':
            row = {'node': x['node'], 'stack': x['stack'],
                   'source': [x['ta'], x['tc'], x['tf']]}
            for m, p in preds.items():
                aa, cc = p(x)
                row[m] = [round(aa, 4), round(max(0.0, cc - aa), 4), round(1 - cc, 4)]
            check82.append(row)

    # worst 30 (defender, hand) cells on holdout, per model
    worst = {}
    for m in preds:
        cells = res[m]['holdout']['cells']
        worst[m] = sorted(({'cell': k, **v} for k, v in cells.items()),
                          key=lambda c: -c['action_brier'])[:30]

    # hand-level movement vs current on holdout
    move = {}
    cur_cells = res['current']['holdout']['cells']
    for m in preds:
        if m == 'current':
            continue
        cells = res[m]['holdout']['cells']
        better = sum(1 for k in cells if cells[k]['action_brier'] < cur_cells[k]['action_brier'] - 1e-12)
        worse = sum(1 for k in cells if cells[k]['action_brier'] > cur_cells[k]['action_brier'] + 1e-12)
        dl = sorted(((cells[k]['action_brier'] - cur_cells[k]['action_brier'], k) for k in cells),
                    reverse=True)
        move[m] = {'better': better, 'worse': worse, 'same': len(cells) - better - worse,
                   'worst_worsening': [{'cell': k, 'delta': d} for d, k in dl[:10]]}

    # residual table (defender) with shrink applied
    ka, kc = kdef['kappa_attack'], kdef['kappa_continue']
    rtab = []
    for key, s in S_def.items():
        ra, rc = shrunk(S_def, key, ka, kc)
        rtab.append({'defender': key[0], 'hand': key[1], 'n': s[2],
                     'raw_attack': s[0] / s[2], 'raw_continue': s[1] / s[2],
                     'attack': ra, 'continue': rc})
    rtab.sort(key=lambda r: -(abs(r['attack']) + abs(r['continue'])))

    # residual sign stability across train stacks (defender level)
    stab = collections.defaultdict(dict)
    for s in sorted(TRAIN):
        Ss = residual_sums(items, fit, {s}, 'defender')
        for k, v in Ss.items():
            stab[k][s] = (v[0] / v[2], v[1] / v[2])
    def same_sign(vals):
        return all(v >= 0 for v in vals) or all(v <= 0 for v in vals)
    top = rtab[:50]
    stab_a = sum(same_sign([stab[(r['defender'], r['hand'])][s][0] for s in sorted(TRAIN)])
                 for r in top) / len(top)
    stab_c = sum(same_sign([stab[(r['defender'], r['hand'])][s][1] for s in sorted(TRAIN)])
                 for r in top) / len(top)

    # gate evaluation
    gates = {}
    cw = max(c['action_brier'] for c in res['current']['holdout']['cells'].values())
    cp = res['current']['holdout']['pure']
    for m in preds:
        if m == 'current':
            continue
        hp = res[m]['holdout']['pure']
        mw = max(c['action_brier'] for c in res[m]['holdout']['cells'].values())
        g = {
            'pure_fold_contra': [hp.get('pure_fold_contra', 0), cp.get('pure_fold_contra', 0)],
            'pure_cont_contra': [hp.get('pure_cont_contra', 0), cp.get('pure_cont_contra', 0)],
            'worst_cell_brier': [mw, cw],
            'allstack_pure_fold_contra': len(inv[m]),
        }
        g['pass'] = (g['pure_fold_contra'][0] <= g['pure_fold_contra'][1]
                     and g['pure_cont_contra'][0] <= g['pure_cont_contra'][1]
                     and mw <= cw and len(inv[m]) == 0)
        gates[m] = g

    params = {
        'edges': [None if math.isinf(e) else e for e in EDGES10],
        'curves': fit['models'], 'lambda': lam,
        'beta': dict(zip(FN, fit['beta'])),
        'kappa_attack': kdef['kappa_attack'], 'kappa_continue': kdef['kappa_continue'],
        'residual': {'%s|%s' % (r['defender'], r['hand']): [r['attack'], r['continue']]
                     for r in rtab},
        'logit_eps': klog['eps'], 'logit_kappa_continue': klog['kappa_continue'],
        'logit_residual': {'%s|%s' % k: list(shrunk(S_log, k, kdef['kappa_attack'],
                                                    klog['kappa_continue']))
                           for k in S_log},
        'node_logit_eps': klogn['eps'],
        'node_logit_kappa': [knode['kappa_attack'], klogn['kappa_continue']],
        'node_logit_residual': {'%s|%s' % k: list(shrunk(S_logn, k, knode['kappa_attack'],
                                                         klogn['kappa_continue']))
                                for k in S_logn},
        'node_kappa': [knode['kappa_attack'], knode['kappa_continue']],
        'node_residual': {'%s|%s' % k: list(shrunk(S_node, k, knode['kappa_attack'],
                                                   knode['kappa_continue']))
                          for k in S_node},
    }
    out = {
        'scope': 'shadow only; production untouched',
        'train_stacks': sorted(TRAIN), 'holdout_stacks': sorted(HOLD),
        'gates': GATES, 'lambda_cv': lam_cv,
        'kappa_defender': kdef, 'kappa_node': knode, 'logit_cv': klog,
        'node_logit_cv': klogn,
        'kappa_defender_grid': kdef_grid,
        'results': {m: {'train': {k: v for k, v in r['train'].items() if k != 'cells'},
                        'holdout': {k: v for k, v in r['holdout'].items() if k != 'cells'}}
                    for m, r in res.items()},
        'holdout_cells': {m: r['holdout']['cells'] for m, r in res.items()},
        'allstack_pure_fold_hands': n_allpure,
        'allstack_pure_fold_contra': inv,
        'check_82o': check82, 'worst30_holdout': worst, 'move_vs_current': move,
        'gate_eval': gates,
        'residual_top50': rtab[:50],
        'residual_stability_top50': {'attack_same_sign': stab_a,
                                     'continue_same_sign': stab_c},
        'params': params,
    }
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, 'defense_residual_candidate_20260928.json')
    json.dump(out, open(p, 'w'), indent=1, sort_keys=True)
    print('wrote', p)
    for m in preds:
        h = res[m]['holdout']['all']
        print('%-12s holdout brier %.5f  A %.5f C %.5f F %.5f  aMAE %.5f cMAE %.5f  pure %s'
              % (m, h['action_brier'], h['attack_brier'], h['call_brier'], h['fold_brier'],
                 h['attack_mae'], h['continue_mae'], res[m]['holdout']['pure']))
    print('gates', json.dumps(gates))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
