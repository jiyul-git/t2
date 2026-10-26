import sys, json, time
sys.path.insert(0, '/home/user/t2/tools/gto_icm')
import numpy as np
import icm_pushfold as ip
_, payouts = ip.load_icm()
M15 = [12, 30, 8, 20, 15, 10, 25, 9, 6]
SC = {
 'B1': (9, 8, 0.0, [15]*9), 'B2': (9, 8, 0.0, M15),
 'B3': (9, 8, 0.0, [20,50,13,33,25,17,42,15,10]), 'B4': (9, 8, 0.0, [8,20,5,13,10,7,17,6,4]),
 'F1': (9, 9, 0.0, [15]*9), 'F2': (9, 9, 0.0, M15), 'F3': (6, 6, 0.0, [12,30,8,20,15,5]),
 'H1': (3, 3, 0.0, [20,15,10]), 'S1': (4, 3, 1.0, [25,15,12,8]),
}
POS = {9: ['UTG','UTG+1','UTG+2','LJ','HJ','CO','BTN','SB','BB']}
def names(n):
    return (['UTG','UTG+1','UTG+2','LJ','HJ','CO'][:max(0, n-3)] + ['BTN','SB','BB']) if n>=3 else ['SB','BB']
def run(sid, mode):
    n, paid, flat, st = SC[sid]
    pay = payouts(paid, flat)
    g = ip.Game(st, pay, mode)
    t = time.time()
    P, C, gap, it = ip.solve(g, iters=60000, tol=0.010)
    u = ip.evaluate(g, P, C)
    return dict(id=sid, mode=mode, players=n, paid=paid, payouts=pay, stacks=st, seats=names(n), iterations=it, gap_total=float(gap),
                converged=bool(gap <= 0.010), secs=round(time.time()-t,1),
                P=[[round(float(x),4) for x in p] for p in P], C={f'{m}-{j}': [round(float(x),4) for x in v] for (m,j),v in C.items()})
if __name__ == '__main__':
    ids = sys.argv[1:] or list(SC)
    for sid in ids:
        for mode in ('icm', 'chip'):
            r = run(sid, mode)
            json.dump(r, open(f'/home/user/t2/data/gto_spot/icm/run_{sid}_{mode}.json', 'w'))
            print(sid, mode, 'gap', round(r['gap_total'],5), 'it', r['iterations'], r['secs'], 's', flush=True)
