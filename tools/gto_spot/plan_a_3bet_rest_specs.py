#!/usr/bin/env python3
"""Opener-vs-3-bet subgame specs for the remaining pairs at 30 / 40 bb (docs/handoff/GTO_HANDOFF_20261026.md item 5; the 3-bettor is not the BB).
Done before (copied scripts plan_a_3bet30_specs.py / plan_a_3bet40_specs.py): CO vs SB, UTG+1 vs SB, UTG vs BTN.
Here: BTN vs SB, HJ vs SB, LJ vs SB, UTG+2 vs SB (SB 3-bet 4.0x), then the BTN-3-bettor pairs CO vs BTN, HJ vs BTN, LJ vs BTN, UTG+2 vs BTN, UTG+1 vs BTN (3.0x).
Same subgame menu as the 60 bb spots (4-bet IP 2.15x / OOP 2.35x + jam, 5-bet jam), parent = cfg_p<stack>_v1, quick grade (max_steps 3, no P144), symmetric stacks.
    python3 tools/gto_spot/plan_a_3bet_rest_specs.py <stack> [pair ...]    -> data/gto_spot/plan_a/specs/p<stack>v1_<pair>[_3b40].json"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_a_specs as P  # noqa: E402

ROOT, CK, POS = P.ROOT, P.CK, P.POS
ARM = 'v1'
PAIRS = {'btn_vs_sb': ('BTN', 'SB'), 'hj_vs_sb': ('HJ', 'SB'), 'lj_vs_sb': ('LJ', 'SB'), 'utg2_vs_sb': ('UTG+2', 'SB'),
         'co_vs_btn': ('CO', 'BTN'), 'hj_vs_btn': ('HJ', 'BTN'), 'lj_vs_btn': ('LJ', 'BTN'), 'utg2_vs_btn': ('UTG+2', 'BTN'),
         'utg1_vs_btn': ('UTG+1', 'BTN')}              # run order
CAP = 3


def main():
    stack = int(sys.argv[1])
    names = sys.argv[2:] or list(PAIRS)
    cfgp = os.path.join(ROOT, f'data/gto_spot/plan_a/cfg_p{stack}_{ARM}.json')
    cfg = json.load(open(cfgp))
    conv = os.path.join(ROOT, f'data/gto_spot/plan_a/parent_p{stack}_{ARM}_convergence.json')
    rows = [r for r in json.load(open(conv))['rows'] if r['gap_exact'] is not None]
    gap = rows[-1]['gap_exact'] if rows else None
    out = os.path.join(ROOT, 'data/gto_spot/plan_a/specs')
    for name in names:
        op, tb = PAIRS[name]
        mults = cfg['raise_mults_by_seat'][POS.index(tb)]
        m = 4.0 if len(mults) > 1 else None              # 4.0x arm first (as at 60 bb); the 3.5x arm is not run in the first pass
        sid = f'p{stack}{ARM}_{name}' + ('' if m is None else f'_3b{int(round(m * 10))}')
        blinds = '/'.join(f'{x}x' for x in cfg['raise_mults_by_seat'][7])
        spec = {'id': sid, 'config': cfgp, 'dump': f'{CK}/p{stack}_{ARM}/dump.jsonl', 'equity': f'{CK}/eq_table_202_1200.json',
                'tables_dir': None, 'iterations': 3000, 'rule': 'v4', 'max_steps': CAP,
                'root_line': P.root_line(cfg, op, tb, m), 'menu': P.MENU,
                'tree_label': f'Plan A p{stack} {ARM} (quick): 9-max hand-start {stack} bb (cfg.stack {cfg["stack"]}), ante 1/9, opens 2.0, '
                              f'3-bet 3.0x / blinds {blinds}; SB open {cfg["open_raises_by_seat"][7][0]} bb, SB limp allowed; open jam excluded; '
                              'parent max_raises 3, 4-bet jam only, static continuation; subgame 4-bet IP 2.15x / OOP 2.35x + jam, 5-bet jam; '
                              'symmetric stacks',
                'parent': {'parent': f'Plan A parent p{stack}_{ARM} (static continuation)', 'gap_total_bb': gap,
                           'source': os.path.relpath(conv, ROOT)},
                'status_cap': 'conditional_verified',
                'status_cap_reason': 'Plan A: subgame menu differs from the parent tree (4-bet jam only), parent continuation static, '
                                     'arriving ranges from the parent; quick grade, symmetric stacks',
                'out': f'/home/user/gto_ckpt/spots/{sid}/spot.json'}
        json.dump(spec, open(os.path.join(out, sid + '.json'), 'w'), indent=1)
        print(sid, spec['root_line'], gap)


if __name__ == '__main__':
    main()
