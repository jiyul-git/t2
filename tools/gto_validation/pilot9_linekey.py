#!/usr/bin/env python3
"""Continuation tables keyed by canonical preflop action line (plan J, section A).

    pilot9_linekey.py tolines <node_manifest> <source_census.json> <out_dir>
        node-keyed tables -> line-keyed tables (+ line manifest). The line comes from the source tree's terminal enumeration.
    pilot9_linekey.py resolve <line_manifest> <target_census.json> <out_dir>
        line-keyed tables -> node-keyed tables + standard manifest for the target tree (node ids from the target census).
        Checks: every line exists exactly once in the target tree; live mask and pot equal (the Rust loader re-checks both).

Canonical line: '|'.join(f'{actor}:{kind}' + (f'@{to_bb:.6f}' for raise / call / jam)) over every action from the root.
A census is t2_cont_census output (any iteration count; 0 is enough): it lists every flop-reaching pot-share terminal with its
actions, terminal_node, terminal_live_mask and pot_bb.
"""
import json
import os
import sys


def canon(actions):
    out = []
    for a in actions:
        s = f"{a['actor']}:{a['kind']}"
        if a['kind'] in ('raise', 'call', 'jam'):
            s += f"@{a['to_bb']:.6f}"
        out.append(s)
    return '|'.join(out)


def census_index(path):
    by_line, by_node = {}, {}
    for e in json.load(open(path))['terminals']:
        ln = canon(e['actions'])
        assert ln not in by_line, f'duplicate line in census: {ln}'
        by_line[ln] = e
        by_node[e['terminal_node']] = ln
    return by_line, by_node


def tolines(manifest, census, out):
    _, by_node = census_index(census)
    os.makedirs(out, exist_ok=True)
    base = os.path.dirname(manifest)
    files = []
    for t in json.load(open(manifest))['tables']:
        tab = json.load(open(os.path.join(base, t['file'])))
        ln = by_node[tab['node']]
        tab['line'] = ln
        tab['line_source_node'] = tab['node']
        fn = f"line_{len(files):03d}.json"
        json.dump(tab, open(os.path.join(out, fn), 'w'))
        files.append({'file': fn, 'line': ln})
    json.dump({'schema': 't2_hu_continuation_line_manifest_v1', 'tables': files}, open(os.path.join(out, 'line_manifest.json'), 'w'), indent=1)
    print(f'{len(files)} tables keyed by line')


def resolve(line_manifest, census, out):
    by_line, _ = census_index(census)
    os.makedirs(out, exist_ok=True)
    base = os.path.dirname(line_manifest)
    files, mapping = [], {}
    for t in json.load(open(line_manifest))['tables']:
        tab = json.load(open(os.path.join(base, t['file'])))
        ln = tab['line']
        assert ln == t['line']
        e = by_line.get(ln)
        assert e is not None, f'line not in target tree: {ln}'
        assert e['terminal_live_mask'] == tab['live'], (ln, e['terminal_live_mask'], tab['live'])
        assert abs(e['pot_bb'] - tab['pot_bb']) < 1e-9, (ln, e['pot_bb'], tab['pot_bb'])
        node = e['terminal_node']
        mapping[tab['line_source_node']] = node
        tab['node'] = node
        fn = f'node{node}.json'
        assert fn not in [f['file'] for f in files], f'two lines resolve to node {node}'
        json.dump(tab, open(os.path.join(out, fn), 'w'))
        files.append({'file': fn})
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': files}, open(os.path.join(out, 'manifest.json'), 'w'))
    json.dump(mapping, open(os.path.join(out, 'node_map_source_to_target.json'), 'w'), indent=1)
    print(f'{len(files)} tables resolved; map {mapping}')


if __name__ == '__main__':
    {'tolines': tolines, 'resolve': resolve}[sys.argv[1]](*sys.argv[2:5])
