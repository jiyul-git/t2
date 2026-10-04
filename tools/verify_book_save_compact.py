#!/usr/bin/env python3
"""Tournament book save size / copy speed (UI per-action latency).

E1  sparse hand snapshots (zero counters left out) play the identical
    tournament: same chips and same estimate() for every pair as full snapshots.
R1  unpack_book_d(pack_book_d(d)) == d and copy_book_d(d) == d (no aliasing).
S1  packed JSON is smaller than the full book.
L1  live2 _dump/_load_field round trip restores the same book.
"""
import copy, hashlib, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('T2_BOT_LOG', '0')
import fieldsim as FS
import reads as RD

_sparse = RD._numeric_snapshot


def _full(r):
    return {k: v for k, v in r.items() if k != '_hand_hist' and isinstance(v, (int, float))
            and not isinstance(v, bool)}


def play(snapshot, hands=30):
    RD._numeric_snapshot = snapshot
    try:
        FS.Field._log_bot_hand = lambda *a, **k: None
        f = FS.Field(entries=27, start_stack=30000, hero_pid=-1, seed=31, hands_per_level=12)
        for _ in range(hands):
            if f.remaining() <= 1:
                break
            f.hand_no += 1
            f.advance_level()
            for tb in list(f.tables.values()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts(); f._balance(notify=False); f.notes = []
    finally:
        RD._numeric_snapshot = _sparse
    chips = sorted((p['pid'], p['stack']) for p in f.players.values())
    ests = {}
    for k in sorted(f.book.d):
        i, _, j = k.partition('>')
        e = RD.estimate(f.book, int(i), int(j), 'TAG', rng=random.Random(k))
        ests[k] = e
    h = hashlib.sha256(json.dumps([chips, ests], sort_keys=True, default=str).encode()).hexdigest()
    return f, h


def main():
    f_full, h_full = play(_full)
    f_new, h_new = play(_sparse)
    d = f_new.book.d
    e1 = {'pass': h_full == h_new, 'full': h_full[:12], 'sparse': h_new[:12], 'pairs': len(d)}
    packed = RD.pack_book_d(d)
    rt = RD.unpack_book_d(json.loads(json.dumps(packed)))
    cp = RD.copy_book_d(d)
    alias = any(cp[k] is d[k] or cp[k].get('_hand_hist') is d[k].get('_hand_hist') for k in d)
    r1 = {'pass': rt == d and cp == d and not alias}
    full_b = len(json.dumps(f_full.book.d)); new_b = len(json.dumps(packed))
    s1 = {'pass': new_b < full_b, 'full_bytes': full_b, 'packed_bytes': new_b}
    import live2 as L
    f2 = L._load_field(json.loads(json.dumps(L._dump(f_new))))
    l1 = {'pass': f2.book.d == d}
    checks = {'E1_same_play_and_estimates': e1, 'R1_pack_copy_exact': r1,
              'S1_smaller': s1, 'L1_live2_round_trip': l1}
    ok = all(v['pass'] for v in checks.values())
    print(json.dumps({'pass': ok, 'checks': checks}, indent=1))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
