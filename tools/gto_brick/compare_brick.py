"""Compare t2_cont_panel artifacts solved with brick merge off (exact) and on (T2_BRICK_MERGE=1), board by board.
  python3 compare_brick.py <dir_off> <dir_on> <terminal.json> [out.json]
Per board and seat: solve time ratio, and the class value difference |V_on - V_off| (gross_eps, bb) weighted by the
class's valid mass (combo weight that arrives), mean and max; plus the range-mean difference (= what feeds a terminal value).
Brick share = merged cards / available cards (turn context, mean over river contexts)."""
import json, os, sys

off_d, on_d = sys.argv[1], sys.argv[2]
keep = {p['position']: p['class_keep_fraction'] for p in json.load(open(sys.argv[3]))['players']}
rows = []
for f in sorted(os.listdir(on_d)):
    if not f.endswith('.json') or f.endswith('strategy.json'):
        continue
    a, b = json.load(open(os.path.join(off_d, f))), json.load(open(os.path.join(on_d, f)))
    ctx = b['brick_merge']['contexts']
    turn = ctx[0]
    riv = ctx[1:]
    r = {'board': a['board'], 'stratum': a['stratum'],
         'solve_s_off': a['cost']['solve_ms'] / 1e3, 'solve_s_on': b['cost']['solve_ms'] / 1e3,
         'iters_off': a['iterations'], 'iters_on': b['iterations'],
         'expl_off': a['exploitability_pct_pot'], 'expl_on': b['exploitability_pct_pot'],
         'turn_bricks': [x[0] for x in turn['bricks']], 'turn_brick_share': len(turn['bricks']) / turn['available'],
         'river_brick_share_mean': sum(len(c['bricks']) / c['available'] for c in riv) / len(riv) if riv else None,
         'seats': {}}
    r['speedup'] = r['solve_s_off'] / r['solve_s_on']
    r['per_iter_speedup'] = (r['solve_s_off'] / r['iters_off']) / (r['solve_s_on'] / r['iters_on'])
    for pa, pb in zip(a['players'], b['players']):
        va, vb = pa['gross_eps'], pb['gross_eps']
        # own arriving combo weight per class = keep fraction x combos on the board
        m = [k * c for k, c in zip(keep[pa['position']], pa['combos_on_board'])]
        d = [(abs(x - y), w) for x, y, w in zip(va, vb, m) if x is not None and y is not None and w > 0]
        W = sum(w for _, w in d)
        top = sorted(((abs(x - y), k) for k, (x, y, w) in enumerate(zip(va, vb, m)) if x is not None and y is not None and w > 0.01), reverse=True)[:3]
        ia, ib = a['invariant']['range_mean_gross'][pa['postflop_role'] == 'IP'], b['invariant']['range_mean_gross'][pb['postflop_role'] == 'IP']
        r['seats'][pa['position']] = {'mean_abs_diff_bb': sum(x * w for x, w in d) / W,
                                      'max_abs_diff_bb_reached': top[0][0] if top else None, 'top_classes': top,
                                      'range_mean_off_bb': ia, 'range_mean_diff_bb': ib - ia}
    rows.append(r)
for r in rows:
    print(f"{r['board']} {r['stratum']:17s} speed x{r['speedup']:.2f} (per iter x{r['per_iter_speedup']:.2f}) iters {r['iters_off']}/{r['iters_on']} "
          f"turn bricks {len(r['turn_bricks'])} ({','.join(r['turn_bricks'])}) river share {r['river_brick_share_mean']:.3f}")
    for s, v in r['seats'].items():
        print(f"   {s}: class |d| mean {v['mean_abs_diff_bb']:.4f} max(keep*combos>0.01) {v['max_abs_diff_bb_reached']:.4f} bb  range-mean d {v['range_mean_diff_bb']:+.4f} bb (of {v['range_mean_off_bb']:.3f})")
if len(sys.argv) > 4:
    json.dump(rows, open(sys.argv[4], 'w'), indent=1)
