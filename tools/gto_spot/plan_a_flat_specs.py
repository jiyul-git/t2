#!/usr/bin/env python3
"""Flat-call pot spots (user decision 2026-10-19: 30 / 40 bb defence is the problem; the flat-call terminals must be corrected).
Root = the big blind facing a single open (or the SB limp): live seats = the opener (limper) and the big blind. Below the root the
parent's own tree (no menu override): fold / call (flat call -> flop) / 3-bet (-> 3-bet-call flop) / jam. One spot therefore covers
priority 1 (BB flat call of a single open) and the 3-bet-call terminal of the same pair; the 4-bet-and-later terminals are research.
    python3 tools/gto_spot/plan_a_flat_specs.py <stack> <arm>     (parent cfg data/gto_spot/plan_a/cfg_p<stack>_<arm>.json)
      -> data/gto_spot/plan_a/specs/p<stack>_flat_<opener>_vs_bb.json (+ p<stack>_flat_sb_limp_vs_bb)
Quick grade: spec max_steps 8 (BTN, CO) or 3 (the other seats, user decision 2026-10-20); the result is made with tools/gto_spot/quick_spot.py (converged -> final step, else mean of last 4 steps).
    python3 tools/gto_spot/plan_a_flat_specs.py <stack> <arm> <open_size> <id_suffix> <max_steps> <openers,...>
      second open size of a multi-size parent (e.g. 40 o25 2.5 _o25 3 BTN,CO -> p40_flat_btn_vs_bb_o25.json), only the listed openers, no SB limp"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CK = '/home/user/gto_ckpt/plan_a'
POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
OPENERS = ['BTN', 'CO', 'SB', 'HJ', 'LJ', 'UTG+2', 'UTG+1', 'UTG']     # priority order: late positions first
SLUG = {'UTG+1': 'utg1', 'UTG+2': 'utg2'}
FULL = {'BTN', 'CO'}       # user decision 2026-10-20: BTN and CO run to convergence (max 8 steps); the other seats stop at step 3 (quick)


def trim(x):
    return f'{x:.4f}'.rstrip('0').rstrip('.')


def line_for(cfg, opener, action):
    o = POS.index(opener)
    line = []
    for i in range(8):
        if i == o:
            line.append(f'{POS[i]}:{action}')
        elif i < o or i > o:
            line.append(f'{POS[i]}:Fold')
    return line


def main():
    stack, arm = int(sys.argv[1]), sys.argv[2]
    size, suffix, cap_all, only = (float(sys.argv[3]), sys.argv[4], int(sys.argv[5]), sys.argv[6].split(',')) if len(sys.argv) > 6 else (None, '', None, None)
    cfgp = os.path.join(ROOT, f'data/gto_spot/plan_a/cfg_p{stack}_{arm}.json')
    cfg = json.load(open(cfgp))
    pdir = f'{CK}/p{stack}_{arm}'
    conv = os.path.join(ROOT, f'data/gto_spot/plan_a/parent_p{stack}_{arm}_convergence.json')
    gap = None
    if not os.path.exists(conv):
        conv = os.path.join(ROOT, f'data/gto_spot/plan_a/open25/parent_p{stack}_{arm}_convergence.json')
    if os.path.exists(conv):
        rows = [r for r in json.load(open(conv))['rows'] if r['gap_exact'] is not None]
        gap = rows[-1]['gap_exact'] if rows else None
    out = os.path.join(ROOT, 'data/gto_spot/plan_a/specs')
    os.makedirs(out, exist_ok=True)
    jobs = []
    for op in [x for x in (only or OPENERS) if x != 'LIMP']:
        o = POS.index(op)
        sz = trim(size if size is not None else cfg["open_raises_by_seat"][o][0])
        assert float(sz) in cfg['open_raises_by_seat'][o], (op, sz)
        jobs.append((f'p{stack}_flat_{SLUG.get(op, op.lower())}_vs_bb{suffix}', op, f'Raise {sz}',
                     f'{op} opens {sz}, BB defends', cap_all or (8 if op in FULL else 3)))
    if only is None or 'LIMP' in only:   # LIMP in the opener list adds the SB-limp spot (id gets the suffix)
        jobs.append((f'p{stack}_flat_sb_limp_vs_bb{suffix}', 'SB', 'Limp 1', 'SB limps, BB acts', 3))
    for sid, op, act, what, cap in jobs:
        spec = {'id': sid, 'config': cfgp, 'dump': f'{pdir}/dump.jsonl', 'equity': f'{CK}/eq_table_202_1200.json', 'tables_dir': None,
                'iterations': 3000, 'rule': 'v4', 'max_steps': cap, 'root_line': line_for(cfg, op, act),
                'tree_label': f'Plan A flat-call pot p{stack} {arm}: 9-max hand-start {stack} bb (cfg.stack {cfg["stack"]}), ante 1/9, {what}; '
                              'below the root the parent tree (call / 3-bet / jam, 4-bet jam only), static continuation in the parent; '
                              'quick grade (symmetric stacks)',
                'parent': {'parent': f'Plan A parent p{stack}_{arm} (static continuation)', 'gap_total_bb': gap, 'source': os.path.relpath(conv, ROOT)},
                'status_cap': 'conditional_verified',
                'status_cap_reason': 'flat-call pot spot: parent continuation static outside the loop, symmetric stacks',
                'out': f'/home/user/gto_ckpt/spots/{sid}/spot.json'}
        json.dump(spec, open(os.path.join(out, sid + '.json'), 'w'), indent=1)
        print(sid, spec['root_line'], gap)


if __name__ == '__main__':
    main()
