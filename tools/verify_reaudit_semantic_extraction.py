#!/usr/bin/env python3
"""Behavior-identity check for the re-audit semantic extractions.

Extractions (no numeric/threshold/RNG change intended):
  icm.players_behind_required_equity_premium  <- plan.calldown_need + preflop.multiway_reraise_decision
  plan.has_showdown_value                      <- two inline predicates in plan.make_plan
  plan.line_owned_by_live_aggressor            <- inline line-ownership block in plan.decide_aggression

Method: run the same deterministic probe in a pristine checkout of BASE
(git show BASE:<file> into a temp dir) and in the working tree, then compare
the JSON outputs byte for byte, including the Random state after each call.

Usage: python tools/verify_reaudit_semantic_extraction.py [BASE]   (default HEAD)
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROBE = r'''
import sys, json, random, hashlib
sys.path.insert(0, sys.argv[1])
import persona as PS, plan as PL, preflop as PF, ranges as R

def prof(v):
    p = {'concepts': {k: v for k in PS.ALL_CONCEPTS},
         'latent': {'study': v, 'aggro': 5.0, 'exp': v},
         'temper': {'aggression': 5.0, 'looseness': 5.0, 'gamble': 5.0, 'tilt_prone': 0.0,
                    'tilt_recovery': v, 'discipline': v, 'adaptability': v, 'consistency': v,
                    'attention': v, 'slowplay_taste': 5.0, 'tilt_swing': 5.0, 'tilt_stack': 0.0}}
    p.update(PS.derive(p))
    return p

def st(rng):
    return hashlib.sha1(repr(rng.getstate()).encode()).hexdigest()[:16]

out = {'calldown': [], 'aggr': [], 'make': [], 'mw': []}
PROFS = [prof(10.0), prof(5.0), prof(2.0)]
deck = [r + s for r in '23456789TJQKA' for s in 'shdc']
g = random.Random(1234)
# calldown_need: players behind 0..4, with and without objective breakeven
for i in range(400):
    p = PROFS[i % 3]
    cards = g.sample(deck, 7)
    hero, board = cards[:2], cards[2:2 + g.choice([3, 4, 5])]
    pot = g.randint(300, 20000); tocall = g.randint(100, max(101, pot // 2))
    rng = random.Random(i)
    r = PL.calldown_need(p, hero, board, ['flop', 'turn', 'river'][len(board) - 3], pot, tocall,
                         g.choice([1.0, 1.3]), None, i % 5, None, n_opp=1 + i % 3, rng=rng,
                         objective_breakeven=(g.random() * 0.5 if i % 2 else None))
    out['calldown'].append([r, st(rng)])
# decide_aggression: every plan x initiative x oop_vs_aggr x street, with prior responses
PLANS = ['value_3street', 'value_2street', 'pot_control', 'block', 'semibluff', 'bluff_2street',
         'river_bluff', 'giveup', 'showdown', 'trap']
for i in range(1500):
    p = g.choice(PROFS)
    street = g.choice(['flop', 'turn', 'river'])
    board = g.sample(deck, {'flop': 3, 'turn': 4, 'river': 5}[street])
    ps = {'response_plans': {'flop': [{'act': g.choice(['call', 'raise', 'fold']),
                                         'response_kind': g.choice(['face_bet', 'check_then_face_bet', None])}],
                              'turn': [{'act': g.choice(['call', 'raise']),
                                        'response_kind': g.choice(['face_bet', 'aggressor_backaction'])}]},
          'flop_checked': bool(i % 2), 'range_adv': g.uniform(-0.5, 0.5),
          'opp_checked_prev': bool(i % 4 == 0)}
    rng = random.Random(i)
    r = PL.decide_aggression(p, board, street, g.choice(PLANS), g.random(), g.choice([1, 2, 3]),
                             g.choice([True, False]), g.choice([True, False]), g.choice([0, 1, 2]),
                             rng, outs=g.choice([0, 4, 9]),
                             plan_state=ps, oop_vs_aggr=g.choice([True, False, None]))
    out['aggr'].append([r, st(rng)])
# make_plan: full plan state (fingerprint) for random spots
for i in range(500):
    p = g.choice(PROFS)
    cards = g.sample(deck, 7)
    hero, board = cards[:2], cards[2:2 + (3 + i % 3)]
    dead = set(hero) | set(board)
    live = [c for c in R._SORTED if c[0] not in dead and c[1] not in dead]
    opp = g.sample(live, 200)
    mine = g.sample(live, 150)
    s = PL.make_plan(hero, board, mine, opp, p, g.randint(400, 9000), g.randint(2000, 60000),
                     ['flop', 'turn', 'river'][len(board) - 3], seed=1000 + i,
                     n_opp=g.choice([1, 2, 3]), to_act_behind=g.choice([0, 1]),
                     oop_vs_aggr=g.choice([True, False, None]),
                     initiative=g.choice([True, False]), bb_chips=200, opp_stack_bb=50.0)
    s = {k: v for k, v in s.items() if k not in ('my_range',)}
    out['make'].append(hashlib.sha1(json.dumps(s, sort_keys=True, default=str).encode()).hexdigest())
# multiway re-raise: players behind 0..3
for i in range(120):
    p = PROFS[i % 3]
    hand = g.sample(deck, 2)
    op = R.preflop_range(p, 'UTG', 'open', 60.0, hand, seats=9, ante=True)
    rr = R.preflop_range(p, 'HJ', '3bet', 60.0, hand, 0, 'UTG', open_bb=2.5, seats=9, ante=True)
    rng = random.Random(i)
    a, sz, au = PF.cold_reraise_decision(p, 'BTN', 'HJ', hand, 60.0, 8.0, 0, rng, raise_level=2,
                                         stack_bb=60.0, seats=9, ante=True, can_raise=True,
                                         pot_bb=12.0, to_call_bb=8.0, original_opener_range=op,
                                         reraiser_range=rr, players_behind=i % 4, decision_seed=i)
    out['mw'].append([a, sz, au.get('need_seen'), au.get('final_likelihoods'), st(rng)])
print(json.dumps(out, sort_keys=True))
'''


def run(root):
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
        f.write(PROBE)
        probe = f.name
    try:
        res = subprocess.run([sys.executable, probe, root], capture_output=True, text=True,
                             timeout=3000)
    finally:
        os.unlink(probe)
    if res.returncode != 0:
        raise SystemExit(res.stderr[-3000:])
    return json.loads(res.stdout)


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
    tmp = tempfile.mkdtemp(prefix='reaudit_base_')
    files = subprocess.check_output(['git', 'ls-tree', '--name-only', base], cwd=ROOT,
                                    text=True).split()
    for fn in files:
        if fn.endswith('.py') or fn.endswith('.json'):
            data = subprocess.check_output(['git', 'show', '%s:%s' % (base, fn)], cwd=ROOT)
            open(os.path.join(tmp, fn), 'wb').write(data)
    before = run(tmp)
    after = run(ROOT)
    report = {k: {'n': len(before[k]), 'equal': before[k] == after[k]} for k in before}
    ok = all(v['equal'] for v in report.values())
    print(json.dumps({'pass': ok, 'base': base, 'checks': report}, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
