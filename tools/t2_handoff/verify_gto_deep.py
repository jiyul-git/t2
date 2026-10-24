"""60~100bb 실제 엔진 경로 검사(2026-10-24, s100 연결): 첫 진입(GTO open 경로·빈도), BB vs BTN 오픈,
오프너 vs 3벳(60bb 초과는 기존 판단이어야 한다).

  STACKS=60,80,98.4 python3 tools/t2_handoff/verify_gto_deep.py [반복수=8]

STACKS 는 시작 스택(bb) - 1/9 - 1.6 이다(검사가 안테·블라인드 몫을 더한다). 98.4 → 실제 100bb.
통과: 모든 핸드가 GTO 경로, 오픈 빈도 차이 ≤ 3%p, 엔진 오류 0, 60bb 초과에서 3벳 응답은 GTO 표를 안 씀.
"""
import os, sys, copy, random
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
os.environ['T2_BOT_LOG'] = '0'; os.environ['T2_TELEMETRY'] = '0'; os.environ.pop('T2_TIMING_V1', None)
import gto_pf as G, preflop as PF, play, session, dynamics, reads
from r2_freeze_defend_baseline import maxskill
POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
RANKS, SUITS = '23456789TJQKA', 'cdhs'
seat_of = {p: i + 1 for i, p in enumerate(POS)}; pos_map = {i + 1: p for i, p in enumerate(POS)}
pre = [seat_of[p] for p in POS]; post = [seat_of['SB'], seat_of['BB']] + [seat_of[p] for p in POS[:7]]
BB = 900; REFP = maxskill(); KINDS = []
_o = PF._timing_bound
PF._timing_bound = lambda d: (KINDS.append(d.get('kind')), _o(d))[1]
class Stop(BaseException): pass
def hand_of(c):
    return [c[0] + 'h', c[1] + 'd'] if len(c) == 2 else [c[0] + 'h', c[1] + ('h' if c[2] == 's' else 'd')]
def w(c): return 4 if c.endswith('s') else (6 if len(c) == 2 else 12)
def play_one(cards, start_bb, forced, actor, seed):
    profs = {str(s): copy.deepcopy(REFP) for s in pos_map}
    stacks = {s: int(round(start_bb * BB)) for s in pos_map}
    h = play.Hand(sorted(pos_map), profs, stacks, seat_of['BTN'], BB // 2, BB, hero=None, seed=seed,
                  book=reads.Book(), dyn=dynamics.Tilt(), position_map=pos_map, pre_seats=pre, post_seats=post,
                  sb_seat=seat_of['SB'], bb_seat=seat_of['BB'])
    deck = [c for c in [r + s for r in RANKS for s in SUITS] if c not in cards]
    random.Random(seed).shuffle(deck); i = 0
    for s in sorted(pos_map):
        if s == actor: h.hole[s] = list(cards)
        else: h.hole[s] = [deck[i], deck[i + 1]]; i += 2
    h.board = deck[i:i + 5]; h.seat_pid = {s: 10000 + s for s in pos_map}
    for kk, v in dict(field_q=0.6, field_remaining=1000, field_itm=150, field_avg_stack=int(start_bb * BB),
                      field_stacks=(), field_pid_stacks={}, payouts=[], payout_flat=0.0, ante=BB,
                      erosion_per_hand=0.0, reentry=False, progress=0.05, money_jump={}, pid_prof={}).items():
        setattr(h, kk, v)
    replay = [(session._cache_key('pre', s, j), a, amt) for j, (s, (a, amt)) in enumerate(forced)]
    out = {}; mark = len(KINDS)
    def cb(ev):
        if ev.get('street') != 'preflop': raise Stop()
        if ev.get('seat') == actor and 'a' not in out:
            out['a'], out['amt'] = ev['action'], ev['amount']; raise Stop()
    run = session.HandRun(h, decisions=replay, on_bot_action=cb)
    try: run.start()
    except Stop: pass
    out['errors'] = len(run.preflop_errors); out['kinds'] = KINDS[mark:]
    return out
C = G._load()['classes']; REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
FAIL = []; errs = 0
for S in tuple(float(x) for x in os.environ.get("STACKS", "60,80,98.4").split(",")):
    for p in ('UTG', 'HJ', 'BTN'):
        forced = [(seat_of[q], ('fold', 0)) for q in POS[:POS.index(p)]]
        t2 = exp = tot = 0.0; gto = n = 0
        for ci, c in enumerate(C):
            e = G.first_in(p, 9, S + 1.0 / 9, hand_of(c)); po = e['open'] + e['jam']
            k = 0
            for r in range(REPS):
                o = play_one(hand_of(c), S + 1.0 / 9 + 0.5 + 1, forced, seat_of[p], 1000 * ci + r)
                errs += o['errors']; n += 1; gto += 'gto_pf_open' in o['kinds']
                k += o.get('a') not in ('fold', None)
            t2 += w(c) * k / REPS; exp += w(c) * po; tot += w(c)
        d = abs(t2 - exp) / tot
        print('%.1fbb %s first-in: gto path %d/%d, open T2 %.1f%% vs ref %.1f%% (diff %.1f%%p)'
              % (S, p, gto, n, 100 * t2 / tot, 100 * exp / tot, 100 * d))
        if gto != n or d > 0.03: FAIL.append((S, p))
    # BB vs BTN 2.0 open: aggression path
    forced = [(seat_of[q], ('fold', 0)) for q in POS[:6]] + [(seat_of['BTN'], ('raise', 2 * BB)), (seat_of['SB'], ('fold', 0))]
    ks = {}
    for ci, c in enumerate(C[::7]):
        o = play_one(hand_of(c), S + 1.0 / 9 + 1.5, forced, seat_of['BB'], 7 * ci); errs += o['errors']
        for k in o['kinds']: ks[k] = ks.get(k, 0) + 1
    print('%.1fbb BB vs BTN open kinds %s' % (S, {k: v for k, v in ks.items() if k and k.startswith('gto')}))
    if not any(k.startswith('gto_pf_aggr') or k.startswith('gto_pf_defend') for k in ks): FAIL.append((S, 'bbvsbtn'))
    # CO open, BTN 3-bet 6bb: opener response
    forced = [(seat_of[q], ('fold', 0)) for q in POS[:5]] + [(seat_of['CO'], ('raise', 2 * BB)), (seat_of['BTN'], ('raise', 6 * BB)),
              (seat_of['SB'], ('fold', 0)), (seat_of['BB'], ('fold', 0))]
    ks = {}; acts = {}
    for ci, c in enumerate(C[::5]):
        o = play_one(hand_of(c), S + 1.0 / 9 + 2.5, forced, seat_of['CO'], 5 * ci); errs += o['errors']
        for k in o['kinds']: ks[k] = ks.get(k, 0) + 1
        acts[o.get('a')] = acts.get(o.get('a'), 0) + 1
    g = {k: v for k, v in ks.items() if k and k.startswith('gto')}
    print('%.1fbb CO vs BTN 3-bet kinds %s acts %s' % (S, g, acts))
    if S > 60.5 and any('vs_3bet' in k or 'aggr_jam' in k for k in g): FAIL.append((S, 'vs3bet should fall back'))
print('engine errors', errs)
print('FAIL', FAIL) if FAIL or errs else print('ALL PASS')
