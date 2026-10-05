#!/usr/bin/env python3
"""Step 3a helpers (HU 3-bet terminals, data/gto_validation/pilot9/step3/t3_selection.json).
    pilot9_t3.py specs              print "name:spec" for the selected terminals
    pilot9_t3.py tables <root>      A4c tables for the selected terminals (root/terminals/term_<name>.json, root/<name>/flops),
                                    then a manifest of the 8 OL state-2 SRP tables + the new 3-bet tables in root/tables_all
"""
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pilot9_tables as PT  # noqa: E402

SEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data/gto_validation/pilot9/step3/t3_selection.json')
S2_TABLES = '/home/user/gto_ckpt/ol/s2/tables/'


def sel():
    return json.load(open(SEL))['terminals']


def main():
    if sys.argv[1] == 'specs':
        print(' '.join(f"{t['name']}:{t['spec']}" for t in sel()))
        return
    root = sys.argv[2]
    nodes = {t['name']: t['node'] for t in sel()}
    for name, node in nodes.items():
        assert json.load(open(os.path.join(root, 'terminals', f'term_{name}.json')))['terminal_node'] == node, name
    os.makedirs(root + '/new_tables', exist_ok=True)
    PT.solved(root, root + '/new_tables', nodes, 'term_')
    out = root + '/tables_all/'
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(S2_TABLES + 'node*.json') + glob.glob(root + '/new_tables/node*.json'):
        shutil.copy(f, out)
    files = sorted(os.path.basename(f) for f in glob.glob(out + 'node*.json'))
    assert len(files) == 8 + len(nodes), len(files)
    json.dump({'schema': 't2_hu_continuation_manifest_v1', 'tables': [{'file': f} for f in files]}, open(out + 'manifest.json', 'w'))


if __name__ == '__main__':
    main()
