"""Compare direct best-five evaluation with the unchanged subset evaluator."""
import argparse
import itertools
import json
import pathlib
import random
import statistics
import sys
import time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import bot

parser = argparse.ArgumentParser()
parser.add_argument('--all-five', action='store_true')
args = parser.parse_args()
def reference(cards):
    return max(bot.eval5(list(c)) for c in itertools.combinations(cards, 5))

# Two trips, three pairs, board-only ties, ace-low straights and competing flushes.
special = ['Ac Ad Ah Kc Kd Kh 2s', 'Ac Ad Kc Kd Qc Qd Js',
           'Ac 2c 3c 4c 5c Ks Kh', 'Ac Kc Qc Jc 8c Tc 2d',
           '9c 9d 9h 9s Ac Kh Qd', 'Ac Ad Ah Ks Qd Jh 9s']
for h in special:
    cards = h.split()
    assert bot._eval_best(cards) == reference(cards), cards
rng = random.Random(20261009)
counts = {5:0, 6:0, 7:0}
hands = []
for n in counts:
    for _ in range(30000):
        cards = rng.sample(bot.FULLDECK, n)
        assert bot._eval_best(cards) == reference(cards), cards
        counts[n] += 1
        if n == 7 and len(hands) < 1000:
            hands.append(cards)
if args.all_five:
    total = 0
    for cards in itertools.combinations(bot.FULLDECK, 5):
        assert bot._eval_best(cards) == bot.eval5(cards), cards
        total += 1
    assert total == 2598960
    counts['exhaustive_five'] = total
old, new = [], []
for _ in range(5):
    t = time.perf_counter(); expected = [reference(h) for h in hands]; old.append(time.perf_counter()-t)
    t = time.perf_counter(); actual = [bot._eval_best(h) for h in hands]; new.append(time.perf_counter()-t)
    assert expected == actual
print(json.dumps({'pass':True,'cases':counts,'median_reference_seconds':statistics.median(old),
 'median_direct_seconds':statistics.median(new),'speedup':statistics.median(old)/statistics.median(new)}))
