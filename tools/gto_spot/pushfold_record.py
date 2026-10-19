#!/usr/bin/env python3
"""Push/fold bucket record (docs/GTO_PUSHFOLD_10_25_V1.md section 3) from a whole-tree dump.

    python3 tools/gto_spot/pushfold_record.py <S>        -> data/gto_spot/records/pf<S>.json  (push/fold buckets)
    python3 tools/gto_spot/pushfold_record.py <S> s      -> data/gto_spot/records/s<S>.json   (30 / 40 bb, docs/GTO_STACK_30_40_V1.md)

Nodes kept: every decision node whose line before the actor holds at most two non-fold actions and no call, i.e. first-in (RFI),
facing a single open or jam, and the opener facing a single 3-bet jam. Per node: overall mix, per-class strategy and action EVs,
arriving combos per class; `unsupported_low_reach` when the actor arrives with < 1e-3 combos or the aggressor's action is taken with
< 1 combo (frequencies there are not used, same idea as standard amendment 8).
"""
import json
import os
import sys

S = int(sys.argv[1])
PFX = sys.argv[2] if len(sys.argv) > 2 else 'pf'
if PFX == 'pf':
    W = f'/home/user/gto_ckpt/pushfold/pf{S}'
    CFG = f'/home/user/t2/data/gto_spot/pushfold/cfg_pf{S}.json'
    STD = 'docs/GTO_PUSHFOLD_10_25_V1.md'
    MENU = 'jam / fold' if S == 10 else 'fold / open 2.0 (SB 3.0) / jam; facing an open: fold / call / 3-bet jam; facing a jam: fold / call'
else:
    W = f'/home/user/gto_ckpt/stack3040/s{S}'
    CFG = f'/home/user/t2/data/gto_spot/stack3040/cfg_s{S}.json'
    STD = 'docs/GTO_STACK_30_40_V1.md'
    MENU = 'Plan A v2b parent menu: open 2.0 (SB 3.0, SB limp), 3-bet 3.0x (blinds 3.5x / 4.0x) or jam, 4-bet jam only'
OUT = f'/home/user/t2/data/gto_spot/records/{PFX}{S}.json'
RANKS = '23456789TJQKA'


def labels():
    out = []
    for i in range(13):
        for j in range(13):
            hi, lo = max(i, j), min(i, j)
            out.append(RANKS[i] * 2 if i == j else RANKS[hi] + RANKS[lo] + ('o' if j > i else 's'))
    return out


LAB = labels()
COMBOS = [6 if len(x) == 2 else (4 if x[2] == 's' else 12) for x in LAB]


def kind(label):
    a = label.split(':', 1)[1] if ':' in label else label
    return a.split(' ')[0].lower()   # fold / call / raise / 3-bet / all-in / check


def main():
    final_n = int(open(f'{W}/final_n').read())
    exact = json.load(open(f'{W}/exact_{final_n}.json'))
    nodes = {}
    for line in open(f'{W}/dump.jsonl'):
        d = json.loads(line)
        nodes[tuple(d['path'])] = d
    kept = []
    for path, d in nodes.items():
        prior = d['line']
        act = [p for p in prior if kind(p) != 'fold']
        if len(act) > 2 or any(kind(p) in ('call', 'check') for p in prior):
            continue
        arr = [r * 1326 for r in d['actor_reach']]
        m = sum(arr)
        mix = {a: (sum(arr[h] * d['sigma'][i][h] for h in range(169)) / m if m > 0 else None) for i, a in enumerate(d['actions'])}
        # aggressor support: combos with which the last non-fold action before the actor was taken
        agg = None
        if act:
            k = max(i for i, p in enumerate(prior) if kind(p) != 'fold')
            pd = nodes.get(tuple(path[:k]))
            if pd is not None:
                ai = path[k]
                agg = sum(pd['actor_reach'][h] * 1326 * pd['sigma'][ai][h] for h in range(169))
            else:
                agg = 0.0   # below the dump's reach floor (1e-6)
        kept.append({
            'line': prior, 'situation': 'first_in' if not act else ('facing_open_or_jam' if len(act) == 1 else ('facing_3bet_jam' if PFX == 'pf' else 'facing_3bet')),
            'actor': d['actor'], 'actions': d['actions'], 'reach_prob': d['reach_prob'],
            'actor_arriving_combos': round(m, 4), 'aggressor_action_combos': None if agg is None else round(agg, 4),
            'unsupported_low_reach': m < 1e-3 or (agg is not None and agg < 1.0),
            'mix': {a: (None if v is None else round(v, 5)) for a, v in mix.items()},
            'class_strategy': {a: [round(x, 4) for x in d['sigma'][i]] for i, a in enumerate(d['actions'])},
            'class_ev_bb': {a: [round(x, 4) for x in d['ev'][i]] for i, a in enumerate(d['actions'])},
            'class_arriving_combos': [round(x, 5) for x in arr],
        })
    kept.sort(key=lambda r: (len([p for p in r['line'] if kind(p) != 'fold']), len(r['line'])))
    rec = {
        'schema': 'pushfold_record_v1', 'id': f'{PFX}{S}', 'stack_bb': S, 'config': json.load(open(CFG)),
        'menu': MENU,
        'iterations': final_n, 'gap_total_exact_bb': exact['gap_total'], 'gaps_exact_bb': exact['gaps'], 'evs_bb': exact['evs'],
        'G2_gap_max_bb': 0.010, 'G2': exact['gap_total'] <= 0.010,
        'solver': {'engine': 'vendored gtopen preflop DCFR', 'driver': 't2_pf_solve', 'eq_seed': 202, 'multiway_seed': 202,
                   'eq_samples': exact['eq_samples'], 'multiway_model': exact['multiway_model'],
                   'iterate_mw_skip_below': 1e-9, 'gap_measured_with_skip': 0},
        'status': 'quick', 'symmetric_stack_assumption': True, 'static_continuation_for_flop_pots': S >= 15, 'chip_ev': True,
        'db_promotion': 'forbidden', 't2_connection': 'needs user approval',
        'caveats': ([] if S == 10 else ['flat calls into a flop pot (open-call, multiway calls) are valued by the static continuation (positional realization vs SPR); observed at 15 bb: BB defends ~100 % vs a 2.0 open from every seat (fold <= 0.05 %) because with the 1 bb ante the call needs ~18 % realized equity - call vs fold there is model-dependent and a refinement target; all-in decisions (jam, call a jam, 3-bet jam) do not use the continuation model']),
        'class_labels': LAB, 'class_combos': COMBOS,
        'standard': STD, 'nodes': kept,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, 'w'), separators=(',', ':'))
    print(f'{PFX}{S}: {len(kept)} nodes, gap {exact["gap_total"]:.6f} bb, {final_n} iterations -> {OUT}')
    for r in kept:
        if r['situation'] == 'first_in':
            print('  RFI', r['actor'], {a: v for a, v in r['mix'].items()})


if __name__ == '__main__':
    main()
