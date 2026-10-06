#!/usr/bin/env python3
"""Exact heads-up spot solver (two-player zero-sum subgame of the 9-max preflop model).

Root: a decision node of the preflop tree where exactly two seats are still live (e.g. "UTG opens 2, all fold, BB to act").
Arriving class ranges come from a whole-tree dump (t2_tree_dump) of a solved preflop state. Below the root the betting tree is
rebuilt with the engine's own rules (legal_actions_of / next_state_of: raise sizes, jam threshold, max_raises, invested = to + ante),
and checked against the dump's action lists. Terminals:
  fold      exact chips;
  flop      solved continuation table (gross share, looked up by canonical action line) or, without a table, the engine's static
            HU payoff min(pot x eq x r, pot), r = 1 + 0.16 * frac * min(spr, 8) / 8;
  all-in    pot x equity (exact, the solver's own class equity table).
Class-level like the engine (no card removal between the two players). Solved by CFR+ (alternating, linear averaging); the
exploitability of the average profile is computed exactly by best response in the same subgame.

    python3 tools/gto_spot/hu_spot.py <spot.json>     (see SPOT_EXAMPLE)
"""
import json
import math
import sys

import numpy as np

NC = 169
SPOT_EXAMPLE = {
    'config': '/home/user/gto_ckpt/step3/j/cfg_mr3_jam.json',
    'dump': '/home/user/gto_ckpt/step3/j/J_dump.jsonl',
    'tables_dir': '/home/user/gto_ckpt/step3/j/mr3_resolved',
    'equity': '/home/user/gto_ckpt/step3/eq_table_202_1200.json',
    'root_line': ['UTG:Raise 2', 'UTG+1:Fold', 'UTG+2:Fold', 'LJ:Fold', 'HJ:Fold', 'CO:Fold', 'BTN:Fold', 'SB:Fold'],
    'iterations': 4000,
    'out': '/home/user/gto_ckpt/spots/utg_bb.json',
}


def combos(lab):
    return 6 if len(lab) == 2 else (4 if lab[2] == 's' else 12)


def kind_of(label):
    if label == 'Fold':
        return 'fold'
    if label == 'Check':
        return 'check'
    if label.startswith('Call'):
        return 'call'
    if label.startswith('All-in'):
        return 'jam'
    return 'raise'


def amount_of(label):
    return float(label.split()[-1]) if kind_of(label) not in ('fold', 'check') else 0.0


def trim(x):
    return ('%f' % x).rstrip('0').rstrip('.')


class Spot:
    def __init__(self, spec):
        self.spec = spec
        self.cfg = json.load(open(spec['config']))
        self.EQ = np.array(json.load(open(spec['equity']))['eq'], dtype=np.float64)
        self.pos = self.cfg['positions']
        self.n = len(self.pos)
        self.ante = self.cfg['ante']
        self.stack = self.cfg['stack']
        self.load_dump()
        self.load_tables()

    # ---------- inputs ----------
    def load_dump(self):
        self.d = {}
        for line in open(self.spec['dump']):
            r = json.loads(line)
            self.d[tuple(r['path'])] = r
        any_r = next(iter(self.d.values()))
        self.labels = None

    def load_tables(self):
        man = json.load(open(self.spec['tables_dir'] + '/manifest.json'))
        self.tables = {}
        for t in man['tables']:
            tab = json.load(open(self.spec['tables_dir'] + '/' + t['file']))
            self.tables[tab['line']] = tab

    # ---------- engine rules ----------
    def mults_of(self, actor, raises):
        if raises >= 2:
            per = self.cfg.get('fourbet_mults_by_seat')
            if per and per[actor]:
                return per[actor]
            if self.cfg.get('fourbet_mults'):
                return self.cfg['fourbet_mults']
        per = self.cfg.get('raise_mults_by_seat')
        if per and per[actor]:
            return per[actor]
        return self.cfg['raise_mults']

    def legal(self, st, actor):
        acts = []
        owed = max(st['to_call'] - (st['invested'][actor] - self.ante), 0.0)
        if owed > 1e-9:
            acts.append(('fold', 0.0, 'Fold'))
            if st['raises'] > 0 or self.cfg.get('limp'):
                acts.append(('call', st['to_call'], ('Call ' if st['raises'] > 0 else 'Limp ') + trim(st['to_call'])))
        else:
            acts.append(('check', st['to_call'], 'Check'))
        if st['raises'] < self.cfg['max_raises'] and actor not in self.cfg.get('call_only_seats', []):
            if st['raises'] == 0:
                per = self.cfg.get('open_raises_by_seat')
                tos = list(per[actor] if per and per[actor] else self.cfg['open_raises'])
            else:
                tos = [max(st['to_call'] * m, st['to_call'] + st['last_raise']) for m in self.mults_of(actor, st['raises'])]
            if self.cfg['add_allin']:
                tos.append(self.stack)
            seen = []
            for to in tos:
                if to >= self.cfg['allin_threshold'] * self.stack:
                    to = self.stack
                if to <= st['to_call'] + 1e-9 or any(abs(x - to) < 1e-9 for x in seen):
                    continue
                seen.append(to)
                jam = abs(to - self.stack) < 1e-9
                lab = ('All-in ' + trim(to)) if jam else (f"{st['raises'] + 2}-bet {trim(to)}" if st['raises'] > 0 else 'Raise ' + trim(to))
                acts.append(('jam' if jam else 'raise', to, lab))
        return acts

    def apply(self, st, actor, act):
        kind, to, _ = act
        ns = {**st, 'invested': list(st['invested']), 'folded': set(st['folded'])}
        if kind == 'fold':
            ns['folded'].add(actor)
        elif kind in ('call', 'check'):
            ns['invested'][actor] = st['to_call'] + self.ante
        else:
            ns['invested'][actor] = to + self.ante
            ns['last_raise'] = to - st['to_call']
            ns['to_call'] = to
            ns['raises'] = st['raises'] + 1
        return ns

    # ---------- root from the dump ----------
    def root(self):
        root_line = self.spec['root_line']
        st = {'invested': [self.cfg['posts'][i] + self.ante for i in range(self.n)], 'folded': set(), 'to_call': max(self.cfg['posts']),
              'last_raise': max(self.cfg['posts']), 'raises': 0}
        path = ()
        reach = None
        lab169 = None
        canon = []
        for i, item in enumerate(root_line):
            actor_name, label = item.split(':', 1)
            r = self.d[path]
            assert r['actor'] == actor_name, (item, r['actor'])
            if reach is None:
                lab169 = self.class_labels()
                prior = np.array([combos(l) / 1326 for l in lab169])
                reach = {p: prior.copy() for p in range(self.n)}
            a = r['actions'].index(label)
            actor = r['actor_seat']
            mine = [x[2] for x in self.legal(st, actor)]
            assert mine == r['actions'], (item, mine, r['actions'])
            reach[actor] = reach[actor] * np.array(r['sigma'][a])
            act = self.legal(st, actor)[a]
            canon.append(self.canon_item(actor, act))
            st = self.apply(st, actor, act)
            path = path + (a,)
        live = [p for p in range(self.n) if p not in st['folded']]
        assert len(live) == 2, live
        r = self.d[path]
        self.root_path = path
        self.root_state = st
        self.root_canon = canon
        self.live = live
        self.first = r['actor_seat']
        self.reach0 = {p: reach[p] for p in live}
        self.lab169 = lab169
        return r

    def class_labels(self):
        ranks = '23456789TJQKA'
        out = []
        for i in range(13):
            for j in range(13):
                hi, lo = max(i, j), min(i, j)
                if i == j:
                    out.append(ranks[i] * 2)
                elif j > i:
                    out.append(ranks[hi] + ranks[lo] + 'o')
                else:
                    out.append(ranks[hi] + ranks[lo] + 's')
        return out

    def canon_item(self, actor, act):
        kind, to, _ = act
        s = f'{self.pos[actor]}:{kind}'
        if kind in ('raise', 'call', 'jam'):
            s += f'@{to:.6f}'
        return s

    # ---------- subgame tree ----------
    def build(self):
        self.nodes = []

        def rec(st, actor, canon, path, depth):
            acts = self.legal(st, actor)
            other = self.live[0] if actor == self.live[1] else self.live[1]
            node = {'actor': actor, 'acts': acts, 'children': [], 'path': path}
            dr = self.d.get(path)
            if dr is not None:
                assert dr['actions'] == [x[2] for x in acts], (path, dr['actions'], acts)
                node['dump'] = dr
            idx = len(self.nodes)
            self.nodes.append(node)
            for ai, act in enumerate(acts):
                ns = self.apply(st, actor, act)
                c2 = canon + [self.canon_item(actor, act)]
                if act[0] == 'fold':
                    node['children'].append(('fold', other, ns))
                elif act[0] in ('call', 'check'):
                    pot = sum(ns['invested']) + self.cfg.get('dead_money', 0.0)
                    allin = abs(st['to_call'] - self.stack) < 1e-9
                    line = '|'.join(c2)
                    node['children'].append(('allin' if allin else 'flop', line, ns, pot))
                else:
                    node['children'].append(('node', rec(ns, other, c2, path + (ai,), depth + 1)))
            return idx

        self.root_idx = rec(self.root_state, self.first, self.root_canon, self.root_path, 0)

    # ---------- payoffs ----------
    def r_weight(self, ns, pot, p):
        min_left = min(self.stack - ns['invested'][q] + self.ante for q in self.live)
        spr = max(min_left / pot, 0.0)
        if spr <= 1e-9:
            return 1.0
        blinds = sorted([i for i in range(self.n) if self.cfg['posts'][i] > 0], key=lambda i: self.cfg['posts'][i])
        order = blinds + [i for i in range(self.n) if i not in blinds]
        lo = [s for s in order if s in self.live]
        rank = lo.index(p)
        frac = rank / (len(lo) - 1) - 0.5
        return 1.0 + 0.16 * frac * (min(spr, 8.0) / 8.0)

    def term_value(self, ch, p, opp_reach):
        """per-class value for seat p times opponent reach mass (counterfactual convention)"""
        q = self.live[0] if p == self.live[1] else self.live[1]
        mass = opp_reach.sum()
        if mass <= 0:
            return np.zeros(NC)
        if ch[0] == 'fold':
            winner, ns = ch[1], ch[2]
            pot = sum(ns['invested']) + self.cfg.get('dead_money', 0.0)
            v = (pot - ns['invested'][p]) if winner == p else -ns['invested'][p]
            return np.full(NC, v * mass)
        kind, line, ns, pot = ch
        dist = opp_reach / mass
        if kind == 'flop' and line in self.tables:
            tab = self.tables[line]
            assert abs(tab['pot_bb'] - pot) < 1e-9, (line, tab['pot_bb'], pot)
            g = {s['seat']: np.array(s['gross']) for s in tab['seats']}[p]
            return (g - ns['invested'][p]) * mass
        eq = self.EQ @ dist
        if kind == 'allin':
            return (pot * eq - ns['invested'][p]) * mass
        r = self.r_weight(ns, pot, p)
        return (np.minimum(pot * eq * r, pot) - ns['invested'][p]) * mass

    # ---------- CFR+ ----------
    def solve(self, iters):
        na = [len(n['acts']) for n in self.nodes]
        self.reg = [np.zeros((k, NC)) for k in na]
        self.ssum = [np.zeros((k, NC)) for k in na]
        for t in range(1, iters + 1):
            for p in self.live:
                reach = {q: self.reach0[q].copy() for q in self.live}
                self.cfr(self.root_idx, p, reach, t)
        self.avg = []
        for k, s in zip(na, self.ssum):
            z = s.sum(0, keepdims=True)
            self.avg.append(np.where(z > 0, s / np.where(z > 0, z, 1), 1.0 / k))

    def strat(self, i):
        r = np.maximum(self.reg[i], 0)
        z = r.sum(0, keepdims=True)
        return np.where(z > 0, r / np.where(z > 0, z, 1), 1.0 / r.shape[0])

    def cfr(self, i, p, reach, t):
        node = self.nodes[i]
        actor = node['actor']
        q = self.live[0] if p == self.live[1] else self.live[1]
        s = self.strat(i)
        vals = []
        for a, ch in enumerate(node['children']):
            r2 = {k: v.copy() for k, v in reach.items()}
            r2[actor] = reach[actor] * s[a]
            if ch[0] == 'node':
                vals.append(self.cfr(ch[1], p, r2, t))
            else:
                vals.append(self.term_value(ch, p, r2[q]))
        vals = np.array(vals)
        if actor == p:
            v = (s * vals).sum(0)
            self.reg[i] = np.maximum(self.reg[i] + (vals - v), 0)
            self.ssum[i] += t * s * reach[p]
            return v
        return vals.sum(0)

    # ---------- evaluation ----------
    def value(self, i, p, reach, br):
        node = self.nodes[i]
        actor = node['actor']
        q = self.live[0] if p == self.live[1] else self.live[1]
        s = self.avg[i]
        vals = []
        for a, ch in enumerate(node['children']):
            r2 = {k: v.copy() for k, v in reach.items()}
            r2[actor] = reach[actor] * s[a]
            if ch[0] == 'node':
                vals.append(self.value(ch[1], p, r2, br))
            else:
                vals.append(self.term_value(ch, p, r2[q]))
        vals = np.array(vals)
        if actor == p:
            return vals.max(0) if br else (s * vals).sum(0)
        return vals.sum(0)

    def exploitability(self):
        out = {}
        for p in self.live:
            q = self.live[0] if p == self.live[1] else self.live[1]
            reach = {k: v.copy() for k, v in self.reach0.items()}
            norm = self.reach0[q].sum()
            ev = self.value(self.root_idx, p, reach, False) / norm
            br = self.value(self.root_idx, p, reach, True) / norm
            w = self.reach0[p] / self.reach0[p].sum()
            out[self.pos[p]] = {'ev': float(w @ ev), 'br': float(w @ br), 'gain': float(w @ (br - ev))}
        pot0 = sum(self.root_state['invested'])
        tot = sum(x['gain'] for x in out.values())
        return {'per_seat': out, 'total_bb': tot, 'pct_of_root_pot': 100 * tot / pot0}

    def report(self):
        nodes = []
        for i, node in enumerate(self.nodes):
            acts = [x[2] for x in node['acts']]
            rec = {'path': list(node['path']), 'actor': self.pos[node['actor']], 'actions': acts,
                   'avg_strategy': self.avg[i].tolist()}
            dr = node.get('dump')
            if dr is not None:
                rec['full_tree_sigma'] = dr['sigma']
                rr = np.array(dr['actor_reach'])
                if rr.sum() > 0:
                    rec['mix_spot'] = {acts[a]: float((rr * self.avg[i][a]).sum() / rr.sum()) for a in range(len(acts))}
                    rec['mix_full_tree'] = {acts[a]: float((rr * np.array(dr['sigma'][a])).sum() / rr.sum()) for a in range(len(acts))}
            nodes.append(rec)
        return nodes


def main():
    spec = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else SPOT_EXAMPLE
    sp = Spot(spec)
    sp.root()
    sp.build()
    sp.solve(spec.get('iterations', 2000))
    ex = sp.exploitability()
    res = {'schema': 'hu_spot_v1', 'spec': spec, 'live': [sp.pos[p] for p in sp.live], 'n_nodes': len(sp.nodes),
           'terminals_with_table': sorted({ch[1] for n in sp.nodes for ch in n['children'] if ch[0] == 'flop' and ch[1] in sp.tables}),
           'terminals_static': sorted({ch[1] for n in sp.nodes for ch in n['children'] if ch[0] == 'flop' and ch[1] not in sp.tables}),
           'exploitability': ex, 'class_labels': sp.lab169, 'nodes': sp.report()}
    import os
    os.makedirs(os.path.dirname(spec['out']), exist_ok=True)
    json.dump(res, open(spec['out'], 'w'))
    print(json.dumps({'live': res['live'], 'n_nodes': res['n_nodes'], 'exploitability': ex,
                      'tables': len(res['terminals_with_table']), 'static_terminals': res['terminals_static']}, indent=1))
    for n in res['nodes']:
        if 'mix_spot' in n:
            print(n['actor'], n['path'][len(sp.root_path):], {k: (round(100 * v, 1), round(100 * n['mix_full_tree'][k], 1)) for k, v in n['mix_spot'].items()})


if __name__ == '__main__':
    main()
