#!/usr/bin/env python3
"""Table-baseline ± deviation samples (compute only; nothing consumes them).

Plays a mixed-persona tournament with the persistent book, then for every live
table computes reads.table_deviation(observer -> target, others = table) and
compares the sign with the target's true profile axes (never visible to bots).

  python tools/table_deviation_samples.py [SEED] [HANDS] [OUT.json]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('T2_BOT_LOG', '0')
import fieldsim as FS
import reads as RD

TRUTH = {'loose': lambda p: -p['tight'], 'aggr': lambda p: p['aggr'],
         'fold': None, 'bluff': lambda p: p['bluff']}


def snapshot(f, hand_no):
    rows = []
    for tid, tb in f.tables.items():
        pids = [p['pid'] for p in tb.alive()]
        for o in pids:
            for t in pids:
                if t == o:
                    continue
                d = RD.table_deviation(f.book, o, t, pids)
                prof = f.players[t]['prof']
                rows.append({'hand': hand_no, 'table': tid, 'obs': o, 'tgt': t, 'type': prof.get('type'),
                             'true': {'tight': prof['tight'], 'aggr': prof['aggr'], 'bluff': prof['bluff']},
                             'dev': d})
    return rows


def run(seed, hands, entries=27, every=20):
    """Snapshot every `every` hands (pairs repeat across snapshots as samples grow)."""
    FS.Field._log_bot_hand = lambda *a, **k: None
    f = FS.Field(entries=entries, start_stack=30000, hero_pid=-1, seed=seed, hands_per_level=12)
    rows = []
    for k in range(1, hands + 1):
        if f.remaining() <= 1:
            break
        f.hand_no += 1
        f.advance_level()
        for tb in list(f.tables.values()):
            if tb.n() >= 2:
                f._play_table(tb)
        f._collect_busts(); f._balance(notify=False); f.notes = []
        if k % every == 0:
            rows += snapshot(f, k)
    return f, rows


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs)/n, sum(ys)/n
    sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    sx = sum((x-mx)**2 for x in xs) ** 0.5
    sy = sum((y-my)**2 for y in ys) ** 0.5
    return sxy/(sx*sy) if sx and sy else None


BANDS = ((0, 9), (10, 29), (30, 10**9))


def summary(rows):
    out = {}
    for axis, tf in TRUTH.items():
        pts = [(r['dev'][axis]['dev'], r) for r in rows if r['dev'][axis]['dev'] is not None]
        if tf:
            by = {}
            for lo, hi in BANDS:
                sub = [(p, r) for p, r in pts if lo <= r['dev'][axis]['n'] <= hi]
                c = corr([p for p, _ in sub], [tf(r['true']) for _, r in sub])
                by['n%d-%s' % (lo, hi if hi < 10**9 else '')] = {
                    'pairs': len(sub), 'corr': round(c, 3) if c is not None else None}
        ns = sorted(r['dev'][axis]['n'] for _, r in pts)
        s = {'pairs': len(pts), 'median_n': ns[len(ns)//2] if ns else 0,
             'dev_range': [round(min(p for p, _ in pts), 3), round(max(p for p, _ in pts), 3)] if pts else None}
        if tf:
            s['corr_with_truth'] = (round(corr([p for p, _ in pts], [tf(r['true']) for _, r in pts]), 3)
                                    if len(pts) >= 3 else None)
            s['by_n'] = by
        out[axis] = s
    return out


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 21
    hands = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    f, rows = run(seed, hands)
    s = summary(rows)
    print(json.dumps({'seed': seed, 'hands': hands, 'summary': s}, indent=1))
    if len(sys.argv) > 3:
        json.dump({'seed': seed, 'hands': hands, 'summary': s, 'rows': rows}, open(sys.argv[3], 'w'), indent=1)


if __name__ == '__main__':
    main()
