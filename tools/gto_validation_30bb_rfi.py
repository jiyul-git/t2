#!/usr/bin/env python3
"""30bb RFI diagnostic: GTOpen 30bb solver pilot vs Jens 9-max MTT 20bb/40bb charts.

Diagnostic only. Nothing here edits solver output or any DB.
20bb / 40bb are NOT a 30bb truth: they are stack-sensitivity brackets.

Inputs are read straight from pinned git commits (no local copies needed):
  solver : chatgpt/mini-cfr-solver-20260928  data/gto_9max_solver_pilot_30bb.json
  jens   : chatgpt/gto-external-harvest-20261003 data/gto_external/jensbaagaard_9max_mtt/MTT_{20,40}_GTO.json
  agg    : same harvest branch, PreflopRanges 30bb aggregate RFI (aggregate only)

Outputs:
  data/gto_validation/30bb_rfi_hand_sample_v1.json
  data/gto_validation/30bb_rfi_hand_sample_v1.md
  data/gto_validation/30bb_rfi_hand_sample_v1.png
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'gto_validation')
STEM = '30bb_rfi_hand_sample_v1'

SOLVER_COMMIT = '434abfeba5c309e3cb29f5dafb982133dd79d6fb'
SOLVER_PATH = 'data/gto_9max_solver_pilot_30bb.json'
JENS_COMMIT = 'c7f2cb38'
JENS_DIR = 'data/gto_external/jensbaagaard_9max_mtt'
PR30 = {'UTG': .165, 'UTG+1': .186, 'UTG+2': .217, 'LJ': .257, 'HJ': .299,
        'CO': .375, 'BTN': .487, 'SB': .894}

POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']
JPOS = {'UTG': 'EP1', 'UTG+1': 'EP2', 'UTG+2': 'EP3', 'LJ': 'LJ', 'HJ': 'HJ',
        'CO': 'CO', 'BTN': 'BTN', 'SB': 'SB'}
SAMPLE_POS = ['UTG', 'HJ', 'CO', 'BTN', 'SB']
# Fixed probes chosen per family before looking at hand-level gaps.
FIXED = ['AA', 'AKo', 'KQo', 'KTo', 'A5s', 'A2s', 'K9s', '98s', '76s', '55', '22', '72o']
N_AUTO_BOUNDARY = 3
TOL = 0.05          # bracket tolerance (reference values are chart-rounded)
CLEAR = 0.95        # clear open / clear fold threshold on the reference pair

R = 'AKQJT98765432'
RV = {r: 14 - i for i, r in enumerate(R)}


def git_json(commit, path):
    raw = subprocess.check_output(['git', '-C', ROOT, 'show', f'{commit}:{path}'])
    return json.loads(raw)


def hands169():
    out = []
    for i, a in enumerate(R):
        for j, b in enumerate(R):
            if i == j:
                out.append(a + b)
            elif i < j:
                out.append(a + b + 's')
            else:
                out.append(b + a + 'o')
    return out   # row-major 13x13 grid, suited above diagonal


GRID = hands169()
HANDS = sorted(set(GRID), key=GRID.index)
assert len(HANDS) == 169


def combos(h):
    return 6 if len(h) == 2 else (4 if h[2] == 's' else 12)


def family(h):
    if len(h) == 2:
        return 'pair'
    hi, lo, s = RV[h[0]], RV[h[1]], h[2] == 's'
    if s:
        if hi == 14:
            return 'suited_Ax'
        if hi == 13:
            return 'suited_Kx'
        if lo >= 10:
            return 'suited_broadway'
        if hi - lo == 1:
            return 'suited_connector'
        if hi - lo == 2:
            return 'suited_one_gapper'
        return 'suited_other'
    if hi == 14:
        return 'offsuit_Ax'
    if lo >= 10:
        return 'offsuit_broadway'
    return 'offsuit_other'


FAMILIES = ['pair', 'suited_Ax', 'suited_Kx', 'suited_broadway', 'suited_connector',
            'suited_one_gapper', 'suited_other', 'offsuit_Ax', 'offsuit_broadway',
            'offsuit_other']


def wavg(rows, key):
    w = sum(combos(r['hand']) for r in rows)
    return sum(combos(r['hand']) * r[key] for r in rows) / w if w else 0.0


def main():
    sol = git_json(SOLVER_COMMIT, SOLVER_PATH)
    j20 = git_json(JENS_COMMIT, f'{JENS_DIR}/MTT_20_GTO.json')
    j40 = git_json(JENS_COMMIT, f'{JENS_DIR}/MTT_40_GTO.json')
    rfi_spots = {s['actor']: s for s in sol['spots'] if s['spot_type'] == 'rfi'}

    positions = {}
    for p in POS:
        sp = rfi_spots[p]
        jk = JPOS[p]
        rows = []
        for h in HANDS:
            raw = {k: float(v) for k, v in sp['hands'][h].items()}
            s_open = sum(v for k, v in raw.items() if k != 'fold')
            s_jam = sum(v for k, v in raw.items() if k.startswith('jam'))
            r20 = float(j20.get('Open' + jk, {}).get(h, 0.0))
            r40 = float(j40.get('Open' + jk, {}).get(h, 0.0))
            l20 = float(j20.get('Limp' + jk, {}).get(h, 0.0))
            l40 = float(j40.get('Limp' + jk, {}).get(h, 0.0))
            lo, hi = min(r20, r40), max(r20, r40)
            if s_open < lo - TOL:
                bracket = 'below_both'
            elif s_open > hi + TOL:
                bracket = 'above_both'
            else:
                bracket = 'inside'
            if r20 >= CLEAR and r40 >= CLEAR:
                ref_class = 'clear_open'
            elif r20 <= 1 - CLEAR and r40 <= 1 - CLEAR:
                ref_class = 'clear_fold'
            else:
                ref_class = 'boundary'
            rows.append({
                'hand': h, 'combos': combos(h), 'family': family(h),
                'solver_raw': raw,
                'solver_open': s_open, 'solver_raise': s_open - s_jam, 'solver_jam': s_jam,
                'jens20_open': r20, 'jens40_open': r40,
                'jens20_limp': l20, 'jens40_limp': l40,
                'midpoint_open': (r20 + r40) / 2,
                'midpoint_residual': s_open - (r20 + r40) / 2,
                'bracket_gap': (s_open - lo) if bracket == 'below_both' else
                               (s_open - hi) if bracket == 'above_both' else 0.0,
                'bracket': bracket, 'ref_class': ref_class,
            })
        positions[p] = summarize(p, rows)
        positions[p]['hands'] = rows

    samples = {p: sample(positions[p]['hands']) for p in SAMPLE_POS}

    doc = {
        'schema_version': 'gto_validation_30bb_rfi_v1',
        'purpose': 'diagnostic only; no solver/DB value is modified by this file',
        'inputs': {
            'solver': {'branch': 'chatgpt/mini-cfr-solver-20260928', 'commit': SOLVER_COMMIT,
                       'path': SOLVER_PATH, 'stack_bb': 30,
                       'iteration': sol['solver']['status']['iteration'],
                       'gap_total': sol['solver']['status']['gap_total'],
                       'target_gap': sol['solver']['target_gap'],
                       'tree': 'no limp; open 2bb (SB 2.5bb) or jam 30; opener vs 3bet = call/fold only (max_raises=2)',
                       'ante': sol['solver_ante_model']},
            'jens': {'branch': 'chatgpt/gto-external-harvest-20261003', 'commit': JENS_COMMIT,
                     'paths': [f'{JENS_DIR}/MTT_20_GTO.json', f'{JENS_DIR}/MTT_40_GTO.json'],
                     'upstream': 'jensbaagaard/poker-practice@449993f7 (MIT)',
                     'stacks_bb': [20, 40],
                     'assumptions_unknown_in_pack': ['ante model', 'open size', 'raise vs jam split', 'chipEV vs ICM'],
                     'precision': 'chart-rounded, mostly 0.01-0.1 steps'},
            'aggregate_30bb': {'source': 'PreflopRanges 9-max MTT 30bb (aggregate RFI only)',
                               'rfi': PR30},
        },
        'reference_status': {
            'exact_30bb_hand_level_reference': False,
            'search': 'all 14 remote branches searched (filenames + data/* content for stack 30); '
                      '30bb hits are only our own solver pilot (and its re-ingest in data/gto_db/spots), '
                      'HU/subgame solver configs, 8-max Matthiola, and aggregate-only public crosschecks. '
                      'Harvest DISCOVERY_AUDIT_20261003 also lists "30 BB full tree" as an open gap.',
            'jens_20_40_role': 'stack-sensitivity bracket only; never 30bb truth',
        },
        'definitions': {
            'open': 'raise + jam (raw actions preserved in solver_raw)',
            'bracket': f'inside if min(J20,J40)-{TOL} <= solver_open <= max(J20,J40)+{TOL}',
            'ref_class': f'clear_open: J20 and J40 >= {CLEAR}; clear_fold: both <= {1-CLEAR:.2f}; else boundary',
            'midpoint_residual': 'solver_open - (J20+J40)/2; linear-interpolation diagnostic, not a truth gap',
            'missing_mass_pp': 'combo-weighted sum of negative bracket_gap, in % of 1326 combos',
            'SB': 'solver has no limp; Jens 20bb SB limps. SB open compared as raise-vs-raise, limp reported separately',
        },
        'positions': positions,
        'samples': samples,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, STEM + '.json'), 'w') as f:
        json.dump(doc, f, indent=1)
    with open(os.path.join(OUT, STEM + '.md'), 'w') as f:
        f.write(render_md(doc))
    render_png(doc, os.path.join(OUT, STEM + '.png'))
    print('wrote', OUT)


def pct(rows, key):
    return 100 * sum(r['combos'] * r[key] for r in rows) / 1326


def summarize(p, rows):
    s = {
        'rfi_solver_open': pct(rows, 'solver_open') / 100,
        'rfi_solver_raise': pct(rows, 'solver_raise') / 100,
        'rfi_solver_jam': pct(rows, 'solver_jam') / 100,
        'rfi_jens20_open': pct(rows, 'jens20_open') / 100,
        'rfi_jens40_open': pct(rows, 'jens40_open') / 100,
        'rfi_jens20_limp': pct(rows, 'jens20_limp') / 100,
        'rfi_jens40_limp': pct(rows, 'jens40_limp') / 100,
        'rfi_midpoint': pct(rows, 'midpoint_open') / 100,
        'rfi_aggregate_30bb': PR30[p],
    }
    lo = min(s['rfi_jens20_open'], s['rfi_jens40_open'])
    hi = max(s['rfi_jens20_open'], s['rfi_jens40_open'])
    s['aggregate_inside_20_40'] = lo <= s['rfi_solver_open'] <= hi
    s['missing_mass_pp'] = 100 * sum(r['combos'] * min(0, r['bracket_gap']) for r in rows) / 1326
    s['extra_mass_pp'] = 100 * sum(r['combos'] * max(0, r['bracket_gap']) for r in rows) / 1326
    s['midpoint_residual_pp'] = 100 * sum(r['combos'] * r['midpoint_residual'] for r in rows) / 1326
    s['bracket_counts'] = {b: sum(1 for r in rows if r['bracket'] == b)
                           for b in ('below_both', 'inside', 'above_both')}
    s['bracket_combos'] = {b: sum(r['combos'] for r in rows if r['bracket'] == b)
                           for b in ('below_both', 'inside', 'above_both')}
    by_cls = {}
    for c in ('clear_open', 'boundary', 'clear_fold'):
        rr = [r for r in rows if r['ref_class'] == c]
        by_cls[c] = {
            'hands': len(rr), 'combos': sum(r['combos'] for r in rr),
            'solver_open_avg': wavg(rr, 'solver_open'),
            'midpoint_open_avg': wavg(rr, 'midpoint_open'),
            'missing_mass_pp': 100 * sum(r['combos'] * min(0, r['bracket_gap']) for r in rr) / 1326,
            'midpoint_residual_pp': 100 * sum(r['combos'] * r['midpoint_residual'] for r in rr) / 1326,
        }
    s['by_ref_class'] = by_cls
    fam = {}
    for f in FAMILIES:
        rr = [r for r in rows if r['family'] == f]
        fam[f] = {
            'hands': len(rr), 'combos': sum(r['combos'] for r in rr),
            'solver_open_pp': pct(rr, 'solver_open'),
            'jens20_open_pp': pct(rr, 'jens20_open'),
            'jens40_open_pp': pct(rr, 'jens40_open'),
            'missing_mass_pp': 100 * sum(r['combos'] * min(0, r['bracket_gap']) for r in rr) / 1326,
            'extra_mass_pp': 100 * sum(r['combos'] * max(0, r['bracket_gap']) for r in rr) / 1326,
            'midpoint_residual_pp': 100 * sum(r['combos'] * r['midpoint_residual'] for r in rr) / 1326,
            'below_both_hands': [r['hand'] for r in rr if r['bracket'] == 'below_both'],
        }
    s['families'] = fam
    bnd = [r for r in rows if r['ref_class'] == 'boundary']
    bnd.sort(key=lambda r: r['midpoint_residual'])
    s['boundary_hands'] = [{k: r[k] for k in ('hand', 'family', 'solver_open', 'solver_jam',
                                               'jens20_open', 'jens40_open', 'midpoint_residual',
                                               'bracket')} for r in bnd]
    s['clear_open_hands_below_both'] = [r['hand'] for r in rows
                                        if r['ref_class'] == 'clear_open' and r['bracket'] == 'below_both']
    return s


def sample(rows):
    by = {r['hand']: r for r in rows}
    picked = list(FIXED)
    # auto boundary picks: reference midpoint closest to 0.5 (chosen from reference, not from gap)
    cand = [r for r in rows if r['ref_class'] == 'boundary' and r['hand'] not in picked]
    cand.sort(key=lambda r: (abs(r['midpoint_open'] - 0.5), -r['combos'], r['hand']))
    picked += [r['hand'] for r in cand[:N_AUTO_BOUNDARY]]
    out = []
    for h in picked:
        r = by[h]
        out.append({'hand': h, 'family': r['family'], 'ref_class': r['ref_class'],
                    'solver_raw': r['solver_raw'], 'solver_open': r['solver_open'],
                    'jens20_open': r['jens20_open'], 'jens40_open': r['jens40_open'],
                    'jens20_limp': r['jens20_limp'],
                    'midpoint_residual': r['midpoint_residual'], 'bracket': r['bracket'],
                    'exact_30bb_reference': None,
                    'note': 'no exact 30bb hand-level reference; 20/40 are brackets only'})
    return out


def f1(x):
    return f'{100*x:.1f}'


def render_md(doc):
    P = doc['positions']
    L = []
    L.append('# 30bb RFI diagnostic — solver 30bb vs Jens 20bb / 40bb (v1)\n')
    L.append('**Diagnostic only.** No solver or DB value was changed. No new solve was run.\n')
    L.append('- Solver: GTOpen 30bb pilot, `chatgpt/mini-cfr-solver-20260928@434abfe`, '
             f"iteration {doc['inputs']['solver']['iteration']}, gap_total "
             f"{doc['inputs']['solver']['gap_total']:.3f} (target {doc['inputs']['solver']['target_gap']}). "
             'Tree: no limp, open 2bb (SB 2.5bb) or jam; opener vs 3-bet can only call/fold.')
    L.append('- Jens: 9-max MTT 20bb / 40bb, `chatgpt/gto-external-harvest-20261003@c7f2cb3`. '
             'Ante, open size, raise/jam split, and chipEV/ICM are not recorded in the pack. Values are chart-rounded.')
    L.append('- **No exact 30bb hand-level reference exists in any branch.** 20/40 are a stack-sensitivity bracket, not truth. '
             'Being "inside" the bracket is not proof of correctness, and being "below both" is not proof of error, '
             'because a hand\'s open frequency need not be monotone in stack depth.')
    L.append('- Open = raise + jam. Raw solver actions are kept in the JSON. SB is handled separately (solver has no limp).\n')

    L.append('## 1. Aggregate RFI (% of 1326 combos)\n')
    L.append('| Pos | Jens 20 | Solver 30 (raise / jam) | Jens 40 | 20–40 midpoint | PR 30 agg | inside 20–40? | missing mass | extra mass | midpoint residual |')
    L.append('|---|---:|---:|---:|---:|---:|:-:|---:|---:|---:|')
    for p in POS:
        s = P[p]
        L.append(f"| {p} | {f1(s['rfi_jens20_open'])} | **{f1(s['rfi_solver_open'])}** "
                 f"({f1(s['rfi_solver_raise'])} / {f1(s['rfi_solver_jam'])}) | {f1(s['rfi_jens40_open'])} | "
                 f"{f1(s['rfi_midpoint'])} | {f1(s['rfi_aggregate_30bb'])} | "
                 f"{'yes' if s['aggregate_inside_20_40'] else 'NO'} | {s['missing_mass_pp']:.1f} | "
                 f"{s['extra_mass_pp']:.1f} | {s['midpoint_residual_pp']:+.1f} |")
    sb = P['SB']
    L.append(f"\nSB note: Jens 20bb SB = open {f1(sb['rfi_jens20_open'])}% + **limp {f1(sb['rfi_jens20_limp'])}%**; "
             f"Jens 40bb SB = open {f1(sb['rfi_jens40_open'])}%, limp {f1(sb['rfi_jens40_limp'])}%. "
             'The solver tree has no limp option, so SB raise-vs-raise is not a like-for-like comparison at 20bb. '
             'PR 30 SB 89.4% very likely includes limps and uses 3.5bb opens — not comparable.\n')

    L.append('## 2. Where the gap sits: reference class (by Jens 20+40 agreement)\n')
    L.append('clear_open = both ≥95%, clear_fold = both ≤5%, boundary = everything else. Mass in pp of 1326 combos.\n')
    L.append('| Pos | clear_open: solver avg / missing | boundary: solver avg vs midpoint / missing | clear_fold: solver avg / midpoint residual | clear_open hands below both |')
    L.append('|---|---|---|---|---|')
    for p in POS:
        c = P[p]['by_ref_class']
        bel = ', '.join(P[p]['clear_open_hands_below_both']) or '—'
        L.append(f"| {p} | {f1(c['clear_open']['solver_open_avg'])}% / {c['clear_open']['missing_mass_pp']:.1f} "
                 f"| {f1(c['boundary']['solver_open_avg'])}% vs {f1(c['boundary']['midpoint_open_avg'])}% / {c['boundary']['missing_mass_pp']:.1f} "
                 f"| {f1(c['clear_fold']['solver_open_avg'])}% / {c['clear_fold']['midpoint_residual_pp']:+.1f} | {bel} |")

    L.append('\n## 3. Family decomposition — missing mass below the 20–40 bracket (pp of 1326)\n')
    L.append('| Pos | ' + ' | '.join(FAMILIES) + ' |')
    L.append('|---|' + '---:|' * len(FAMILIES))
    for p in POS:
        fam = P[p]['families']
        L.append(f'| {p} | ' + ' | '.join(f"{fam[f]['missing_mass_pp']:.1f}" for f in FAMILIES) + ' |')
    L.append('\nFamily open rate (pp of all 1326 combos): Jens 20 / solver 30 / Jens 40\n')
    L.append('| Pos | ' + ' | '.join(FAMILIES) + ' |')
    L.append('|---|' + '---|' * len(FAMILIES))
    for p in POS:
        fam = P[p]['families']
        L.append(f'| {p} | ' + ' | '.join(
            f"{fam[f]['jens20_open_pp']:.1f} / **{fam[f]['solver_open_pp']:.1f}** / {fam[f]['jens40_open_pp']:.1f}"
            for f in FAMILIES) + ' |')
    L.append('\nHands below both brackets, by family:\n')
    for p in POS:
        parts = [f"{f}: {', '.join(v['below_both_hands'])}" for f, v in P[p]['families'].items()
                 if v['below_both_hands']]
        L.append(f'- **{p}** — ' + ('; '.join(parts) or 'none'))

    L.append('\n## 4. Boundary hands (Jens 20/40 disagree or mix), sorted by midpoint residual\n')
    for p in SAMPLE_POS:
        L.append(f'### {p}\n')
        L.append('| Hand | family | J20 | Solver 30 (jam) | J40 | residual | bracket |')
        L.append('|---|---|---:|---:|---:|---:|---|')
        for r in P[p]['boundary_hands']:
            L.append(f"| {r['hand']} | {r['family']} | {f1(r['jens20_open'])} | {f1(r['solver_open'])} "
                     f"({f1(r['solver_jam'])}) | {f1(r['jens40_open'])} | {100*r['midpoint_residual']:+.1f} | {r['bracket']} |")
        L.append('')

    L.append('## 5. Hand sample (12 fixed family probes + 3 reference-boundary hands)\n')
    L.append('Exact 30bb reference column: **no exact 30bb hand-level reference** for every row.\n')
    for p in SAMPLE_POS:
        L.append(f'### {p}\n')
        L.append('| Hand | family | ref class | solver fold / raise / jam | solver open | J20 open | J40 open | J20 limp | bracket |')
        L.append('|---|---|---|---|---:|---:|---:|---:|---|')
        for r in doc['samples'][p]:
            raw = r['solver_raw']
            fr = raw.get('fold', 0)
            jm = sum(v for k, v in raw.items() if k.startswith('jam'))
            rs = 1 - fr - jm
            L.append(f"| {r['hand']} | {r['family']} | {r['ref_class']} | {f1(fr)} / {f1(rs)} / {f1(jm)} | "
                     f"{f1(r['solver_open'])} | {f1(r['jens20_open'])} | {f1(r['jens40_open'])} | "
                     f"{f1(r['jens20_limp'])} | {r['bracket']} |")
        L.append('')
    L.append('## Caveats\n')
    L.append('- Solver pilot is a 20-iteration run (gap_total 0.309). A later convergence-qualified run '
             '(gap 0.095) gave similar aggregate RFI, but its per-hand table was not stored, so hand values here come from the loose run.')
    L.append('- Solver trash hands show a ~0.01% jam floor (averaging residue); treat <1% as zero.')
    L.append('- Jens pack conditions (ante, sizing, ICM) are unknown, so even an "inside" result is only a consistency check.')
    L.append('- 20 and 40 are not bracketing endpoints of a monotone function; some families (e.g. small pairs, offsuit Ax) '
             'can legitimately move non-monotonically with stack depth.')
    return '\n'.join(L) + '\n'


def render_png(doc, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    # diverging: red = solver opens less than both brackets, blue = more; gray = inside
    cmap = LinearSegmentedColormap.from_list('div', ['#c4322f', '#f0efec', '#2a78d6'])
    norm = TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)
    pos = SAMPLE_POS
    fig, axes = plt.subplots(2, len(pos), figsize=(4.2 * len(pos), 9.2), facecolor='#fcfcfb')
    for k, p in enumerate(pos):
        rows = {r['hand']: r for r in doc['positions'][p]['hands']}
        s = doc['positions'][p]
        for rowi, (key, title) in enumerate([('solver_open', 'solver 30 open'), ('bracket_gap', 'gap vs 20–40 bracket')]):
            ax = axes[rowi][k]
            for i in range(13):
                for j in range(13):
                    h = GRID[i * 13 + j]
                    r = rows[h]
                    if key == 'solver_open':
                        v = r['solver_open']
                        col = (1 - 0.85 * v, 1 - 0.55 * v, 1 - 0.2 * v)
                        txtc = '#0b0b0b' if v < 0.6 else '#ffffff'
                    else:
                        col = cmap(norm(r['bracket_gap']))
                        txtc = '#0b0b0b' if abs(r['bracket_gap']) < 0.55 else '#ffffff'
                    ax.add_patch(plt.Rectangle((j, 12 - i), 0.94, 0.94, color=col, lw=0))
                    ax.text(j + 0.47, 12 - i + 0.47, h, ha='center', va='center', fontsize=5.6, color=txtc)
            ax.set_xlim(0, 13); ax.set_ylim(0, 13); ax.set_aspect('equal'); ax.axis('off')
            if rowi == 0:
                ax.set_title(f"{p}  solver {100*s['rfi_solver_open']:.1f}%\n"
                             f"(J20 {100*s['rfi_jens20_open']:.1f}% · J40 {100*s['rfi_jens40_open']:.1f}%)",
                             fontsize=10, color='#0b0b0b')
            else:
                ax.set_title(f"missing {s['missing_mass_pp']:.1f}pp · extra {s['extra_mass_pp']:.1f}pp",
                             fontsize=9, color='#52514e')
    fig.text(0.01, 0.73, 'Solver 30bb\nopen (raise+jam)', fontsize=10, color='#0b0b0b', rotation=90, va='center')
    fig.text(0.01, 0.27, 'Gap vs Jens\n20–40 bracket', fontsize=10, color='#0b0b0b', rotation=90, va='center')
    cax = fig.add_axes([0.35, 0.035, 0.3, 0.012])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation='horizontal')
    cb.set_ticks([-1, -0.5, 0, 0.5, 1])
    cb.set_ticklabels(['-100pp\nsolver opens less', '-50', 'inside ±5pp', '+50', '+100pp\nsolver opens more'])
    cb.ax.tick_params(labelsize=7, colors='#52514e'); cb.outline.set_visible(False)
    fig.suptitle('30bb RFI diagnostic — GTOpen 30bb vs Jens 9-max 20bb/40bb (brackets, not truth). '
                 'SB: solver has no limp; Jens 20bb SB limp not shown.', fontsize=11, color='#0b0b0b')
    fig.subplots_adjust(left=0.04, right=0.995, top=0.9, bottom=0.08, wspace=0.05, hspace=0.12)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())


if __name__ == '__main__':
    sys.exit(main())
