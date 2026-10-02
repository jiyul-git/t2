#!/usr/bin/env python3
"""R2-B: summarize an external preflop chart set into defend/call/3bet/fold frequencies.

Source (default): matthiola0/poker-hand-review gto-preflop/mtt/8max/charts
(commit recorded in output).  The repository states only "8-max MTT, four-action
(raise/allin/call/fold)"; it does not state the solver, the ante size or the open
size.  The audit therefore treats it as a public solver-approximate chart with
partially unknown conditions (confidence: medium-low), and as 8-max only.

Frequencies are combo-weighted over 1326 combos (pair 6 / suited 4 / offsuit 12);
hands missing from a chart are folds.  3bet = raise + allin.

Usage: python tools/r2_reference_charts.py <chart_root> [out.json]
"""
import json, os, subprocess, sys

N = lambda k: 6 if len(k) == 2 else (4 if k.endswith('s') else 12)


def summarize(path):
    d = json.load(open(path))
    acts = d.get('actions') or {}
    tb = call = 0.0
    tb_hands = {}
    cont_hands = {}
    for k, a in acts.items():
        n = N(k)
        r = float(a.get('raise', 0)) + float(a.get('allin', 0))
        c = float(a.get('call', 0))
        tb += n * r
        call += n * c
        tb_hands[k] = r
        cont_hands[k] = r + c
    allin = sum(N(k) * float(a.get('allin', 0)) for k, a in acts.items())
    return {'defend': round((tb + call) / 1326, 4), '3bet': round(tb / 1326, 4),
            'allin': round(allin / 1326, 4), 'call': round(call / 1326, 4),
            'fold': round(1 - (tb + call) / 1326, 4),
            '3bet_share': round(tb / (tb + call), 4) if tb + call else None,
            'hand_3bet': tb_hands, 'hand_continue': cont_hands}


def summarize_rfi(path):
    d = json.load(open(path))
    acts = d.get('actions') or {}
    tot = sum(N(k) * (float(a.get('raise', 0)) + float(a.get('allin', 0)) + float(a.get('call', 0)))
              for k, a in acts.items())
    hands = {k: float(a.get('raise', 0)) + float(a.get('allin', 0)) + float(a.get('call', 0))
             for k, a in acts.items()}
    return {'open': round(tot / 1326, 4), 'hand_open': hands}


def main():
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    repo = os.path.abspath(os.path.join(root, '..', '..', '..', '..'))
    try:
        sha = subprocess.check_output(['git', '-C', repo, 'rev-parse', 'HEAD'], text=True).strip()
    except Exception:
        sha = None
    res = {'source': 'matthiola0/poker-hand-review gto-preflop/mtt/8max/charts',
           'source_commit': sha,
           'stated_conditions': '8-max MTT, four-action; solver, ante size and open size not stated',
           'vs_open': {}, 'rfi': {}}
    for st in sorted((s for s in os.listdir(root) if s.endswith('bb')), key=lambda s: int(s[:-2])):
        vo = os.path.join(root, st, 'vs-open')
        if os.path.isdir(vo):
            for fn in sorted(os.listdir(vo)):
                if '-vs-' in fn and 'open-vs' not in fn and 'limp' not in fn:
                    res['vs_open']['%s|%s' % (st, fn[:-5])] = summarize(os.path.join(vo, fn))
        rf = os.path.join(root, st, 'rfi')
        if os.path.isdir(rf):
            for fn in sorted(os.listdir(rf)):
                res['rfi']['%s|%s' % (st, fn[:-5])] = summarize_rfi(os.path.join(rf, fn))
    s = json.dumps(res, ensure_ascii=False)
    if out:
        open(out, 'w').write(s + '\n')
    for k, v in res['vs_open'].items():
        print(k, {x: v[x] for x in ('defend', '3bet', 'allin', 'call', 'fold', '3bet_share')})
    for k, v in res['rfi'].items():
        if k.split('|')[0] in ('20bb', '25bb', '30bb', '40bb', '50bb', '100bb'):
            print(k, v['open'])


if __name__ == '__main__':
    main()
