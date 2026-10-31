"""GTO quick 기록 연결 검사 (2026-10-24, 3벳 받은 오프너 / SB 림프 받은 BB / BB 플랫콜 새 자리).

  python3 tools/t2_handoff/verify_gto_connect.py <기록폴더> [반복수=40] [결과.json]

기록폴더는 tools/t2_handoff/fetch_records.sh 로 만든다. 생산 코드는 바꾸지 않는다(측정 전용).
검사 다섯 묶음 — 하나라도 실패하면 종료 코드 1:

  A. 값 일치   : 조회 함수(gto_pf.defend_vs_open / defend_vs_3bet / defend_vs_limp)가 버킷 스택에서
                 기록의 클래스별 빈도를 그대로 내는가(≤ 0.002). 기록에 없는 클래스는 None 이어야 한다.
  B. 실제 경로 : 기록의 상황(앞 행동을 엔진 REPLAY 로 강제)을 session.HandRun → plan.preflop_plan 으로
                 재현해, 대상 좌석의 첫 행동을 클래스마다 [반복수]번 뽑는다. (1) 그 판단이 GTO 연결 경로를
                 탔는지(preflop._timing_bound 의 kind), (2) 실제 행동 빈도(도착 콤보 가중) vs 기록의 차이,
                 (3) 엔진 오류 0. 섞인 빈도는 표본 수만큼 흔들린다 — 허용치는 표본 오차 기준(아래 TOL).
  C. 경로 선택 : 버킷 사이(35bb, 두 기록 보간), 범위 밖(25/45bb), 크기 밖(3벳 12bb, 오픈 3bb), 멀티웨이,
                 ICM 압력(BF 1.2), 다른 림퍼·SB 아닌 림퍼 → GTO 경로를 타지 않거나(None) 탄다(보간)를 확인.
  D. 실패 내성 : 새 표가 없는 데이터 / 모듈 없음에서도 None(기존 판단)이고 예외가 없다.
  F. 10bb 미만 : pf4·pf6·pf8(2026-10-31) 첫 진입·단독 올인 콜 값 일치 + 엔진 경로(BTN·SB 첫 진입, SB 올인 받은 BB) + 경로 선택.
  E. 요약      : 기록별 표 — 결과 JSON 에 클래스별 숫자를 남긴다(값을 맞추지 않는다, 차이는 그대로 보고).
"""
import copy, glob, json, math, os, random, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools'))
os.environ['T2_BOT_LOG'] = '0'; os.environ['T2_TELEMETRY'] = '0'; os.environ.pop('T2_TIMING_V1', None)
import gto_pf as G
import preflop as PF
import play, session, dynamics, reads
from r2_freeze_defend_baseline import maxskill

REC = sys.argv[1]
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 40
OUTP = sys.argv[3] if len(sys.argv) > 3 else None
POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
NAME = lambda s: {'utg1': 'UTG+1', 'utg2': 'UTG+2'}.get(s, s.upper())
RANKS, SUITS = '23456789TJQKA', 'cdhs'
FAIL = []
REPORT = {'reps_per_class': REPS, 'records': {}, 'routing': [], 'robustness': []}


def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + (('  ' + detail) if detail else ''))
    if not cond:
        FAIL.append(name)


def hand_of(c):
    return [c[0] + 'h', c[1] + 'd'] if len(c) == 2 else [c[0] + 'h', c[1] + ('h' if c[2] == 's' else 'd')]


def combos(cls):
    a, b = cls[0], cls[1]
    if len(cls) == 2:
        return [[a + s1, a + s2] for i, s1 in enumerate(SUITS) for s2 in SUITS[i + 1:]]
    if cls[2] == 's':
        return [[a + s, b + s] for s in SUITS]
    return [[a + s1, b + s2] for s1 in SUITS for s2 in SUITS if s1 != s2]


def kind_of(rec_id):
    if '_limp_' in rec_id:
        return 'limp'
    if 'v1_' in rec_id:
        return '3bet'
    return 'flat'


def spot_of(rec):
    """기록 → (종류, 오프너, 수비자/3벳터, 스택, 뿌리 노드, 조회 함수, 조회 결과 열 → 기록 행동 접두사)."""
    rid = rec['id']
    k = kind_of(rid)
    n = rec['nodes'][0]
    if k == 'limp':
        S = int(re.match(r'p(\d+)_', rid).group(1))
        cols = {'check': ('Check',), 'raise': ('Raise',)}
        return k, 'SB', 'BB', S, n, (lambda h, eff=S: G.defend_vs_limp(9, eff, h)), cols
    if k == '3bet':
        m = re.match(r'p(\d+)v1_([a-z0-9]+)_vs_([a-z0-9]+)', rid)
        S, op, tb = int(m.group(1)), NAME(m.group(2)), NAME(m.group(3))
        tb_bb = float(n['actions'][1].split()[1])
        cols = {'fold': ('Fold',), 'call': ('Call',), 'r4': ('4-bet',), 'jam': ('All-in',)}
        return k, op, tb, S, n, (lambda h, eff=S: G.defend_vs_3bet(op, tb, 9, eff, h, tb_bb)), cols
    m = re.match(r'p(\d+)_flat_([a-z0-9]+)_vs_([a-z0-9]+)', rid)
    S, op, df = int(m.group(1)), NAME(m.group(2)), NAME(m.group(3))
    ob = float(n['actions'][1].split()[1])
    cols = {'fold': ('Fold',), 'call': ('Call',), 'r3': ('3-bet',), 'jam': ('All-in',)}
    return k, op, df, S, n, (lambda h, eff=S: G.defend_vs_open(op, df, 9, eff, h, ob)), cols


def rec_freq(hd, cols):
    return {c: sum(v for a, v in hd['freq'].items() if a.startswith(p)) for c, ps in cols.items() for p in ps}


# ---------------------------------------------------------------- A. 값 일치
records = []
for path in sorted(glob.glob(os.path.join(REC, 'p[136]0*_vs_*.json')) + glob.glob(os.path.join(REC, 'p40*_vs_*.json'))):   # 2026-10-30: p100 도
    rec = json.load(open(path))
    if rec.get('schema') != 'spot_quick_v1' or rec['id'].endswith('_dcfr_stop'):
        continue
    if kind_of(rec['id']) == 'flat' and rec['id'] in ('p30_flat_btn_vs_bb', 'p30_flat_co_vs_bb', 'p30_flat_sb_vs_bb',
                                                       'p40_flat_btn_vs_bb', 'p40_flat_co_vs_bb', 'p40_flat_sb_vs_bb',
                                                       'p40_flat_hj_vs_bb'):
        new = False                                      # 2026-10-21 까지 연결된 자리(회귀 확인용으로 함께 본다)
    else:
        new = True
    records.append((rec, new))
print('records:', len(records), '(new %d)' % sum(1 for _, n in records if n))
for rec, new in records:
    k, a, b, S, n, look, cols = spot_of(rec)
    worst, missing_ok, missing_bad = 0.0, 0, 0
    labels = G._load()['classes']
    for c in labels:
        g = look(hand_of(c))
        if c not in n['hands']:
            if k == '3bet':
                missing_ok += g is None
                missing_bad += g is not None
            continue
        if g is None:
            worst = 9.0
            continue
        ref = rec_freq(n['hands'][c], cols)
        worst = max(worst, max(abs(g[kk] - ref[kk]) for kk in cols))
    check('A value %-24s max|hook-record| = %.4f' % (rec['id'], worst), worst <= 0.002)
    if k == '3bet':
        check('A value %-24s classes not in the record -> None (%d)' % (rec['id'], missing_ok), missing_bad == 0)
    REPORT['records'][rec['id']] = {'kind': k, 'new': new, 'value_max_abs_diff': round(worst, 4),
                                    'status_note': rec.get('status_note'), 'method': rec.get('method'),
                                    'stopped_at_step_cap': rec.get('stopped_at_step_cap'),
                                    'unstable_combos': n.get('unstable_combos'), 'reach_combos': n.get('reach_combos')}

# ---------------------------------------------------------------- B. 실제 경로
seat_of = {p: i + 1 for i, p in enumerate(POS)}
pos_map = {i + 1: p for i, p in enumerate(POS)}
pre = [seat_of[p] for p in POS]
post = [seat_of['SB'], seat_of['BB']] + [seat_of[p] for p in POS[:7]]
BB = 900
REFP = maxskill()
KINDS = []
_orig_tb = PF._timing_bound


def _spy(d):
    KINDS.append(d.get('kind'))
    return _orig_tb(d)


PF._timing_bound = _spy


class Stop(BaseException):
    pass


def line_of(k, a, b, n):
    """뿌리 노드에 이르는 앞 행동(엔진 REPLAY 용)과 대상 좌석.

    flat : 오프너 앞 전원 폴드 → 오프너 오픈(기록 크기) → 사이 전원 폴드 → BB 차례
    3bet : 오프너 앞 폴드 → 오픈 2.0(SB 3.0) → 사이 폴드 → 3벳터 3벳(기록 크기) → 나머지 폴드 → 오프너 차례
    limp : UTG..BTN 폴드 → SB 림프(콜 1bb) → BB 차례
    """
    out = []
    if k == 'limp':
        out += [(seat_of[p], ('fold', 0)) for p in POS[:7]]
        out.append((seat_of['SB'], ('call', 0)))
        return out, seat_of['BB']
    open_bb = float(n['actions'][1].split()[1]) if k == 'flat' else (3.0 if a == 'SB' else 2.0)
    ia = POS.index(a)
    out += [(seat_of[p], ('fold', 0)) for p in POS[:ia]]
    out.append((seat_of[a], ('raise', int(round(open_bb * BB)))))
    if k == 'flat':
        out += [(seat_of[p], ('fold', 0)) for p in POS[ia + 1:POS.index(b)]]
        return out, seat_of[b]
    ib = POS.index(b)
    out += [(seat_of[p], ('fold', 0)) for p in POS[ia + 1:ib]]
    out.append((seat_of[b], ('raise', int(round(float(n['actions'][1].split()[1]) * BB)))))
    out += [(seat_of[p], ('fold', 0)) for p in POS[ib + 1:]]
    return out, seat_of[a]


def play_one(cards, start_bb, forced, actor, seed, extra_caller=None):
    profs = {str(s): copy.deepcopy(REFP) for s in pos_map}
    stacks = {s: int(round(start_bb * BB)) for s in pos_map}
    h = play.Hand(sorted(pos_map), profs, stacks, seat_of['BTN'], BB // 2, BB, hero=None,
                  seed=seed, book=reads.Book(), dyn=dynamics.Tilt(), position_map=pos_map,
                  pre_seats=pre, post_seats=post, sb_seat=seat_of['SB'], bb_seat=seat_of['BB'])
    deck = [c for c in [r + s for r in RANKS for s in SUITS] if c not in cards]
    random.Random(seed).shuffle(deck)
    i = 0
    for s in sorted(pos_map):
        if s == actor:
            h.hole[s] = list(cards)
        else:
            h.hole[s] = [deck[i], deck[i + 1]]; i += 2
    h.board = deck[i:i + 5]
    h.seat_pid = {s: 10000 + s for s in pos_map}
    for kk, v in dict(field_q=0.6, field_remaining=1000, field_itm=150, field_avg_stack=int(start_bb * BB),
                      field_stacks=(), field_pid_stacks={}, payouts=[], payout_flat=0.0, ante=BB,
                      erosion_per_hand=0.0, reentry=False, progress=0.05, money_jump={}, pid_prof={}).items():
        setattr(h, kk, v)
    replay = [(session._cache_key('pre', s, j), a, amt) for j, (s, (a, amt)) in enumerate(forced)]
    out = {}
    mark = len(KINDS)

    def cb(ev):
        if ev.get('street') != 'preflop':
            raise Stop()
        if ev.get('seat') == actor and 'a' not in out:
            out['a'], out['amt'] = ev['action'], ev['amount']
            raise Stop()
    run = session.HandRun(h, decisions=replay, on_bot_action=cb)
    try:
        run.start()
    except Stop:
        pass
    out['errors'] = len(run.preflop_errors)
    out['kinds'] = KINDS[mark:]
    return out


def KIND_OF(label):
    for pre, k in (('Fold', 'fold'), ('Check', 'call'), ('Call', 'call'), ('Limp', 'call'), ('All-in', 'jam'),
                   ('Raise', 'raise'), ('3-bet', 'raise'), ('4-bet', 'raise'), ('5-bet', 'raise')):
        if label.startswith(pre):
            return k
    return label


GTO_KIND = {'flat': 'gto_pf_defend_full', '3bet': 'gto_pf_vs_3bet_full', 'limp': 'gto_pf_vs_limp'}


def translate(k, n, a, amt, start_bb):
    acts = n['actions']
    if a == 'fold':
        return 'Fold'
    if a in ('call', 'check'):
        return next(x for x in acts if x.startswith('Call') or x == 'Check')
    allin = next((x for x in acts if x.startswith('All-in')), None)
    if a == 'allin':
        return allin or 'off_menu_allin'
    if a == 'raise':
        to = amt / BB
        if allin and to >= start_bb - 1 / 9 - 1e-6:
            return allin
        rs = [(x, float(x.split()[1])) for x in acts if re.match(r'(Raise|\d-bet)', x)]
        if not rs:
            return 'off_menu_raise'
        return min(rs, key=lambda t: abs(math.log(to / t[1])))[0]
    return 'other:' + a


for rec, new in records:
    if not new:
        continue
    k, a, b, S, n, look, cols = spot_of(rec)
    forced, actor = line_of(k, a, b, n)
    stats = {'classes': {}, 'gto_path_share': None, 'engine_errors': 0}
    tot_w = tot_gto = 0.0
    real = {x: 0.0 for x in n['actions']}
    want = {x: 0.0 for x in n['actions']}
    worst = 0.0
    for ci, (c, hd) in enumerate(sorted(n['hands'].items())):
        w = float(hd['combos'])
        if w < 0.05:
            continue
        cnt, gto_n, errs = {}, 0, 0
        cl = combos(c)
        for j in range(REPS):
            o = play_one(cl[j % len(cl)], S, forced, actor, 700001 + 7919 * j + 104729 * ci)
            errs += o['errors']
            if 'a' not in o:
                cnt['no_decision'] = cnt.get('no_decision', 0) + 1
                continue
            gto_n += GTO_KIND[k] in o['kinds']
            lab = translate(k, n, o['a'], o['amt'], S)
            cnt[lab] = cnt.get(lab, 0) + 1
        got = {x: cnt.get(x, 0) / REPS for x in n['actions']}
        for x in n['actions']:
            real[x] += w * got[x]
            want[x] += w * hd['freq'].get(x, 0.0)
        # 비교는 행동 종류 단위(폴드/콜·체크/레이즈 종류/올인). 연결은 종류별 빈도만 기록대로 하고, 같은
        # 종류 안의 크기(예: 플랫콜 기록의 3벳 7bb/8bb)는 봇의 기존 크기 습관이 정한다(2026-10-20 설계,
        # gto_pf_build 의 r3 합산). 크기 배분 차이는 결과 JSON 의 size_split 에 따로 남긴다.
        gk = {}; rk = {}
        for x in n['actions']:
            kk = KIND_OF(x)
            gk[kk] = gk.get(kk, 0.0) + got[x]
            rk[kk] = rk.get(kk, 0.0) + hd['freq'].get(x, 0.0)
        d = max(abs(gk[kk] - rk[kk]) for kk in gk)
        # 클래스 하나의 허용치: 이항 표준오차 4배(섞인 빈도) + 0.02
        p = max(rk.values())
        tol = 4 * math.sqrt(max(p * (1 - p), 1e-9) / REPS) + 0.02
        worst = max(worst, d - tol)
        stats['classes'][c] = {'t2': cnt, 'record': hd['freq'], 'combos': w, 'gto_path': gto_n / REPS,
                               'abs_diff_max': round(d, 3), 'tol': round(tol, 3)}
        tot_w += w; tot_gto += w * gto_n / REPS
        stats['engine_errors'] += errs
    stats['gto_path_share'] = round(tot_gto / max(tot_w, 1e-9), 4)
    stats['mix_t2'] = {x: round(real[x] / tot_w, 4) for x in real}
    stats['mix_record'] = {x: round(want[x] / tot_w, 4) for x in want}
    kt, kr = {}, {}
    for x in real:
        kt[KIND_OF(x)] = kt.get(KIND_OF(x), 0.0) + stats['mix_t2'][x]
        kr[KIND_OF(x)] = kr.get(KIND_OF(x), 0.0) + stats['mix_record'][x]
    stats['mix_kind_t2'] = {kk: round(v, 4) for kk, v in kt.items()}
    stats['mix_kind_record'] = {kk: round(v, 4) for kk, v in kr.items()}
    stats['size_split'] = {x: (stats['mix_t2'][x], stats['mix_record'][x]) for x in real
                           if sum(1 for y in real if KIND_OF(y) == KIND_OF(x)) > 1}
    stats['mix_abs_diff_max'] = round(max(abs(kt[kk] - kr[kk]) for kk in kt), 4)
    REPORT['records'][rec['id']]['engine'] = stats
    check('B path %-24s GTO path used for %.1f%% of reaching combos' % (rec['id'], 100 * stats['gto_path_share']),
          stats['gto_path_share'] >= 0.999)
    check('B mix  %-24s T2 %s vs record %s (max diff %.3f)' % (
        rec['id'], stats['mix_kind_t2'], stats['mix_kind_record'], stats['mix_abs_diff_max']),
        stats['mix_abs_diff_max'] <= 0.03)
    check('B class%-24s every class within its sampling tolerance (worst excess %.3f)' % (rec['id'], worst),
          worst <= 0.0)
    check('B eng  %-24s engine errors = %d' % (rec['id'], stats['engine_errors']), stats['engine_errors'] == 0)

# ---------------------------------------------------------------- F. 10bb 미만 푸시/폴드 (pf4·pf6·pf8, 2026-10-31)
# 값 일치: 기록의 모든 첫 진입·단독 올인 노드에서 조회 == 기록(≤ 0.002, 표는 소수 3자리).
# 실제 경로: 버킷마다 첫 진입 BTN·SB 와 SB 올인 받은 BB 를 엔진으로 재현(B 와 같은 방식, 같은 허용치).
PF_SPOTS = (('first_in', 'BTN', None), ('first_in', 'SB', None), ('vs_jam', 'BB', 'SB'))
for S in (4, 6, 8):
    p = os.path.join(REC, 'pf%d.json' % S)
    if not os.path.exists(p):
        check('F pf%d record present' % S, False)
        continue
    prec = json.load(open(p))
    labels = prec['class_labels']
    worst = 0.0
    nn = 0
    for nd in prec['nodes']:
        acts = [x.split(':', 1) for x in nd['line'] if not x.endswith(':Fold')]
        cs = nd['class_strategy']
        if nd['situation'] == 'first_in':
            jam = next(a for a in nd['actions'] if a.startswith('All-in'))
            for i, c in enumerate(labels):
                g = G.first_in(nd['actor'], 9, S, hand_of(c))
                worst = max(worst, 9.0 if g is None else abs(g['jam'] - cs[jam][i]))
            nn += 1
        elif (nd['situation'] == 'facing_open_or_jam' and len(acts) == 1 and acts[0][1].startswith('All-in')
              and not nd['unsupported_low_reach'] and (nd['aggressor_action_combos'] or 0) >= 10):
            call = next(a for a in nd['actions'] if a.startswith('Call'))
            for i, c in enumerate(labels):
                g = G.call_vs_jam(acts[0][0], nd['actor'], 9, S, hand_of(c))
                worst = max(worst, 9.0 if g is None else abs(g - cs[call][i]))
            nn += 1
    check('F value pf%d %d nodes max|hook-record| = %.4f' % (S, nn, worst), worst <= 0.002)
    REPORT['records']['pf%d' % S] = {'kind': 'pushfold', 'new': True, 'value_max_abs_diff': round(worst, 4),
                                     'nodes_checked': nn, 'gap_total_exact_bb': prec['gap_total_exact_bb']}
    for sit, actor_pos, jammer in PF_SPOTS:
        if sit == 'first_in':
            nd = next(x for x in prec['nodes'] if x['situation'] == 'first_in' and x['actor'] == actor_pos)
            forced = [(seat_of[q], ('fold', 0)) for q in POS[:POS.index(actor_pos)]]
            want_kind = 'gto_pf_open'
        else:
            nd = next(x for x in prec['nodes'] if x['actor'] == actor_pos and x['situation'] == 'facing_open_or_jam'
                      and [y.split(':', 1)[0] for y in x['line'] if not y.endswith(':Fold')] == [jammer])
            ij = POS.index(jammer)
            forced = ([(seat_of[q], ('fold', 0)) for q in POS[:ij]] + [(seat_of[jammer], ('allin', 0))]
                      + [(seat_of[q], ('fold', 0)) for q in POS[ij + 1:POS.index(actor_pos)]])
            want_kind = 'gto_pf_vs_jam'
        aggr = next(a for a in nd['actions'] if a != 'Fold')        # 'All-in x' 또는 'Call x'
        cs = nd['class_strategy']
        tot_w = tot_gto = real = want = 0.0
        worst_x, errs = 0.0, 0
        cls_out = {}
        for ci, c in enumerate(labels):
            w = float(nd['class_arriving_combos'][ci])
            if w < 0.05:
                continue
            cl = combos(c)
            k_aggr = k_gto = 0
            for j in range(REPS):
                o = play_one(cl[j % len(cl)], S, forced, seat_of[actor_pos], 900001 + 7919 * j + 104729 * ci)
                errs += o['errors']
                k_gto += want_kind in o['kinds']
                k_aggr += o.get('a') in ('allin', 'call', 'raise')
            got = k_aggr / REPS
            ref = cs[aggr][ci]
            tol = 4 * math.sqrt(max(ref * (1 - ref), 1e-9) / REPS) + 0.02
            worst_x = max(worst_x, abs(got - ref) - tol)
            tot_w += w; tot_gto += w * k_gto / REPS; real += w * got; want += w * ref
            cls_out[c] = {'t2': round(got, 3), 'record': ref, 'combos': w}
        name = 'pf%d %s%s' % (S, (jammer + ' jam -> ') if jammer else 'first-in ', actor_pos)
        share = tot_gto / max(tot_w, 1e-9)
        REPORT['records']['pf%d' % S].setdefault('engine', {})[name] = {
            'gto_path_share': round(share, 4), 'mix_t2': round(real / tot_w, 4), 'mix_record': round(want / tot_w, 4),
            'engine_errors': errs, 'classes': cls_out}
        check('F path  %-24s GTO path used for %.1f%% of combos' % (name, 100 * share), share >= 0.999)
        check('F mix   %-24s T2 %.4f vs record %.4f' % (name, real / tot_w, want / tot_w), abs(real - want) / tot_w <= 0.03)
        check('F class %-24s every class within tolerance (worst excess %.3f)' % (name, worst_x), worst_x <= 0.0)
        check('F eng   %-24s engine errors = %d' % (name, errs), errs == 0)
f_cases = [
    ('first-in 3.5bb (below the 4bb bucket) -> None (old rule)', G.first_in('BTN', 9, 3.5, ['Ah', 'Kc']) is None),
    ('first-in 7bb / 9bb -> interpolated (6-8, 8-10)', G.first_in('BTN', 9, 7, ['Ah', 'Kc']) is not None
     and G.first_in('BTN', 9, 9, ['Ah', 'Kc']) is not None),
    ('vs_jam 5bb SB jam -> BB call value', G.call_vs_jam('SB', 'BB', 9, 5, ['9h', '4c']) is not None),
    ('below 10bb: open / 3-bet / flat tables still None',
     G.aggr_vs_open('BTN', 'BB', 9, 8, ['Ah', 'Kc']) is None and G.defend_vs_open('BTN', 'BB', 9, 8, ['Ah', 'Kc'], 2.0) is None
     and G.call_vs_3bet_jam('BTN', 'BB', 9, 8, ['Ah', 'Kc']) is None),
    ('first-in hook 3bb -> None, 6bb -> GTO jam/fold',
     PF.gto_pf_first_in_choice(prof if 'prof' in dir() else maxskill(), 'CO', 3.0, ['Ah', 'Kc'], random.Random(1)) is None
     and PF.gto_pf_first_in_choice(maxskill(), 'CO', 6.0 - 1 / 9.0, ['Ah', 'Kc'], random.Random(1)) in ('jam', 'fold')),
]
for name, okc in f_cases:
    check('F ' + name, bool(okc))
    REPORT['routing'].append({'case': 'F ' + name, 'pass': bool(okc)})

# ---------------------------------------------------------------- C. 경로 선택
r = random.Random(5)
prof = maxskill()
AK, Q = ['Ah', 'Kc'], ['Qh', 'Qc']
cases = [
    ('3bet 35bb between 30/40 -> interpolated (not None)', G.defend_vs_3bet('CO', 'SB', 9, 35, AK, 8.0) is not None),
    ('3bet 25bb / 45bb -> None', G.defend_vs_3bet('CO', 'SB', 9, 25, AK, 8.0) is None
     and G.defend_vs_3bet('CO', 'SB', 9, 45, AK, 8.0) is None),
    ('3bet size 12bb vs 8bb record -> None; 7.5bb -> used',
     G.defend_vs_3bet('CO', 'SB', 9, 35, AK, 12.0) is None and G.defend_vs_3bet('CO', 'SB', 9, 35, AK, 7.5) is not None),
    # 2026-10-28: 40bb vs BTN 짝이 다 들어왔다(UTG+1 vs BTN 30·40bb). 60bb 는 BTN vs SB(오픈 2.5, 3벳 10bb) 하나뿐.
    ('3bet UTG+1 vs BTN 35bb (30/40 both) -> interpolated', G.defend_vs_3bet('UTG+1', 'BTN', 9, 35, AK, 6.0) is not None),
    ('3bet pair with only one bucket (CO vs SB 50bb, no 60bb) -> None', G.defend_vs_3bet('CO', 'SB', 9, 50, AK, 8.0) is None),
    ('3bet BTN vs SB 35bb 8bb still used (60bb 10bb record not size-checked)',
     G.defend_vs_3bet('BTN', 'SB', 9, 35, AK, 8.0) is not None),
    ('3bet BTN vs SB 50bb: 8bb -> None (60bb record is 10bb), 10bb -> interpolated',
     G.defend_vs_3bet('BTN', 'SB', 9, 50, AK, 8.0) is None and G.defend_vs_3bet('BTN', 'SB', 9, 50, AK, 10.0) is not None),
    # 2026-10-30: 100bb BTN vs SB(3벳 10bb) 기록이 들어와 60~100bb 는 보간. 두 버킷이 없는 짝(CO vs SB 70bb)은 여전히 None
    ('3bet BTN vs SB 60/70/100bb 10bb -> used (60·100 interpolated); CO vs SB 70bb (no 60/100 record) -> None',
     G.defend_vs_3bet('BTN', 'SB', 9, 60, AK, 10.0) is not None and G.defend_vs_3bet('BTN', 'SB', 9, 70, AK, 10.0) is not None
     and G.defend_vs_3bet('BTN', 'SB', 9, 100, AK, 10.0) is not None and G.defend_vs_3bet('CO', 'SB', 9, 70, AK, 10.0) is None),
    ('3bet hook: caller in pot -> None (old path)',
     PF.gto_pf_aggr_choice(prof, 'SB', 'CO', AK, r, 34.0, 8.0, 6.0, 2, other_live_actors=1, actor_acted=True,
                           aggressor_total_bb=35.0) is None),
    ('3bet hook: ICM pressure BF 1.2 -> None',
     PF.gto_pf_aggr_choice(prof, 'SB', 'CO', AK, r, 34.0, 8.0, 6.0, 2, other_live_actors=0, actor_acted=True,
                           bf=1.2, aggressor_total_bb=35.0) is None),
    ('3bet hook: AKo CO vs SB 8bb 3-bet at 35bb -> GTO answer',
     PF.gto_pf_aggr_choice(prof, 'SB', 'CO', AK, r, 34.0, 8.0, 6.0, 2, other_live_actors=0, actor_acted=True,
                           aggressor_total_bb=35.0) in ('jam', '4bet', 'call', 'fold')),
    ('3bet hook: hand not in the record (72o) -> 4-bet-jam-only path (old connection)',
     PF.gto_pf_aggr_choice(prof, 'SB', 'CO', ['7h', '2c'], r, 34.0, 8.0, 6.0, 2, other_live_actors=0, actor_acted=True,
                           aggressor_total_bb=35.0) in ('jam', 'pass', None)),
    ('limp 35bb -> interpolated; 25/45bb -> None', G.defend_vs_limp(9, 35, Q) is not None
     and G.defend_vs_limp(9, 25, Q) is None and G.defend_vs_limp(9, 45, Q) is None),
    ('limp hook: SB limp, BB to act -> check/raise',
     (PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 35.0, 1, other_live_actors=1, can_check=True) or ('x',))[0]
     in ('check', 'raise')),
    ('limp hook: limper not SB / two limpers / extra money / cannot check / not BB / ICM -> None',
     all(x is None for x in (
         PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'BTN', 35.0, 1, other_live_actors=1, can_check=True),
         PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 35.0, 2, other_live_actors=2, can_check=True),
         PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 35.0, 1, other_live_actors=2, can_check=True),
         PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 35.0, 1, other_live_actors=1, can_check=False),
         PF.gto_pf_limp_choice(prof, 'SB', Q, r, 34.0, 'SB', 35.0, 1, other_live_actors=1, can_check=True),
         PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 35.0, 1, other_live_actors=1, can_check=True, bf=1.2)))),
    ('limp hook: effective stack = smaller of the two (SB 20bb -> out of 30-40 range -> None)',
     PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 20.0, 1, other_live_actors=1, can_check=True) is None),
    ('flat new seat UTG vs BB 35bb (30 and 40 records) -> used; 3bb open -> None',
     G.defend_vs_open('UTG', 'BB', 9, 35, Q, 2.0) is not None and G.defend_vs_open('UTG', 'BB', 9, 35, Q, 3.0) is None),
    ('flat UTG+2 between 30 and 40 -> None while only the 30bb record exists',
     G.defend_vs_open('UTG+2', 'BB', 9, 35, Q, 2.0) is None
     or 'UTG+2>BB' in (G._load().get('vs_open_full') or {}).get('40', {})),
    ('6-handed table maps to 9-max seats (6-max UTG = 9-max LJ)', G.pos9('UTG', 6) == 'LJ'),
]
for name, ok in cases:
    check('C ' + name, bool(ok))
    REPORT['routing'].append({'case': name, 'pass': bool(ok)})

# ---------------------------------------------------------------- D. 실패 내성
saved = G._DATA
try:
    G._DATA = {kk: v for kk, v in saved.items() if kk not in ('vs_3bet_full', 'vs_limp_full')}
    ok = (G.defend_vs_3bet('CO', 'SB', 9, 35, AK, 8.0) is None and G.defend_vs_limp(9, 35, Q) is None
          and PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 35.0, 1, other_live_actors=1, can_check=True) is None)
    check('D data without the new tables -> None, no exception', ok)
except Exception as exc:                      # noqa: BLE001
    check('D data without the new tables -> None, no exception', False, repr(exc))
finally:
    G._DATA = saved
saved_mod = list(PF._GPF_MOD)
try:
    PF._GPF_MOD[:] = [True, None]
    ok = (PF.gto_pf_limp_choice(prof, 'BB', Q, r, 34.0, 'SB', 35.0, 1, other_live_actors=1, can_check=True) is None
          and PF.gto_pf_aggr_choice(prof, 'SB', 'CO', AK, r, 34.0, 8.0, 6.0, 2, other_live_actors=0,
                                    actor_acted=True, aggressor_total_bb=35.0) is None)
    check('D module missing -> None, no exception', ok)
except Exception as exc:                      # noqa: BLE001
    check('D module missing -> None, no exception', False, repr(exc))
finally:
    PF._GPF_MOD[:] = saved_mod
REPORT['robustness'] = [f for f in FAIL if f.startswith('D ')]

REPORT['failed'] = FAIL
if OUTP:
    json.dump(REPORT, open(OUTP, 'w'), indent=1)
print('%d failed' % len(FAIL) if FAIL else 'all connection checks passed')
sys.exit(1 if FAIL else 0)
