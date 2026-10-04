#!/usr/bin/env python3
"""Other tables in parallel processes (UI worker) == sequential simultaneous play.

P1  live2.compute_others_parallel on the same round-start dump gives the same
    players, tables, tilt, book, notes and bot log (timing field removed) with
    T2_TABLE_WORKERS=1 (one process, tables in order) and with N processes.
P2  simultaneous play ignores within-round results of other tables: every hand
    of the round is stamped with the round-start field context.
T1  wall time of both (reported, not a pass condition).

  python tools/verify_parallel_table_processes.py [ENTRIES] [WARM_ROUNDS] [SEED]
"""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = os.environ.get('T2_BOT_LOG', '2')
import fieldsim as FS
import live2 as L


def warm_dump(entries, rounds, seed):
    f = FS.Field(entries=entries, start_stack=30000, hero_pid=0, seed=seed)
    _log = FS.Field._log_bot_hand
    FS.Field._log_bot_hand = lambda *a, **k: None
    try:
        for _ in range(rounds):
            f.hand_no += 1
            f.advance_level()
            for tb in list(f.tables.values()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts(); f._balance(notify=False); f.notes = []
    finally:
        FS.Field._log_bot_hand = _log
    f.hand_no += 1
    f.advance_level()
    return L._dump(f)


def strip_log(text):
    rows = []
    for line in (text or '').splitlines():
        r = json.loads(line)
        r.pop('compute_ms', None)
        rows.append(r)
    return rows


def run(dump, workers):
    os.environ['T2_TABLE_WORKERS'] = str(workers)
    t = time.time()
    out = L.compute_others_parallel(json.loads(json.dumps(dump)))
    return out, time.time() - t


def main():
    entries = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    warm = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    dump = warm_dump(entries, warm, seed)
    seq, t_seq = run(dump, 1)
    par, t_par = run(dump, max(2, min(8, os.cpu_count() or 2)))
    keys = ('players', 'tables', 'tilt', 'book', 'notes')
    diff = [k for k in keys if seq.get(k) != par.get(k)]
    log_same = strip_log(seq.get('bot_log')) == strip_log(par.get('bot_log'))
    p1 = {'pass': not diff and log_same and bool(seq.get('bot_log')),
          'diff_keys': diff, 'bot_log_same': log_same,
          'bot_hands': len(strip_log(seq.get('bot_log')))}
    rows = strip_log(seq.get('bot_log'))
    ctxs = {json.dumps(r.get('field_context', {}).get('remaining')) for r in rows}
    p2 = {'pass': len(ctxs) == 1, 'field_remaining_seen': sorted(ctxs)}
    checks = {'P1_parallel_equals_sequential': p1, 'P2_round_start_context': p2,
              'T1_seconds': {'pass': True, 'sequential': round(t_seq, 1), 'parallel': round(t_par, 1),
                             'workers': max(2, min(8, os.cpu_count() or 2))}}
    ok = all(v['pass'] for v in checks.values())
    print(json.dumps({'pass': ok, 'checks': checks}, indent=1))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
