"""Effective-stack approximation error (T2 request 2026-10-26): asymmetric stacks vs the symmetric table T2 picks.
Chip-EV jam/fold game of icm_pushfold.py (first caller only, no flop, ante 1 bb total over 9 seats, folded seats leave dead money).
Asymmetric solution = Nash of the actual stack vector. Approximation = for every decision node, the strategy of the symmetric game
(all active seats at stack X) where X comes from a rule; the loss is measured against the asymmetric equilibrium of the others
(unilateral deviation at that node only), in bb conditional on reaching the node (average over the actor's 169 classes, combo weighted).
Rules: R1 (T2) first-in X = min(own, max stack behind); facing a jam X = min(own, jammer).  R2 first-in X = min(own, min stack behind).
R3 first-in X = expected min(own, first caller's stack) with the asymmetric first-caller probabilities (calls: as R1).
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import icm_pushfold as ip

SEATS9 = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
W, L = ip.W, ip.LABELS


class DeadGame(ip.Game):
    """chip-EV game among n active seats; the 9-n folded seats contribute their ante as dead money."""
    def __init__(self, stacks):
        self.n = n = len(stacks); self.s = np.array(stacks, float); self.mode = 'chip'
        self.dead = (9 - n) / 9.0
        blind = np.zeros(n); blind[n - 2] = 0.5; blind[n - 1] = 1.0
        self.post = 1.0 / 9 + blind
        self._f = lambda c: np.array(c, float); self._cache = {}
        self.steal = [self.val(self.chips_steal(m)) for m in range(n)]
        self.call = {}
        for m in range(n - 1):
            for j in range(m + 1, n):
                self.call[(m, j)] = (self.val(self.chips_call(m, j, True)), self.val(self.chips_call(m, j, False)))

    def chips_steal(self, m):
        c = self.s - self.post
        c[m] = self.s[m] + self.post.sum() + self.dead - self.post[m]
        return c

    def chips_call(self, m, j, m_wins):
        e = min(self.s[m], self.s[j])
        pot = 2 * e + self.post.sum() + self.dead - self.post[m] - self.post[j]
        c = self.s - self.post
        c[m] = self.s[m] - e; c[j] = self.s[j] - e
        c[m if m_wins else j] += pot
        return c


_cache = {}
def sym(n, x):
    k = (n, round(float(x), 4))
    if k not in _cache:
        P, C, gap, it = ip.solve(DeadGame([x] * n), iters=30000, tol=0.010)
        _cache[k] = (P, C, gap)
    return _cache[k]


def first_caller_probs(g, P, C, m):
    cr = {k: float(W @ v) for k, v in C.items()}
    out = {}; p = 1.0
    for k in range(m + 1, g.n):
        out[k] = p * cr[(m, k)]; p *= 1 - cr[(m, k)]
    return out


def run(name, seats, stacks):
    n = len(stacks)
    g = DeadGame(stacks)
    P, C, gap, it = ip.solve(g, iters=30000, tol=0.010)
    Uj, Uf, Uc, Ufc, rf, rfc = ip.evaluate(g, P, C)
    res = {'name': name, 'seats': seats, 'stacks': stacks, 'gap': gap, 'rules': {}}
    for rule in ('R1', 'R2', 'R3'):
        nodes = []
        for i in range(n - 1):
            behind = stacks[i + 1:]
            if rule == 'R1': X = min(stacks[i], max(behind))
            elif rule == 'R2': X = min(stacks[i], min(behind))
            else:
                fc = first_caller_probs(g, P, C, i); tot = sum(fc.values())
                X = sum(w * min(stacks[i], stacks[k]) for k, w in fc.items()) / tot if tot > 1e-9 else min(stacks[i], max(behind))
            Pa = sym(n, X)[0][i]
            diff = np.abs(Pa - P[i]); loss = float(W @ (np.maximum(Uj[i], Uf[i]) - (Pa * Uj[i] + (1 - Pa) * Uf[i])))
            flips = [L[h] for h in range(169) if (Pa[h] >= .5) != (P[i][h] >= .5)]
            nodes.append({'node': f'{seats[i]} first-in', 'stack': stacks[i], 'X': round(X, 2), 'jam_asym': round(100 * float(W @ P[i]), 1),
                          'jam_approx': round(100 * float(W @ Pa), 1), 'mean_abs_diff_pct': round(100 * float(W @ diff), 2),
                          'flips': flips, 'loss_bb': round(loss, 4), 'reach': round(float(rf[i]), 4)})
        for (m, j), Ca_asym in C.items():
            X = min(stacks[m], stacks[j])   # all rules: min(own, jammer)
            Ca = sym(n, X)[1][(m, j)]
            diff = np.abs(Ca - Ca_asym); loss = float(W @ (np.maximum(Uc[(m, j)], Ufc[(m, j)]) - (Ca * Uc[(m, j)] + (1 - Ca) * Ufc[(m, j)])))
            flips = [L[h] for h in range(169) if (Ca[h] >= .5) != (Ca_asym[h] >= .5)]
            if rfc[(m, j)] < 1e-4: continue
            nodes.append({'node': f'{seats[j]} calls {seats[m]} jam', 'stack': stacks[j], 'X': X, 'call_asym': round(100 * float(W @ Ca_asym), 1),
                          'call_approx': round(100 * float(W @ Ca), 1), 'mean_abs_diff_pct': round(100 * float(W @ diff), 2),
                          'flips': flips, 'loss_bb': round(loss, 4), 'reach': round(float(rfc[(m, j)]), 4)})
        res['rules'][rule] = nodes
    return res


CONFIGS = [
    ('A1', ['BTN', 'SB', 'BB'], [20, 8, 40]),
    ('A2', ['CO', 'BTN', 'SB', 'BB'], [15, 40, 10, 10]),
    # request lists 7 values behind UTG for 8 seats; BB assumed 18 (stated in the report)
    ('A3', SEATS9, [25, 10, 40, 15, 60, 8, 30, 20, 18]),
    ('A4', ['SB', 'BB'], [20, 60]),
]
if __name__ == '__main__':
    out = []
    for name, seats, stacks in CONFIGS:
        r = run(name, seats, stacks); out.append(r)
        print('==', name, dict(zip(seats, stacks)), 'gap %.4f' % r['gap'], flush=True)
        for rule, nodes in r['rules'].items():
            fi = [x for x in nodes if 'first-in' in x]; ca = [x for x in nodes if 'calls' in x]
            lw = sum(x['loss_bb'] * x['reach'] for x in nodes)
            print(f"  {rule}: first-in mean|diff| {np.mean([x['mean_abs_diff_pct'] for x in fi]):.1f}%  call mean|diff| {np.mean([x['mean_abs_diff_pct'] for x in ca]) if ca else 0:.1f}%  reach-weighted loss {lw:.4f} bb/hand", flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'gto_spot', 'icm', 'eff_stack_A.json'), 'w'), indent=1)
