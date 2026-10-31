"""멀티웨이(3인+) 무저항 첫 행동에서 탑페어·오버페어가 왜 체크하는지 기록(진단 전용, 행동 불변).

    python3 tools/multiway_passivity_diag.py 핸드수 시드 [--old] --jsonl 파일

multiway_betfreq.py 와 같은 기회 정의(그 스트리트에 벳이 없을 때 그 자리 첫 행동).
attach_intent / decide_aggression 을 감싸 읽기만 한다(반환값·RNG 그대로).
--old : 상대 프리플랍 레인지를 GTO 동기화 이전 경로로(ranges.gto_pf_story_range → None).
기록마다 eq(현재 레인지), eq_field35·eq_rand(넓은 기준 레인지), rel_joint/rel_union,
밸류 사다리 문턱(v3/v2/pcz)과 다인원 가산분, 계획, 벳 확률, 실제 행동.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import tourney as T
import bot as B
import plan as P
import ranges as R

args = sys.argv[1:]
OLD = '--old' in args
args = [a for a in args if a != '--old']
i = args.index('--jsonl'); out = args[i + 1]; del args[i:i + 2]
relfit_out = None
if '--relfit' in args:      # rel 단위 보정용: 멀티웨이 joint rel 과 좌석별 헤즈업 rel 을 같이 남긴다
    i = args.index('--relfit'); relfit_out = args[i + 1]; del args[i:i + 2]
HANDS, SEED = int(args[0]), int(args[1])
NB = {'flop': 3, 'turn': 4, 'river': 5}
AGG = ('bet', 'raise', 'allin')

if OLD:
    R.gto_pf_story_range = lambda *a, **k: (None, {'source': 'disabled_for_diag'})

REC = {}          # (hand, street, hero) -> 첫 기록
CUR = {'hand': 0}
_da, _ai = P.decide_aggression, P.attach_intent


def hand_class(hole, board):
    m = B.made_strength(list(hole), board)
    if m >= 2:
        return '2p+'
    if m < 1:
        return None
    rv = sorted((B.RV[b[0]] for b in board), reverse=True)
    if hole[0][0] == hole[1][0]:
        return 'overpair' if B.RV[hole[0][0]] > rv[0] else None
    hit = [c for c in hole if B.RV[c[0]] == rv[0]]
    if not hit:
        return None
    kick = B.RV[[c for c in hole if c is not hit[0]][0][0]]
    return 'tp_gk' if kick >= 12 else 'tp_weak'      # 키커 Q+ = 좋은 키커


LAST = {}


def decide_aggression(*a, **k):
    r = _da(*a, **k)
    LAST['r'] = r
    return r


def attach_intent(st, hero, board, *a, **k):
    LAST.clear()
    r = _ai(st, hero, board, *a, **k)
    street = a[6] if len(a) > 6 else k.get('street')
    key = (CUR['hand'], len(board), tuple(hero))
    n = int(st.get('n_opp') or 1)
    cls = hand_class(hero, board) if n >= 2 else None
    if key not in REC and cls and 'r' in LAST:
        dead = set(hero) | set(board)
        f35 = B.range_combos(0.35, dead); fr = B.range_combos(1.0, dead)
        diag = {'cls': cls,
                'eq_f35': B.equity_vs_combos(hero, board, [f35] * n, sims=400),
                'eq_rand': B.equity_vs_combos(hero, board, [fr] * n, sims=400)}
        mw, v3, v2, pcz = P.multiway_value_thresholds(n, 0, 0)
        REC[key] = dict(diag, street_made=st.get('street_made'), revised=st.get('revised'), street=len(board), n_opp=n, plan=st.get('plan'),
                        eq=st.get('eq'), eq_current=st.get('eq_current'),
                        rel=st.get('rel'), rel_joint=st.get('rel_joint'),
                        rel_union=st.get('rel_union'), made=st.get('made'),
                        mw=mw, v3=v3, v2=v2, pcz=pcz, pc=st.get('pc'),
                        type=st.get('type'), p_bet=LAST['r'][0], why_bet=LAST['r'][1],
                        why=(st.get('why') or [])[-3:])
    return r


P.decide_aggression, P.attach_intent = decide_aggression, attach_intent

RELFIT = []
_drs = P._decision_relative_strength


def _decision_relative_strength(hero, board, opp_range, n_opp=1, opp_ranges=None, sims=600, seed=None):
    r = _drs(hero, board, opp_range, n_opp=n_opp, opp_ranges=opp_ranges, sims=sims, seed=seed)
    meta = r[1] if isinstance(r, tuple) else {}
    if (relfit_out and int(n_opp or 1) >= 2 and meta.get('source') == 'joint_seat_pools'
            and isinstance(opp_ranges, dict) and len(board) >= 3):
        # 읽기만 한다: relative_strength 는 RNG 를 쓰지 않는 정확 계산(캐시만 채움).
        seat = [P.relative_strength(list(hero), list(board), rr) for _k, rr in sorted(opp_ranges.items(), key=lambda kv: str(kv[0]))]
        RELFIT.append({'n_opp': int(n_opp), 'street': len(board), 'joint': meta.get('joint'),
                       'union': meta.get('union'), 'seat': seat})
    return r


P._decision_relative_strength = _decision_relative_strength

rows = []
t = T.Tournament(entries=100, seed=SEED, fmt=os.environ.get('MW_FMT', 'standard'), hero_seat=7)
for hn in range(HANDS):
    if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
        break
    CUR['hand'] = hn
    st = t.next_hand(); g = 0
    while st and not st.get('done') and g < 250:
        st = t.submit('fold'); g += 1
    h = t.run.h
    log = getattr(t.run, 'full_log', []) or []
    for stt in ('flop', 'turn', 'river'):
        rr = [x for x in log if x[0] == stt]
        if not rr:
            break
        seats = []
        for x in rr:
            if x[1] not in seats:
                seats.append(x[1])
        if len(seats) < 3:
            continue
        bet_seen = False; acted = set()
        for (_s, x, act, _m) in rr:
            if not bet_seen and x not in acted:
                rec = REC.get((hn, NB[stt], tuple(h.hole[x])))
                if rec:
                    rows.append(dict(rec, act=act, bet=act in AGG, seed=SEED, hand=hn,
                                     players=len(seats), old=OLD))
            acted.add(x)
            if act in AGG:
                bet_seen = True
    t.finish_hand()
with open(out, 'w') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
if relfit_out:
    with open(relfit_out, 'w') as f:
        for r in RELFIT:
            f.write(json.dumps(r) + '\n')
print('rows', len(rows), 'old' if OLD else 'cur')
