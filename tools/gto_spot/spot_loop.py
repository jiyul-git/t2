#!/usr/bin/env python3
"""Verified-frequency pipeline for one heads-up spot (docs/GTO_VERIFIED_FREQUENCY_STANDARD_V1.md).

Local outer loop on the spot's own flop terminals, with the arriving ranges held at the parent preflop state (the dump):
  step k: solve the spot (hu_spot, CFR+) with tables V_k (static payoff where no table yet) -> terminal ranges -> panel_v1 flop
          solves (solve_panel.py) -> A4c tables V_raw,k -> D / U per terminal and seat (OL definitions) -> V_{k+1} = 0.5 V_k + 0.5 V_raw
          (a terminal without a previous solved table takes V_raw) -> next step.
  stop: step 0 always continues; from step 1 on, stop when every terminal-seat has D <= U; at most 3 steps (k = 0, 1, 2).
Then the final spot solve is graded per class (G2 exploitability, G3 D <= U, G4 static share, G5 EV gap vs u).

    python3 tools/gto_spot/spot_loop.py <spot.json> [k_start]
spot.json: hu_spot spec + "id"; work dir /home/user/gto_ckpt/spots/<id>/
"""
import hashlib
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'gto_validation'))
sys.path.insert(0, os.path.join(HERE, '..', 'gto_hu_continuation'))
import hu_spot as H  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PANEL = os.path.join(ROOT, 'data/gto_hu_continuation/panel_v1.json')
MENU = os.path.join(ROOT, 'data/gto_hu_continuation/menu_m2_single_v1.json')
ALPHA = 0.5
MAX_STEPS = 8   # rule v2 (standard amendment 1)


def atomic(o, p):
    json.dump(o, open(p + '.tmp', 'w'))
    os.replace(p + '.tmp', p)


def panel_setup():
    import a4c_run as C
    panel = json.load(open(PANEL))
    boards = [f['board'] for f in panel['panel']]
    draws = {}
    for f in panel['panel']:
        draws.setdefault(f['stratum'], []).append(f['board'])
    p = {s: v['probability'] for s, v in panel['strata'].items()}
    return C, boards, draws, p, C.compat_of(boards), panel


def board_values(flops_dir):
    _, boards, _, _, _, _ = panel_setup()
    out = {}
    for b in boards:
        d = json.load(open(os.path.join(flops_dir, b + '.json')))
        assert d['converged'] and d['exploitability_pct_pot'] <= 0.3, (flops_dir, b)
        out[b] = {pl['position']: [0.0 if x is None else x for x in pl['gross_eps']] for pl in d['players']}
    return out


def stratified(vals):
    C, boards, draws, p, compat, _ = panel_setup()
    ptot = sum(p.values())
    est, se = {}, {}
    for pos in vals[boards[0]]:
        e, u = [], []
        for h in range(169):
            tot, v2 = 0.0, 0.0
            for s, bs in draws.items():
                y = [compat[b][h] * vals[b][pos][h] for b in bs]
                m = sum(y) / len(y)
                tot += p[s] * m
                v2 += (p[s] / (ptot * C.RHO)) ** 2 * sum((x - m) ** 2 for x in y) / (len(y) - 1) / len(y)
            e.append(tot / ptot / C.RHO)
            u.append(math.sqrt(v2))
        est[pos], se[pos] = e, u
    return est, se


class Loop:
    def __init__(self, spec):
        self.spec = spec
        self.v3 = spec.get('rule') == 'v3'
        self.dir = f"/home/user/gto_ckpt/spots/{spec['id']}/"
        os.makedirs(self.dir, exist_ok=True)

    def spot(self, tables, matrices=None):
        sp = H.Spot(self.spec)
        for line, tab in tables.items():
            sp.tables[line] = tab
        for line, m in (matrices or {}).items():
            sp.matrices[line] = {int(seat): np.array([[np.nan if x is None else x for x in row] for row in mm]) for seat, mm in m.items()}
        sp.root()
        sp.build()
        sp.solve(self.spec.get('iterations', 3000))
        return sp

    def terminals(self, sp):
        """flop terminals of the spot with each live seat's arriving class reach under the spot's average strategy"""
        out = {}

        def rec(i, reach):
            node = sp.nodes[i]
            s = sp.avg[i]
            for a, ch in enumerate(node['children']):
                r2 = {k: v.copy() for k, v in reach.items()}
                r2[node['actor']] = reach[node['actor']] * s[a]
                if ch[0] == 'node':
                    rec(ch[1], r2)
                elif ch[0] == 'flop':
                    out[ch[1]] = {'state': ch[2], 'pot': ch[3], 'reach': r2}
        rec(sp.root_idx, {k: v.copy() for k, v in sp.reach0.items()})
        return out

    def term_json(self, sp, line, t):
        prior = np.array([H.combos(l) / 1326 for l in sp.lab169])
        st = t['state']
        to = max(st['invested'][p] for p in sp.live) - sp.ante
        players = []
        for p in sp.live:
            keep = (t['reach'][p] / prior).tolist()
            players.append({'seat': p, 'position': sp.pos[p], 'class_keep_fraction': keep, 'invested_bb': st['invested'][p]})
        hsh = hashlib.sha256(json.dumps([pl['class_keep_fraction'] for pl in players]).encode()).hexdigest()[:16]
        aggr = None
        for item in line.split('|'):
            pos, k = item.split(':')[0], item.split(':')[1].split('@')[0]
            if k in ('raise', 'jam'):
                aggr = pos
        extra = {}
        if self.v3 and self.is_matrix_line(line):
            extra['matrix_opp_classes'] = {sp.pos[q]: [j for j in range(169) if sp.reach0[q][j] > 0] for q in sp.live}
        return {**extra, 'schema': 'spot_terminal_v1', 'line': line, 'players': players, 'pot_bb': t['pot'],
                'effective_behind_bb': sp.stack - to, 'path_spec': line, 'aggressor': aggr, 'ranges_hash_fnv1a64': hsh,
                'terminal_live_mask': sum(1 << p for p in sp.live), 'reach_probability': float(np.prod([t['reach'][p].sum() for p in sp.live]))}

    @staticmethod
    def is_matrix_line(line):
        """rule v3: range-reactive matrices for 3-bet-or-larger pots (two or more raises on the line)"""
        return sum(1 for it in line.split('|') if ':raise@' in it) >= 2

    def matrix_from(self, fd, sp):
        C, boards, draws, p, compat, _ = panel_setup()
        wb = {b: p[s_] / len(bs) for s_, bs in draws.items() for b in bs}
        num, den = {}, {}
        for b in boards:
            d = json.load(open(os.path.join(fd, b + '.json')))
            c = np.array(compat[b])
            cc = np.outer(c, c) * wb[b]
            for pl in d['matrix']['players']:
                pos = pl['position']
                m = np.array([[np.nan if x is None else x for x in row] for row in pl['matrix']])
                ok = ~np.isnan(m)
                num.setdefault(pos, np.zeros((169, 169)))
                den.setdefault(pos, np.zeros((169, 169)))
                num[pos][ok] += (cc * np.where(ok, m, 0))[ok]
                den[pos][ok] += cc[ok]
        return {pos: np.where(den[pos] > 0, num[pos] / np.where(den[pos] > 0, den[pos], 1), np.nan) for pos in num}

    def run(self, k_start=0):
        state = self.load_state()
        state.setdefault('matrices', {})
        max_steps = 6 if self.v3 else MAX_STEPS
        for k in range(k_start, max_steps):
            sd = self.dir + f'step{k}/'
            os.makedirs(sd, exist_ok=True)
            sp = self.spot(state['tables'], state['matrices'])
            terms = self.terminals(sp)
            atomic(state['tables'], sd + 'tables_used.json')
            atomic(state['matrices'], sd + 'matrices_used.json')
            atomic({'exploitability': sp.exploitability(), 'nodes': sp.report(), 'class_labels': sp.lab169,
                    'live': [sp.pos[p] for p in sp.live], 'tables_used': sorted(state['tables'])}, sd + 'spot.json')
            rep = {'k': k, 'terminals': {}, 'rule': 'v3' if self.v3 else 'v2'}
            new_tables = {}
            new_matrices = dict(state['matrices'])
            for j, (line, t) in enumerate(sorted(terms.items())):
                tj = self.term_json(sp, line, t)
                tf = sd + f'term{j}.json'
                json.dump(tj, open(tf, 'w'))
                fd = sd + f'term{j}_flops'
                is_m = self.v3 and self.is_matrix_line(line)
                if not os.path.exists(fd + '/done'):
                    env = dict(os.environ)
                    if is_m:
                        env.update({'T2_PANEL_MATRIX': '1', 'T2_BIN_DIR': '/home/user/gto_ckpt/target_multi/release/examples'})
                    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/gto_hu_continuation/solve_panel.py'), tf, MENU, PANEL, fd,
                                    '--workers', '4', '--threads', '1'], check=True, stdout=open(sd + 'solve.log', 'a'), stderr=subprocess.STDOUT, env=env)
                    open(fd + '/done', 'w').write('ok')
                bv = board_values(fd)
                raw, se = stratified(bv)
                Mraw = self.matrix_from(fd, sp) if is_m else None
                prior = np.array([H.combos(l) for l in sp.lab169])
                cur = state['tables'].get(line)
                seats = {}
                for pl in tj['players']:
                    pos = pl['position']
                    w = prior * np.array(pl['class_keep_fraction'])
                    W = w.sum()
                    U = float((w * np.array(se[pos])).sum() / W)
                    if is_m:
                        # value at the current ranges: new matrix x current opponent distribution vs what the step-k spot used
                        q = [x for x in sp.live if sp.pos[x] != pos][0]
                        dist = t['reach'][q] / t['reach'][q].sum()
                        Mr = Mraw[pos]
                        use = dist > 0
                        g_new = Mr[:, use] @ dist[use]
                        g_used = sp.gross_at(line, ('flop', line, t['state'], t['pot']), pl['seat'], dist)
                        D = float((w * np.abs(g_new - g_used)).sum() / W)
                        sg = float((w * (g_new - g_used)).sum() / W)
                        cons = float((w * np.abs(g_new - np.array(raw[pos]))).sum() / W)
                    elif cur is not None and cur.get('provenance', {}).get('kind', '').startswith('spot'):
                        g = {s['position']: np.array(s['gross']) for s in cur['seats']}[pos]
                        D = float((w * np.abs(np.array(raw[pos]) - g)).sum() / W)
                        sg = float((w * (np.array(raw[pos]) - g)).sum() / W)
                        cons = None
                    else:
                        D, sg, cons = None, None, None
                    seats[pos] = {'D': D, 'signed': sg, 'U': U, 'pass': (D is not None and D <= U),
                                  'matrix_vs_table_at_solve_ranges': cons}
                rep['terminals'][line] = {'term': j, 'seats': seats, 'prev': (cur or {}).get('provenance', {}).get('kind', 'static')}
                # damped update (only against a previous spot-solved table; otherwise the raw table)
                tab = {'schema': 't2_hu_continuation_table_v1', 'line': line, 'live': tj['terminal_live_mask'], 'pot_bb': tj['pot_bb'],
                       'value_convention': 'gross_share', 'zero_reach_definition': 'eps_tremble_avg', 'seats': [],
                       'se': {pos: se[pos] for pos in se},
                       'provenance': {'kind': f'spot {self.spec["id"]} step {k}', 'raw_from': fd}}
                # rule v2: undamped when every seat's signed change keeps the sign of the previous step (monotone drift)
                prev_rep = self.dir + f'step{k - 1}/report.json'
                alpha = ALPHA
                if os.path.exists(prev_rep) and all(seats[p]['signed'] is not None for p in seats):
                    pr = json.load(open(prev_rep))['terminals'].get(line, {}).get('seats', {})
                    if pr and all(pr.get(p, {}).get('signed') is not None and pr[p]['signed'] * seats[p]['signed'] > 0 for p in seats):
                        alpha = 1.0
                rep['terminals'][line]['alpha'] = alpha
                for pl in tj['players']:
                    pos = pl['position']
                    r = np.array(raw[pos])
                    if cur is not None and cur.get('provenance', {}).get('kind', '').startswith('spot'):
                        g = {s['position']: np.array(s['gross']) for s in cur['seats']}[pos]
                        r = (1 - alpha) * g + alpha * r
                    tab['seats'].append({'seat': pl['seat'], 'position': pos, 'gross': r.tolist()})
                if is_m:
                    rep['terminals'][line]['mode'] = 'matrix'
                    new_matrices[line] = {str(pl['seat']): [[None if np.isnan(x) else float(x) for x in row] for row in Mraw[pl['position']]]
                                          for pl in tj['players']}
                    tab['provenance']['kind'] += ' (matrix terminal; table kept for SE / reference)'
                new_tables[line] = tab
            all_pass = all(s['pass'] for t in rep['terminals'].values() for s in t['seats'].values())
            rep['all_pass'] = all_pass
            if k == 0:
                rep['decision'] = 'continue (minimum one update)'
            elif all_pass:
                rep['decision'] = 'stop: converged at panel_v1 resolution (value space); step-k tables accepted'
            elif k + 1 >= MAX_STEPS:
                rep['decision'] = f'stop: not converged after {MAX_STEPS} steps'
            else:
                rep['decision'] = 'continue'
            atomic(rep, sd + 'report.json')
            print(json.dumps({'k': k, 'decision': rep['decision'], 'terminals': {l[-60:]: {p: (s['D'], round(s['U'], 3)) for p, s in t['seats'].items()} for l, t in rep['terminals'].items()}}), flush=True)
            if rep['decision'].startswith('stop'):
                state['final_step'] = k
                state['converged'] = all_pass and k > 0
                if all_pass and k > 0:
                    # accepted tables: the step-k tables (D <= U against them); keep them, do not apply the k update
                    pass
                else:
                    state['tables'] = new_tables
                    state['matrices'] = new_matrices
                self.save_state(state)
                break
            state['tables'] = new_tables
            state['matrices'] = new_matrices
            state['k'] = k + 1
            self.save_state(state)
        return state

    def load_state(self):
        f = self.dir + 'state.json'
        if os.path.exists(f):
            return json.load(open(f))
        return {'k': 0, 'tables': {}}

    def save_state(self, st):
        atomic(st, self.dir + 'state.json')


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    L = Loop(spec)
    k0 = int(sys.argv[2]) if len(sys.argv) > 2 else L.load_state().get('k', 0)
    st = L.run(k0)
    print('final', st.get('final_step'), 'converged', st.get('converged'))
