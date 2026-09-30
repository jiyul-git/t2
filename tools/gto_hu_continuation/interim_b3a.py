#!/usr/bin/env python3
"""B3a interim: B (factorized) at trunk iteration 50 vs A' (monolithic, same simultaneous schedule) and A at iteration 50.

    python3 tools/gto_hu_continuation/interim_b3a.py [B_run.json]

The B file is the 50-iteration re-run (deterministic; checked against the main B log line at iteration 50). The
registered criteria are applied for orientation only: the registered verdict is on the 400-iteration runs.
"""
import json
import sys

sys.path.insert(0, 'tools/gto_hu_continuation')
import compare_b3a as c  # noqa: E402


def at(run, it):
    """run truncated to its checkpoint at iteration `it`"""
    tr = [t for t in run['trace'] if t['iteration'] <= it]
    last = tr[-1]
    assert last['iteration'] == it, (last['iteration'], it)
    return run | {'final': last['eval'], 'root_mix': last['root_mix'], 'trace': tr, 'time_split': last['time_split']}


def main():
    bpath = sys.argv[1] if len(sys.argv) > 1 else 'b3a_rerun_B_1.json'
    B = c.load(bpath)
    A2, A = c.load('b3a_A2_mono_sim.json'), c.load('b3a_A_mono_alt.json')
    B50 = at(B, 50)
    out = {'B_file': bpath, 'iteration': 50, 'note': 'interim, not the registered verdict'}
    for tag, ref in (("A'@50", at(A2, 50)), ('A@50', at(A, 50)), ("A'@400", A2), ('A@400', A)):
        r = c.compare(ref, B50)
        out[f'B@50_vs_{tag}'] = {'checks': r['checks'], 'players': r['players'],
                                  'strategy_max_abs_diff': max(s['max_abs_diff'] for s in r['strategy']),
                                  'strategy': [{k: s[k] for k in ('line', 'player', 'actions', 'mix_x', 'mix_y', 'max_abs_diff')} for s in r['strategy']]}
    ev = lambda run: {run['positions'][p['player']]: {'range_value': p['range_value'], 'br_gain_bb': p['br_gain_bb']} for p in run['final']['players']} | \
        {'exploitability_pct_pot': run['final']['exploitability_pct_pot'], 'conservation_error': run['final']['conservation_error']}
    out['state'] = {'B@50': ev(B50), "A'@50": ev(at(A2, 50)), 'A@50': ev(at(A, 50))}
    ts = B50['time_split']
    it = 50
    out['B_time'] = {'wall_s_to_50': B50['trace'][-1]['seconds'], 'threads': 2,
                     'per_trunk_iteration_s': {k: ts[k] / it for k in ('collect', 'frontier_solve', 'trunk_update')},
                     'evaluation_s_total': ts['evaluation'],
                     'hu_frontier_share_of_iteration_time': ts['frontier_solve'] / (ts['collect'] + ts['frontier_solve'] + ts['trunk_update']),
                     'frontiers': B.get('frontiers'), 'counters': B.get('counters'), 'peak_rss_kb': B.get('peak_rss_kb')}
    A2ts = at(A2, 50)['time_split']
    out["A'_time"] = {'wall_s_to_50': at(A2, 50)['trace'][-1]['seconds'], 'threads': 1, 'per_iteration_s': A2ts['trunk_update'] / 50}
    json.dump(out, open(c.O + 'b3a_interim_it50.json', 'w'), indent=1)
    for k, v in out.items():
        if k.startswith('B@50_vs'):
            print(k, v['checks'], 'strategy max', round(v['strategy_max_abs_diff'], 4))
            print('   ', {p: (round(d['range_value_diff_bb'], 4), round(d['class_mean_abs_diff_bb'], 4)) for p, d in v['players'].items()})
    print(json.dumps(out['state'], indent=1))
    print(json.dumps(out['B_time'], indent=1)[:1500])


if __name__ == '__main__':
    main()
