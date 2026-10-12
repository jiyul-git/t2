#!/usr/bin/env python3
"""Plan A (docs/GTO_PLAN_A_60BB_V1.md) spot specs: 5 opener-vs-3-bet pairs x blind 3-bet arms at one stack.
    python3 tools/gto_spot/plan_a_specs.py [stack=60]  -> data/gto_spot/plan_a/specs/p<stack>_<pair>_<arm>.json
The parent gap is read from the parent's convergence file when it exists (else null; the grader then reports G2 unknown)."""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CK = '/home/user/gto_ckpt/plan_a'
POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
PAIRS = {'co_vs_sb': ('CO', 'SB'), 'utg1_vs_sb': ('UTG+1', 'SB'), 'utg_vs_btn': ('UTG', 'BTN'), 'btn_vs_bb': ('BTN', 'BB'),
         'hj_vs_bb': ('HJ', 'BB')}
MENU = {'max_raises': 4, 'fourbet_ip': 2.15, 'fourbet_oop': 2.35, 'fivebet': 'jam'}


def trim(x):
    s = f'{x:.4f}'.rstrip('0').rstrip('.')
    return s


def root_line(cfg, opener, threebettor):
    """seats in order: folds, the opener's open, folds, the 3-bettor's 3-bet, folds to the end (the opener then acts)"""
    o, t = POS.index(opener), POS.index(threebettor)
    assert t > o
    line = []
    for i in range(9):
        if i == o:
            line.append(f'{POS[i]}:Raise {trim(cfg["open_raises_by_seat"][i][0])}')
        elif i == t:
            line.append(f'{POS[i]}:3-bet {trim(cfg["open_raises_by_seat"][o][0] * cfg["raise_mults_by_seat"][i][0])}')
        else:
            line.append(f'{POS[i]}:Fold')
    return line


def main():
    stack = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    out = os.path.join(ROOT, 'data/gto_spot/plan_a/specs')
    os.makedirs(out, exist_ok=True)
    for arm in ('b35', 'b40'):
        cfgp = os.path.join(ROOT, f'data/gto_spot/plan_a/cfg_p{stack}_{arm}.json')
        cfg = json.load(open(cfgp))
        pdir = f'{CK}/p{stack}_{arm}'
        conv = os.path.join(ROOT, f'data/gto_spot/plan_a/parent_p{stack}_{arm}_convergence.json')
        gap = None
        if os.path.exists(conv):
            rows = [r for r in json.load(open(conv))['rows'] if r['gap_exact'] is not None]
            gap = rows[-1]['gap_exact'] if rows else None
        for name, (op, tb) in PAIRS.items():
            sid = f'p{stack}_{name}_{arm}'
            spec = {'id': sid, 'config': cfgp, 'dump': f'{pdir}/dump.jsonl', 'equity': f'{CK}/eq_table_202_1200.json',
                    'tables_dir': None, 'iterations': 3000, 'rule': 'v3', 'root_line': root_line(cfg, op, tb), 'menu': MENU,
                    'tree_label': f'Plan A p{stack}: 9-max hand-start {stack} bb exact (cfg.stack {cfg["stack"]}), ante 1/9, opens 2.0, '
                                  f'3-bet 3.0x / blinds {cfg["raise_mults_by_seat"][7][0]}x; parent max_raises 3, 4-bet jam only, static '
                                  'continuation; subgame 4-bet IP 2.15x / OOP 2.35x + jam, 5-bet jam',
                    'parent': {'parent': f'Plan A parent p{stack}_{arm} (static continuation)', 'gap_total_bb': gap,
                               'source': os.path.relpath(conv, ROOT)},
                    'status_cap': 'conditional_verified',
                    'status_cap_reason': 'Plan A: subgame menu differs from the parent tree (4-bet jam only), parent continuation '
                                         'static, arriving ranges from the parent (docs/GTO_PLAN_A_60BB_V1.md section 4)',
                    'out': f'/home/user/gto_ckpt/spots/{sid}/spot.json'}
            if name == 'utg_vs_btn' and arm == 'b35':
                spec['role'] = 'parent-arm sensitivity replicate of p%d_utg_vs_btn_b40 (amendment A2); not a separate result' % stack
            json.dump(spec, open(os.path.join(out, sid + '.json'), 'w'), indent=1)
            print(sid, spec['root_line'])


if __name__ == '__main__':
    main()
