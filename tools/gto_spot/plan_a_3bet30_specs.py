#!/usr/bin/env python3
"""30 bb opener-vs-3-bet subgame specs (T2 coordinator assignment 2026-10-21): the 3-bettor is not the BB.
Pairs: CO vs SB (3-bet 4.0x), UTG+1 vs SB (4.0x), UTG vs BTN (3.0x); the 3.5x arms are not run in the first pass. Copied from claude/p40_3bet_20261021 (STACK 30).
Same subgame menu as the 60 bb spots (4-bet 2.15x IP / 2.35x OOP + jam, 5-bet jam; docs/GTO_PLAN_A_60BB_V1.md), parent = cfg_p30_v1 (v2b sizes at stack 29.89).
Quick grade (user 2026-10-19 / 2026-10-20): max_steps 3, no P144; result via tools/gto_spot/quick_spot.py.
    python3 tools/gto_spot/plan_a_3bet30_specs.py     -> data/gto_spot/plan_a/specs/p30v1_<pair>[_3b<size>].json
Reuses root_line / PAIRS / MENU of plan_a_specs.py; writes only the 30 bb files (the 60 bb specs are not touched)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_a_specs as P  # noqa: E402

ROOT, CK, POS = P.ROOT, P.CK, P.POS
STACK, ARM = 30, 'v1'
PAIRS = ['co_vs_sb', 'utg1_vs_sb', 'utg_vs_btn']       # run order (user/coordinator: CO vs SB, UTG+1 vs SB, UTG vs BTN)


def main():
    cfgp = os.path.join(ROOT, f'data/gto_spot/plan_a/cfg_p{STACK}_{ARM}.json')
    cfg = json.load(open(cfgp))
    conv = os.path.join(ROOT, f'data/gto_spot/plan_a/parent_p{STACK}_{ARM}_convergence.json')
    rows = [r for r in json.load(open(conv))['rows'] if r['gap_exact'] is not None]
    gap = rows[-1]['gap_exact'] if rows else None
    out = os.path.join(ROOT, 'data/gto_spot/plan_a/specs')
    os.makedirs(out, exist_ok=True)
    for name in PAIRS:
        op, tb = P.PAIRS[name]
        mults = cfg['raise_mults_by_seat'][POS.index(tb)]
        for m in ([4.0, 3.5] if len(mults) > 1 else [None]):     # 4.0x arm first (as at 60 bb)
            sid = f'p{STACK}{ARM}_{name}' + ('' if m is None else f'_3b{int(round(m * 10))}')
            blinds = '/'.join(f'{x}x' for x in cfg['raise_mults_by_seat'][7])
            spec = {'id': sid, 'config': cfgp, 'dump': f'{CK}/p{STACK}_{ARM}/dump.jsonl', 'equity': f'{CK}/eq_table_202_1200.json',
                    'tables_dir': None, 'iterations': 3000, 'rule': 'v4', 'max_steps': 3,
                    'root_line': P.root_line(cfg, op, tb, m), 'menu': P.MENU,
                    'tree_label': f'Plan A p{STACK} {ARM} (quick): 9-max hand-start {STACK} bb (cfg.stack {cfg["stack"]}), ante 1/9, opens 2.0, '
                                  f'3-bet 3.0x / blinds {blinds}; SB open {cfg["open_raises_by_seat"][7][0]} bb, SB limp allowed; open jam excluded; '
                                  'parent max_raises 3, 4-bet jam only, static continuation; subgame 4-bet IP 2.15x / OOP 2.35x + jam, 5-bet jam; '
                                  'symmetric stacks',
                    'parent': {'parent': f'Plan A parent p{STACK}_{ARM} (static continuation)', 'gap_total_bb': gap,
                               'source': os.path.relpath(conv, ROOT)},
                    'status_cap': 'conditional_verified',
                    'status_cap_reason': 'Plan A: subgame menu differs from the parent tree (4-bet jam only), parent continuation static, '
                                         'arriving ranges from the parent; quick grade, symmetric stacks',
                    'out': f'/home/user/gto_ckpt/spots/{sid}/spot.json'}
            json.dump(spec, open(os.path.join(out, sid + '.json'), 'w'), indent=1)
            print(sid, spec['root_line'], gap)


if __name__ == '__main__':
    main()
