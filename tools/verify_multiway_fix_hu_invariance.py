"""멀티웨이 밸류 문턱 수정(2026-10-31)이 헤즈업 판단을 바꾸지 않는지 확인.

    python3 tools/verify_multiway_fix_hu_invariance.py [핸드수] [시드]

1) 식 확인: multiway_value_thresholds 의 mw 는 예전과 같고, 문턱은 인원 무관(0.80/0.66/0.50).
   per_opponent_rel 은 헤즈업에서 항등, 멀티웨이에서 rel^(1/k) (k = MW_REL_JOINT_EXPONENT).
2) 실제 판: 봇만 시뮬하며 make_plan 호출마다, 같은 입력으로 **예전 식**(인원 가산 + joint rel 그대로)을
   넣은 make_plan 을 한 번 더 불러 결과를 비교한다(시드를 넘기므로 같은 RNG). 헤즈업은 전부 같아야 하고,
   멀티웨이는 다른 건수를 센다(정보용). 시뮬 진행은 새 식 결과로 한다.
"""
import sys, os, math, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import plan as P

fail = []


def old_thresholds(n_opp, monster, strong):
    mw = max(0, n_opp - 1)
    if monster: mw = 0
    elif strong: mw = min(mw, 1)
    return mw, 0.80 + 0.06*mw, 0.66 + 0.07*mw, 0.50 + 0.06*mw


for n in range(1, 7):
    for m in (0, 1):
        for s in (0, 1):
            new = P.multiway_value_thresholds(n, m, s)
            old = old_thresholds(n, m, s)
            if new[0] != old[0] or new[1:] != (0.80, 0.66, 0.50):
                fail.append(('thresholds', n, m, s, new, old))
    for i in range(101):
        r = i / 100.0
        pr = P.per_opponent_rel(r, n)
        if n == 1 and pr != r:
            fail.append(('hu_rel_identity', r, pr))
        if n > 1:
            k = P.MW_REL_JOINT_EXPONENT.get(n, float(n))
            if abs(pr - r ** (1.0 / k)) > 1e-12:
                fail.append(('mw_rel', n, r, pr))
for n, k in P.MW_REL_JOINT_EXPONENT.items():
    if abs(k - n) / n > 0.10:           # 독립 가정(k=N)에서 10% 넘게 벗어나면 측정을 의심
        fail.append(('exponent_far_from_independence', n, k))
print('formula checks', 'ok' if not fail else fail[:5])

HANDS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 9100
import tourney as T
_mp = P.make_plan
_new_thr, _new_rel = P.multiway_value_thresholds, P.per_opponent_rel
cnt = {'hu': 0, 'hu_diff': 0, 'mw': 0, 'mw_diff': 0}


def _strip(d):
    return repr(d)                       # 같은 코드 경로면 키 순서도 같다


def make_plan(*a, **k):
    r = _mp(*a, **k)
    if k.get('seed') is None and len(a) < 9:
        return r                         # 시드 없는 호출은 RNG 가 달라 비교 불가(세지 않음)
    P.multiway_value_thresholds, P.per_opponent_rel = old_thresholds, (lambda rel, n: rel)
    try:
        o = _mp(*a, **k)
    finally:
        P.multiway_value_thresholds, P.per_opponent_rel = _new_thr, _new_rel
    n = int(k.get('n_opp', 1) or 1)
    key = 'hu' if n <= 1 else 'mw'
    cnt[key] += 1
    if _strip(r) != _strip(o):
        cnt[key + '_diff'] += 1
    return r


P.make_plan = make_plan
t = T.Tournament(entries=100, seed=SEED, fmt=os.environ.get('MW_FMT', 'standard'), hero_seat=7)
for _ in range(HANDS):
    if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
        break
    st = t.next_hand(); g = 0
    while st and not st.get('done') and g < 250:
        st = t.submit('fold'); g += 1
    t.finish_hand()
print('make_plan calls', cnt)
if cnt['hu'] == 0:
    fail.append(('no_hu_calls_seen',))
if cnt['hu_diff']:
    fail.append(('hu_changed', cnt['hu_diff']))
print('PASS' if not fail else 'FAIL %s' % fail[:5])
sys.exit(1 if fail else 0)
