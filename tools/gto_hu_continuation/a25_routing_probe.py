#!/usr/bin/env python3
"""A2.5 frozen-table routing probe: ONE preflop re-solve with a frozen multi-terminal manifest (not an outer step,
not production values). Where does preflop mass move when node 6's solved table is injected next to node 28?

    python3 tools/gto_hu_continuation/a25_routing_probe.py

Runs (T2_CONT_FILE manifest, t2_cont_terminal exports for nodes 28/6/46/246 + t2_cont_census):
  P10     : M9 = {node 28: k9/table.json, node 6: node6_72/table72.json}          (the requested probe)
  P10_28  : control {node 28: k9/table.json} only (separates node 6's effect from the node-28 table update k8 -> k9)
Reference P9 = existing exports (T2_CONT_FILE = k8/table.json): terminals/p9_node*.json, census_p9.json.
No postflop re-solve of P10.
"""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(ROOT, 'vendor/gtopen/target/release/examples')
CFG = os.path.join(ROOT, 'data/gto_hu_continuation/cfg_4h_mr4_30bb.json')
ENV = {'PREFLOP_EQ_SEED': '202', 'PREFLOP_MULTIWAY_SEED': '202', 'PREFLOP_EQ_SAMPLES': '1200'}
D = os.path.join(ROOT, 'data/gto_terminal_expansion/')
OUT = D + 'a25_routing_probe/'
K9 = os.path.join(ROOT, 'data/gto_hu_continuation/panel72/outer_v2_damped_a05/k9/table.json')
T6 = D + 'node6_72/table72.json'
SPEC = {28: 'fold,raise,fold,call', 6: 'fold,fold,raise,call', 46: 'fold,raise,call,call', 246: 'raise,fold,call,call'}
NODES = (28, 6, 46, 246)


def run(cmd, env):
    print('+', ' '.join(os.path.relpath(c, ROOT) if c.startswith(ROOT) else c for c in cmd), flush=True)
    subprocess.run(cmd, check=True, env={**os.environ, **ENV, **env})


def solve(tag, tables):
    d = OUT + tag + '/'
    os.makedirs(d, exist_ok=True)
    man = d + 'manifest.json'
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': [{'file': os.path.relpath(t, d)} for t in tables]}, open(man, 'w'), indent=1)
    for n in NODES:
        f = d + f'terminal_node{n}.json'
        if not os.path.exists(f):
            run([BIN + '/t2_cont_terminal', CFG, '400', SPEC[n], f], {'T2_CONT_FILE': man})
    c = d + 'census.json'
    if not os.path.exists(c):
        run([BIN + '/t2_cont_census', CFG, '400', c], {'T2_CONT_FILE': man})
    return {n: json.load(open(d + f'terminal_node{n}.json')) for n in NODES}, json.load(open(c)), man


def state(terms, census):
    ref = terms[28]
    for n, t in terms.items():  # all exports come from the same preflop solve
        assert t['gaps'] == ref['gaps'] and t['evs'] == ref['evs'], n
    assert census['gap_total'] == ref['gap_total']
    by_live = {}
    for r in census['terminals']:
        by_live[r['live_count']] = by_live.get(r['live_count'], 0.0) + r['reach_probability']
    tot = sum(by_live.values())
    reach = {r['terminal_node']: r for r in census['terminals']}
    freqs = {'rfi_CO': ref['frequencies']['rfi_CO']['mix'], 'rfi_BTN': ref['frequencies']['rfi_BTN']['mix'], 'rfi_SB': ref['frequencies']['rfi_SB']['mix']}
    for n, t in terms.items():
        for pn in t['path_nodes']:
            freqs[f"node{n}_path:{pn['actor']}@{pn['node']}"] = pn['mix']
    return {'gap_total': ref['gap_total'], 'gaps': ref['gaps'],
            'conservation_evs_sum': sum(ref['evs'].values()) if isinstance(ref['evs'], dict) else sum(ref['evs']),
            'ranges_hash': {n: terms[n]['ranges_hash_fnv1a64'] for n in NODES},
            'reach': {n: reach[n]['reach_probability'] for n in NODES},
            'flop_share': {n: reach[n]['share_of_flop_reach'] for n in NODES},
            'flop_reach_by_live_count': {f'{k}-way': v for k, v in sorted(by_live.items())}, 'flop_reach_total': tot,
            'flop_share_by_live_count': {f'{k}-way': v / tot for k, v in sorted(by_live.items())},
            'reach_check': census['summary'].get('reach_check'), 'frequencies': freqs,
            'multiway_share_of_flop_reach': census['summary']['multiway_share_of_flop_reach']}


def main():
    if os.environ.get('A25_FIGURE_ONLY'):
        res = json.load(open(OUT + 'probe.json'))
        ik = lambda d: {int(k): v for k, v in d.items()}
        for k in ('P9', 'P10', 'P10_control_28_only'):
            res[k]['reach'] = ik(res[k]['reach'])
        res['reach_change'] = {k: ik(v) for k, v in res['reach_change'].items()}
        figure(res, OUT + '../../../docs/GTO_TERMINAL_A25_ROUTING_V2.png')
        return
    os.makedirs(OUT, exist_ok=True)
    p9 = state({n: json.load(open(D + f'terminals/p9_node{n}.json')) for n in NODES}, json.load(open(D + 'census_p9.json')))
    t10, c10, m10 = solve('P10_M9_28k9_6a1', [K9, T6])
    t28, c28, m28 = solve('P10_control_28k9_only', [K9])
    s10, s28 = state(t10, c10), state(t28, c28)
    delta = lambda a, b: {k: b[k] - a[k] for k in a}
    res = {'schema': 't2_a25_routing_probe_v1', 'note': 'single frozen-table preflop re-solve (M9 -> P10); diagnostic only, not an outer-loop or production result',
           'manifests': {'P10': os.path.relpath(m10, ROOT), 'P10_control': os.path.relpath(m28, ROOT)},
           'tables': {'node28': os.path.relpath(K9, ROOT), 'node6': os.path.relpath(T6, ROOT)},
           'P9': p9, 'P10': s10, 'P10_control_28_only': s28,
           'reach_change': {'P9_to_P10': delta(p9['reach'], s10['reach']), 'P9_to_control': delta(p9['reach'], s28['reach']),
                            'node6_effect_P10_minus_control': delta(s28['reach'], s10['reach'])},
           'flop_reach_by_live_change': {'P9_to_P10': delta(p9['flop_reach_by_live_count'], s10['flop_reach_by_live_count']),
                                         'node6_effect_P10_minus_control': delta(s28['flop_reach_by_live_count'], s10['flop_reach_by_live_count'])}}
    mw = lambda s: sum(v for k, v in s['flop_reach_by_live_count'].items() if k != '2-way')
    res['multiway_legacy_mass'] = {'P9': mw(p9), 'P10': mw(s10), 'P10_control': mw(s28),
                                   'node6_effect': mw(s10) - mw(s28), 'node6_effect_on_46_246': {n: s10['reach'][n] - s28['reach'][n] for n in (46, 246)}}
    json.dump(res, open(OUT + 'probe.json', 'w'), indent=1)
    for k in ('reach_change', 'flop_reach_by_live_change', 'multiway_legacy_mass'):
        print(k, json.dumps(res[k], indent=1))
    print('gap', p9['gap_total'], s10['gap_total'], s28['gap_total'])
    print('hash', s10['ranges_hash'])
    figure(res, OUT + '../../../docs/GTO_TERMINAL_A25_ROUTING_V2.png')


def figure(res, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    INK, MUTED, SURF, GRID = '#1f1f1e', '#6b6a64', '#fcfcfb', '#e6e5df'
    cols = {'P9': '#b5b3aa', 'P10_control_28_only': '#8a5cd1', 'P10': INK}
    labs = {'P9': 'P9 (node 28 = k8 table)', 'P10_control_28_only': 'control: node 28 = k9 only', 'P10': 'P10 probe: node 28 = k9 + node 6 solved'}
    fig, ax = plt.subplots(1, 4, figsize=(25, 5.8), dpi=115)
    fig.patch.set_facecolor(SURF)
    names = {28: '28 BTN open / BB call (HU)', 6: '6 SB open / BB call (HU)', 46: '46 BTN open, SB+BB call (3-way)', 246: '246 CO open, SB+BB call (3-way)'}
    g = ax[0]
    xs = range(len(NODES))
    for j, k in enumerate(('P9', 'P10_control_28_only', 'P10')):
        v = [res[k]['reach'][n] if k != 'P9' else res['P9']['reach'][n] for n in NODES]
        g.bar([x + (j - 1) * 0.27 for x in xs], v, 0.26, color=cols[k], label=labs[k])
    g.set_xticks(list(xs))
    g.set_xticklabels([names[n] for n in NODES], fontsize=7.5, rotation=10)
    g.set_ylabel('reach probability of the terminal', fontsize=9, color=MUTED)
    g.set_title('(1) terminal reach: P9 vs frozen-table re-solves', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False, loc='upper left')
    g.set_ylim(0, 0.36)
    g = ax[1]
    ch = res['reach_change']
    for j, (k, lab, col) in enumerate((('P9_to_control', 'node 28 k8→k9 only', '#8a5cd1'), ('node6_effect_P10_minus_control', 'node 6 solved (P10 − control)', '#c0392b'),
                                       ('P9_to_P10', 'total P9 → P10', INK))):
        v = [ch[k][n] for n in NODES]
        g.bar([x + (j - 1) * 0.27 for x in xs], v, 0.26, color=col, label=lab)
    g.axhline(0, color=INK, lw=1)
    g.set_xticks(list(xs))
    g.set_xticklabels([f'node {n}' for n in NODES], fontsize=8.5)
    g.set_ylabel('reach change (probability)', fontsize=9, color=MUTED)
    g.set_title('(2) decomposition of the reach change', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[2]
    keys = list(res['P9']['flop_reach_by_live_count'].keys())
    for j, k in enumerate(('P9', 'P10_control_28_only', 'P10')):
        v = [res[k]['flop_reach_by_live_count'][x] for x in keys]
        g.bar([x + (j - 1) * 0.27 for x in range(len(keys))], v, 0.26, color=cols[k], label=labs[k])
    g.set_xticks(range(len(keys)))
    g.set_xticklabels(keys, fontsize=9)
    g.set_ylabel('flop reach probability', fontsize=9, color=MUTED)
    mwe = res['multiway_legacy_mass']['node6_effect']
    g.set_title(f'(3) flop reach by players: node-6 effect on 3/4-way mass {mwe:+.1e}', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=8, frameon=False)
    g = ax[3]
    rows = [('rfi_SB', 'SB open (unopened to SB)'), ('node6_path:BB@4', 'BB vs SB 2.5 open (node 6 parent)')]
    labels, vals = [], {k: [] for k in ('P9', 'P10_control_28_only', 'P10')}
    for key, name in rows:
        acts = list(res['P9']['frequencies'][key].keys())
        for act in acts:
            labels.append(f'{name}: {act}')
            for k in vals:
                vals[k].append(res[k]['frequencies'][key].get(act, 0.0))
    y = range(len(labels))
    for j, k in enumerate(('P9', 'P10_control_28_only', 'P10')):
        g.barh([t + (j - 1) * 0.27 for t in y], vals[k], 0.26, color=cols[k], label=labs[k])
    g.set_yticks(list(y))
    g.set_yticklabels(labels, fontsize=7.5)
    g.invert_yaxis()
    g.set_xlabel('aggregate frequency', fontsize=9, color=MUTED)
    g.set_title('(4) preflop frequencies that moved', loc='left', fontsize=10, color=INK)
    g.legend(fontsize=7.5, frameon=False, loc='lower right')
    for g in ax:
        g.set_facecolor(SURF)
        g.grid(color=GRID, lw=0.8)
        for sp in ('top', 'right'):
            g.spines[sp].set_visible(False)
    fig.suptitle('A2.5 frozen-table routing probe — one preflop re-solve, diagnostic only (no postflop re-solve, not an outer-loop step)',
                 fontsize=10.5, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(os.path.normpath(path), facecolor=SURF, bbox_inches='tight')


if __name__ == '__main__':
    main()
