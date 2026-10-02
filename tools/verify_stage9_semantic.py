#!/usr/bin/env python3
"""Stage 9 behaviour-identity check: pristine BASE checkout vs working tree.

Runs one deterministic probe (randomised inputs, fixed seeds) in a temp copy of
BASE's *.py/*.json files and in the working tree, then compares the JSON outputs
byte for byte (including Random state digests and mutated record dicts).

Usage: python tools/verify_stage9_semantic.py [BASE] [--probe b1|b2] [--mutate 'FILE|||OLD|||NEW']
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
        i = args.index('--probe'); probe = {'b1': PROBE, 'b2': PROBE_B2}[args[i + 1]]; del args[i:i + 2]
    if '--mutate' in args:
        i = args.index('--mutate'); mutate = args[i + 1].split('|||', 2); del args[i:i + 2]
    base = args[0] if args else 'HEAD'
    before = run(copy_tree(src_ref=base), probe)
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
