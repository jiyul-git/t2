"""ICM jam/fold Nash solver (docs/GTO_ICM_PLAN.md). Own solver: gtopen takes ONE equal stack and chip payoffs only.

Game: n-handed (2..9) single table, hand-start stacks s[k] (bb, blinds+ante included), blinds 0.5/1, ante 1 bb total split
evenly (1/n each). First-in: jam / fold. Facing a jam: call / fold. Only the FIRST caller can call (no overcalls: every seat
behind the first caller folds). Payoffs: chips ('chip') or Malmuth-Harville ICM of the final stack vector ('icm', T2's icm.py
subset DP, payouts from T2 formats.payouts) scaled to bb (mean stack = mean prize). Class-level hands, card removal only through
the pairwise class-equity table (same as gtopen). Equity win+tie/2 is treated as win probability (no chop branch).
Solver: damped fictitious play on per-class jam/call probabilities, exact gap = sum over players of best-response gain (bb, ICM units).
"""
import sys, json, gzip, itertools
import numpy as np

ROOT = '/home/user/t2'
EQ = np.loadtxt(gzip.open(ROOT + '/data/gto_spot/icm/eq169_20000.txt.gz'))   # EQ[h,g] = equity of class h vs g
def _lab():
    r = '23456789TJQKA'; o = []
    for i in range(13):
        for j in range(13):
            hi, lo = max(i, j), min(i, j)
            o.append(r[i]*2 if i == j else r[hi] + r[lo] + ('o' if j > i else 's'))
    return o
LABELS = _lab()
COMBOS = np.array([6.0 if l[0]==l[1] else (4.0 if l.endswith('s') else 12.0) for l in LABELS])
W = COMBOS / COMBOS.sum()
Q = EQ.copy()


def load_icm():
    import subprocess
    src = subprocess.check_output(['git', '-C', ROOT, 'show', 'origin/test3:icm.py']).decode()
    ns = {}
    exec(compile(src, 'icm_t2', 'exec'), ns)
    fsrc = subprocess.check_output(['git', '-C', ROOT, 'show', 'origin/test3:formats.py']).decode()
    fn = {}
    exec(compile(fsrc, 'formats_t2', 'exec'), fn)
    return ns['icm_equity'], fn['payouts']


class Game:
    def __init__(self, stacks, payouts_pct=None, mode='icm'):
        self.n = n = len(stacks)
        self.s = np.array(stacks, float)
        self.mode = mode
        ante = 1.0 / n
        blind = np.zeros(n); blind[n - 2] = 0.5; blind[n - 1] = 1.0
        self.post = ante + blind
        if mode == 'icm':
            icm_equity, _ = load_icm()
            pay = list(payouts_pct)
            self.scale = self.s.sum() / sum(pay)
            self._f = lambda chips: np.array(icm_equity(list(chips), pay)) * self.scale
        else:
            self._f = lambda chips: np.array(chips, float)
        self._cache = {}
        n = self.n
        self.steal = [self.val(self.chips_steal(m)) for m in range(n)]
        self.call = {}
        for m in range(n - 1):
            for j in range(m + 1, n):
                self.call[(m, j)] = (self.val(self.chips_call(m, j, True)), self.val(self.chips_call(m, j, False)))  # m wins / j wins

    def val(self, chips):
        key = tuple(np.round(chips, 9))
        if key not in self._cache:
            self._cache[key] = self._f(chips)
        return self._cache[key]

    def chips_steal(self, m):
        c = self.s - self.post
        c[m] = self.s[m] + self.post.sum() - self.post[m]
        return c

    def chips_call(self, m, j, m_wins):
        e = min(self.s[m], self.s[j])
        pot = 2 * e + self.post.sum() - self.post[m] - self.post[j]
        c = self.s - self.post
        c[m] = self.s[m] - e; c[j] = self.s[j] - e
        c[m if m_wins else j] += pot
        return c

    def by(self, i, m, k, pm):
        """value for bystander i when m jammed and k called, m wins with probability pm."""
        wv, lv = self.call[(m, k)]
        return pm * wv[i] + (1 - pm) * lv[i]


def evaluate(g, P, C):
    """P[i] (169) jam prob for i in 0..n-2; C[(m,j)] (169) call prob of j facing m's jam (first caller).
    Returns (Ujam[i], Ufold_first[i], Ucall[(m,j)], Ufold_face[(m,j)], reach_first[i], reach_face[(m,j)])."""
    n = g.n
    pr = [W @ P[i] for i in range(n - 1)]
    cr = {k: W @ v for k, v in C.items()}
    Jm = [(W * P[m]) / max(pr[m], 1e-300) for m in range(n - 1)]
    # P(m wins | m called by k)
    pw = {}
    for (m, k), c in C.items():
        cc = (W * c) / max(cr[(m, k)], 1e-300)
        pw[(m, k)] = float(Jm[m] @ (Q @ cc))
    # F[m][k] = prob nobody in (m,k) exclusive calls; Fnone[m]
    def Fp(m, k):
        p = 1.0
        for l in range(m + 1, k):
            p *= 1 - cr[(m, l)]
        return p
    Fnone = [Fp(m, n) if m < n - 1 else 1.0 for m in range(n - 1)]
    # note Fp(m,n) loops l up to n-1 (BB included)
    # T[m][i]: expected value of bystander i given m jammed (i < m  or i > k handled by caller via by())
    def T_first(m, i):
        tot = Fnone[m] * g.steal[m][i]
        for k in range(m + 1, n):
            tot += Fp(m, k) * cr[(m, k)] * g.by(i, m, k, pw[(m, k)])
        return tot
    Ujam = []; Ufold_first = []; reach_first = []
    for i in range(n - 1):
        u = np.zeros(169)
        for j in range(i + 1, n):
            wv, lv = g.call[(i, j)]
            wc = W * C[(i, j)]
            A = (Q @ wc)                       # sum_g w_g C_g q[h,g] -> prob h beats-ish
            u += Fp(i, j) * (A * wv[i] + (cr[(i, j)] - A) * lv[i])
        u += Fnone[i] * g.steal[i][i]
        Ujam.append(u)
        f = 0.0
        pre = 1.0
        for m in range(i + 1, n - 1):
            f += pre * pr[m] * T_first(m, i)
            pre *= 1 - pr[m]
        f += pre * g.steal[n - 1][i]
        Ufold_first.append(f)
        rp = 1.0
        for k in range(i):
            rp *= 1 - pr[k]
        reach_first.append(rp)
    Ucall = {}; Ufold_face = {}; reach_face = {}
    for m in range(n - 1):
        rm = 1.0
        for k in range(m):
            rm *= 1 - pr[k]
        rm *= pr[m]
        for j in range(m + 1, n):
            wv, lv = g.call[(m, j)]
            Qm = Q.T @ Jm[m]                   # Qm[g] = m's equity vs g
            Ucall[(m, j)] = lv[j] * (1 - Qm) + wv[j] * Qm
            f = Fnone_after(g, m, j, cr, pw, Fp)
            Ufold_face[(m, j)] = f
            reach_face[(m, j)] = rm * Fp(m, j)
    return Ujam, Ufold_first, Ucall, Ufold_face, reach_first, reach_face


def Fnone_after(g, m, j, cr, pw, Fp):
    n = g.n
    tot = 1.0
    for l in range(j + 1, n):
        tot *= 1 - cr[(m, l)]
    v = tot * g.steal[m][j]
    for k in range(j + 1, n):
        p = 1.0
        for l in range(j + 1, k):
            p *= 1 - cr[(m, l)]
        v += p * cr[(m, k)] * g.by(j, m, k, pw[(m, k)])
    return v


def solve(g, iters=3000, tol=0.010, log=None, check=25):
    n = g.n
    P = [np.full(169, 0.3) for _ in range(n - 1)]
    C = {(m, j): np.full(169, 0.3) for m in range(n - 1) for j in range(m + 1, n)}
    # running average strategy (what we report); damped FP: sigma_{t+1} = sigma + (BR - sigma)/(t+1)
    gap = None
    for t in range(1, iters + 1):
        Uj, Uf, Uc, Ufc, rf, rfc = evaluate(g, P, C)
        if t % check == 1 or t == iters:
            gap = 0.0
            for i in range(n - 1):
                cur = P[i] * Uj[i] + (1 - P[i]) * Uf[i]
                gap += rf[i] * float(W @ (np.maximum(Uj[i], Uf[i]) - cur))
            for k, c in C.items():
                cur = c * Uc[k] + (1 - c) * Ufc[k]
                gap += rfc[k] * float(W @ (np.maximum(Uc[k], Ufc[k]) - cur))
            if log:
                log(t, gap)
            if gap <= tol:
                return P, C, gap, t
        a = 1.0 / (t + 1)
        for i in range(n - 1):
            br = (Uj[i] > Uf[i]).astype(float)
            P[i] = P[i] + a * (br - P[i])
        for k in C:
            br = (Uc[k] > Ufc[k]).astype(float)
            C[k] = C[k] + a * (br - C[k])
    return P, C, gap, iters
