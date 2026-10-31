"""Count merged cards per board from t2_cont_panel artifacts solved with T2_BRICK_MERGE=1 (any iteration count, e.g. 0).
  python3 brick_counts.py <dir> [<dir> ...]
turn: bricks / merged on the flop's 49 turn cards; river: mean over the 49 turn cards of bricks / merged per 48 river cards.
'merged' counts suit-isomorphism representatives that reuse another branch (their iso siblings follow them)."""
import json, os, sys
for d in sys.argv[1:]:
    print(d)
    for f in sorted(os.listdir(d)):
        if not f.endswith('.json') or 'strategy' in f:
            continue
        a = json.load(open(os.path.join(d, f)))
        c = a['brick_merge']['contexts']
        t, riv = c[0], c[1:]
        tm = sorted(k for k, v in t['bricks'].items() if v.get('merged'))
        rb = sum(len(x['bricks']) for x in riv) / len(riv)
        rm = sum(x['merged_iso_reps'] for x in riv) / len(riv)
        print(f"  {a['board']:7s} turn bricks {len(t['bricks']):2d} merged {t['merged_iso_reps']:2d} {tm}  river bricks {rb:5.2f} merged {rm:5.2f} (per 48)")
