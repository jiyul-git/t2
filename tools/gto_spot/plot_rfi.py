#!/usr/bin/env python3
"""RFI grid PNG from a parent_chart_quick_v1 file:  python3 tools/gto_spot/plot_rfi.py <chart.json> <out.png> <title>"""
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

R = 'AKQJT98765432'
d = json.load(open(sys.argv[1]))
rfi = [n for n in d['nodes'] if n['kind'] == 'rfi']
fig, axs = plt.subplots(2, 4, figsize=(20, 11))
for ax, n in zip(axs.flat, rfi):
    M = np.zeros((13, 13))
    for i, a in enumerate(R):
        for j, b in enumerate(R):
            lab = a + b if i == j else (a + b + 's' if i < j else b + a + 'o')
            M[i, j] = 1 - n['hands'].get(lab, {}).get('freq', {}).get('Fold', 1.0)
            ax.text(j, i, lab, ha='center', va='center', fontsize=6.5, color='white' if M[i, j] > 0.55 else '#222')
    ax.imshow(M, cmap='Blues', vmin=0, vmax=1)
    ax.set_xticks([])
    ax.set_yticks([])
    mix = n['mix']
    extra = ''
    if n['actor'] == 'SB':
        extra = '  ' + ', '.join('%s %.0f%%' % (a, 100 * v) for a, v in mix.items() if a != 'Fold')
    ax.set_title('%s  play %.1f%%%s' % (n['actor'], 100 * (1 - mix.get('Fold', 0)), extra), fontsize=11, pad=4)
fig.suptitle(sys.argv[3], fontsize=13)
plt.tight_layout(rect=[0, 0, 1, 0.95], h_pad=2.0)
plt.savefig(sys.argv[2], dpi=100)
