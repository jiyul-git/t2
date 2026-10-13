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


def root_line(cfg, opener, threebettor, mult=None):
    """seats in order: folds, the opener's open, folds, the 3-bettor's 3-bet, folds to the end (the opener then acts)"""
    o, t = POS.index(opener), POS.index(threebettor)
    assert t > o
    line = []
    for i in range(9):
        if i == o:
            line.append(f'{POS[i]}:Raise {trim(cfg["open_raises_by_seat"][i][0])}')
        elif i == t:
            m = mult if mult is not None else cfg["raise_mults_by_seat"][i][0]
            assert m in cfg["raise_mults_by_seat"][i], (m, cfg["raise_mults_by_seat"][i])
            line.append(f'{POS[i]}:3-bet {trim(cfg["open_raises_by_seat"][o][0] * m)}')
        else:
            line.append(f'{POS[i]}:Fold')
    return line


def main():
    stack = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    out = os.path.join(ROOT, 'data/gto_spot/plan_a/specs')
    os.makedirs(out, exist_ok=True)
    # arms: b40 (single blind 3-bet size 4.0x); v2b (SB limp, open jam excluded, blind 3-bets {3.5x, 4.0x} -> one spot per size)
    for arm in ('b40', 'v2b'):
        cfgp = os.path.join(ROOT, f'data/gto_spot/plan_a/cfg_p{stack}_{arm}.json')
        if not os.path.exists(cfgp):
            continue
        cfg = json.load(open(cfgp))
        pdir = f'{CK}/p{stack}_{arm}'
        conv = os.path.join(ROOT, f'data/gto_spot/plan_a/parent_p{stack}_{arm}_convergence.json')
        gap = None
        if os.path.exists(conv):
            rows = [r for r in json.load(open(conv))['rows'] if r['gap_exact'] is not None]
            gap = rows[-1]['gap_exact'] if rows else None
        blinds = '/'.join(f'{m}x' for m in cfg['raise_mults_by_seat'][7])
        for name, (op, tb) in PAIRS.items():
            tbi = POS.index(tb)
            mults = cfg['raise_mults_by_seat'][tbi] if arm != 'b40' and len(cfg['raise_mults_by_seat'][tbi]) > 1 else [None]
            for m in mults:
                sid = f'p{stack}_{name}_{arm}' if m is None else f'p{stack}{arm}_{name}_3b{int(round(m * 10))}'
                if arm != 'b40' and m is None:
                    sid = f'p{stack}{arm}_{name}'
                spec = {'id': sid, 'config': cfgp, 'dump': f'{pdir}/dump.jsonl', 'equity': f'{CK}/eq_table_202_1200.json',
                        'tables_dir': None, 'iterations': 3000, 'rule': 'v4', 'root_line': root_line(cfg, op, tb, m), 'menu': MENU,
                        'tree_label': f'Plan A p{stack}{"" if arm == "b40" else " " + arm}: 9-max hand-start {stack} bb exact (cfg.stack {cfg["stack"]}), ante 1/9, opens 2.0, '
                                      f'3-bet 3.0x / blinds {blinds}; SB open {cfg["open_raises_by_seat"][7][0]} bb, SB limp '
                                      f'{"allowed" if 7 in (cfg.get("limp_seats") or []) else "excluded"}; open jam '
                                      f'{"excluded" if cfg.get("open_allin") is False else "included"}; parent max_raises 3, 4-bet jam only, static '
                                      'continuation; subgame 4-bet IP 2.15x / OOP 2.35x + jam, 5-bet jam',
                        'parent': {'parent': f'Plan A parent p{stack}_{arm} (static continuation)', 'gap_total_bb': gap,
                                   'source': os.path.relpath(conv, ROOT)},
                        'status_cap': 'conditional_verified',
                        'status_cap_reason': 'Plan A: subgame menu differs from the parent tree (4-bet jam only), parent continuation '
                                             'static, arriving ranges from the parent (docs/GTO_PLAN_A_60BB_V1.md section 4)',
                        'out': f'/home/user/gto_ckpt/spots/{sid}/spot.json'}
                json.dump(spec, open(os.path.join(out, sid + '.json'), 'w'), indent=1)
                print(sid, spec['root_line'], gap)


if __name__ == '__main__':
    main()
