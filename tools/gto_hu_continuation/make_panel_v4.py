#!/usr/bin/env python3
"""A4c nested per-terminal panels (data/gto_terminal_expansion/a4c/prereg.json).

    python3 tools/gto_hu_continuation/make_panel_v4.py

panel_v3_144 (12 boards per stratum) is kept verbatim. Per stratum, ONE sequential draw continues panel_v1/v2/v3's scheme
(proportional to raw-flop count, without replacement, from the stratum pool minus the 144 panel boards), seed 20261004,
strata in sorted order, L_s = max(target6, target28) - 12 draws. Node 6 takes the first target6 - 12 of that sequence and
node 28 the first target28 - 12, so the two extensions are nested in one sequence (shared boards where both extend).
The v2/v3 coverage rule (>= 3 per texture / rank category) already holds on the 144 base and counts only grow, so no
rejection step applies. weight = P(s) / n_s per terminal panel.
"""
import hashlib
import itertools
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_panel as mp  # noqa: E402
from make_panel_v2 import tags  # noqa: E402

SEED = 20261004
TARGET = {
    6: {'paired/A': 15, 'paired/J_or_lower': 21, 'paired/KQ': 17, 'rainbow/A': 18, 'rainbow/J_or_lower': 27, 'rainbow/KQ': 25,
        'twotone/A': 21, 'twotone/J_or_lower': 27, 'twotone/KQ': 25, 'monotone/A': 12, 'monotone/J_or_lower': 12, 'monotone/KQ': 12},
    28: {'paired/J_or_lower': 19, 'paired/KQ': 14, 'rainbow/J_or_lower': 23, 'rainbow/KQ': 19, 'twotone/J_or_lower': 30, 'twotone/KQ': 41,
         'paired/A': 12, 'rainbow/A': 12, 'twotone/A': 12, 'monotone/A': 12, 'monotone/J_or_lower': 12, 'monotone/KQ': 12},
}
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    v3 = json.load(open(os.path.join(ROOT, 'data/gto_hu_continuation/panel_v3_144.json')))
    v2 = json.load(open(os.path.join(ROOT, 'data/gto_hu_continuation/panel_v2_72.json')))
    assert {n: sum(t.values()) - 144 for n, t in TARGET.items()} == {6: 88, 28: 74}
    deck = [(r, s) for r in range(13) for s in range(4)]
    classes = {}
    for f in itertools.combinations(deck, 3):
        k = mp.canon(f)
        classes.setdefault(k, [0, mp.stratum(f)])
        classes[k][0] += 1
    strata = {}
    for k, (n, st) in classes.items():
        strata.setdefault(st, []).append((k, n))
    old = {}
    for f in v3['panel']:
        old.setdefault(f['stratum'], []).append(f)
    assert all(len(v) == 12 for v in old.values()) and set(old) == set(TARGET[6]) == set(TARGET[28])
    rng = random.Random(SEED)
    seq = {}
    for st in sorted(strata):
        members = sorted(strata[st])
        have = {f['board'] for f in old[st]}
        pool = [(k, n) for k, n in members if mp.fmt(k) not in have]
        assert len(pool) == len(members) - 12
        L = max(TARGET[6][st], TARGET[28][st]) - 12
        draws = []
        for _ in range(L):
            tot = sum(n for _, n in pool)
            x = rng.uniform(0, tot)
            acc = 0
            for i, (k, n) in enumerate(pool):
                acc += n
                if x <= acc:
                    k, n = pool.pop(i)
                    draws.append((mp.fmt(k), n))
                    break
        seq[st] = draws
    out = {}
    for term in (6, 28):
        panel = []
        for st in sorted(strata):
            raw = sum(n for _, n in strata[st])
            m = TARGET[term][st]
            for f in old[st]:
                panel.append({**{k: v for k, v in f.items() if k != 'weight'}, 'weight': raw / 22100 / m, 'in_panel_v3_144': True})
            for b, n in seq[st][:m - 12]:
                panel.append({'board': b, 'stratum': st, 'raw_flops_of_class': n, 'weight': raw / 22100 / m,
                              'origin': f'a4c_extension_seed_{SEED}', 'in_panel_v3_144': False, **tags(b)})
        boards = [p['board'] for p in panel]
        assert len(boards) == len(set(boards)) == 144 + {6: 88, 28: 74}[term]
        assert all(sum(1 for p in panel if p['stratum'] == st) == TARGET[term][st] for st in strata)
        assert abs(sum(p['weight'] for p in panel) - 1.0) < 1e-12
        text = json.dumps(panel, sort_keys=True).encode()
        doc = {'schema': 'flop_panel_v4_nested_per_terminal', 'terminal_node': term,
               'parent_panel': {'file': 'panel_v3_144.json', 'panel_hash_sha256': v3['panel_hash_sha256']},
               'ancestor_panel_hashes': [v3['panel_hash_sha256'], v2['panel_hash_sha256']],
               'seed_extension': SEED, 'allocation': TARGET[term], 'new_boards': len(boards) - 144,
               'strata': v3['strata'], 'panel': panel, 'panel_hash_sha256': hashlib.sha256(text).hexdigest(),
               'estimator': 'stratified: sum_strata P(stratum) * mean(panel values in stratum) (n_s may differ by stratum)',
               'caveat': v3['caveat'], 'extension_sequence': {st: [b for b, _ in v] for st, v in seq.items()}}
        path = os.path.join(ROOT, f'data/gto_hu_continuation/panel_v4_node{term}.json')
        json.dump(doc, open(path, 'w'), indent=1)
        out[term] = {'file': path, 'hash': doc['panel_hash_sha256'], 'boards': len(boards), 'new': doc['new_boards']}
        print(term, out[term])
    shared = set(seq_b for st in seq for seq_b, _ in seq[st][:min(TARGET[6][st], TARGET[28][st]) - 12])
    print('boards shared by both extensions:', len(shared))


if __name__ == '__main__':
    main()
