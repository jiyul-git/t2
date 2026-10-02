#!/usr/bin/env python3
"""Baseline max-skill field sim used to seal the R2 'before' behaviour.

Baseline conditions (user rule): tilt 0, exploit / opponent adaptation neutral
(the read book never accumulates), every player the same max-skill profile with
neutral temperament, no per-hand profile change.

  python tools/r2_baseline_sim.py SEED [CAP_HANDS] [OUT.json]

Prints a SHA-256 digest of the canonical JSON of (all preflop_plan decisions,
all hand records).  Identical code + seed => identical digest.  Run each seed in
its own process: decision records accumulate per process.
"""
import hashlib, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
import persona as PS  # noqa: E402


def uniform_player(rng=None, field_quality=0.6, pid=None, *a, **k):
    p = {'id': pid, 'concepts': {k2: 10.0 for k2 in PS.ALL_CONCEPTS},
         'latent': {'study': 10.0, 'aggro': 5.0, 'exp': 10.0},
         'temper': {'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0, 'tilt_prone': 0.0,
                    'tilt_recovery': 10.0, 'discipline': 10.0, 'adaptability': 10.0,
                    'consistency': 10.0, 'attention': 10.0, 'slowplay_taste': 5.0,
                    'tilt_swing': 5.0, 'tilt_stack': 0.0}}
    p.update(PS.derive(p))
    if rng is not None:
        rng.random()
    return p


PS.make_player = uniform_player
import plan as PL, fieldsim as FS, play as PLY, reads as RD  # noqa: E402

PLY.Hand.emotion_level = lambda self, s: 0.0
_orig_rec = RD.Book.rec
RD.Book.rec = lambda self, i, j: _orig_rec(RD.Book(), i, j)

PF = []
_orig = PL.preflop_plan


def pf_wrap(ax, pos, hand, bbs, rng, **kw):
    r = _orig(ax, pos, hand, bbs, rng, **kw)
    fr = sys._getframe(1)
    h = fr.f_locals.get('h')
    PF.append({'hash': getattr(h, 'hash', None), 'seat': fr.f_locals.get('s'), 'pos': pos,
               'hand': list(hand), 'bbs': bbs, 'aggr_pos': kw.get('aggressor_pos'),
               'open_bb': kw.get('open_bb'), 'callers': kw.get('n_callers'),
               'limpers': kw.get('n_limpers'), 'rlevel': kw.get('raise_level'),
               'act': r[0], 'sz': r[1],
               'seed': {k: v for k, v in (r[2] or {}).items()
                        if isinstance(v, (int, float, str, bool, type(None)))}})
    return r


PL.preflop_plan = pf_wrap
HANDS = []


def grab(self, tb, h, run):
    res = getattr(run, 'result', None) or {}
    HANDS.append({'hand_no': self.hand_no, 'tid': tb.id, 'hash': h.hash, 'bb': h.bb,
                  'full_log': res.get('full_log'), 'board': res.get('board'),
                  'hole': {str(k): v for k, v in h.hole.items()},
                  'end': {str(k): v for k, v in h.stacks.items()},
                  'winners': res.get('winners'), 'how': res.get('how')})


FS.Field._log_bot_hand = grab


def main():
    seed = int(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    out = sys.argv[3] if len(sys.argv) > 3 else None
    f = FS.Field(entries=90, start_stack=30000, hero_pid=-1, seed=seed, hands_per_level=12)
    while f.remaining() > 1 and f.hand_no < cap:
        f.hand_no += 1
        f.advance_level()
        for tid, tb in list(f.tables.items()):
            if tb.n() >= 2:
                f._play_table(tb)
        f._collect_busts()
        f._balance(notify=False)
        f.notes = []
    blob = json.dumps({'pf': PF, 'hands': HANDS}, sort_keys=True, default=str)
    if out:
        open(out, 'w').write(blob)
    print(json.dumps({'seed': seed, 'cap': cap, 'hands': len(HANDS), 'pf_decisions': len(PF),
                      'errors': len(f.errors),
                      'sha256': hashlib.sha256(blob.encode()).hexdigest()}))


if __name__ == '__main__':
    main()
