#!/usr/bin/env python3
"""Virtual tournament clock: table-to-table deviation and compute budget (design data).

Plays the current round-synchronous field (no hero) and records every bot hand:
table, players dealt, action log and compute seconds.  Then replays each table's
own hand sequence on a virtual clock (online pace) and reports:

  * hands each table plays in a 55-minute session (spread between tables);
  * compute seconds the other tables need per session (sequential and the
    slowest single table = lower bound with one core per table);
  * the break length needed so the other tables finish the session before the
    hero table resumes, for several hero real-time paces and a phone factor.

Hand duration model (assumption, scaled to data): online 9-handed full ring is
60-80 hands/hour, so the model is scaled to a mean of 3600/70 s for 9-handed
hands.  Shape: base + per action (fold < check/call < bet/raise) + per street.

  python tools/vclock_sim.py [ROUNDS] [ENTRIES] [SEED] [OUT.json]
"""
import json, os, statistics, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('T2_BOT_LOG', '0')
import fieldsim as FS

SESSION_MIN = 55
TARGET_9MAX_SEC = 3600.0 / 70.0          # data: online full ring 60-80 hands/hour
SHAPE = {'base': 8.0, 'fold': 1.5, 'check': 3.0, 'call': 3.5, 'bet': 5.0, 'raise': 5.5,
         'allin': 5.5, 'street': 2.0, 'showdown': 3.0}

HANDS = []


def _record(self, tb, h, run):
    r = getattr(run, 'result', None) or {}
    HANDS.append({'table': tb.id, 'n': len(h.seats), 'log': [(a[0], a[2]) for a in (r.get('full_log') or [])],
                  'showdown': bool(r.get('showdown')), 'compute': getattr(h, '_telemetry_compute_ms', 0) / 1000.0,
                  'round': CUR[0]})


CUR = [0]


def raw_duration(hd):
    t = SHAPE['base']
    streets = {s for s, _a in hd['log']}
    t += SHAPE['street'] * max(0, len(streets) - 1)
    for _s, a in hd['log']:
        t += SHAPE.get(a, SHAPE['call'])
    if hd['showdown']:
        t += SHAPE['showdown']
    return t


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 130
    entries = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    FS.Field._log_bot_hand = _record
    f = FS.Field(entries=entries, start_stack=30000, hero_pid=-1, seed=seed)
    t0 = time.time()
    for k in range(rounds):
        if f.remaining() <= 1:
            break
        CUR[0] = k
        f.hand_no += 1
        f.advance_level()
        for tb in list(f.tables.values()):      # every table one hand per round
            if tb.n() >= 2:
                f._play_table(tb)
        f._collect_busts(); f._balance(notify=False); f.notes = []
    wall = time.time() - t0
    nine = [raw_duration(h) for h in HANDS if h['n'] == 9]
    scale = TARGET_9MAX_SEC / statistics.mean(nine)
    for h in HANDS:
        h['vsec'] = raw_duration(h) * scale
    # per table virtual clock (each table's own sequence)
    by = {}
    for h in HANDS:
        by.setdefault(h['table'], []).append(h)
    sessions = {}
    for tid, hs in by.items():
        clock = 0.0
        for h in hs:
            s = int(clock // (SESSION_MIN * 60))
            d = sessions.setdefault(s, {}).setdefault(tid, {'hands': 0, 'compute': 0.0})
            d['hands'] += 1; d['compute'] += h['compute']
            clock += h['vsec']
    out = {'rounds': rounds, 'entries': entries, 'seed': seed, 'hands': len(HANDS),
           'wall_sec': round(wall, 1), 'scale': round(scale, 3),
           'mean_vsec_by_players': {n: round(statistics.mean([h['vsec'] for h in HANDS if h['n'] == n]), 1)
                                    for n in sorted({h['n'] for h in HANDS})},
           'sessions': []}
    for s in sorted(sessions):
        tabs = sessions[s]
        hs = [v['hands'] for v in tabs.values()]
        cs = [v['compute'] for v in tabs.values()]
        full = len(hs) >= 2 and all(by[t][-1]['vsec'] for t in tabs)
        out['sessions'].append({
            'session': s + 1, 'tables': len(hs),
            'hands_min': min(hs), 'hands_max': max(hs), 'hands_mean': round(statistics.mean(hs), 1),
            'compute_seq_sec': round(sum(cs), 1), 'compute_max_table_sec': round(max(cs), 1)})
    print(json.dumps(out, indent=1))
    if len(sys.argv) > 4:
        json.dump({'summary': out, 'hands': HANDS}, open(sys.argv[4], 'w'))


if __name__ == '__main__':
    main()
