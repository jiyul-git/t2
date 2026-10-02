#!/usr/bin/env python3
"""A4c design analysis 4 (no solve): calibrated option predictions and paired-stratum FPC sensitivity.

The isolated-stratum sum over-predicts the pooled 144-board seat loss by 1.38-1.50x (sub-additive: loss grows slower than the
summed table variance, consistent with the 72->144 exponent beta = 0.70-0.87 of loss_scaling.json). Calibrated prediction:
loss(alloc) = observed_pooled_144 * (V(alloc) / V(144))^beta, with V = sum_s c_s g_s(m) the additive (FPC-aware) prediction.
This keeps the measured level and the measured scaling; the allocation shape (which depends only on the stratum weights c_s)
is unaffected by a monotone transform of V."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
O = 'data/gto_terminal_expansion/a4c_preanalysis/'
d = json.load(open(O + 'allocation_downstream.json'))
rec = json.load(open(O + 'reconstruction.json'))['reconstruction']
ls = json.load(open(O + 'loss_scaling.json'))['summary']['seats']
beta = {s: ls[s]['loss_vs_variance_exponent_beta'] for s in ('BTN', 'SB', 'BB')}
obs = {s: rec[f'seat_dEV:{s}']['observed_pooled_mean'] for s in ('BTN', 'SB', 'BB')}
cur = d['options']['current_144']['predicted']
out = {'beta': beta, 'observed_pooled_144': obs, 'options': {}}
for k, o in d['options'].items():
    p = o['predicted']
    out['options'][k] = {'new_solves': o['new_solves'], 'cpu_h': o['cpu_h'], 'wall_h_4cores': o['wall_h_4cores'], 'new_by_terminal': o.get('new_by_terminal'),
                         'calibrated_seat_loss': {s: obs[s] * (p[f'seat_dEV:{s}'] / cur[f'seat_dEV:{s}']) ** beta[s] for s in beta}}
m = d['matching_equal24_downstream']
# matching option: recompute via the allocation code
import a4c_reconstruct as R
json.dump(out, open(O + 'calibrated_options.json', 'w'), indent=1)
for k, v in out['options'].items():
    print(f"{k:16s} new={v['new_solves']:3d} cpu_h={v['cpu_h']:5.1f} wall={v['wall_h_4cores']:4.1f}  calibrated BTN/SB/BB = " + ' / '.join(f"{v['calibrated_seat_loss'][s]:.5f}" for s in ('BTN', 'SB', 'BB')))
