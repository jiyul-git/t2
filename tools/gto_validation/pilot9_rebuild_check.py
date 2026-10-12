#!/usr/bin/env python3
"""Rebuild checks against the committed evidence (pilot9_rebuild_run.sh). Never stops the chain; writes
data/gto_validation/pilot9/rebuild/check_<stage>.json with the max |diff| of every compared number (0.0 = bit-exact).
    python3 tools/gto_validation/pilot9_rebuild_check.py S|H|OL|T3|L
"""
import glob
import json
import os
import sys

R = '/home/user/gto_ckpt/'
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data/gto_validation/pilot9/')
OUT = D + 'rebuild/'
POS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN')


def rfi(export):
    t = json.load(open(export))
    out = {}
    for pos in POS:
        p = next(x for x in t['path_nodes'] if x['actor'] == pos)
        out[pos] = 1 - p['mix'].get('Fold', 0.0)
    return t['gap_total'], out


def cmp_state(export, ref):
    if not os.path.exists(export):
        return {'missing': export}
    g, r = rfi(export)
    d = {pos: abs(r[pos] - ref['rfi'][pos]['open']) for pos in POS}
    return {'gap_total': g, 'gap_total_ref': ref['gap_total'], 'gap_abs_diff': abs(g - ref['gap_total']),
            'rfi_max_abs_diff': max(d.values()), 'bit_exact': g == ref['gap_total'] and max(d.values()) == 0.0}


def main():
    st = sys.argv[1]
    res = {'schema': 'pilot9_rebuild_check_v1', 'stage': st}
    if st == 'S':
        res['S'] = cmp_state(R + 'c3/export_btn.json', json.load(open(D + 's_analysis.json'))['metrics']['S'])
    elif st == 'H':
        res['H'] = cmp_state(R + 'h1/H/export_btn.json', json.load(open(D + 'h1/h1_analysis.json'))['metrics']['H'])
    elif st == 'OL':
        for k in (1, 2):
            res[f's{k}'] = cmp_state(R + f'ol/s{k}/export_btn.json', json.load(open(D + f'ol/state{k}_freq.json'))['metrics'])
        for k in (0, 1):
            f = R + f'ol/step{k}/report.json'
            if not os.path.exists(f):
                res[f'step{k}'] = {'missing': f}
                continue
            a, b = json.load(open(f)), json.load(open(D + f'ol/step{k}_report.json'))
            diffs = [abs(a['nodes'][n]['seats'][p][q] - b['nodes'][n]['seats'][p][q])
                     for n in b['nodes'] for p in b['nodes'][n]['seats'] for q in ('D', 'U', 'signed')]
            res[f'step{k}'] = {'D_U_signed_max_abs_diff': max(diffs), 'decision': a['decision'], 'decision_ref': b['decision'],
                               'same_decision': a['decision'] == b['decision']}
    elif st == 'T3':
        f = R + 'step3/t3/tables_report.json'
        res['tables'] = sorted(os.path.basename(x) for x in glob.glob(R + 'step3/t3/tables_all/node*.json'))
        res['n_tables'] = len(res['tables'])
        res['report_present'] = os.path.exists(f)
    elif st == 'L':
        man = json.load(open(R + 'step3/j/mr3_resolved/manifest.json'))
        lm = json.load(open(R + 'step3/j/lines/line_manifest.json'))
        ref = json.load(open(D + 'step3/j_node_map_mr2_to_mr3.json'))
        nodes = sorted(int(t['file'][4:-5]) for t in man['tables'])
        res['n_tables'] = len(nodes)
        res['node_set_equals_committed_map'] = nodes == sorted(ref.values())
        res['n_lines'] = len(lm.get('tables', lm.get('lines', [])))
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(OUT + f'check_{st}.json', 'w'), indent=1)
    print(json.dumps(res)[:600])


if __name__ == '__main__':
    main()
