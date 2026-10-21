"""솔버 스팟 기록 ↔ T2 봇 핸드별 대조 장치 (생산 코드 무수정, 측정 전용).

  python3 spotcmp.py <code_dir> <record.json> <node_idx> <reps_per_class> <out.json> [profile=ref]

- 기록(spot_record_v2)의 노드 경로를 그대로 재현한다: 앞선 행동은 엔진 REPLAY 로 정확한 raise-to 금액까지 강제.
- 대상 좌석의 홀카드를 169 클래스별로 지정(구체 콤보를 돌아가며), 나머지 좌석 카드는 남은 덱에서 배분.
- 스택 = 기록의 hand_start_bb (안테 전), 안테 = 1bb 전원 균등(uniform_total_1bb), 9맥스.
- 대상 좌석은 실제 경로 session.HandRun → plan.preflop_plan 으로 판단. 첫 행동만 측정하고 멈춘다.
- T2 행동을 기록 메뉴로 번역: 폴드/콜/체크 그대로, 올인은 All-in, 비올인 레이즈는 로그 거리 최근접 메뉴 크기
  (메뉴에 비올인 레이즈가 없으면 off_menu 로 따로 센다). 번역 거리 기록.
- 조건: ICM 중립, 상대 읽기 없음(빈 장부), 틸트 없음 — spot.py 와 동일.
"""
import copy, json, math, os, random, re, sys
code, REC, NODE, REPS, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
PROFILE = sys.argv[6] if len(sys.argv) > 6 else 'ref'
sys.path.insert(0, code); sys.path.insert(0, os.path.join(code, 'tools'))
os.environ['T2_BOT_LOG'] = '0'; os.environ['T2_TELEMETRY'] = '0'; os.environ.pop('T2_TIMING_V1', None)
import play, session, dynamics, reads, preflop as PF
from r2_freeze_defend_baseline import maxskill

rec = json.load(open(REC))
node = rec['nodes'][NODE]
POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
seat_of = {p: i + 1 for i, p in enumerate(POS)}
pos_map = {i + 1: p for i, p in enumerate(POS)}
pre = [seat_of[p] for p in POS]
post = [seat_of['SB'], seat_of['BB']] + [seat_of[p] for p in POS[:7]]
BB = 900                                   # 안테 1bb / 9좌석 = 100칩 정확
START = int(round(rec['stack_bb'] * BB))   # 손 시작 스택 (안테 전), 전원 동일
line = [tuple(x.split(':', 1)) for x in node['line']]

def lab2t2(lab):
    m = re.match(r'(Fold|Check|Call|Raise|\d-bet|All-in)\s*([\d.]+)?', lab)
    kind, amt = m.group(1), m.group(2)
    if kind == 'Fold': return ('fold', 0)
    if kind == 'Check': return ('check', 0)
    if kind == 'Call': return ('call', 0)
    if kind == 'All-in': return ('allin', 0)
    return ('raise', int(round(float(amt) * BB)))

forced = [(seat_of[w], lab2t2(l), l) for w, l in line]
ACTOR = seat_of[node['actor']]
menu = node['actions']
menu_raises = [(l, float(re.search(r'([\d.]+)', l).group(1))) for l in menu
               if re.match(r'(Raise|\d-bet)', l)]
menu_allin = next((l for l in menu if l.startswith('All-in')), None)
menu_call = next((l for l in menu if l.startswith('Call') or l.startswith('Limp') or l == 'Check'), None)

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
def combos(cls):
    a, b = cls[0], cls[1]
    if len(cls) == 2: return [[a + s1, a + s2] for i, s1 in enumerate(SUITS) for s2 in SUITS[i + 1:]]
    if cls[2] == 's': return [[a + s, b + s] for s in SUITS]
    return [[a + s1, b + s2] for s1 in SUITS for s2 in SUITS if s1 != s2]

REFP = maxskill()
class Stop(BaseException): pass

def one(cls, j):
    cards = combos(cls)[j % len(combos(cls))]
    profs = {str(s): copy.deepcopy(REFP) for s in pos_map}
    stacks = {s: START for s in pos_map}
    seed = 900001 + 7919 * j + 104729 * NODE
    h = play.Hand(sorted(pos_map), profs, stacks, seat_of['BTN'], BB // 2, BB, hero=None,
                  seed=seed, book=reads.Book(), dyn=dynamics.Tilt(), position_map=pos_map,
                  pre_seats=pre, post_seats=post, sb_seat=seat_of['SB'], bb_seat=seat_of['BB'])
    # 대상 좌석 카드 지정, 나머지는 남은 덱에서 (같은 시드 순서 유지)
    deck = [c for c in [r + s for r in RANKS for s in SUITS] if c not in cards]
    random.Random(seed).shuffle(deck)
    i = 0
    for s in sorted(pos_map):
        if s == ACTOR: h.hole[s] = list(cards)
        else: h.hole[s] = [deck[i], deck[i + 1]]; i += 2
    h.board = deck[i:i + 5]
    h.seat_pid = {s: 10000 + s for s in pos_map}
    for k, v in dict(field_q=0.6, field_remaining=1000, field_itm=150, field_avg_stack=START,
                     field_stacks=(), field_pid_stacks={}, payouts=[], payout_flat=0.0, ante=BB,
                     erosion_per_hand=0.0, reentry=False, progress=0.05, money_jump={}, pid_prof={}).items():
        setattr(h, k, v)
    replay = [(session._cache_key('pre', s, n), a, amt) for n, (s, (a, amt), _) in enumerate(forced)]
    out = {}
    applied = []
    def cb(ev):
        if ev.get('street') != 'preflop': raise Stop()
        if ev.get('seat') == ACTOR and len(applied) >= 0 and 'a' not in out:
            out['a'] = ev['action']; out['amt'] = ev['amount']
            raise Stop()
    run = session.HandRun(h, decisions=replay, on_bot_action=cb)
    try: run.start()
    except Stop: pass
    out['errors'] = len(run.preflop_errors)
    return out

def translate(a, amt):
    if a == 'fold': return 'Fold', None
    if a in ('call', 'check'): return menu_call, None
    if a == 'allin': return menu_allin or 'off_menu_allin', None
    if a == 'raise':
        to = amt / BB
        if to >= START / BB - 1e-6 - 1 / 9 and menu_allin: return menu_allin, None
        if not menu_raises: return 'off_menu_raise', round(to, 2)
        lab, sz = min(menu_raises, key=lambda x: abs(math.log(to / x[1])))
        return lab, round(abs(math.log(to / sz)), 3)
    return 'other:' + a, None

L = rec['class_labels']; CS = node['class_strategy']
res = {'record': rec['id'], 'status': rec.get('status'), 'node': NODE, 'actor': node['actor'],
       'line': node['line'], 'menu': menu, 'profile': PROFILE, 'reps': REPS, 'situation': node['situation'],
       'unsupported_low_reach': node['unsupported_low_reach'], 'aggressor_action_combos': node['aggressor_action_combos'],
       'stack_bb_hand_start': START / BB, 'classes': {}}
for ci, cls in enumerate(L):
    cnt = {}; dists = []; errs = 0
    for j in range(REPS):
        o = one(cls, j)
        if 'a' not in o: cnt['no_decision'] = cnt.get('no_decision', 0) + 1; continue
        lab, d = translate(o['a'], o['amt'])
        cnt[lab] = cnt.get(lab, 0) + 1
        if d is not None: dists.append(d)
        errs += o['errors']
    res['classes'][cls] = {'t2': cnt, 'solver': {k: v[ci] for k, v in CS.items()},
                           'ev': {k: v[ci] for k, v in node.get('class_ev_bb', {}).items()},
                           'combos': rec['class_combos'][ci],
                           'size_dist_max': max(dists) if dists else None, 'engine_errors': errs}
json.dump(res, open(OUT, 'w'), indent=1)
print('done', OUT)
