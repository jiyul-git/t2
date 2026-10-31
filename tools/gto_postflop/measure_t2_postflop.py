"""T2 bot postflop frequencies in the SAME heads-up situations as the GTO postflop reference (measurement only; no
production code is changed).

  python3 tools/gto_postflop/measure_t2_postflop.py <spot> <term.json> <hands_per_board> <out.jsonl.gz> [seed] [boards]

<spot> is one of the keys of SPOTS below. Both players are the max-skill standard profile (tools/r2_freeze_defend_baseline.maxskill,
the profile the GTO connection checks use). The preflop line is forced with the engine's REPLAY (session.HandRun decisions);
the two players' hole cards are drawn from the GTO terminal's arriving ranges (term.json class_keep_fraction x combos, card
removal by rejection), the flop is the panel board, turn and river are random. Every postflop bot decision is recorded with
its GTO-style line key (a<i> per action as the solver tree numbers them, c per new street), the hand category on the board so
far (classify.py = the solver's report classifier) and the action kind. Sizes differ from the GTO menu (one 50 % pot bet,
raise = all-in): kinds are compared, sizes are recorded separately.
"""
import copy
import gzip
import json
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'
os.environ.pop('T2_TIMING_V1', None)
import play, session, dynamics, reads  # noqa: E402
from r2_freeze_defend_baseline import maxskill  # noqa: E402
from classify import classify, group  # noqa: E402

POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
SEAT = {p: i + 1 for i, p in enumerate(POS)}
POSMAP = {i + 1: p for i, p in enumerate(POS)}
PRE = [SEAT[p] for p in POS]
POST = [SEAT['SB'], SEAT['BB']] + [SEAT[p] for p in POS[:7]]
BB = 900
RANKS, SUITS = '23456789TJQKA', 'cdhs'
PANEL = ['AcQc2c', 'AcKc6c', 'Tc9c7c', 'Jc6c2c', 'Qc5c2c', 'KcQc6c', 'AdAc9c', 'AdAcKc', 'JdJc3c', '6d6c3c', 'KcJhJd', 'Kc3d3c',
         'Ac4d3h', 'Ac4d2h', 'Tc9d5h', '9c7d4h', 'Kc7d4h', 'KcTd9h', 'AcQdJc', 'AcKd5d', '6c4d3d', '8c4d3d', 'Qc9d7d', 'Qc4d3c']


def _fold(ps):
    return [(SEAT[p], ('fold', 0)) for p in ps]


SPOTS = {
    # 40 bb, BTN opens 2.0, BB calls (p40_flat_btn_vs_bb, terminal BTN raise 2 / BB call)
    'p40_flat_btn_vs_bb': {'stack_bb': 40, 'live': ('BTN', 'BB'),
                           'forced': _fold(POS[:6]) + [(SEAT['BTN'], ('raise', 2 * BB))] + _fold(['SB']) + [(SEAT['BB'], ('call', 0))]},
    # 60 bb, CO opens 2.5, BB calls (p60_flat_co_vs_bb_o25)
    'p60_flat_co_vs_bb_o25': {'stack_bb': 60, 'live': ('CO', 'BB'),
                              'forced': _fold(POS[:5]) + [(SEAT['CO'], ('raise', int(2.5 * BB)))] + _fold(['BTN', 'SB']) + [(SEAT['BB'], ('call', 0))]},
    # 40 bb, BTN opens 2.0, SB 3-bets to 8, BB folds, BTN calls (p40v1_btn_vs_sb_3b40)
    'p40v1_btn_vs_sb_3b40': {'stack_bb': 40, 'live': ('BTN', 'SB'),
                             'forced': _fold(POS[:6]) + [(SEAT['BTN'], ('raise', 2 * BB)), (SEAT['SB'], ('raise', 8 * BB))] + _fold(['BB'])
                             + [(SEAT['BTN'], ('call', 0))]},
}
REFP = maxskill()


def class_combos(lab):
    a, b = lab[0], lab[1]
    if len(lab) == 2:
        return [(a + s1, a + s2) for i, s1 in enumerate(SUITS) for s2 in SUITS[i + 1:]]
    if lab[2] == 's':
        return [(a + s, b + s) for s in SUITS]
    return [(a + s1, b + s2) for s1 in SUITS for s2 in SUITS if s1 != s2]


def class_labels():
    out = []
    for i in range(13):
        for j in range(13):
            hi, lo = max(i, j), min(i, j)
            out.append(RANKS[i] * 2 if i == j else (RANKS[hi] + RANKS[lo] + ('o' if j > i else 's')))
    return out


class RangeSampler:
    def __init__(self, keep):
        labs = class_labels()
        self.items = [(labs[k], c) for k in range(169) for c in class_combos(labs[k])]
        self.w = [keep[k] for k in range(169) for _ in class_combos(labs[k])]

    def draw(self, rng, dead):
        while True:
            lab, c = rng.choices(self.items, weights=self.w)[0]
            if c[0] not in dead and c[1] not in dead:
                return lab, list(c)


def play_one(spot, cards, board, seed):
    sp = SPOTS[spot]
    profs = {str(s): copy.deepcopy(REFP) for s in POSMAP}
    stacks = {s: int(round(sp['stack_bb'] * BB)) for s in POSMAP}
    h = play.Hand(sorted(POSMAP), profs, stacks, SEAT['BTN'], BB // 2, BB, hero=None, seed=seed, book=reads.Book(),
                  dyn=dynamics.Tilt(), position_map=POSMAP, pre_seats=PRE, post_seats=POST, sb_seat=SEAT['SB'], bb_seat=SEAT['BB'])
    used = set(board)
    for c in cards.values():
        used |= set(c)
    deck = [r + s for r in RANKS for s in SUITS if r + s not in used]
    random.Random(seed).shuffle(deck)
    i = 0
    for s in sorted(POSMAP):
        if POSMAP[s] in cards:
            h.hole[s] = list(cards[POSMAP[s]])
        else:
            h.hole[s] = [deck[i], deck[i + 1]]
            i += 2
    h.board = list(board) + deck[i:i + 2]
    h.seat_pid = {s: 10000 + s for s in POSMAP}
    for k, v in dict(field_q=0.6, field_remaining=1000, field_itm=150, field_avg_stack=int(sp['stack_bb'] * BB), field_stacks=(),
                     field_pid_stacks={}, payouts=[], payout_flat=0.0, ante=BB, erosion_per_hand=0.0, reentry=False, progress=0.05,
                     money_jump={}, pid_prof={}).items():
        setattr(h, k, v)
    replay = [(session._cache_key('pre', s, j), a, amt) for j, (s, (a, amt)) in enumerate(sp['forced'])]
    ev = []
    run = session.HandRun(h, decisions=replay, on_bot_action=lambda e: ev.append(e))
    run.start()
    return ev, h, len(getattr(run, 'preflop_errors', []) or [])


def decisions(spot, ev, h, pot0):
    """GTO-style line keys and action kinds for every postflop bot decision of the hand"""
    live = SPOTS[spot]['live']
    oop = 'BB' if 'BB' in live and 'SB' not in live else 'SB'
    role = {oop: 'OOP', [p for p in live if p != oop][0]: 'IP'}
    key = []
    out = []
    street = None
    pot = pot0
    cur = 0
    put = {}
    for e in ev:
        if e['kind'] == 'street' and e['street'] != street:
            if street is not None:
                key.append('c')
            street = e['street']
            pot += sum(put.values())
            cur, put = 0, {}
            continue
        if e['kind'] != 'bot_action' or e['street'] == 'preflop':
            continue
        pos = POSMAP[e['seat']]
        a, amt = e['action'], e['amount']
        facing = cur > put.get(pos, 0)
        n_aggr = sum(1 for x in out if x['street'] == street and x['kind'] in ('bet', 'raise'))
        if a in ('check',):
            kind, idx = 'check', 0
        elif a == 'fold':
            kind, idx = 'fold', 0
        elif a == 'call' or (a == 'allin' and facing and amt <= cur):
            kind, idx = 'call', 1
        elif facing:
            kind, idx = 'raise', 2
        else:
            kind, idx = 'bet', 1
        board = list(e.get('board') or h.board[:{'flop': 3, 'turn': 4, 'river': 5}[street]])
        hole = h.hole[e['seat']]
        made, draw = classify(board, hole[0], hole[1])
        live_pot = pot + sum(put.values())
        rec = {'street': street, 'pos': pos, 'role': role[pos], 'key': ','.join(key), 'facing': 'raise' if n_aggr >= 2 else ('bet' if facing else 'none'),
               'kind': kind, 'made': made, 'draw': draw, 'group': group(made, draw), 'hole': hole, 'board': board}
        if kind in ('bet', 'raise'):
            rec['size_pot'] = round((amt - put.get(pos, 0)) / live_pot, 3) if kind == 'bet' else round(amt / max(cur, 1), 3)
        out.append(rec)
        key.append('a%d' % idx)
        if kind in ('bet', 'raise', 'call'):
            put[pos] = max(amt, put.get(pos, 0))
            cur = max(cur, amt)
    return out


def main():
    spot, termf, n, outp = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    boards = sys.argv[6].split(',') if len(sys.argv) > 6 else PANEL
    term = json.load(open(termf))
    samplers = {pl['position']: RangeSampler(pl['class_keep_fraction']) for pl in term['players']}
    pot0 = int(round(term['pot_bb'] * BB))
    rng = random.Random(seed)
    errs = 0
    with gzip.open(outp, 'wt') as f:
        for bi, b in enumerate(boards):
            board = [b[i:i + 2] for i in range(0, 6, 2)]
            for j in range(n):
                dead = set(board)
                cards = {}
                cls = {}
                for pos in SPOTS[spot]['live']:
                    cls[pos], cards[pos] = samplers[pos].draw(rng, dead)
                    dead |= set(cards[pos])
                hs = seed * 1000003 + bi * 10007 + j
                ev, h, e = play_one(spot, cards, board, hs)
                errs += e
                f.write(json.dumps({'board': b, 'j': j, 'classes': cls, 'decisions': decisions(spot, ev, h, pot0)}) + '\n')
            print(b, 'done', flush=True)
    print('engine preflop errors', errs)


if __name__ == '__main__':
    main()
