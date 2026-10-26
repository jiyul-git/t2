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
PANEL_V1 = PANEL
P144_PANEL = os.path.join(ROOT, 'data/gto_hu_continuation/panel_v3_144.json')
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


def retry_flops(term_file, flops_dir, panel, is_m, bad):
    """amendment 11 (a), CFR+ variant (docs/GTO_AMENDMENT_CFRPLUS_RETRY.md): one retry with T2_ALGO=cfr+ at the same iteration budget and
    target for each unconverged board; the first (DCFR) artifact is kept"""
    os.makedirs(os.path.join(flops_dir, 'first_attempt'), exist_ok=True)
    procs = []   # the retries run in parallel (one thread each): a single 3x retry can take longer than the 2 h task limit
    for b in bad:
        src = os.path.join(flops_dir, b['board'] + '.json')
        first = os.path.join(flops_dir, 'first_attempt', b['board'] + '.json')
        if os.path.exists(first) and os.path.exists(src):
            continue   # already retried once (e.g. the P144 pass whose flops step 0 of the 144-board loop reuses)
        if not os.path.exists(first):
            os.replace(src, first)
        # else: a retry killed by a relaunch (first attempt moved, no retry artifact): run it again
        target = json.load(open(first))['provenance_key']['target_exploitability_pct_pot']   # same target as the first attempt
        env = dict(os.environ, T2_PANEL_BOARDS=b['board'], RAYON_NUM_THREADS='1', T2_ALGO='cfr+',
                   T2_SOURCE_COMMIT=subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip())
        if is_m:
            env['T2_PANEL_MATRIX'] = '1'
        procs.append(subprocess.Popen([os.path.join(ROOT, 'vendor/gtopen/target/release/examples/t2_cont_panel'), term_file, MENU, panel, flops_dir,
                        str(b['iterations']), str(target), '25'], env=env,
                       stdout=open(os.path.join(flops_dir, 'logs', b['board'] + '.retry.log'), 'w'), stderr=subprocess.STDOUT))
    for p_ in procs:
        if p_.wait() != 0:
            raise subprocess.CalledProcessError(p_.returncode, p_.args)
    return flop_failures(flops_dir)


def terminal_exempt_level(sp, t):
    """amendment 11 (b): either live seat arrives at the terminal with < 1 combo"""
    return min(float(t['reach'][q].sum() * 1326) for q in sp.live) < 1.0


def flop_failures(flops_dir):
    """boards whose solve ended unconverged at the iteration budget (standard amendment 7)"""
    _, boards, _, _, _, _ = panel_setup()
    bad = []
    for b in boards:
        f = os.path.join(flops_dir, b + '.json')
        if not os.path.exists(f) and os.path.exists(os.path.join(flops_dir, 'first_attempt', b + '.json')):
            f = os.path.join(flops_dir, 'first_attempt', b + '.json')   # retry interrupted: still counts as unconverged
        d = json.load(open(f))
        if not (d['converged'] and d['exploitability_pct_pot'] <= d['provenance_key']['target_exploitability_pct_pot'] <= 0.6):
            bad.append({'board': b, 'exploitability_pct_pot': d['exploitability_pct_pot'], 'iterations': d['iterations']})
    return bad


def board_values(flops_dir, allow=()):
    _, boards, _, _, _, _ = panel_setup()
    out = {}
    for b in boards:
        d = json.load(open(os.path.join(flops_dir, b + '.json')))
        assert b in allow or d['converged'] and d['exploitability_pct_pot'] <= d['provenance_key']['target_exploitability_pct_pot'] <= 0.6, (flops_dir, b)
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
        self.v4 = spec.get('rule') == 'v4'
        self.v3 = spec.get('rule') in ('v3', 'v4')   # v4 = v3 with damped matrices (standard amendment 6)
        self.dir = f"/home/user/gto_ckpt/spots/{spec['id']}/"
        self.state_file = 'state.json'
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

    def run(self, k_start=0, p144=False):
        # p144 = standard amendment 10: after an inconsistent P144 the v4 loop continues on panel_v3_144 from the 24-board
        # converged state; step 0 is the P144 pass itself (its flops are reused), at most 3 further steps, criterion D <= U144.
        global PANEL
        if p144:
            PANEL = P144_PANEL
            self.state_file = 'state.json'      # the 24-board converged state
            st24 = self.load_state()
            fk = st24['final_step']
            self.state_file = 'state_p144.json'
            if not os.path.exists(self.dir + self.state_file):
                self.save_state({'k': 0, 'tables': st24['tables'], 'matrices': st24.get('matrices', {}), 'from_step': fk})
        state = self.load_state()
        state.setdefault('matrices', {})
        max_steps = 4 if p144 else (self.spec.get('max_steps') or (12 if self.v4 else (6 if self.v3 else MAX_STEPS)))   # quick spots cap the loop
        for k in range(k_start, max_steps):
            sd = self.dir + (f'p144s{k}/' if p144 else f'step{k}/')
            os.makedirs(sd, exist_ok=True)
            sp = self.spot(state['tables'], state['matrices'])
            terms = self.terminals(sp)
            atomic(state['tables'], sd + 'tables_used.json')
            atomic(state['matrices'], sd + 'matrices_used.json')
            atomic({'exploitability': sp.exploitability(), 'nodes': sp.report(), 'class_labels': sp.lab169,
                    'live': [sp.pos[p] for p in sp.live], 'tables_used': sorted(state['tables'])}, sd + 'spot.json')
            rep = {'k': k, 'terminals': {}, 'rule': 'v4' if self.v4 else ('v3' if self.v3 else 'v2')}
            new_tables = {}
            new_matrices = dict(state['matrices'])
            for j, (line, t) in enumerate(sorted(terms.items())):
                tj = self.term_json(sp, line, t)
                tf = sd + f'term{j}.json'
                json.dump(tj, open(tf, 'w'))
                fd = sd + f'term{j}_flops'
                is_m = self.v3 and self.is_matrix_line(line)
                if p144:
                    if k == 0:   # the P144 pass solved these 144 boards at exactly these ranges
                        fd = self.dir + f"step{state['from_step']}/term{j}_flops"
                        assert json.load(open(self.dir + f"step{state['from_step']}/term{j}.json"))['ranges_hash_fnv1a64'] == tj['ranges_hash_fnv1a64']
                    elif not os.path.exists(fd + '/done144'):
                        env = dict(os.environ)
                        if is_m:
                            env.update({'T2_PANEL_MATRIX': '1', 'T2_BIN_DIR': os.path.join(ROOT, 'vendor/gtopen/target/release/examples')})
                        w_ = os.environ.get('SPOT_PANEL_WORKERS', '4')
                        for extra in ([PANEL_V1], [P144_PANEL, '--exclude-origin', 'panel_v1', '--postflop', '1000', '0.6', '25']):
                            subprocess.run([sys.executable, os.path.join(ROOT, 'tools/gto_hu_continuation/solve_panel.py'), tf, MENU, extra[0], fd,
                                            *extra[1:], '--workers', w_, '--threads', '1'], check=True, stdout=open(sd + 'solve.log', 'a'),
                                           stderr=subprocess.STDOUT, env=env)
                        open(fd + '/done144', 'w').write('ok')
                elif not os.path.exists(fd + '/done'):
                    env = dict(os.environ)
                    if is_m:
                        env.update({'T2_PANEL_MATRIX': '1', 'T2_BIN_DIR': os.path.join(ROOT, 'vendor/gtopen/target/release/examples')})
                    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/gto_hu_continuation/solve_panel.py'), tf, MENU, PANEL, fd,
                                    '--workers', os.environ.get('SPOT_PANEL_WORKERS', '4'), '--threads', '1'], check=True, stdout=open(sd + 'solve.log', 'a'), stderr=subprocess.STDOUT, env=env)
                    open(fd + '/done', 'w').write('ok')
                bad = flop_failures(fd)
                if bad and self.v4:   # amendment 11 (a) CFR+ variant: one retry with CFR+ at the same budget
                    first = bad
                    bad = retry_flops(tf, fd, PANEL, is_m, first)
                    rep.setdefault('flop_retries', []).append({'terminal': j, 'first': first, 'after_retry': bad})
                allow = ()
                if bad and self.v4 and terminal_exempt_level(sp, t):   # amendment 11 (b): recorded, not stopping
                    rep.setdefault('flop_failures_exempt_terminal', []).append({'terminal': j, 'boards': bad})
                    rep['verdict_without_amendment11'] = 'research (amendment 7: unconverged flop)'
                    allow = {b['board'] for b in bad}
                    bad = []
                if bad:
                    rep['decision'] = f'stop: flop solver did not converge (terminal {j}, step {k}): {bad}'
                    rep['flop_failures'] = bad
                    atomic(rep, sd + 'report.json')
                    print(json.dumps({'k': k, 'decision': rep['decision']}), flush=True)
                    state['final_step'] = k
                    state['converged'] = False
                    state['stop_reason'] = rep['decision']
                    self.save_state(state)
                    return state
                bv = board_values(fd, allow)
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
                    q_ = [x for x in sp.live if sp.pos[x] != pos][0]
                    opp_mass = float(t['reach'][q_].sum() * 1326)
                    strict = (D is not None and D <= U)
                    exempt = self.v4 and opp_mass < 1.0   # standard amendment 8 (post-observation; user review)
                    seats[pos] = {'D': D, 'signed': sg, 'U': U, 'pass': strict or exempt, 'pass_strict': strict,
                                  'opp_arriving_combos': opp_mass, 'exempt': exempt,
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
                    Mnew = {}
                    for pl in tj['players']:
                        Mr = Mraw[pl['position']]
                        old = state['matrices'].get(line, {}).get(str(pl['seat']))
                        if self.v4 and k >= 1 and old is not None:
                            Mo = np.array([[np.nan if x is None else x for x in row] for row in old])
                            Mr = np.where(np.isnan(Mo), Mr, np.where(np.isnan(Mr), Mo, 0.5 * Mo + 0.5 * Mr))
                            rep['terminals'][line]['matrix_alpha'] = 0.5
                        Mnew[str(pl['seat'])] = [[None if np.isnan(x) else float(x) for x in row] for row in Mr]
                    new_matrices[line] = Mnew
                    tab['provenance']['kind'] += ' (matrix terminal; table kept for SE / reference)'
                new_tables[line] = tab
            all_pass = all(s['pass'] for t in rep['terminals'].values() for s in t['seats'].values())
            rep['all_pass'] = all_pass
            rep['all_pass_strict'] = all(s.get('pass_strict', s['pass']) for t in rep['terminals'].values() for s in t['seats'].values())
            if k == 0 and not p144:
                rep['decision'] = 'continue (minimum one update)'
            elif all_pass:
                rep['decision'] = 'stop: converged at panel_v1 resolution (value space); step-k tables accepted'
            elif k + 1 >= max_steps:
                rep['decision'] = f'stop: not converged after {max_steps} steps'
            else:
                rep['decision'] = 'continue'
            atomic(rep, sd + 'report.json')
            print(json.dumps({'k': k, 'decision': rep['decision'], 'terminals': {l[-60:]: {p: (s['D'], round(s['U'], 3)) for p, s in t['seats'].items()} for l, t in rep['terminals'].items()}}), flush=True)
            if rep['decision'].startswith('stop'):
                state['final_step'] = k
                state['converged'] = all_pass and k > 0
                state['converged_strict'] = rep['all_pass_strict'] and k > 0
                if p144:
                    state['converged'] = all_pass
                    state['converged_strict'] = rep['all_pass_strict']
                state['exempt_used'] = all_pass and not rep['all_pass_strict']
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
        f = self.dir + self.state_file
        if os.path.exists(f):
            return json.load(open(f))
        return {'k': 0, 'tables': {}}

    def save_state(self, st):
        atomic(st, self.dir + self.state_file)


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    L = Loop(spec)
    if '--p144' in sys.argv[2:]:
        # standard amendment 10: 144-board continuation after an inconsistent P144; the result replaces the grader's P144 inputs
        st24 = L.load_state()
        fk = st24['final_step']
        L.state_file = 'state_p144.json'
        k0 = L.load_state().get('k', 0) if os.path.exists(L.dir + L.state_file) else 0
        st = L.run(k0, p144=True)
        od = L.dir + f'step{fk}_p144/'
        os.makedirs(od, exist_ok=True)
        if os.path.exists(od + 'report.json') and not os.path.exists(od + 'report_p144_check.json'):
            os.replace(od + 'report.json', od + 'report_p144_check.json')
        last = st['final_step']
        rep = json.load(open(L.dir + f'p144s{last}/report.json'))
        atomic(json.load(open(L.dir + f'p144s{last}/tables_used.json')) if st.get('converged') else st['tables'], od + 'tables_used.json')
        atomic(json.load(open(L.dir + f'p144s{last}/matrices_used.json')) if st.get('converged') else st['matrices'], od + 'matrices_used.json')
        atomic({'k': fk, 'panel': 'panel_v3_144 (amendment-10 loop)', 'p144_loop_steps': last + 1,
                'consistent_with_24': bool(st.get('converged')), 'consistent_with_24_strict': bool(st.get('converged_strict')),
                'terminals': rep.get('terminals', {}), 'flop_failures': rep.get('flop_failures'),
                'decision': rep.get('decision'), 'note': 'criterion D <= U144 at each 144-board step (standard amendment 10)'},
               od + 'report.json')
        print('p144 loop final', last, 'converged', st.get('converged'))
    else:
        k0 = int(sys.argv[2]) if len(sys.argv) > 2 else L.load_state().get('k', 0)
        st = L.run(k0)
        print('final', st.get('final_step'), 'converged', st.get('converged'))
