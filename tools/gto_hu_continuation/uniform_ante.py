#!/usr/bin/env python3
"""T2 uniform ante for GTO configs and its verifier (GTO side only; the T2 engine change is handled elsewhere).

Rule: N = hand_start_players (dealt-in seats, 5..9) is fixed at the start of the hand; every dealt-in player pays 1/N bb ante
(dead money, never part of a call / current bet / min-raise); SB 0.5 and BB 1.0 are live blinds; total ante is exactly 1 bb;
initial pot 2.5 bb. Folds never re-split the ante. A CO/BTN/SB/BB continuation of an N-max hand therefore has per-seat ante 1/N
and dead_money (N - 4) / N for the antes of the N - 4 players who folded before CO.

    python3 tools/gto_hu_continuation/uniform_ante.py config <N> [--base cfg.json] [--out path]
    python3 tools/gto_hu_continuation/uniform_ante.py verify        # reference engine + GTOpen tree, N = 5..9
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from fractions import Fraction as F

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, 'data/gto_hu_continuation/cfg_4h_mr4_30bb.json')
BIN = os.path.join(ROOT, 'vendor/gtopen/target/release/examples')
ENV = {'PREFLOP_EQ_SEED': '202', 'PREFLOP_MULTIWAY_SEED': '202', 'PREFLOP_EQ_SAMPLES': '1200'}
SPEC = {28: 'fold,raise,fold,call', 6: 'fold,fold,raise,call'}
ORDER_FROM_BB = ['BB', 'SB', 'BTN', 'CO', 'HJ', 'LJ', 'MP', 'UTG1', 'UTG']


def positions(n):
    return list(reversed(ORDER_FROM_BB[:n]))


def continuation_config(n, base=BASE):
    """CO/BTN/SB/BB continuation of an n-max uniform-ante hand (floats for the solver; exact values in the provenance)."""
    if not 5 <= n <= 9:
        raise ValueError('hand_start_players must be 5..9')
    c = json.load(open(base))
    assert c['positions'] == ['CO', 'BTN', 'SB', 'BB'] and c['posts'] == [0, 0, 0.5, 1.0]
    S = c['stack']
    # GTOpen pays the ante from outside cfg.stack (behind = stack - invested + ante), so cfg.stack is the stack AFTER the ante:
    # hand-start stack S -> cfg.stack = S - 1/N
    c['stack'] = S - 1.0 / n
    c['ante'] = 1.0 / n
    c['dead_money'] = (n - 4) / n
    c['t2_ante_rule'] = {'model': 'uniform_total_1bb', 'hand_start_players': n, 'hand_start_stack_bb': S, 'cfg_stack_after_ante_bb': f'{S} - 1/{n}', 'per_player_ante_bb': f'1/{n}',
                         'folded_before_subgame': positions(n)[:n - 4], 'dead_money_bb': f'{n - 4}/{n}'}
    return c


# ---------------- reference engine (exact fractions) ----------------
def full_hand(n, S):
    """hand start of an n-max uniform-ante hand: ante first, then blinds (a short stack pays what it can)."""
    pos = positions(n)
    stack = {p: F(S) for p in pos}
    ante_paid, live = {}, {}
    for p in pos:
        a = min(F(1, n), stack[p]); stack[p] -= a; ante_paid[p] = a
    for p, b in (('SB', F(1, 2)), ('BB', F(1))):
        x = min(b, stack[p]); stack[p] -= x; live[p] = x
    for p in pos:
        live.setdefault(p, F(0))
    return {'pos': pos, 'stack': stack, 'ante': ante_paid, 'live': live, 'folded': set(), 'dead': F(0)}


def pot(st):
    return sum(st['ante'].values()) + sum(st['live'].values())


def act(st, p, kind, to=None):
    cur = max(st['live'].values())
    if kind == 'fold':
        st['folded'].add(p)
    elif kind == 'call':
        pay = min(cur - st['live'][p], st['stack'][p]); st['stack'][p] -= pay; st['live'][p] += pay
    elif kind == 'raise':
        pay = F(to) - st['live'][p]; assert pay <= st['stack'][p]; st['stack'][p] -= pay; st['live'][p] = F(to)
    return st


def to_call(st, p):
    return max(st['live'].values()) - st['live'][p]


def min_raise_to(st):
    lv = sorted(st['live'].values(), reverse=True)
    return lv[0] + max(F(1), lv[0] - lv[1])


def continuation(n, S):
    """the same state built the way the solver config describes it: 4 seats, ante 1/n each, dead_money (n-4)/n."""
    pos = ['CO', 'BTN', 'SB', 'BB']
    stack = {p: F(S) - F(1, n) for p in pos}
    live = {'CO': F(0), 'BTN': F(0), 'SB': F(1, 2), 'BB': F(1)}
    stack['SB'] -= F(1, 2); stack['BB'] -= F(1)
    return {'pos': pos, 'stack': stack, 'ante': {p: F(1, n) for p in pos}, 'live': live, 'folded': set(), 'dead': F(n - 4, n)}


def pot_c(st):
    return pot(st) + st['dead']


def verify(gtopen=True):
    res = {'N': {}, 'errors': []}
    err = res['errors'].append
    S = 30
    for n in range(5, 10):
        r = {}
        h = full_hand(n, S)
        pos = h['pos']
        r['1_hand_start'] = {p: str(F(S) - h['stack'][p]) for p in pos}
        exp = {p: F(1, n) + (F(1, 2) if p == 'SB' else F(1) if p == 'BB' else F(0)) for p in pos}
        if any(F(S) - h['stack'][p] != exp[p] for p in pos):
            err(f'N={n}: hand-start deductions')
        if sum(h['ante'].values()) != 1:
            err(f'N={n}: total ante != 1')
        r['2_initial_pot'] = str(pot(h))
        if pot(h) != F(5, 2):
            err(f'N={n}: initial pot {pot(h)}')
        for p in pos[:n - 4]:
            act(h, p, 'fold')
        r['3_pot_after_folds'] = str(pot(h))
        if pot(h) != F(5, 2):
            err(f'N={n}: pot changed by folds')
        c = continuation(n, S)
        surv = ['CO', 'BTN', 'SB', 'BB']
        r['4_survivor_stacks'] = {p: str(h['stack'][p]) for p in surv}
        if any(h['stack'][p] != c['stack'][p] for p in surv) or pot(h) != pot_c(c):
            err(f'N={n}: full game vs continuation at CO')
        r['5_to_call_CO'] = str(to_call(h, 'CO'))
        r['5_min_raise_to'] = str(min_raise_to(h))
        if to_call(h, 'CO') != 1 or min_raise_to(h) != 2 or to_call(c, 'CO') != 1 or min_raise_to(c) != 2:
            err(f'N={n}: ante leaked into call / min-raise')
        # 7: full game -> continuation along the node 6 and node 28 lines
        lines = {6: [('CO', 'fold'), ('BTN', 'fold'), ('SB', 'raise', 2.5), ('BB', 'call')],
                 28: [('CO', 'fold'), ('BTN', 'raise', 2), ('SB', 'fold'), ('BB', 'call')]}
        for node, line in lines.items():
            hh, cc = full_hand(n, S), continuation(n, S)
            for p in pos[:n - 4]:
                act(hh, p, 'fold')
            costs = []
            for a in line:
                before = hh['stack'][a[0]]
                act(hh, *a)
                act(cc, *a)
                costs.append(str(before - hh['stack'][a[0]]))
            live = [p for p in surv if p not in hh['folded']]
            r[f'7_node{node}'] = {'pot': str(pot(hh)), 'behind': {p: str(hh['stack'][p]) for p in live}, 'action_costs': costs}
            if pot(hh) != pot_c(cc) or any(hh['stack'][p] != cc['stack'][p] for p in surv):
                err(f'N={n} node {node}: full game vs continuation differ')
        res['N'][n] = r
    # 6: all-in edge cases (reference engine; the solver fails closed)
    e = full_hand(9, F(105, 100))
    res['6_allin_edge'] = {'N=9, S=1.05': {'BB_paid_ante': str(e['ante']['BB']), 'BB_paid_blind': str(e['live']['BB']), 'BB_behind': str(e['stack']['BB']),
                                          'note': 'BB all-in for less than the blind after its ante; GTOpen v1 (no side pots) must reject this config'}}
    tiny = full_hand(5, F(1, 10))
    res['6_allin_edge']['N=5, S=0.1'] = {'ante_paid': {p: str(v) for p, v in tiny['ante'].items()}, 'total_ante': str(sum(tiny['ante'].values())),
                                         'note': 'every seat all-in on its ante (0.1 < 0.2); total ante below 1 bb by construction'}
    if gtopen:
        g = {}
        tmp = tempfile.mkdtemp()
        for n in range(5, 10):
            cfg = continuation_config(n)
            cf = os.path.join(tmp, f'cfg{n}.json')
            json.dump(cfg, open(cf, 'w'))
            g[n] = {}
            for node, spec in SPEC.items():
                out = os.path.join(tmp, f't{n}_{node}.json')
                p = subprocess.run([BIN + '/t2_cont_terminal', cf, '10', spec, out], env={**os.environ, **ENV}, capture_output=True, text=True)
                if p.returncode:
                    err(f'GTOpen N={n} node {node}: {p.stderr[-300:]}')
                    continue
                t = json.load(open(out))
                ref = res['N'][n][f'7_node{node}']
                got = {'pot_bb': t['pot_bb'], 'behind': {pl['position']: pl['behind_bb'] for pl in t['players']}, 'invested': {pl['position']: pl['invested_bb'] for pl in t['players']}}
                g[n][node] = got
                if abs(t['pot_bb'] - float(F(ref['pot']))) > 1e-9 or any(abs(got['behind'][q] - float(F(v))) > 1e-9 for q, v in ref['behind'].items()):
                    err(f'GTOpen N={n} node {node}: tree {got} vs reference {ref}')
            # fail-closed edge: hand-start stack S = BB + ante -> cfg.stack = S - 1/N = BB (all-in for exactly the blind)
            bad = dict(cfg, stack=1.0)
            bf = os.path.join(tmp, f'bad{n}.json')
            json.dump(bad, open(bf, 'w'))
            p = subprocess.run([BIN + '/t2_cont_terminal', bf, '1', SPEC[6], os.path.join(tmp, 'x.json')], env={**os.environ, **ENV}, capture_output=True, text=True)
            g[n]['edge_stack_eq_bb_plus_ante_rejected'] = p.returncode != 0 and 'blind' in (p.stderr + p.stdout)
            if not g[n]['edge_stack_eq_bb_plus_ante_rejected']:
                err(f'GTOpen N={n}: config with stack = BB + ante was not rejected')
        res['gtopen_tree'] = g
    res['ok'] = not res['errors']
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['config', 'verify'])
    ap.add_argument('n', nargs='?', type=int)
    ap.add_argument('--base', default=BASE)
    ap.add_argument('--out')
    a = ap.parse_args()
    if a.cmd == 'config':
        c = continuation_config(a.n, a.base)
        out = a.out or os.path.join(ROOT, f'data/gto_hu_continuation/cfg_4h_mr4_30bb_ua{a.n}.json')
        json.dump(c, open(out, 'w'), indent=1)
        print(out)
        return
    r = verify()
    out = os.path.join(ROOT, 'data/gto_terminal_expansion/uniform_ante_verify.json')
    json.dump(r, open(out, 'w'), indent=1, default=str)
    print(json.dumps({'ok': r['ok'], 'errors': r['errors'], 'N9': r['N'][9], 'gtopen_N9': r.get('gtopen_tree', {}).get(9)}, indent=1, default=str))
    sys.exit(0 if r['ok'] else 1)


if __name__ == '__main__':
    main()
