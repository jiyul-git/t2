#!/usr/bin/env python3
"""Precision check of one quick HU spot (standard draft docs/GTO_PRECISION_PRIORITY_20261030.md section 3; runner doc docs/GTO_PRECISION_RUNNER.md).

    PREC_CALC_ROOT=/home/user/calc python3 tools/gto_precision/precision_loop.py <spot_id>

PREC_CALC_ROOT = a checkout of the spot's calculation branch (tools/gto_spot, tools/gto_hu_continuation, vendor/gtopen built with
`cargo build --release -p solver --features t2-cont --example t2_cont_panel`, the spec and the parent dump installed). This script never
touches the T2 runtime (gto_pf_data.json): it computes and records only.

Start: the 24-board loop's final state (state.json of the quick run: tables + matrices after its last step; PREC_START overrides the path).
PREC_START=fresh: a new spot without a quick run -> step 0 uses the static continuation and never passes (minimum one update), then the
precision rule from step 1; default PREC_MAX_STEPS 4 and no stage pause; not passed -> no record to connect.
Step k (work dir /home/user/gto_ckpt/precision/<id>/s<k>/):
  spot solve with the current tables -> terminal ranges -> every terminal solved on panel A (72) and panel B (72)
  (data/gto_precision/panels, pairwise disjoint and disjoint from panel_v1; same flop solver target as quick, CFR+ retry of
  unconverged flops = amendment 11 (a)) -> values from A, B and A u B (stratified estimator, matrices for 3-bet-or-larger pots).
  Pass (both):
   (1) every terminal-seat: D = weighted |V_AuB - V_used| <= U(144) = weighted se of A u B   (amendment 8 exemption recorded as in quick)
   (2) replication: every terminal-seat weighted |V_A - V_B| <= 2 sqrt(U_A^2 + U_B^2), AND the root strategy solved with A-only and with
       B-only values differs by <= 5 pp per class (max over actions) on >= 95 % of the root combos.
  pass -> precision state = the spot with the A u B values (as the P144 pass does); stop.
  fail -> next tables = (1 - a) T_k + a V_AuB, a = 0.5; a terminal whose D/U cycles (down then up, or up then down, while > 1) gets a = 0.25.
  At most PREC_MAX_STEPS = 3 steps; still failing -> `precision_failed` (the quick record stays in use; a mean of steps is never called precision).
PREC_STAGE_LIMIT (default 1) = how many steps this launch may run before it pauses for the coordinator's go (stage 1 = replication only).
Every step writes report.json; the grade (grade_spot.py rule + u_rep = |gap_A - gap_B| / 2) is written after every step to
data/gto_precision/records/<id>.json with status `precision` only when (1) and (2) pass.
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CALC = os.path.abspath(os.environ.get('PREC_CALC_ROOT', '/home/user/calc'))
for d in ('tools/gto_spot', 'tools/gto_validation', 'tools/gto_hu_continuation'):
    sys.path.insert(0, os.path.join(CALC, d))
import spot_loop as L  # noqa: E402
import hu_spot as H  # noqa: E402
import grade_spot as G  # noqa: E402

PANELS = os.environ.get('PREC_PANELS') or os.path.join(REPO, 'data/gto_precision/panels')
TEST = os.environ.get('PREC_TEST') == '1'   # plumbing test only: tiny panels / budgets, solver checks off, output under PREC_WORKDIR
PANEL_FILE = {'A': os.path.join(PANELS, 'panel_prec_A72.json'), 'B': os.path.join(PANELS, 'panel_prec_B72.json')}
MAX_STEPS = int(os.environ.get('PREC_MAX_STEPS', '3'))
ALPHA, ALPHA_CYCLE = 0.5, 0.25
FRESH = os.environ.get('PREC_START') == 'fresh'
if FRESH and 'PREC_MAX_STEPS' not in os.environ:
    MAX_STEPS = 4   # fresh spot: step 0 (static) + up to 3 precision updates; the coordinator may set PREC_MAX_STEPS
STAGE_LIMIT = int(os.environ.get('PREC_STAGE_LIMIT', str(MAX_STEPS) if FRESH else '1'))   # fresh spot: run to the end unless limited
ROOT_CLASS_PP = 0.05
ROOT_SHARE_MIN = 0.95
REACH_FLOOR = 1e-3
WORKERS = os.environ.get('SPOT_PANEL_WORKERS', '4')


def atomic(o, p):
    json.dump(o, open(p + '.tmp', 'w'))
    os.replace(p + '.tmp', p)


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def load_spec(sid):
    txt = open(os.path.join(CALC, 'data/gto_spot/plan_a/specs', sid + '.json')).read()
    spec = json.loads(txt.replace('/home/user/t2/', CALC + '/'))   # specs carry the calc checkout's absolute paths
    return spec


# ---------------- estimators over an explicit board set ----------------
_compat = {}


def compat(boards):
    import a4c_run as C
    miss = [b for b in boards if b not in _compat]
    if miss:
        _compat.update(C.compat_of(miss))
    return C, {b: _compat[b] for b in boards}


def panel_boards(names):
    """names: subset of ['A', 'B'] -> (board -> panel name), stratum -> boards, stratum probabilities"""
    owner, draws, prob = {}, {}, None
    for n in names:
        pj = json.load(open(PANEL_FILE[n]))
        prob = {s: v['probability'] for s, v in pj['strata'].items()}
        for f in pj['panel']:
            owner[f['board']] = n
            draws.setdefault(f['stratum'], []).append(f['board'])
    return owner, draws, prob


def stratified(vals, names):
    """same estimator as spot_loop.stratified, over the boards of the named panels"""
    owner, draws, p = panel_boards(names)
    C, cp = compat(list(owner))
    ptot = sum(p.values())
    est, se = {}, {}
    first = next(iter(owner))
    for pos in vals[first]:
        e, u = [], []
        for h in range(169):
            tot, v2 = 0.0, 0.0
            for s, bs in draws.items():
                y = [cp[b][h] * vals[b][pos][h] for b in bs]
                m = sum(y) / len(y)
                tot += p[s] * m
                v2 += (p[s] / (ptot * C.RHO)) ** 2 * sum((x - m) ** 2 for x in y) / (len(y) - 1) / len(y)
            e.append(tot / ptot / C.RHO)
            u.append(math.sqrt(v2))
        est[pos], se[pos] = e, u
    return est, se


def matrix_from(fds, names):
    """same ratio estimator as spot_loop.Loop.matrix_from, over the boards of the named panels (fds: panel -> flops dir)"""
    owner, draws, p = panel_boards(names)
    _, cp = compat(list(owner))
    wb = {b: p[s_] / len(bs) for s_, bs in draws.items() for b in bs}
    num, den = {}, {}
    for b, n in owner.items():
        d = json.load(open(os.path.join(fds[n], b + '.json')))
        c = np.array(cp[b])
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


def board_values(fd, panel, allow=()):
    pj = json.load(open(PANEL_FILE[panel]))
    out = {}
    for f in pj['panel']:
        b = f['board']
        d = json.load(open(os.path.join(fd, b + '.json')))
        assert TEST or b in allow or d['converged'] and d['exploitability_pct_pot'] <= d['provenance_key']['target_exploitability_pct_pot'] <= 0.6, (fd, b)
        out[b] = {pl['position']: [0.0 if x is None else x for x in pl['gross_eps']] for pl in d['players']}
    return out


def flop_solver_stats(fd, panel):
    pj = json.load(open(PANEL_FILE[panel]))
    ex, over = [], []
    for f in pj['panel']:
        d = json.load(open(os.path.join(fd, f['board'] + '.json')))
        ex.append(d['exploitability_pct_pot'])
        if d['exploitability_pct_pot'] > d['provenance_key']['target_exploitability_pct_pot']:
            over.append({'board': f['board'], 'exploitability_pct_pot': d['exploitability_pct_pot']})
    return {'max_pct_pot': max(ex), 'mean_pct_pot': sum(ex) / len(ex), 'above_target': over,
            'above_target_share': len(over) / len(ex)}


def mat_json(M):
    return [[None if np.isnan(x) else float(x) for x in row] for row in M]


# ---------------- the loop ----------------
class Prec:
    def __init__(self, sid):
        self.sid = sid
        self.spec = load_spec(sid)
        self.lp = L.Loop(self.spec)   # spot / terminals / term_json of the quick loop (rule v4); its own work dir is not written
        self.dir = os.environ.get('PREC_WORKDIR', '/home/user/gto_ckpt/precision') + f'/{sid}/'
        os.makedirs(self.dir, exist_ok=True)

    def load_state(self):
        f = self.dir + 'state.json'
        if os.path.exists(f):
            return json.load(open(f))
        commit = subprocess.run(['git', '-C', CALC, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        panels = json.load(open(os.path.join(PANELS, 'MANIFEST.json')))['files']
        if FRESH:   # new spot: no 24-board state; static continuation at step 0, then the precision panels from the start
            st = {'k': 0, 'tables': {}, 'matrices': {}, 'history': {}, 'fresh': True,
                  'start': {'file': None, 'mode': 'fresh (static continuation; precision panels from step 0)', 'calc_commit': commit}, 'panels': panels}
            self.save_state(st)
            return st
        src = os.environ.get('PREC_START') or os.path.join(CALC, 'data/gto_spot/plan_a/progress', self.sid, 'state.json')
        st24 = json.load(open(src))
        st = {'k': 0, 'tables': st24['tables'], 'matrices': st24.get('matrices', {}), 'history': {},
              'start': {'file': os.path.relpath(src, CALC) if src.startswith(CALC) else src, 'sha256': sha(src), 'mode': 'from the 24-board quick state',
                        'quick_final_step': st24.get('final_step'), 'quick_converged': st24.get('converged'), 'calc_commit': commit},
              'panels': panels}
        self.save_state(st)
        return st

    def save_state(self, st):
        atomic(st, self.dir + 'state.json')

    def solve_panel(self, tf, fd, panel, is_m, sp, t, sd):
        """flops of one terminal on one panel; returns the boards allowed above target (exempt terminal) or raises StopFail"""
        if not os.path.exists(fd + '/done'):
            env = dict(os.environ)
            if is_m:
                env.update({'T2_PANEL_MATRIX': '1', 'T2_BIN_DIR': os.path.join(CALC, 'vendor/gtopen/target/release/examples')})
            subprocess.run([sys.executable, os.path.join(CALC, 'tools/gto_hu_continuation/solve_panel.py'), tf, L.MENU, PANEL_FILE[panel], fd,
                            '--workers', WORKERS, '--threads', '1', *(['--postflop', *os.environ['PREC_POSTFLOP'].split()] if TEST else [])], check=True, stdout=open(sd + 'solve.log', 'a'), stderr=subprocess.STDOUT, env=env)
            open(fd + '/done', 'w').write('ok')
        L.PANEL = PANEL_FILE[panel]   # spot_loop.flop_failures / retry_flops read the panel from this global
        bad = [] if TEST else L.flop_failures(fd)
        info = {}
        if bad:   # amendment 11 (a): one CFR+ retry at the same budget and target
            first = bad
            bad = L.retry_flops(tf, fd, PANEL_FILE[panel], is_m, first)
            info['flop_retries'] = {'first': first, 'after_retry': bad}
        allow = ()
        if bad and L.terminal_exempt_level(sp, t):   # amendment 11 (b)
            info['flop_failures_exempt_terminal'] = bad
            allow = {b['board'] for b in bad}
            bad = []
        info['bad'] = bad
        return allow, info

    def run(self):
        st = self.load_state()
        k0 = st['k']
        for k in range(k0, MAX_STEPS):
            if st.get('final'):
                break
            if k - k0 >= STAGE_LIMIT:
                st['paused'] = f'paused after {k} step(s): PREC_STAGE_LIMIT={STAGE_LIMIT} (next step needs the coordinator go)'
                self.save_state(st)
                print(st['paused'], flush=True)
                return st
            st.pop('paused', None)
            sd = self.dir + f's{k}/'
            os.makedirs(sd, exist_ok=True)
            t0 = time.time()
            sp = self.lp.spot(st['tables'], st['matrices'])
            terms = self.lp.terminals(sp)
            atomic(st['tables'], sd + 'tables_used.json')
            atomic(st['matrices'], sd + 'matrices_used.json')
            atomic({'exploitability': sp.exploitability(), 'nodes': sp.report(), 'class_labels': sp.lab169,
                    'live': [sp.pos[p] for p in sp.live]}, sd + 'spot.json')
            rep = {'k': k, 'panels': st['panels'], 'terminals': {}, 'start': st['start']}
            raw = {'A': {}, 'B': {}, 'AB': {}}     # line -> (est, se) or matrices
            mats = {'A': {}, 'B': {}, 'AB': {}}
            failed = []
            for j, (line, t) in enumerate(sorted(terms.items())):
                tj = self.lp.term_json(sp, line, t)
                tf = sd + f'term{j}.json'
                if not os.path.exists(tf):
                    json.dump(tj, open(tf, 'w'))
                assert json.load(open(tf))['ranges_hash_fnv1a64'] == tj['ranges_hash_fnv1a64'], 'terminal ranges changed under a relaunch'
                is_m = self.lp.v3 and self.lp.is_matrix_line(line)
                fds = {n: sd + f'term{j}_{n}' for n in 'AB'}
                bv, allow, finfo = {}, set(), {}
                for n in 'AB':
                    al, info = self.solve_panel(tf, fds[n], n, is_m, sp, t, sd)
                    finfo[n] = {**info, 'solver': flop_solver_stats(fds[n], n)}
                    if info['bad']:
                        failed.append({'terminal': j, 'panel': n, 'boards': info['bad']})
                        continue
                    allow |= set(al)
                    bv.update(board_values(fds[n], n, al))
                rep['terminals'][line] = {'term': j, 'mode': 'matrix' if is_m else 'table', 'flops': finfo}
                if failed:
                    continue
                for key, names in (('A', ['A']), ('B', ['B']), ('AB', ['A', 'B'])):
                    raw[key][line] = stratified(bv, names)
                    if is_m:
                        mats[key][line] = matrix_from(fds, names)
                print(json.dumps({'k': k, 'terminal': j, 'line': line[-50:], 'min': round((time.time() - t0) / 60, 1)}), flush=True)
            if failed:   # amendment 7: an unconverged flop is never accepted silently -> precision failed, quick stays
                rep['flop_failures'] = failed
                rep['decision'] = 'precision_failed: flop solver did not converge after the CFR+ retry'
                atomic(rep, sd + 'report.json')
                st.update({'final': 'precision_failed', 'final_step': k, 'stop_reason': rep['decision']})
                self.save_state(st)
                self.grade(st, k, None)
                return st
            prior = np.array([H.combos(l) for l in sp.lab169])
            ok1, ok1_strict, ok2v = True, True, True
            for line, t in sorted(terms.items()):
                tr = rep['terminals'][line]
                tj = json.load(open(sd + f"term{tr['term']}.json"))
                seats = {}
                for pl in tj['players']:
                    pos = pl['position']
                    w = prior * np.array(pl['class_keep_fraction'])
                    W = w.sum()
                    q = [x for x in sp.live if sp.pos[x] != pos][0]
                    dist = t['reach'][q] / t['reach'][q].sum()
                    use = dist > 0
                    ch = ('flop', line, t['state'], t['pot'])
                    g_used = sp.gross_at(line, ch, pl['seat'], dist)
                    if tr['mode'] == 'matrix':
                        V = {n: mats[n][line][pos][:, use] @ dist[use] for n in ('A', 'B', 'AB')}
                    else:
                        V = {n: np.array(raw[n][line][0][pos]) for n in ('A', 'B', 'AB')}
                    U = {n: float((w * np.array(raw[n][line][1][pos])).sum() / W) for n in ('A', 'B', 'AB')}
                    D = float((w * np.abs(V['AB'] - g_used)).sum() / W)
                    sg = float((w * (V['AB'] - g_used)).sum() / W)
                    Drep = float((w * np.abs(V['A'] - V['B'])).sum() / W)
                    bound = 2 * math.sqrt(U['A'] ** 2 + U['B'] ** 2)
                    opp_mass = float(t['reach'][q].sum() * 1326)
                    exempt = opp_mass < 1.0   # amendment 8, as in the quick loop (rule v4)
                    p1 = D <= U['AB']
                    p2 = Drep <= bound
                    seats[pos] = {'D': D, 'signed': sg, 'U144': U['AB'], 'U_A': U['A'], 'U_B': U['B'], 'D_over_U': D / U['AB'] if U['AB'] > 0 else None,
                                  'rep_diff': Drep, 'rep_bound': bound, 'pass_D_le_U': p1 or exempt, 'pass_D_le_U_strict': p1,
                                  'pass_rep_value': p2 or exempt, 'pass_rep_value_strict': p2, 'opp_arriving_combos': opp_mass, 'exempt': exempt}
                    ok1 &= p1 or exempt
                    ok1_strict &= p1
                    ok2v &= p2 or exempt
                tr['seats'] = seats
            # A-only / B-only / A u B states (raw values, no damping) and the root replication check
            states = {}
            for n in ('A', 'B', 'AB'):
                tabs = {}
                for line in terms:
                    est, se = raw[n][line]
                    tj = json.load(open(sd + f"term{rep['terminals'][line]['term']}.json"))
                    tabs[line] = {'schema': 't2_hu_continuation_table_v1', 'line': line, 'live': tj['terminal_live_mask'], 'pot_bb': tj['pot_bb'],
                                  'value_convention': 'gross_share', 'zero_reach_definition': 'eps_tremble_avg',
                                  'seats': [{'seat': pl['seat'], 'position': pl['position'], 'gross': est[pl['position']]} for pl in tj['players']],
                                  'se': se, 'provenance': {'kind': f'precision {self.sid} step {k} panel {n} (raw)', 'raw_from': f's{k}/term*_{"".join(n)}'}}
                mm = {line: {str(pl['seat']): mat_json(mats[n][line][pl['position']])
                             for pl in json.load(open(sd + f"term{rep['terminals'][line]['term']}.json"))['players']}
                      for line in mats[n]}
                atomic(tabs, sd + f'tables_{n}.json')
                atomic(mm, sd + f'matrices_{n}.json')
                states[n] = (tabs, mm)
            spA, spB = self.lp.spot(*states['A']), self.lp.spot(*states['B'])
            root = rootcmp(spA, spB)
            rep['root_replication'] = root
            ok2 = ok2v and root['pass']
            rep.update({'pass_D_le_U144': ok1, 'pass_D_le_U144_strict': ok1_strict, 'pass_rep_values': ok2v, 'pass_rep_root': root['pass'],
                        'pass': ok1 and ok2, 'minutes': round((time.time() - t0) / 60, 1)})
            # cycle detection per terminal (max D/U over its seats)
            hist = st.setdefault('history', {})
            alphas = {}
            for line, tr in rep['terminals'].items():
                du = max((s['D_over_U'] or 0.0) for s in tr['seats'].values())
                h = hist.setdefault(line, [])
                h.append(du)
                cyc = len(h) >= 3 and h[-1] > 1 and (h[-3] - h[-2]) * (h[-2] - h[-1]) < 0
                tr['max_D_over_U'] = du
                tr['cycling'] = cyc
                alphas[line] = ALPHA_CYCLE if cyc else ALPHA
                tr['alpha_next'] = alphas[line]
            if st.get('fresh') and k == 0:
                rep['pass'] = False   # fresh spot: step 0 was solved against the static continuation -> minimum one update (as the quick loop)
                rep['fresh_step0'] = True
            if rep['pass']:
                rep['decision'] = 'precision_pass: (1) D <= U144 and (2) A/B replication; precision state = A u B values'
                st.update({'final': 'precision_pass', 'final_step': k})
            elif k + 1 >= MAX_STEPS:
                rep['decision'] = f'precision_failed: not passed after {MAX_STEPS} steps; ' + ('no record for this spot' if st.get('fresh') else 'the quick record stays') + ' (a mean of steps is not precision)'
                st.update({'final': 'precision_failed', 'final_step': k, 'stop_reason': rep['decision']})
            else:
                rep['decision'] = 'continue: next tables = (1 - a) T_k + a V_AuB (a = 0.5, cycling terminal 0.25)'
                new_t, new_m = {}, dict(st['matrices'])
                for line in terms:
                    a = alphas[line]
                    cur = st['tables'].get(line)
                    tab = json.loads(json.dumps(states['AB'][0][line]))
                    tab['provenance'] = {'kind': f'precision {self.sid} step {k} (damped a={a})', 'raw_from': f's{k}'}
                    if cur is not None:
                        g = {s_['position']: np.array(s_['gross']) for s_ in cur['seats']}
                        for s_ in tab['seats']:
                            s_['gross'] = ((1 - a) * g[s_['position']] + a * np.array(s_['gross'])).tolist()
                    new_t[line] = tab
                    if line in mats['AB']:
                        Mn = {}
                        old = st['matrices'].get(line, {})
                        for seat, Mr in states['AB'][1][line].items():
                            Mr = np.array([[np.nan if x is None else x for x in row] for row in Mr])
                            if seat in old:
                                Mo = np.array([[np.nan if x is None else x for x in row] for row in old[seat]])
                                Mr = np.where(np.isnan(Mo), Mr, np.where(np.isnan(Mr), Mo, (1 - a) * Mo + a * Mr))
                            Mn[seat] = mat_json(Mr)
                        new_m[line] = Mn
                st['tables'], st['matrices'], st['k'] = new_t, new_m, k + 1
            atomic(rep, sd + 'report.json')
            self.save_state(st)
            print(json.dumps({'k': k, 'decision': rep['decision'], 'root_share': root['share_within_5pp'],
                              'terminals': {l[-40:]: {p: (round(s['D'], 4), round(s['U144'], 4), round(s['rep_diff'], 4), round(s['rep_bound'], 4))
                                                      for p, s in tr['seats'].items()} for l, tr in rep['terminals'].items()}}), flush=True)
            self.grade(st, k, states)
            if st.get('final'):
                break
        return st

    # ---------------- grade (grade_spot.py rule + u_rep) ----------------
    def grade(self, st, k, states):
        spec = self.spec
        sd = self.dir + f's{k}/'
        rep = json.load(open(sd + 'report.json'))
        ref = f's{k}/' if st.get('fresh') else 's0/'   # u_outer reference: the 24-board start state, or (fresh spot) the tables this step used
        t24 = json.load(open(self.dir + ref + 'tables_used.json'))
        m24 = json.load(open(self.dir + ref + 'matrices_used.json'))
        out = {'schema': 'precision_check_v1', 'id': self.sid, 'step': k, 'decision': rep['decision'],
               'status': 'precision' if st.get('final') == 'precision_pass' else ('no_record (fresh spot, precision not passed)' if st.get('fresh') else 'quick'),
               'status_note': None if st.get('final') == 'precision_pass' else
               ('precision check not passed (yet): the quick record stays in use; the values below are the A u B candidate, NOT precision'),
               'standard': 'docs/GTO_PRECISION_PRIORITY_20261030.md section 3; runner docs/GTO_PRECISION_RUNNER.md',
               'start': st['start'], 'panels': st['panels'], 'db_promotion': 'forbidden', 'runtime_connection': 'none (compute + record only)'}
        if states is None:
            out['grade'] = None
            json.dump(out, open(self._rec_path(), 'w'), indent=1)
            return
        sp = self.lp.spot(*states['AB'])
        ev = sp.node_evs()
        expl = sp.exploitability()
        sp24 = self.lp.spot(t24, m24)
        ev24 = sp24.node_evs()
        evA = self.lp.spot(*states['A']).node_evs()
        evB = self.lp.spot(*states['B']).node_evs()
        tabs = states['AB'][0]
        q = {}
        for line in [l for l in sp.tables if l in tabs]:
            for p in sp.live:
                ev2 = sp.node_evs(shift=(line, p, 1.0))
                for i in ev2:
                    if sp.nodes[i]['actor'] == p:
                        q.setdefault(i, []).append((line, p, ev2[i] - ev[i]))
        nodes = []

        def rec(i, reach, reach24):
            node = sp.nodes[i]
            actor = node['actor']
            s = sp.avg[i]
            acts = [x[2] for x in node['acts']]
            E = ev[i]
            order = np.argsort(-E, axis=0)
            best, second = order[0], order[1]
            idx = np.arange(169)
            gap = E[best, idx] - E[second, idx]
            up = np.zeros((len(acts), 169))
            for line, p, dq in q.get(i, []):
                se = np.array(sp.tables[line]['se'][sp.pos[p]]) if 'se' in sp.tables[line] else np.zeros(169)
                up += (dq * se[None, :]) ** 2
            up = np.sqrt(up)
            u_panel = np.sqrt(up[best, idx] ** 2 + up[second, idx] ** 2)
            g_of = lambda Ex: Ex[best, idx] - Ex[second, idx]   # noqa: E731
            u_outer = np.abs(gap - g_of(ev24[i])) if i in ev24 else np.zeros(169)
            u_rep = np.abs(g_of(evA[i]) - g_of(evB[i])) / 2 if i in evA and i in evB else np.zeros(169)
            u_solver = expl['total_bb']
            u = u_panel + u_outer + u_solver + u_rep
            w = reach[actor] * 1326
            status = np.where(gap > 2 * u, 'stable', 'near_indifferent')
            s24 = sp24.avg[i] if i < len(sp24.avg) else None
            nodes.append({'path': list(node['path']), 'actor': sp.pos[actor], 'actions': acts, 'reach_combos': float(w.sum()),
                          'mix': {acts[a]: float((reach[actor] * s[a]).sum() / reach[actor].sum()) if reach[actor].sum() > 0 else None for a in range(len(acts))},
                          'hands': {sp.lab169[h]: {'freq': {acts[a]: round(float(s[a, h]), 4) for a in range(len(acts))},
                                                   'freq_24board_start': None if s24 is None else {acts[a]: round(float(s24[a, h]), 4) for a in range(len(acts))},
                                                   'ev': {acts[a]: round(float(E[a, h]), 4) for a in range(len(acts))},
                                                   'gap': round(float(gap[h]), 4), 'u_panel': round(float(u_panel[h]), 4),
                                                   'u_outer': round(float(u_outer[h]), 4), 'u_solver': round(float(u_solver), 5),
                                                   'u_rep': round(float(u_rep[h]), 4), 'status': str(status[h]),
                                                   'best': acts[best[h]], 'reach_combos': round(float(w[h]), 4)}
                                    for h in range(169) if w[h] > 1e-6}})
            for a, ch in enumerate(node['children']):
                if ch[0] == 'node':
                    r2 = {kk: v.copy() for kk, v in reach.items()}
                    r2[actor] = reach[actor] * s[a]
                    rec(ch[1], r2, None)
        rec(sp.root_idx, {kk: v.copy() for kk, v in sp.reach0.items()}, None)
        # G4 static share
        flop, static = 0.0, 0.0

        def rec2(i, reach):
            nonlocal flop, static
            node = sp.nodes[i]
            s = sp.avg[i]
            for a, ch in enumerate(node['children']):
                r2 = {kk: v.copy() for kk, v in reach.items()}
                r2[node['actor']] = reach[node['actor']] * s[a]
                if ch[0] == 'node':
                    rec2(ch[1], r2)
                elif ch[0] == 'flop':
                    m = float(np.prod([r2[p].sum() for p in sp.live]))
                    flop += m
                    if ch[1] not in tabs:
                        static += m
        rec2(sp.root_idx, {kk: v.copy() for kk, v in sp.reach0.items()})
        passed = st.get('final') == 'precision_pass'
        g = {'schema': 'spot_record_v2', 'id': spec['id'], 'tree': spec.get('tree_label'),
             'parent_preflop_state': {'dump': spec['dump'], **(spec.get('parent') or {})},
             'root_line': spec['root_line'], 'live': [sp.pos[p] for p in sp.live], 'final_step': k,
             'grade_inputs': {'config': spec['config'], 'rule': 'precision (A72 + B72)', 'spot_converged': passed, 'precision_final': True,
                              'p144_consistent_with_24': rep.get('pass_D_le_U144'), 'static_share': static / flop if flop > 0 else 0.0,
                              'status_cap': spec.get('status_cap'), 'status_cap_reason': spec.get('status_cap_reason'),
                              'converged_strict': rep.get('pass_D_le_U144_strict'), 'exempt_used': rep.get('pass_D_le_U144') and not rep.get('pass_D_le_U144_strict'),
                              'stop_reason': None if passed else rep['decision']},
             'exploitability': expl, 'tables': {l: tabs[l]['provenance'] for l in tabs}, 'matrix_terminals': sorted(states['AB'][1]), 'nodes': nodes,
             'panel': 'precision A72 u B72', 'u_rule': 'u = u_panel(A u B) + u_outer(|gap - gap at the 24-board start state|) + u_solver + u_rep(|gap_A - gap_B| / 2)'}
        exempt = [(line, pos, sd_.get('opp_arriving_combos')) for line, t_ in rep.get('terminals', {}).items()
                  for pos, sd_ in t_.get('seats', {}).items() if sd_.get('exempt')]
        g['amendment8_unsupported_nodes'] = [{'path': list(nd['path']), 'actor': pos, 'terminal': line, 'opp_arriving_combos': mass}
                                             for line, pos, mass in exempt for nd in sp.nodes
                                             if sp.pos[nd['actor']] == pos and any(ch[0] == 'flop' and ch[1] == line for ch in nd['children'])]
        try:
            G.label(g, sp.cfg)
        except Exception as e:   # labels are informative here; the precision decision is the report's
            g['label_error'] = repr(e)
        out['grade'] = g
        out['summary'] = summary(g, rep, self.quick_root())
        json.dump(out, open(self._rec_path(), 'w'))
        print(json.dumps(out['summary'], ensure_ascii=False)[:3000], flush=True)

    def _rec_path(self):
        d = os.path.join(os.environ['PREC_WORKDIR'], 'records') if TEST else os.path.join(REPO, 'data/gto_precision/records')
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, self.sid + '.json')

    def quick_root(self):
        f = os.path.join(CALC, 'data/gto_spot/quick', self.sid + '.json')
        if not os.path.exists(f):
            return None
        return json.load(open(f))['nodes'][0]


def rootcmp(spA, spB):
    i = spA.root_idx
    assert spB.root_idx == i
    actor = spA.nodes[i]['actor']
    acts = [x[2] for x in spA.nodes[i]['acts']]
    w = spA.reach0[actor] * 1326
    diff = np.abs(np.array(spA.avg[i]) - np.array(spB.avg[i])).max(0)
    ok = w >= REACH_FLOOR
    good = ok & (diff <= ROOT_CLASS_PP + 1e-12)
    share = float(w[good].sum() / w[ok].sum())
    worst = sorted(((float(diff[h]), spA.lab169[h], float(w[h])) for h in range(169) if ok[h] and diff[h] > ROOT_CLASS_PP), reverse=True)
    return {'actor': spA.pos[actor], 'actions': acts, 'share_within_5pp': share, 'pass': share >= ROOT_SHARE_MIN,
            'classes_over_5pp': [{'class': c, 'max_abs_diff': round(d, 4), 'combos': round(m, 3),
                                  'A': {acts[a]: round(float(spA.avg[i][a][spA.lab169.index(c)]), 4) for a in range(len(acts))},
                                  'B': {acts[a]: round(float(spB.avg[i][a][spA.lab169.index(c)]), 4) for a in range(len(acts))}} for d, c, m in worst]}


def summary(g, rep, qroot):
    root = g['nodes'][0]
    tot = sum(x['reach_combos'] for x in root['hands'].values() if x['reach_combos'] >= REACH_FLOOR)
    st_root = sum(x['reach_combos'] for x in root['hands'].values() if x['reach_combos'] >= REACH_FLOOR and x['status'] == 'stable')
    changed = []
    if qroot is not None:
        for h, x in root['hands'].items():
            qh = qroot['hands'].get(h)
            if qh is None or x['reach_combos'] < REACH_FLOOR:
                continue
            d = max(abs(x['freq'].get(a, 0.0) - qh['freq'].get(a, 0.0)) for a in x['freq'])
            if d > 0.05:
                changed.append({'class': h, 'max_abs_diff_vs_quick': round(d, 4), 'quick': qh['freq'], 'candidate': x['freq'],
                                'status': x['status'], 'combos': x['reach_combos']})
    changed.sort(key=lambda c: -c['max_abs_diff_vs_quick'])
    du = {l[-60:]: {p: {'D': round(s['D'], 4), 'U144': round(s['U144'], 4), 'D/U': None if s['D_over_U'] is None else round(s['D_over_U'], 2),
                        'rep_diff': round(s['rep_diff'], 4), 'rep_bound': round(s['rep_bound'], 4), 'exempt': s['exempt']}
                for p, s in t['seats'].items()} for l, t in rep['terminals'].items()}
    return {'decision': rep['decision'], 'pass_D_le_U144': rep['pass_D_le_U144'], 'pass_rep_values': rep['pass_rep_values'],
            'root_replication_share_within_5pp': rep['root_replication']['share_within_5pp'], 'pass_rep_root': rep['pass_rep_root'],
            'terminals': du, 'spot_exploitability_bb': g['exploitability']['total_bb'],
            'stable_combo_share_all_nodes': g.get('hand_frequency', {}).get('stable_combo_share'),
            'stable_combo_share_root': st_root / tot if tot > 0 else None,
            'root_mix_candidate': root['mix'], 'root_mix_quick': None if qroot is None else qroot.get('mix'),
            'root_classes_changed_over_5pp_vs_quick': changed}


if __name__ == '__main__':
    P = Prec(sys.argv[1])
    s = P.run()
    print('final', s.get('final'), 'k', s.get('k'), s.get('paused'))
