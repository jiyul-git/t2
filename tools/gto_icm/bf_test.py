"""Bubble-factor (risk-premium) chip-EV model vs exact ICM, on the 9 pre-registered ICM jam/fold scenarios.
BF model: terminal values are chips; for the two players in the all-in the chip LOSS is multiplied by that player's pairwise
bubble factor BF = (ICM(base)-ICM(lose)) / (ICM(win)-ICM(base)) computed from exact ICM of the same two outcomes. Bystanders: chips."""
import sys, json, numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import icm_pushfold as ip

class BFGame(ip.Game):
    def __init__(self, stacks, payouts_pct):
        self.n = n = len(stacks); self.s = np.array(stacks, float); self.mode = 'bf'
        ante = 1.0 / n
        blind = np.zeros(n); blind[n - 2] = 0.5; blind[n - 1] = 1.0
        self.post = ante + blind
        icm_equity, _ = ip.load_icm()
        pay = list(payouts_pct); scale = self.s.sum() / sum(pay)
        f = lambda c: np.array(icm_equity(list(c), pay)) * scale
        base = self.s - self.post
        V0 = f(base)
        self.BF = {}
        self.steal = [self.chips_steal(m) for m in range(n)]
        self.call = {}
        for m in range(n - 1):
            for j in range(m + 1, n):
                cw, cl = self.chips_call(m, j, True), self.chips_call(m, j, False)
                bf = {}
                for i, win_c, lose_c in ((m, cw, cl), (j, cl, cw)):
                    up = f(win_c)[i] - V0[i]; dn = V0[i] - f(lose_c)[i]
                    bf[i] = dn / up if up > 1e-9 else 1.0
                self.BF[(m, j)] = bf
                def adj(c):
                    c = c.copy()
                    for i in (m, j):
                        d = c[i] - base[i]
                        c[i] = base[i] + (d if d >= 0 else bf[i] * d)
                    return c
                self.call[(m, j)] = (adj(cw), adj(cl))

def cls(P, thr=.5): return np.asarray(P) >= thr

def main():
    W = ip.W
    tot = {}
    for sid in ['B1', 'B2', 'B3', 'B4', 'F1', 'F2', 'F3', 'H1', 'S1']:
        a = json.load(open(f'/home/user/t2/data/gto_spot/icm/run_{sid}_icm.json'))
        c = json.load(open(f'/home/user/t2/data/gto_spot/icm/run_{sid}_chip.json'))
        g = BFGame(a['stacks'], a['payouts'])
        P, C, gap, it = ip.solve(g, iters=20000, tol=0.010)
        n = a['players']
        print(f"== {sid} n={n} stacks={a['stacks']}  BF-model gap {gap:.4f} it {it}", flush=True)
        # decision error = combos-weighted share of classes (weighted by reach-independent combo weight) with different 0.5-decision
        def mis(x, y): return float((W * (cls(x) != cls(y))).sum())
        jam_row = []; e_chip = []; e_bf = []
        for i in range(n - 1):
            pi, pc, pb = np.array(a['P'][i]), np.array(c['P'][i]), P[i]
            jam_row.append((a['seats'][i], a['stacks'][i], 100*W@pc, 100*W@pb, 100*W@pi))
            e_chip.append(mis(pc, pi)); e_bf.append(mis(pb, pi))
        call_chip = []; call_bf = []; cm = []
        for k, ca in a['C'].items():
            m, j = map(int, k.split('-'))
            call_chip.append(mis(np.array(c['C'][k]), np.array(ca))); call_bf.append(mis(C[(m, j)], np.array(ca)))
            cm.append((100*W@np.array(c['C'][k]), 100*W@C[(m, j)], 100*W@np.array(ca)))
        print('  seat stack | jam% chip  BF   exact')
        for r in jam_row: print('  %-6s %3d | %6.1f %6.1f %6.1f' % r)
        cm = np.array(cm)
        print('  call%% mean chip %.1f BF %.1f exact %.1f' % tuple(cm.mean(0)))
        print('  wrong-decision share of hand weight: jam chip %.1f%% BF %.1f%% | call chip %.1f%% BF %.1f%%' % (
            100*np.mean(e_chip), 100*np.mean(e_bf), 100*np.mean(call_chip), 100*np.mean(call_bf)), flush=True)
        tot[sid] = (np.mean(e_chip), np.mean(e_bf), np.mean(call_chip), np.mean(call_bf))
    t = np.array(list(tot.values())).mean(0) * 100
    print('MEAN over scenarios: wrong jam decisions chip %.1f%% -> BF %.1f%% ; wrong call decisions chip %.1f%% -> BF %.1f%%' % tuple(t))
    json.dump({k: list(map(float, v)) for k, v in tot.items()}, open('/home/user/t2/data/gto_spot/icm/bf_summary.json', 'w'))
main()
