#!/usr/bin/env python3
"""Import Termux worker v1 spots (t2_gto_spot_v2 files, old sha256 address) into the sk1 store, without re-solving.

    python3 tools/gto_db_v2/migrate_termux_v1.py --ref origin/chatgpt/gto-db-worker-v1-20261003 --expect 30=44 [--expect 25=44 ...]  # dry run
    ... --commit      # append to data/gto_db_v2/solutions.jsonl through Index.add_solution (only after the worker has finished)

Source files are read through git (ls-tree / cat-file) or from --dir; they are never modified, moved or deleted.
Per old spot: check the old address (sha256 of its own canonical state JSON), rebuild the T2 raw state, canonical_state() -> sk1
spot_key, check the canonical history equals the old explicit history, and import every solution's strategy object verbatim
(frequencies untouched; the round trip is verified value by value and byte by byte in canonical JSON).
Checks: expected spot count per stack; no two old spots on one sk1 key (abort and report, never overwrite); every add must be
accepted by Index.add_solution, otherwise the run stops and reports why.
Quality: tier 3 (the solver used a uniform per-player ante with the same dead money, not exact T2 1BB BBA; low-iteration
GTOpen solves). exploitability_pct_pot is not available (the worker records GTOpen gap_total), so it is None.
"""
import argparse
import collections
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index as IX  # noqa: E402
import spot_key as SK  # noqa: E402

ROOT = IX.ROOT
KIND = {'fold': 'fold', 'check': 'check', 'call': 'call', 'raise': 'raise', 'jam': 'allin', 'allin': 'allin'}


def old_key(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def read_source(ref, d):
    if d:
        for p in sorted(glob.glob(os.path.join(d, 'data/gto_db/spots/*/*.json'))):
            yield os.path.relpath(p, d), open(p, 'rb').read()
        return
    names = subprocess.run(['git', '-C', ROOT, 'ls-tree', '-r', '--name-only', ref, 'data/gto_db/spots/'], check=True, capture_output=True, text=True).stdout.split()
    for n in names:
        if n.endswith('.json'):
            yield n, subprocess.run(['git', '-C', ROOT, 'show', f'{ref}:{n}'], check=True, capture_output=True).stdout


def raw_state(st):
    g, b = st['game'], st['blinds']
    if st.get('schema') != 't2_gto_state_v1' or g['street'] != 'preflop':
        raise ValueError(f"unsupported old state schema {st.get('schema')}")
    ante = b['ante']
    model = {'big_blind_ante': 'bb_ante', 'none': 'none', 'per_player': 'per_player'}[ante['model']]
    return {'table_players': g['table_players'], 'hero': st['hero_position'], 'stacks_bb': st['stack']['prehand_bb'],
            'blinds_bb': {'sb': b['sb_bb'], 'bb': b['bb_bb']}, 'ante': {'model': model, 'amount_bb': ante.get('total_bb', 0)},
            'format': g['format'], 'variant': g['variant'], 'icm': None if not st['icm'] else st['icm'],
            'rake': {'pct': st.get('rake_pct', 0), 'cap_bb': 0},
            'history': [{'pos': a['actor'], 'act': KIND[a['kind']], **({'to_bb': a['to_bb']} if 'to_bb' in a else {})} for a in st['history']]}


def same_history(old, canon, table):
    """old explicit history (folds included) vs canonical history: same actors, same kinds, same amounts."""
    if len(old) != len(canon):
        return False
    for a, c in zip(old, canon):
        if SK.pos_name(a['actor'], table) != c['pos'] or KIND[a['kind']] != c['act']:
            return False
        if 'to_bb' in a and SK.num(a['to_bb']) != c.get('to_bb'):
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', default='origin/chatgpt/gto-db-worker-v1-20261003')
    ap.add_argument('--dir')
    ap.add_argument('--expect', action='append', default=[], help='stack=count, e.g. 30=44')
    ap.add_argument('--commit', action='store_true')
    ap.add_argument('--report', default=os.path.join(ROOT, 'data/gto_db_v2/migration_termux_v1_report.json'))
    a = ap.parse_args()
    commit = None if a.dir else subprocess.run(['git', '-C', ROOT, 'rev-parse', a.ref], check=True, capture_output=True, text=True).stdout.strip()
    rep = {'source': {'ref': a.ref, 'commit': commit, 'dir': a.dir}, 'mode': 'commit' if a.commit else 'dry_run', 'errors': []}
    spots = []
    for path, raw in read_source(a.ref, a.dir):
        d = json.loads(raw)
        st = d['state']
        if d.get('schema') != 't2_gto_spot_v2' or d.get('spot_key') != old_key(st) or os.path.basename(path)[:-5] != d['spot_key']:
            rep['errors'].append({'path': path, 'error': 'old address does not match its state'})
            continue
        r = raw_state(st)
        key, canon = SK.key_of(r)
        if not same_history(st['history'], canon['history'], SK.positions(canon['table_players'])):
            rep['errors'].append({'path': path, 'error': 'canonical history differs from the old explicit history'})
            continue
        spots.append({'path': path, 'old_key': d['spot_key'], 'sk1': key, 'raw': r, 'doc': d})
    by_stack = collections.Counter(float(s['doc']['state']['stack']['prehand_bb']) for s in spots)
    rep['spots_by_stack'] = {str(k): v for k, v in sorted(by_stack.items())}
    for e in a.expect:
        stck, n = e.split('=')
        if by_stack.get(float(stck), 0) != int(n):
            rep['errors'].append({'error': f'stack {stck}: expected {n} spots, found {by_stack.get(float(stck), 0)}'})
    dup = collections.defaultdict(list)
    for s in spots:
        dup[s['sk1']].append(s['path'])
    rep['duplicate_sk1'] = {k: v for k, v in dup.items() if len(v) > 1}
    if rep['duplicate_sk1']:
        rep['errors'].append({'error': 'several old spots map to one sk1 key; nothing imported', 'keys': list(rep['duplicate_sk1'])})
    store = IX.V2 if a.commit else os.path.join(tempfile.mkdtemp(), 'solutions.jsonl')
    ix = IX.Index(v2_path=store)
    rep['store'] = store
    imported, refused = [], []
    if not rep['errors']:
        for s in spots:
            for sol in s['doc']['solutions']:
                strat = sol['strategy']
                q = {'tier': 3, 'exploitability_pct_pot': None, 'method': 'GTOpen preflop (Termux worker v1)',
                     'status': sol['quality'].get('status'), 'exact_target_match': sol['quality'].get('exact_target_match'),
                     'gap_total': sol['solver'].get('gap_total'), 'target_gap': sol['solver'].get('target_gap'), 'iteration': sol['solver'].get('iteration'),
                     'notes': ['ante solved as uniform per-player ante with the same total dead money, not exact T2 1BB BBA']}
                src = {'db': 'termux_worker_v1', 'ref': a.ref, 'commit': commit, 'old_path': s['path'], 'old_spot_key': s['old_key'],
                       'old_solution_id': sol['solution_id'], 'solver': sol['solver'], 'strategy_format': 'termux_v1_policy'}
                ok, key, why = ix.add_solution(s['raw'], strat, q, src)
                (imported if ok else refused).append({'old': s['old_key'], 'sk1': key, 'reason': why})
        # round trip: reload the store, compare every strategy with the source, value by value and canonical bytes
        ix2 = IX.Index(v2_path=store)
        mism = 0
        for s in spots:
            got = [x for x in ix2.all(s['sk1']) if x['source'].get('old_spot_key') == s['old_key']]
            for sol in s['doc']['solutions']:
                m = [x for x in got if x['source']['old_solution_id'] == sol['solution_id']]
                src, dst = sol['strategy'], m[0]['strategy'] if m else None
                same = dst is not None and json.dumps(src, sort_keys=True, separators=(',', ':')) == json.dumps(dst, sort_keys=True, separators=(',', ':')) \
                    and all(src['hands'][h][i] == dst['hands'][h][i] for h in src['hands'] for i in range(len(src['actions']))) \
                    and len(src['hands']) == 169
                mism += not same
        rep['roundtrip_strategy_mismatches'] = mism
    rep['imported'] = len(imported)
    rep['refused'] = refused
    rep['ok'] = not rep['errors'] and not refused and rep.get('roundtrip_strategy_mismatches') == 0
    rep['mapping'] = [{'old_spot_key': s['old_key'], 'sk1': s['sk1'], 'label': SK.label(SK.canonical_state(s['raw']))} for s in spots]
    if a.commit:
        os.makedirs(os.path.dirname(a.report), exist_ok=True)
        json.dump(rep, open(a.report + '.tmp', 'w'), indent=1)
        os.replace(a.report + '.tmp', a.report)
    print(json.dumps({k: v for k, v in rep.items() if k != 'mapping'}, indent=1)[:3000])
    sys.exit(0 if rep['ok'] else 1)


if __name__ == '__main__':
    main()
