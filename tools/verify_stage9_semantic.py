#!/usr/bin/env python3
"""Stage 9 behaviour-identity check: pristine BASE checkout vs working tree.

Runs one deterministic probe (randomised inputs, fixed seeds) in a temp copy of
BASE's *.py/*.json files and in the working tree, then compares the JSON outputs
byte for byte (including Random state digests and mutated record dicts).

Usage: python tools/verify_stage9_semantic.py [BASE] [--probe b1|b2|b3] [--mutate 'FILE|||OLD|||NEW'] [--base-cache FILE]
  --mutate applies a textual change to a scratch copy of the working tree and
  must make the probe FAIL (proves the probe is sensitive to that site).
"""
import json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBE = r'''
import sys, json, random, hashlib, copy
sys.path.insert(0, sys.argv[1])
import persona as PS, preflop as PF, gto as G, ranges as R, bot as B

def st(rng): return hashlib.sha1(repr(rng.getstate()).encode()).hexdigest()[:16]
def rnd(x):
    if isinstance(x, float): return round(x, 12)
    if isinstance(x, dict): return {str(k): rnd(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)): return [rnd(v) for v in x]
    return x

g = random.Random(4242)
PROFS = []
for i in range(40):
    PROFS.append(PS.make_player(random.Random(1000 + i), field_quality=g.choice([0.3, 0.6, 0.9, 1.2]), pid=i))
deck = [r + s for r in '23456789TJQKA' for s in 'shdc']
POS9 = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
out = {}

def exploit():
    if g.random() < 0.4: return None
    return {'w': g.random(), 'tb_gap': g.uniform(-.2, .3), 'tb_polar': g.uniform(0, .2), 'f2fb_gap': g.uniform(-.2, .3),
            'open_gap': g.uniform(-.3, .3), 'f2tb_gap': g.uniform(-.2, .3), 'fold_gap': g.uniform(-.2, .3), 'fb_gap': g.uniform(-.1, .3)}

for v3 in (False, True):
    PS.PREFLOP_REASONING_V3 = v3
    key = 'v3' if v3 else 'v2'
    rows = []
    for i in range(300):
        p = g.choice(PROFS); seats = g.choice([8, 9]); bb = g.choice([4, 9, 14, 18, 22, 26, 30, 45, 80, 140])
        ante = g.random() < .8; pos = g.choice(POS9[:-1] if seats == 9 else ['UTG','UTG+1','LJ','HJ','CO','BTN','SB'])
        rows.append(PS.open_pct(p, pos, seats, bb, ante))
        dp = g.choice(['UTG+1','LJ','HJ','CO','BTN','SB','BB']); op = g.choice(['UTG','LJ','CO','BTN','SB'])
        ob = g.choice([2.0, 2.15, 2.5, 3.0, 4.5, 7.0, 12.0])
        rows.append([G.defend_pct(dp, op, seats, bb, ante, ob), G.threebet_pct(dp, op, seats, bb, ante, ob)])
        rows.append(list(PF.defend_thresholds(p, dp, op, bb, ob, g.choice([0,0,1,2]), g.choice([1,1,2,3,4]), seats, ante)))
    out['widths_' + key] = rnd(rows)
PS.PREFLOP_REASONING_V3 = False

rows = []
for i in range(1500):
    p = g.choice(PROFS); hand = g.sample(deck, 2); seats = g.choice([8, 9])
    bb = g.choice([8, 12, 15, 18, 22, 25, 30, 40, 70, 120]); ob = g.choice([2.0, 2.2, 2.5, 3.0, 6.5, 9.0, bb * 0.95, bb])
    kw = dict(raise_level=g.choice([1,1,2,3]), stack_bb=g.choice([None, bb, bb * 1.5]), exploit=exploit(),
              bf=g.choice([1.0, 1.4]), seats=seats, ante=g.random() < .8, opener_allin=g.random() < .25,
              can_raise=g.random() < .8, pot_bb=g.choice([None, 6.0, 25.0]), to_call_bb=g.choice([None, 4.0, ob]))
    dp = g.choice(['LJ','HJ','CO','BTN','SB','BB']); op = g.choice(['UTG','UTG+1','LJ','HJ','CO','BTN','SB'])
    nc = g.choice([0, 0, 1, 2])
    lk = PF.defend_action_likelihoods(p, dp, op, hand, bb, ob, nc, **kw)
    r = random.Random(i)
    a = PF.defend_decision(p, dp, op, hand, bb, ob, nc, r, **kw)
    rows.append([rnd(lk), rnd(list(a)), st(r)])
out['defend'] = rows

rows = []
for i in range(1200):
    p = g.choice(PROFS); hand = g.sample(deck, 2); seats = g.choice([8, 9]); pos = g.choice(['UTG','UTG+1','LJ','HJ','CO','BTN','SB'])
    bb = g.choice([5, 9, 13, 18, 24, 30, 50, 100])
    mo = None if g.random() < .5 else {'range_factor': g.uniform(.6, 1.4), 'limp_pull_shadow': g.random()}
    reads = None if g.random() < .5 else [{'w': g.random(), 'tb_gap': g.uniform(-.2, .3), 'open_gap': g.uniform(-.2, .2),
                                           'fold_gap': g.uniform(-.2, .3), 'passive': g.random()} for _ in range(g.randint(1, 4))]
    stacks = None if g.random() < .4 else [g.choice([8, 14, 20, 40, 90]) for _ in range(g.randint(1, 5))]
    r = random.Random(i)
    a = PF.open_decision(p, pos, bb, hand, r, behind_stacks=stacks, seats=seats, ante=g.random() < .8,
                         behind_reads=reads, bb_chips=g.choice([None, 200, 1000, 6000]), money_open=mo)
    r2 = random.Random(i + 77)
    b = PF.iso_decision(p, pos, hand, g.randint(1, 3), bb, r2,
                        limper_reads=reads, behind_stacks=stacks, behind_reads=reads, seats=seats,
                        can_check=(pos == 'BB'))
    rows.append([rnd(list(a)), st(r), rnd(mo), rnd(list(b)), st(r2),
                 rnd(PF.limp_p(p, g.random(), g.random(), pos))])
out['open_iso'] = rows

rows = []
for i in range(800):
    p = g.choice(PROFS); r = random.Random(i)
    stk = g.choice([12, 20, 35, 60, 100]); tgt = g.uniform(5, stk * 1.1)
    rows.append([rnd(list(PF.raise_form(p, stk, tgt, g.uniform(3, 30), r, exploit=exploit(), level=g.choice([1, 2, 3]),
                                       n_opp=g.choice([1, 2, 3]), facing_bb=g.uniform(0, 10)))), st(r)])
out['raise_form'] = rows

rows = []
for i in range(400):
    p = g.choice(PROFS)
    sh = {'pure_calloff': True, 'complete': True, 'effective_equity': g.random(), 'call_cost': g.uniform(2, 40),
          'contestable_after_call': g.uniform(10, 90)}
    rows.append(rnd(PF.calloff_layer_judgment(p, sh, bubble_factor=g.choice([1.0, 1.3, 2.0]), seed=i)))
    hand = g.sample(deck, 2)
    rows.append(rnd(PF.calloff_cap(p, 'BB', g.choice(['UTG','CO','BTN','SB']), g.choice([10, 20, 40]), g.choice([10, 20]), g.choice([1, 2]),
                                   bf=g.choice([1.0, 1.5]), exploit=exploit(), seats=9)))
out['calloff'] = rows

rows = []
for i in range(120):
    p = g.choice(PROFS); hand = g.sample(deck, 2)
    op = R.preflop_range(p, 'UTG', 'open', 60.0, hand, seats=9, ante=True)
    rr = R.preflop_range(p, 'HJ', '3bet', 60.0, hand, 0, 'UTG', open_bb=2.5, seats=9, ante=True)
    r = random.Random(i)
    a, sz, au = PF.multiway_reraise_decision(p, 'BTN', 'HJ', hand, 60.0, 8.0, 0, r, raise_level=2, stack_bb=60.0, seats=9,
                                             ante=True, can_raise=True, pot_bb=12.0, to_call_bb=8.0,
                                             opponent_ranges={'a': op, 'b': rr}, players_behind=i % 3, decision_seed=i,
                                             locked_keys=(['a'] if i % 4 == 0 else None), exploit=exploit())
    rows.append([a, rnd(sz), rnd({k: v for k, v in au.items()}), st(r),
                 rnd(PF.preflop_blocker_share(hand, [op, rr]))])
    post = R.preflop_reraise_posterior(op, g.uniform(.01, .2), polar=g.random())
    rows.append(hashlib.sha1(json.dumps(rnd({str(k): v for k, v in post.items()}), sort_keys=True).encode()).hexdigest())
    rows.append(len(B.range_combos(g.choice([.22, .30, .35]), set(hand))))
out['multiway_ranges'] = rows

print(json.dumps(out, sort_keys=True))
'''


PROBE_B2 = r'''
import sys, json, random, hashlib
sys.path.insert(0, sys.argv[1])
import persona as PS, ranges as R, bot as B, reads as RD, plan as PL, money_pressure as MP

def st(rng): return hashlib.sha1(repr(rng.getstate()).encode()).hexdigest()[:16]
def rnd(x):
    if isinstance(x, float): return round(x, 12)
    if isinstance(x, dict): return {str(k): rnd(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)): return [rnd(v) for v in x]
    return x
def H(x): return hashlib.sha1(json.dumps(rnd(x), sort_keys=True, default=str).encode()).hexdigest()[:20]

g = random.Random(777)
PROFS = [PS.make_player(random.Random(2000 + i), field_quality=g.choice([0.3, 0.6, 0.9, 1.2]), pid=i) for i in range(40)]
deck = [r + s for r in '23456789TJQKA' for s in 'shdc']
out = {}

def rand_range(dead, weighted):
    live = [c for c in R._SORTED if c[0] not in dead and c[1] not in dead]
    sub = g.sample(live, g.randint(30, 400))
    if weighted:
        return {tuple(c): g.choice([1.0, 0.5, 0.2, g.random()]) for c in sub}
    return [tuple(c) for c in sub]

rows = []
for i in range(700):
    cards = g.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    rr = rand_range(set(hero) | set(board), g.random() < .5)
    rows.append(H(R._bet_range(rr, board, street, g.uniform(1, 10), g.choice([.25, .33, .5, .75, 1.0, 1.5]),
                               g.choice([1.0, .7, .4]), g.uniform(-.8, .8), n_barrels=g.choice([1, 2, 3]))))
    rows.append(rnd(R.blocker_score(hero, rr, board)))
    rr_h = rand_range(set(board), g.random() < .5)   # hero 카드를 포함할 수 있는 레인지(함수 의미 검증용)
    rows.append(rnd(R.blocker_score(hero, rr_h, board)))
    ranked = sorted(R.range_support(rr), key=lambda c: B.eval7(list(c) + board), reverse=True)
    rows.append(H(B.pick_bluffs(ranked, board, street, g.randint(0, 30))))
    acts = []
    for stt in ['flop', 'turn', 'river'][:len(board) - 2]:
        for _ in range(g.randint(0, 2)):
            if g.random() < .5:
                acts.append((stt, g.choice(['bet', 'raise', 'call', 'check', 'allin']), g.choice([.33, .5, .75, 1.2])))
            else:
                acts.append({'street': stt, 'action_kind': g.choice(['bet', 'raise', 'call', 'check']),
                             'size_frac': g.choice([.33, .5, .75, 1.2]), 'facing_kind': g.choice([None, 'bet', 'raise']),
                             'facing_size_frac': g.choice([None, .5, .9])})
    rd = None if g.random() < .5 else {'w': g.random(), 'bluff_gap': g.uniform(-.3, .3), 'passive': g.random(),
                                        'barrel_gap': g.uniform(-.5, .5)}
    rows.append(H(R.narrow_by_actions(rr, board, acts, actor_read=rd)))
out['ranges'] = rows

rows = []
for i in range(500):
    p = g.choice(PROFS)
    rows.append(rnd([PS.exploit_weight(p, g.random(), g.randint(0, 40)),
                     PS._exploit_base_weight(p, g.random(), g.randint(0, 40)),
                     PS.opponent_read_application_weight(g.uniform(0, 10), g.uniform(0, 10), g.uniform(0, 10),
                                                         g.random() * 1.2, g.randint(0, 30))]))
    book = RD.Book()
    rec = book.rec(1, 2)
    for k in list(rec.keys()):
        if isinstance(rec[k], (int, float)) and not isinstance(rec[k], bool):
            rec[k] = g.randint(0, 40) if isinstance(rec[k], int) else g.random()
    rec['hands'] = g.randint(0, 80)
    for a, b in (('cbet', 'cbet_opp'), ('barrel', 'barrel_opp'), ('fold_to_bet', 'facing_bet'), ('vpip', 'hands'), ('pfr', 'vpip')):
        if a in rec and b in rec: rec[a] = min(rec[a], rec[b])
    rng = random.Random(i)
    try:
        est = RD.estimate(book, 1, 2, g.choice(list(RD.OBSERVER.keys()) or ['TAG']), rng)
        rows.append([H(est), st(rng)])
        rows.append(rnd(PS.read_opponent(p, est)))
    except Exception as e:
        rows.append('ERR ' + type(e).__name__)
out['reads'] = rows

rows = []
for i in range(600):
    p = g.choice(PROFS)
    cards = g.sample(deck, 7); hero, board = cards[:2], cards[2:2 + g.choice([3, 4, 5])]
    pot = g.randint(300, 20000); tocall = g.randint(100, max(101, pot // 2))
    est = {'confidence': g.uniform(.3, 1.0), 'n': g.randint(5, 60), 'bluff': g.uniform(1, 10), 'aggr': g.uniform(1, 10),
           'tight': g.uniform(1, 10), 'vpip': g.random(), 'pfr': g.random() * .4, 'cbet': g.random(), 'barrel': g.random(),
           'ftb': g.random(), 'sz_mean': g.uniform(.3, 1.2), 'sz_sd': g.uniform(.05, .5), 'sz_big': g.random() * .4,
           'sz_river': g.uniform(.4, 1.5), 'sz_n': g.randint(0, 40)}
    rng = random.Random(i)
    r = PL.calldown_need(p, hero, board, ['flop', 'turn', 'river'][len(board) - 3], pot, tocall,
                         g.choice([1.0, 1.3]), None, i % 3, est if g.random() < .7 else None, n_opp=1 + i % 2, rng=rng,
                         objective_breakeven=(g.random() * .5 if i % 2 else None),
                         facing_size_frac=g.choice([None, .5, 1.0, 2.5, 4.0]))
    rows.append([rnd(r), st(rng)])
    hs = {'stack_start_bb': g.uniform(5, 120), 'covered_by_yet_to_act': g.randint(0, 4)}
    ts = {'stack_start_bb': g.uniform(5, 120), 'jump_frac_next': g.random(), 'jump_vs_mincash': g.uniform(0, 3),
          'distance_frac_itm': g.uniform(0, .5), 'bf': 1.0 + g.random(), 'n_shorter': g.randint(0, 8),
          'players_to_jump': g.randint(0, 6)}
    actor = {k: g.uniform(0, 10) for k in ('money_jump', 'fold_equity', 'range_read', 'attention', 'adaptability', 'aggression')}
    try:
        rows.append(rnd(MP.pressure_opportunity(hs, ts, actor, read={'w': g.random(), 'fold_gap': g.uniform(-.3, .3)},
                                                read_channel=g.choice(['generic', 'preflop_3bet']))))
    except Exception as e:
        rows.append('ERR ' + type(e).__name__)
out['price_pressure'] = rows
print(json.dumps(out, sort_keys=True))
'''


PROBE_B3 = r'''
import sys, json, random, hashlib, copy
sys.path.insert(0, sys.argv[1])
import persona as PS, ranges as R, bot as B, plan as PL

def st(rng): return hashlib.sha1(repr(rng.getstate()).encode()).hexdigest()[:16]
def rnd(x):
    if isinstance(x, float): return round(x, 12)
    if isinstance(x, dict): return {str(k): rnd(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple)): return [rnd(v) for v in x]
    return x
def H(x): return hashlib.sha1(json.dumps(rnd(x), sort_keys=True, default=str).encode()).hexdigest()[:20]

g = random.Random(31337)
PROFS = [PS.make_player(random.Random(3000 + i), field_quality=g.choice([0.3, 0.6, 0.9, 1.2]), pid=i) for i in range(40)]
deck = [r + s for r in '23456789TJQKA' for s in 'shdc']
PLANS = ['value_3street', 'value_2street', 'pot_control', 'block', 'semibluff', 'bluff_2street',
         'river_bluff', 'giveup', 'showdown', 'trap', 'thin_river']
out = {}

def spot():
    cards = g.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
    opp = g.sample(live, g.randint(60, 300))
    if g.random() < .4:
        opp = {tuple(c): g.choice([1.0, .5, .3, g.random()]) for c in opp}
    mine = g.sample(live, g.randint(80, 250))
    return hero, board, street, opp, mine

def est():
    return {'confidence': g.uniform(.2, 1.0), 'n': g.randint(0, 60), 'bluff': g.uniform(1, 10), 'aggr': g.uniform(1, 10),
            'tight': g.uniform(1, 10), 'vpip': g.random(), 'pfr': g.random() * .4, 'cbet': g.random(), 'barrel': g.random(),
            'ftb': g.random(), 'ftb_flop': g.random(), 'ftb_turn': g.random(), 'ftb_river': g.random(),
            'sz_mean': g.uniform(.3, 1.2), 'sz_sd': g.uniform(.05, .5), 'sz_big': g.random() * .4,
            'sz_river': g.uniform(.4, 1.5), 'sz_n': g.randint(0, 40), 'fold': g.random(), 'sizing_tell': g.uniform(0, 10)}

rows = []
states = []
for i in range(450):
    p = g.choice(PROFS); hero, board, street, opp, mine = spot()
    n_opp = g.choice([1, 1, 2, 3])
    oppr = None
    if n_opp > 1 and g.random() < .6:
        oppr = {'s%d' % k: (g.sample([c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)], 120)) for k in range(n_opp)}
    s0 = PL.make_plan(hero, board, mine, opp, p, g.randint(400, 9000), g.randint(1500, 60000), street,
                      seed=500 + i, n_opp=n_opp, to_act_behind=g.choice([0, 1, 2]),
                      oop_vs_aggr=g.choice([True, False, None]), initiative=g.choice([True, False]),
                      opp_est=(est() if g.random() < .6 else None), opp_stack_bb=g.choice([None, 15.0, 60.0]),
                      tilt=g.random() * .3, bb_chips=g.choice([None, 200]), opp_ranges=oppr)
    s0c = {k: v for k, v in s0.items() if k != 'my_range'}
    rows.append(H(s0c))
    states.append((s0, hero, board, street, opp, mine, p))
out['make_plan'] = rows

rows = []
for i, (s0, hero, board, street, opp, mine, p) in enumerate(states):
    plan = g.choice(PLANS)
    ps = dict(s0); ps['opp_checked_prev'] = g.random() < .4; ps['flop_checked'] = g.random() < .4
    rng = random.Random(i)
    rows.append([rnd(PL.decide_aggression(p, board, street, plan, g.random(), g.choice([1, 2, 3]), g.choice([True, False]),
                                          g.choice([True, False]), g.choice([0, 1, 2]), rng, opp_est=(est() if g.random() < .5 else None),
                                          outs=g.choice([0, 4, 9]), plan_state=ps, oop_vs_aggr=g.choice([True, False, None]))), st(rng)])
    ps2 = dict(s0); ps2['bluff_mode'] = g.choice([None, 'merged', 'barrel', 'probe', 'polarized', 'habit']); ps2['bluff_mul'] = g.uniform(.4, 1.5)
    rng = random.Random(10000 + i)
    rows.append([rnd(PL.decide_size(p, hero, board, street, plan, g.random(), opp, mine, g.randint(400, 9000),
                                     g.randint(1500, 60000), rng, opp_est=(est() if g.random() < .5 else None),
                                     nut=g.uniform(-.5, .8), deviating=g.random() < .2, stackoff=s0.get('stackoff'),
                                     plan_state=ps2)), st(rng)])
    rng = random.Random(20000 + i)
    rows.append([rnd(PL.overbet_frac(p, hero, board, opp, mine, street, g.choice(PLANS), g.random(), rng,
                                     opp_est=(est() if g.random() < .5 else None), nut=g.uniform(-.2, .8))), st(rng)])
    rows.append([rnd(PL.perceived_rel(p, g.random(), hero, board, g.choice([0, 4, 8, 12]), g.choice([0, 1, 2, 3])))])
    rows.append([PL._allowed(p, g.choice(PLANS), random.Random(i))])
    rng = random.Random(30000 + i)
    rows.append([rnd(PL.checkraise_decision(hero, board, p, dict(s0, plan=plan), 3000, 800, 20000, street, seed=i)),
                 rnd(PL.checkraise_size(p, 3000, 800, g.randint(1000, 40000), board, street, rng)), st(rng)])
    rng = random.Random(40000 + i)
    rows.append([rnd(PL.bluff_mode(p, g.random(), g.random(), g.random(), est(), street, g.uniform(1, 15), rng)), st(rng),
                 rnd(PL.target_commit(p, g.random(), g.choice([0, 1, 3, 5]), g.uniform(1, 12), street,
                                      opp_stack_bb=g.choice([None, 20.0]), opp_eff=g.choice([None, .4, 1.0])))])
out['aggr_size'] = rows

rows = []
for i, (s0, hero, board, street, opp, mine, p) in enumerate(states):
    pot = g.randint(600, 12000); tocall = g.randint(200, max(201, pot // 2)); stack = g.randint(1000, 60000)
    ps = copy.deepcopy({k: v for k, v in s0.items()})
    ps['plan'] = g.choice(PLANS)
    rc = {'facing_target': g.choice([None, tocall, tocall + 200]), 'facing_kind': g.choice(['bet', 'raise']),
          'facing_seat': g.choice([None, 's0'])}
    rk = g.choice([None, 'face_bet', 'check_then_face_bet', 'aggressor_backaction'])
    cv = None if g.random() < .6 else {'breakeven_equity': g.uniform(.1, .5), 'effective_equity': g.random()}
    a = PL.act_with_plan(hero, board, p, ps, pot, tocall, stack, street, initiative=g.choice([True, False]),
                         opp_range=(opp if g.random() < .85 else None), bf=g.choice([1.0, 1.4]), seed=7000 + i,
                         n_opp=g.choice([1, 2]), to_act_behind=g.choice([0, 1]), opp_est=(est() if g.random() < .6 else None),
                         facing_seat='s0', checked_before=g.random() < .3, can_raise=g.random() < .85,
                         checkraise_seed=i, checkraise_size_seed=i + 1, facing_size_frac=g.choice([None, .5, 1.0, 2.5]),
                         hero_contrib=g.choice([0, 0, 300]), response_kind=rk, response_context=rc, call_value=cv,
                         size_shape_seed=i + 2)
    rows.append([rnd(list(a)), H({k: v for k, v in ps.items() if k != 'my_range'})])
    ps3 = dict(s0); ps3['intents'] = {street: {'act': g.choice(['bet', 'check']), 'size': g.choice([0.0, .005, .33, .75, 1.4]), 'src': ''}}
    a3 = PL.act_with_plan(hero, board, p, ps3, pot, 0, stack, street, seed=8000 + i, size_shape_seed=i + 3)
    rows.append([rnd(list(a3)), H(ps3.get('deviations'))])
    rng = random.Random(9000 + i)
    rows.append([rnd(PL.calldown_need(p, hero, board, street, pot, tocall, g.choice([1.0, 1.3]), None, i % 3,
                                      est() if g.random() < .7 else None, n_opp=1 + i % 2, rng=rng,
                                      objective_breakeven=(g.random() * .5 if i % 2 else None),
                                      facing_size_frac=g.choice([None, .5, 1.0, 2.5, 4.0]))), st(rng)])
out['response'] = rows

rows = []
for i, (s0, hero, board, street, opp, mine, p) in enumerate(states[:250]):
    st2 = PL.refresh(copy.deepcopy(s0), hero, board, opp, p, g.randint(400, 9000), g.randint(1500, 60000), street,
                     n_opp=1, seed=600 + i, opp_est=(est() if g.random() < .5 else None), my_range=mine)
    rows.append(H({k: v for k, v in st2.items() if k != 'my_range'}))
out['refresh'] = rows

# ---- river_fix / refresh next-street: continue-range call equity (L119) ----
rows = []
g3 = random.Random(4242)
for i, (s0, hero, board, street, opp, mine, p) in enumerate(states):
    stt = copy.deepcopy(s0)
    if i % 2 == 0:
        stt['plan'] = g3.choice(['bluff_2street', 'river_bluff', 'semibluff'])
    oppr = None; n_opp = 1
    if i % 3 == 0:
        live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
        oppr = {'s0': g3.sample(live, 90), 's1': g3.sample(live, 90)}; n_opp = 2
    if len(board) == 5:
        if i % 2 == 1:
            stt['plan'] = g3.choice(['showdown', 'pot_control', 'value_2street', 'thin_river'])
        rng = random.Random(i)
        r = PL.river_fix(stt, hero, board, profile=p, opp_range=opp, rng=rng, n_opp=n_opp, opp_ranges=oppr)
        rows.append([H({k: v for k, v in (r or {}).items() if k != 'my_range'} if isinstance(r, dict) else r),
                     H({k: v for k, v in stt.items() if k != 'my_range'}), st(rng)])
    else:
        nxt = [c for c in deck if c not in set(hero) | set(board)]
        b2 = board + [g3.choice(nxt)]
        s2 = ['flop', 'turn', 'river'][len(b2) - 3]
        r = PL.refresh(stt, hero, b2, opp, p, g3.randint(400, 9000), g3.randint(1500, 60000), s2,
                       n_opp=n_opp, seed=900 + i, opp_est=None, my_range=mine, opp_ranges=oppr)
        rows.append(H({k: v for k, v in r.items() if k != 'my_range'}))
out['next_street'] = rows

# ---- mp_sweep: make_plan branch ladder with stubbed equity + swept RNG draw ----
# The probabilistic plan gates (rng.random() < p) are invisible to 450 random
# draws when p moves by ~0.01.  Here every rng.random() returns the same swept
# value u, and the expensive equity estimators are replaced by deterministic
# hash stubs (identical for BASE and working tree), so the branch boundary in u
# is observed directly.
import types, random as _random
_orig = (PL._eq_vs, PL._eq_current, PL._decision_relative_strength, PL.random)
def _hu(*xs):
    return int(hashlib.sha1(repr(xs).encode()).hexdigest()[:12], 16) / float(16**12)
SW = {'u': 0.5}
class _SweepRandom(_random.Random):
    def random(self):
        return SW['u']
_shim = types.ModuleType('random'); _shim.__dict__.update(_random.__dict__); _shim.Random = _SweepRandom
PL.random = _shim
PL._eq_vs = lambda hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None: _hu('eq', tuple(hero), tuple(board), n_opp)
PL._eq_current = lambda hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None: _hu('eqc', tuple(hero), tuple(board), n_opp) * 0.8
PL._decision_relative_strength = (lambda hero, board, opp_range, n_opp=1, opp_ranges=None, sims=600, seed=None:
                                  (_hu('rel', tuple(hero), tuple(board), len(opp_range or ())), {'src': 'stub'}))
g2 = random.Random(777)
rows = []
GRID = [0.0025 + 0.005*k for k in range(200)]
SWEEP_SPOTS, COMMIT_SPOTS, RESP_SPOTS = 240, 120, 270
for i in range(SWEEP_SPOTS):
    p = g2.choice(PROFS) if i % 3 else PROFS[0]
    if i % 4 == 0:   # flush-draw spot (outs >= 8) for the semibluff gate
        su = g2.choice('shdc'); ranks = g2.sample('23456789TJQKA', 4)
        hero = [ranks[0] + su, ranks[1] + su]
        other = [c for c in deck if c[1] != su and c not in hero]
        board = [ranks[2] + su, ranks[3] + su] + g2.sample(other, g2.choice([1, 2]))
    else:
        cards = g2.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g2.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
    opp = g2.sample(live, g2.randint(40, 220)); mine = g2.sample(live, 120)
    kw = dict(seed=i, n_opp=g2.choice([1, 1, 1, 2]), to_act_behind=g2.choice([0, 0, 1]),
              oop_vs_aggr=g2.choice([True, True, False, None]), initiative=g2.choice([False, False, True]),
              opp_est=(est() if g2.random() < .5 else None), opp_stack_bb=None, tilt=0.0, bb_chips=None)
    pot = g2.randint(400, 6000); stack = g2.randint(800, 60000)
    seq = []
    for u in GRID:
        SW['u'] = u
        s0 = PL.make_plan(hero, board, mine, opp, p, pot, stack, street, **kw)
        seq.append((s0.get('plan'), s0.get('bluff_mode'), rnd(s0.get('stackoff')), s0.get('commit_rel'),
                    H(s0.get('why'))))
    # compress: boundaries where the outcome changes along u
    bnd = [(round(GRID[k], 4), H(seq[k])) for k in range(len(seq)) if k == 0 or seq[k] != seq[k-1]]
    rows.append(bnd)
out['mp_sweep'] = rows

# commit boundary of continue_range_commit_strength (_commit > 0.30): sweep the
# target commit itself across the threshold; commit_rel/stackoff expose the branch.
_tc = PL.target_commit
rows = []
SW['u'] = 0.5
for i in range(COMMIT_SPOTS):
    p = PROFS[i % len(PROFS)]
    cards = g2.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g2.choice([3, 4])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
    opp = g2.sample(live, g2.randint(60, 220)); mine = g2.sample(live, 120)
    seq = []
    for k in range(21):
        cval = 0.290 + 0.001*k
        PL.target_commit = (lambda cv: (lambda *a, **kw: cv))(cval)
        s0 = PL.make_plan(hero, board, mine, opp, p, 1000, 30000, street, seed=i, n_opp=1,
                          to_act_behind=0, oop_vs_aggr=None, initiative=True, opp_est=None)
        seq.append((round(cval, 3), s0.get('commit_rel'), rnd(s0.get('stackoff'))))
    rows.append(H(seq))
PL.target_commit = _tc
PL._eq_vs, PL._eq_current, PL._decision_relative_strength, PL.random = _orig
out['commit_boundary'] = rows

# ---- resp_sweep: decide_response gates with swept RNG draw + stubbed equity ----
_beq = B.equity_vs_combos
B.equity_vs_combos = lambda hero, board, pools, sims=400, seed=None: _hu('eqc2', tuple(hero), tuple(board), sum(len(p) for p in pools))
PL._decision_relative_strength = (lambda hero, board, opp_range, n_opp=1, opp_ranges=None, sims=600, seed=None:
                                  (_hu('rel', tuple(hero), tuple(board), len(opp_range or ())), {'src': 'stub'}))
rows = []
RPLANS = ['semibluff', 'value_3street', 'value_2street', 'trap', 'bluff_2street', 'giveup', 'river_bluff', 'pot_control', 'showdown']
for i in range(RESP_SPOTS):
    p = PROFS[i % len(PROFS)]
    if i % 3 == 0:
        p = dict(p); p['concepts'] = {}
    cards = g2.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g2.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
    opp = g2.sample(live, g2.randint(40, 220))
    plan = RPLANS[i % len(RPLANS)]
    ps = {'rel': g2.random(), 'outs': g2.choice([0, 8, 9, 12]), 'made': g2.choice([0, 1, 2, 5]),
          'stackoff': g2.choice([None, {'commit': g2.uniform(.2, 1.0)}])}
    eq = g2.random(); need = g2.uniform(.1, .5)
    pot = g2.randint(600, 9000); tocall = g2.randint(100, pot); stack = g2.randint(500, 60000)
    rc = {'facing_target': g2.choice([None, tocall, tocall + 300]), 'facing_contrib': tocall, 'facing_seat': None}
    kw = dict(allow_raise=g2.random() < .85, call_eq=(g2.random() if i % 4 == 0 else None),
              call_need=(g2.uniform(.1, .5) if i % 4 == 0 else None), n_opp=g2.choice([1, 1, 2]),
              rel_seed=i, response_context=rc, hero_contrib=g2.choice([0.0, 200.0]))
    seq = []
    for u in GRID:
        SW['u'] = u
        r = PL.decide_response(p, hero, board, street, plan, dict(ps), eq, need,
                               PL.bot.made_strength(hero, board), opp, pot, tocall, stack,
                               (i % 5 == 0), _SweepRandom(0), **kw)
        seq.append(H(r))
    rows.append([(round(GRID[k], 4), seq[k]) for k in range(len(seq)) if k == 0 or seq[k] != seq[k-1]])
B.equity_vs_combos = _beq
PL._decision_relative_strength = _orig[2]
out['resp_sweep'] = rows
AGGR_SPOTS, OB_SPOTS, VR_SPOTS, CKR_SPOTS = 150, 140, 300, 300

# ---- mp_sweep_aggr: high-aggression OOP no-initiative spots (blockbet cap) ----
# Appended after the other sections with its own RNG so earlier rows are unchanged.
PL._eq_vs = lambda hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None: _hu('eq', tuple(hero), tuple(board), n_opp)
PL._eq_current = lambda hero, board, opp_range, n_opp, sims=400, seed=None, opp_ranges=None: _hu('eqc', tuple(hero), tuple(board), n_opp) * 0.8
PL._decision_relative_strength = (lambda hero, board, opp_range, n_opp=1, opp_ranges=None, sims=600, seed=None:
                                  (_hu('rel', tuple(hero), tuple(board), len(opp_range or ())), {'src': 'stub'}))
PL.random = _shim
g4 = random.Random(99)
rows = []
for i in range(AGGR_SPOTS):
    p = dict(PROFS[i % len(PROFS)]); p['aggr'] = g4.uniform(8.0, 10.0); p['bluff'] = g4.uniform(1.0, 3.0)
    cards = g4.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g4.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
    opp = g4.sample(live, g4.randint(40, 220)); mine = g4.sample(live, 120)
    seq = []
    for u in GRID:
        SW['u'] = u
        s0 = PL.make_plan(hero, board, mine, opp, p, 1500, 30000, street, seed=i, n_opp=1, to_act_behind=0,
                          oop_vs_aggr=True, initiative=False, opp_est=None, opp_stack_bb=None, tilt=0.0, bb_chips=None)
        seq.append((s0.get('plan'), H(s0.get('why'))))
    rows.append([(round(GRID[k], 4), H(seq[k])) for k in range(len(seq)) if k == 0 or seq[k] != seq[k-1]])
PL._eq_vs, PL._eq_current, PL._decision_relative_strength, PL.random = _orig
out['mp_sweep_aggr'] = rows

# ---- ob_sweep: overbet_frac selection with swept draw (fine grid) ----
_rs = PL.relative_strength
PL.relative_strength = lambda hero, board, opp_range=None: _hu('rs', tuple(hero), tuple(board), len(opp_range or ()))
GRID_OB = [0.0005 + 0.001*k for k in range(400)]
OBPLANS = ['value_3street', 'value_2street', 'trap', 'thin_river', 'bluff_2street', 'river_bluff', 'semibluff']
rows = []
for i in range(OB_SPOTS):
    p = PROFS[i % len(PROFS)]
    cards = g4.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g4.choice([4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
    opp = g4.sample(live, g4.randint(40, 220)); mine = g4.sample(live, 120)
    plan = OBPLANS[i % len(OBPLANS)]
    rel = g4.random(); nut = g4.uniform(-0.2, 0.8)
    seq = []
    for u in GRID_OB:
        SW['u'] = u
        seq.append(PL.overbet_frac(p, hero, board, opp, mine, street, plan, rel, _SweepRandom(0), opp_est=None, nut=nut))
    rows.append([(round(GRID_OB[k], 4), seq[k]) for k in range(len(seq)) if k == 0 or seq[k] != seq[k-1]])
PL.relative_strength = _rs
out['ob_sweep'] = rows

# ---- vr_boundary: value-raise qualification with continue-range equity near 0.5 ----
_beq = B.equity_vs_combos
B.equity_vs_combos = lambda hero, board, pools, sims=400, seed=None: 0.49 + 0.02*_hu('vr', tuple(hero), tuple(board), sum(len(p) for p in pools))
PL._decision_relative_strength = (lambda hero, board, opp_range, n_opp=1, opp_ranges=None, sims=600, seed=None:
                                  (_hu('rel', tuple(hero), tuple(board), len(opp_range or ())), {'src': 'stub'}))
rows = []
for i in range(VR_SPOTS):
    p = PROFS[i % len(PROFS)]
    cards = g4.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g4.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    live = [c for c in R._SORTED if c[0] not in set(board) and c[1] not in set(board)]
    opp = g4.sample(live, g4.randint(40, 220))
    plan = ['value_3street', 'value_2street', 'trap'][i % 3]
    ps = {'rel': g4.uniform(.5, 1.0), 'outs': 0, 'made': 2, 'stackoff': g4.choice([None, {'commit': g4.uniform(.3, 1.0)}])}
    pot = g4.randint(600, 6000); tocall = g4.randint(100, pot // 2); stack = g4.randint(5000, 60000)
    rc = {'facing_target': tocall, 'facing_contrib': tocall, 'facing_seat': None}
    res = []
    for u in (0.1, 0.5, 0.9):
        SW['u'] = u
        res.append(H(PL.decide_response(p, hero, board, street, plan, dict(ps), g4.uniform(.7, .95), g4.uniform(.1, .3),
                                        PL.bot.made_strength(hero, board), opp, pot, tocall, stack, False, _SweepRandom(0),
                                        allow_raise=True, n_opp=1, rel_seed=i, response_context=rc, hero_contrib=0.0)))
    rows.append(res)
B.equity_vs_combos = _beq
PL._decision_relative_strength = _orig[2]
out['vr_boundary'] = rows

# ---- ckr_extra: checkraise size with large facing bets (pot cap binds) and
#      no-concept / unknown-type skill fallback ----
rows = []
for i in range(CKR_SPOTS):
    p = PROFS[i % len(PROFS)]
    pot = g4.randint(500, 6000); tocall = int(pot * g4.uniform(0.3, 3.0)); stack = g4.randint(tocall * 3, tocall * 30)
    cards = g4.sample(deck, 5); board = cards[:g4.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    rng = random.Random(70000 + i)
    rows.append([PL.checkraise_size(p, pot, tocall, stack, board, street, rng), st(rng)])
    pn = dict(p); pn['concepts'] = {}; pn['type'] = g4.choice(['__unknown__', p.get('type')])
    cards = g4.sample(deck, 7); hero = cards[:2]; board = cards[2:2 + g4.choice([3, 4, 5])]
    street = ['flop', 'turn', 'river'][len(board) - 3]
    psn = {'plan': g4.choice(PLANS), 'rel': g4.random(), 'outs': g4.choice([0, 8, 12])}
    rows.append(rnd(PL.checkraise_decision(hero, board, pn, psn, 3000, 800, 20000, street, seed=i)))
out['ckr_extra'] = rows
print(json.dumps(out, sort_keys=True))
'''


def run(root, probe=None):
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
        f.write(probe or PROBE)
        probe = f.name
    try:
        res = subprocess.run([sys.executable, probe, root], capture_output=True, text=True, timeout=3000)
    finally:
        os.unlink(probe)
    if res.returncode != 0:
        raise SystemExit(res.stderr[-3000:])
    return json.loads(res.stdout)


def copy_tree(src_ref=None, src_dir=None):
    tmp = tempfile.mkdtemp(prefix='s9_')
    if src_ref:
        files = subprocess.check_output(['git', 'ls-tree', '--name-only', src_ref], cwd=ROOT, text=True).split()
        for fn in files:
            if fn.endswith('.py') or fn.endswith('.json'):
                open(os.path.join(tmp, fn), 'wb').write(
                    subprocess.check_output(['git', 'show', '%s:%s' % (src_ref, fn)], cwd=ROOT))
    else:
        for fn in os.listdir(src_dir):
            if fn.endswith('.py') or fn.endswith('.json'):
                shutil.copy(os.path.join(src_dir, fn), tmp)
    return tmp


def main():
    args = sys.argv[1:]
    mutate = None
    probe = PROBE
    if '--probe' in args:
        i = args.index('--probe'); probe = {'b1': PROBE, 'b2': PROBE_B2, 'b3': PROBE_B3}[args[i + 1]]; del args[i:i + 2]
    if '--mutate' in args:
        i = args.index('--mutate'); mutate = args[i + 1].split('|||', 2); del args[i:i + 2]
    cache = None
    if '--base-cache' in args:
        i = args.index('--base-cache'); cache = args[i + 1]; del args[i:i + 2]
    base = args[0] if args else 'HEAD'
    # BASE output depends only on (resolved base commit, probe text): cache it so
    # mutation runs only execute the working-tree side.
    import hashlib as _hl
    key = subprocess.check_output(['git', 'rev-parse', base], cwd=ROOT, text=True).strip() + ':' + \
        _hl.sha256(probe.encode()).hexdigest()
    before = None
    if cache and os.path.exists(cache):
        c = json.load(open(cache))
        if c.get('key') == key:
            before = c['out']
    if before is None:
        before = run(copy_tree(src_ref=base), probe)
        if cache:
            json.dump({'key': key, 'out': before}, open(cache, 'w'))
    if mutate:
        work = copy_tree(src_dir=ROOT)
        fp = os.path.join(work, mutate[0]); txt = open(fp).read()
        assert mutate[1] in txt, 'mutation anchor not found'
        open(fp, 'w').write(txt.replace(mutate[1], mutate[2], 1))
        after = run(work, probe)
    else:
        after = run(ROOT, probe)
    report = {k: {'n': len(before[k]), 'equal': before[k] == after.get(k)} for k in before}
    ok = all(v['equal'] for v in report.values())
    print(json.dumps({'pass': ok, 'base': base, 'mutated': bool(mutate), 'checks': report}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
