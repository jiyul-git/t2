#!/usr/bin/env python3
"""Pre-beta bug fixes: same-state attribution of three corrections.

  1. showdown visibility (L163/L194): observers now record only shown hands.
     Counted: showdowns, live seats, seats observed (shown), mucked seats skipped.
  2. _was_3bettor (L049): full-raise events instead of raw 'raise'/'allin' strings.
     At every call, the retired rule is evaluated on the same hand state.
  3. made_strength two pair (L-RA09): hero-involved pairs only.
     At every call, the retired rule is evaluated on the same arguments.

No RNG is consumed by the instrumentation; the printed digest must equal the
plain sim digest of the same tree (tools/r2_baseline_sim.py SEED CAP).

  OUT=attr.json python tools/bugfix3_attribution.py SEED [CAP]
"""
import collections, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import r2_baseline_sim as SIM
import bot as BOT
import session as SE

C = collections.Counter()
EX = {'made': [], 'threebet': []}


def _old_made(hero, board):
    if not board:
        return 0
    full = BOT.eval7(list(hero) + list(board))
    if len(board) >= 5:
        bb = BOT.eval7(list(board))
        return 0 if full[0] <= bb[0] else full[0]
    cnt = {}
    for c in board:
        cnt[c[0]] = cnt.get(c[0], 0) + 1
    m = max(cnt.values()) if cnt else 1
    cat = {1: 0, 2: 1, 3: 3, 4: 7}.get(m, 0)
    su = {}
    for c in board:
        su[c[1]] = su.get(c[1], 0) + 1
    if su and max(su.values()) >= 5:
        cat = max(cat, 5)
    return 0 if full[0] <= cat else full[0]


_made = BOT.made_strength


def made(hero, board):
    new = _made(hero, board)
    old = _old_made(hero, board)
    C['made_calls'] += 1
    if new != old:
        C['made_diff'] += 1
        C['made_%d->%d' % (old, new)] += 1
        if len(EX['made']) < 12:
            EX['made'].append({'hero': list(hero), 'board': list(board), 'old': old, 'new': new})
    return new
BOT.made_strength = made


def _old_3b(self, seat):
    n = 0
    for row in (getattr(self, 'full_log', []) or []):
        if row[0] != 'preflop':
            continue
        if row[2] in ('raise', 'allin'):
            n += 1
            if n >= 2 and row[1] == seat:
                return True
    return False


_w3 = SE.HandRun._was_3bettor


def was3(self, seat):
    new = _w3(self, seat)
    old = _old_3b(self, seat)
    C['3b_calls'] += 1
    if new != old:
        C['3b_diff'] += 1
        C['3b_%s->%s' % (old, new)] += 1
        if len(EX['threebet']) < 8:
            EX['threebet'].append({'log': [list(r) for r in self.full_log if r[0] == 'preflop'],
                                   'seat': seat, 'old': old, 'new': new})
    return new
SE.HandRun._was_3bettor = was3

_fin = SE.HandRun._finish


def fin(self, contrib, dead, folded, live, board, how):
    r = _fin(self, contrib, dead, folded, live, board, how)
    if r.get('showdown'):
        C['showdowns'] += 1
        C['sd_live'] += len(r.get('hole') or {})
        C['sd_shown'] += len(r.get('shown_hole') or {})
        C['sd_mucked_not_observed'] += len(r.get('mucked') or [])
    return r
SE.HandRun._finish = fin

sys.argv = ['x', sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '60']
try:
    SIM.main()
finally:
    out = {'counts': dict(C), 'examples': EX}
    if os.environ.get('OUT'):
        json.dump(out, open(os.environ['OUT'], 'w'), indent=1)
    print(json.dumps(dict(C), sort_keys=True))
