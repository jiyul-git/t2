import json, sys
import numpy as np
sys.path.insert(0, '/home/user/t2/tools/gto_icm')
import icm_pushfold as ip
W = ip.W; L = ip.LABELS
def ld(s, m): return json.load(open(f'/home/user/t2/data/gto_spot/icm/run_{s}_{m}.json'))
out = []
for s in ['B1','B2','B3','B4','F1','F2','F3','H1','S1']:
    a, c = ld(s, 'icm'), ld(s, 'chip'); n = a['players']
    row = f"{s} n={n} stacks={a['stacks']}\n  seat  stack  jam%chip  jam%icm  flips(J->F / F->J)\n"
    for i in range(n-1):
        pa, pc = np.array(a['P'][i]), np.array(c['P'][i])
        jf = [L[h] for h in range(169) if pc[h] >= .5 and pa[h] < .5]
        fj = [L[h] for h in range(169) if pc[h] < .5 and pa[h] >= .5]
        row += f"  {a['seats'][i]:6s} {a['stacks'][i]:5} {100*W@pc:7.1f} {100*W@pa:8.1f}  {len(jf)}/{len(fj)}\n"
    # average call rate vs the first-in jammer
    cs = []
    for k in a['C']:
        m, j = map(int, k.split('-')); ca, cc = np.array(a['C'][k]), np.array(c['C'][k])
        cs.append((m, j, 100*W@cc, 100*W@ca))
    row += "  call pct (jammer->caller: chip / icm), mean over pairs: %.1f / %.1f\n" % (np.mean([x[2] for x in cs]), np.mean([x[3] for x in cs]))
    out.append(row)
print(''.join(out))
# pilot detail
a, c = ld('B2', 'icm'), ld('B2', 'chip')
for i in range(8):
    pa, pc = np.array(a['P'][i]), np.array(c['P'][i])
    jf = [L[h] for h in range(169) if pc[h] >= .5 and pa[h] < .5]
    fj = [L[h] for h in range(169) if pc[h] < .5 and pa[h] >= .5]
    print(a['seats'][i], a['stacks'][i], 'jam->fold:', ' '.join(jf) or '-', '| fold->jam:', ' '.join(fj) or '-')
for k in ['0-8','1-8','7-8','6-7']:
    ca, cc = np.array(a['C'][k]), np.array(c['C'][k])
    m, j = map(int, k.split('-'))
    jf = [L[h] for h in range(169) if cc[h] >= .5 and ca[h] < .5]
    fj = [L[h] for h in range(169) if cc[h] < .5 and ca[h] >= .5]
    print('call', a['seats'][m], a['stacks'][m], 'vs', a['seats'][j], a['stacks'][j], f'chip {100*W@cc:.1f}% icm {100*W@ca:.1f}%', 'call->fold:', ' '.join(jf) or '-', '| fold->call:', ' '.join(fj) or '-')
