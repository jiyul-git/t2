"""상대 레인지 모델 ↔ GTO 프리플랍 기준 동기화 검사 (2026-10-30).

  python3 tools/verify_range_sync.py

봇은 기준 범위 안에서 gto_pf 빈도로 행동한다(preflop.gto_pf_*_choice). 그 행동을 본 상대의
레인지(session._preflop_story_range → ranges.gto_pf_story_range)는 같은 빈도여야 한다.

1) 연결 목록: gto_pf_data.json 의 모든 빈도 표와 gto_pf 의 모든 조회 함수가
   preflop.GTO_PF_SPOT_TABLES / gto_pf_spot_freqs 에 들어 있어야 한다. 새 표를 연결하면서
   레인지 모델 동기화를 빠뜨리면 여기서 실패한다.
2) 기준 안 격자: 기록의 모든 (표, 버킷, 자리 짝) + 버킷 사이 중점 + 오픈 2.0~2.5 사이에서
   169 클래스마다 훅을 실제로 불러 훅이 쓴 빈도(시간 기록의 gto 값)를 받고, 같은 spot 으로
   만든 레인지의 클래스 질량이 그 빈도와 같아야 한다(허용 0.005). partial 콜은
   'pass' 빈도 × 관찰자 모델의 기존 계속 확률, 기록 없는 클래스는 기존 경로 질량.
3) 기준 밖(스택·노안테·5인·ICM·콜러 낀 팟): 훅이 None, spot 이 남지 않고, 레인지는 옛 경로와 같다.
4) 배선: preflop_plan 이 seed 에 pf_gto_spot 을 남기고, _merge_pf_seed 가 줄(pf_line)에 옮기고,
   앞 행동도 기준이면 곱한다(오픈 × 3벳 받고 콜).
"""
import inspect, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.environ.setdefault('T2_DATA_DIR', os.path.join('/tmp', 't2_range_sync'))
import gto_pf as G
import preflop as P
import ranges as R
import session as SE
import persona as PS
import plan as PL

TOL = 0.005
SHARE = 1.0 / 9.0
SEATS = 9
d = G._load()
REP = {}
for c in R._SORTED:
    REP.setdefault(P.cls(list(c)), list(c))
PROF = PS.make_player(random.Random(7), pid=1)
fails = []
n_spots = n_cmp = 0


def fail(msg):
    fails.append(msg)
    if len(fails) <= 20:
        print('FAIL', msg)


class _Roll(random.Random):
    def random(self):
        return 0.999


# ---------------- 1) 연결 목록 ----------------
META = {'schema', 'source', 'buckets', 'classes', 'assumptions'}
tables = {k for k, v in d.items() if k not in META and isinstance(v, dict)}
synced = {t for ts in P.GTO_PF_SPOT_TABLES.values() for t in ts}
for t in sorted(tables - synced):
    fail('table %s is in gto_pf_data.json but not synced into the range model '
         '(preflop.GTO_PF_SPOT_TABLES / gto_pf_spot_freqs / ranges.GTO_ACT_KEY)' % t)
LOOKUPS = {'first_in', 'call_vs_jam', 'call_vs_3bet_jam', 'aggr_vs_open', 'defend_vs_open',
           'jam_vs_3bet', 'defend_vs_3bet', 'defend_vs_limp'}
NON_LOOKUP = {'hand_class', 'pos9', 'covered'}
pub = {n for n, f in vars(G).items() if inspect.isfunction(f) and not n.startswith('_')
       and f.__module__ == G.__name__}
for n in sorted(pub - LOOKUPS - NON_LOOKUP):
    fail('gto_pf.%s is a new public lookup; route it through preflop.gto_pf_spot_freqs '
         'and add it to this check' % n)
src = inspect.getsource(P.gto_pf_spot_freqs)
for n in sorted(LOOKUPS):
    if n not in src:
        fail('gto_pf.%s not used by preflop.gto_pf_spot_freqs' % n)
for fn in P.GTO_PF_SPOT_TABLES:
    if fn not in R.GTO_ACT_KEY:
        fail('spot %s has no action mapping in ranges.GTO_ACT_KEY' % fn)
print('tables', sorted(tables), 'synced' if tables <= synced else 'NOT SYNCED')


# ---------------- 2) 기준 안 격자 ----------------
def stack_points(table, key):
    bk = sorted(int(b) for b, e in d[table].items() if key in e)
    pts = [float(b) for b in bk]
    pts += [(a + b) / 2.0 for a, b in zip(bk, bk[1:])]          # 보간
    return pts


def hook_call(fn, a, hand):
    """훅을 실제로 부르고 (훅이 쓴 빈도, spot, 상태)."""
    P.take_timing_bound(); P.take_gto_spot()
    rng = _Roll(1)
    E = a['eff'] - SHARE
    if fn == 'first_in':
        # a['rf'] 가 있으면 머니점프 진입 폭 배수를 합성한 첫 진입(2026-10-31)
        mo = {'range_factor': a['rf']} if a.get('rf') else None
        out = P.gto_pf_first_in_choice(PROF, a['pos'], E - P._POSTED_BB.get(a['pos'], 0.0),
                                       hand, rng, None, 1.0, SEATS, True, money_open=mo)
    elif fn in ('vs_jam', 'vs_3bjam'):
        out = P.gto_pf_call_choice(PROF, a['aggressor_pos'], a['pos'], hand, rng, E, E, E,
                                   1 if fn == 'vs_jam' else 2, other_live_actors=0, bf=1.0,
                                   seats=SEATS, ante=True, actor_acted=(fn == 'vs_3bjam'))
    elif fn in ('vs_open', 'vs_3bet'):
        o = a['open_bb']
        out = P.gto_pf_aggr_choice(PROF, a['aggressor_pos'], a['pos'], hand, rng, E, o, o,
                                   1 if fn == 'vs_open' else 2, other_live_actors=0,
                                   actor_acted=(fn == 'vs_3bet'), bf=1.0, seats=SEATS, ante=True)
    elif fn == 'vs_limp':
        out = P.gto_pf_limp_choice(PROF, 'BB', hand, rng, E - 1.0, 'SB', E, 1,
                                   other_live_actors=1, can_check=True, bf=1.0, seats=SEATS, ante=True)
    tb = P.take_timing_bound()
    spot = P.take_gto_spot()
    if out is None:
        return None, spot, None
    if 'gto' in tb:
        g = dict(tb['gto'])
        if fn == 'vs_jam' or fn == 'vs_3bjam':
            pass
        return g, spot, 'full'
    if 'gto_call' in tb:
        return {'call': tb['gto_call']}, spot, 'full'
    return {'jam': tb['gto_jam'], 'r3': tb['gto_r3'],
            'pass': 1.0 - tb['gto_jam'] - tb['gto_r3']}, spot, 'partial'


ACTS = {'first_in': [('shove', 'jam'), ('raise', 'open'), ('limp', 'limp')],
        'vs_jam': [('call', 'call')], 'vs_3bjam': [('call', 'call')],
        'vs_open': [('shove', 'jam'), ('3bet', 'r3'), ('call', 'call')],
        'vs_3bet': [('shove', 'jam'), ('3bet', 'r4'), ('call', 'call')],
        'vs_limp': [('check', 'check'), ('raise', 'raise')]}
OLD_ACT = {'shove': 'open', 'raise': 'open', 'limp': 'limp', 'call': 'call', '3bet': '3bet',
           'check': 'check'}


def range_cls(pfo, pos, stack, act):
    rr, meta = SE._preflop_story_range(PROF, pos, stack, set(), SEATS, True, OLD_ACT[act], pfo=pfo)
    w = {}
    for c, m in R.weighted_range(rr).items():
        k = P.cls(list(c))
        w[k] = max(w.get(k, 0.0), m)
    return w, meta


def check_spot(fn, a, pos, aggressor_pos, open_bb, level):
    global n_spots, n_cmp
    hook = {}
    spot0 = None
    for k, hand in REP.items():
        g, spot, mode = hook_call(fn, a, hand)
        if g is not None:
            hook[k] = (g, mode)
            if spot0 is None:
                spot0 = spot
            elif spot != spot0:
                fail('%s %s: spot differs between hands' % (fn, a))
    if spot0 is None:
        return False
    n_spots += 1
    stack = a['eff'] - SHARE
    for act, key in ACTS[fn]:
        pfo = {'pf_gto_spot': spot0, 'pf_act': act, 'pf_vs': aggressor_pos,
               'pf_open_bb': open_bb, 'pf_level': level, 'pf_n_callers': 0}
        w, meta = range_cls(pfo, pos, stack, act)
        if not w and not any((g.get(key, g.get('r3') if key == 'r4' else 0.0) or 0) > 0
                             for g, _m in hook.values()):
            continue
        if (meta or {}).get('source') != 'gto_pf_spot_range':
            fail('%s %s %s: range not built from gto (%s)' % (fn, a, act, (meta or {}).get('source')))
            continue
        old = None
        for k in REP:
            got = w.get(k, 0.0)
            if k not in hook:                            # 그 패는 기존 경로로 행동
                if old is None:
                    old, _ = range_cls(dict(pfo, pf_gto_spot=None), pos, stack, act)
                want = old.get(k, 0.0)
            else:
                g, mode = hook[k]
                if mode == 'partial' and act == 'call':
                    lk = P.defend_action_likelihoods(PROF, pos, aggressor_pos, REP[k], stack,
                                                     open_bb, 0, raise_level=level, stack_bb=stack,
                                                     seats=SEATS, ante=True)
                    want = g['pass'] * min(1.0, lk['call'] + lk['attack'])
                elif mode == 'partial':
                    want = g['r3'] if key in ('r3', 'r4') else g.get(key, 0.0)
                else:
                    want = g.get(key, 0.0)
            n_cmp += 1
            if abs(got - want) > TOL:
                fail('%s %s %s %s: range %.4f != hook %.4f' % (fn, a, act, k, got, want))
    return True


def pairs(table):
    return sorted({key for e in d[table].values() for key in e})


covered = 0
for key in pairs('first_in'):
    for x in stack_points('first_in', key):
        a = {'pos': key, 'seats': SEATS, 'eff': x, 'ante': True}
        covered += check_spot('first_in', a, key, None, 0.0, 1)
        # 머니점프 합성 빈도(좁힘·넓힘)도 훅과 레인지가 같아야 한다.
        for rf in (0.85, 1.2):
            covered += check_spot('first_in', dict(a, rf=rf), key, None, 0.0, 1)
for table, fn in (('vs_jam', 'vs_jam'), ('vs_3bjam', 'vs_3bjam')):
    for key in pairs(table):
        o, dfn = key.split('>')
        pos, agg = (dfn, o) if fn == 'vs_jam' else (o, dfn)
        for x in stack_points(table, key):
            a = {'aggressor_pos': agg, 'pos': pos, 'seats': SEATS, 'eff': x, 'ante': True}
            covered += check_spot(fn, a, pos, agg, x, 1 if fn == 'vs_jam' else 2)
for key in sorted(set(pairs('vs_open')) | set(pairs('vs_open_full')) | set(pairs('vs_open_full_o25'))):
    o, dfn = key.split('>')
    pts = set()
    for t in ('vs_open', 'vs_open_full', 'vs_open_full_o25'):
        if key in pairs(t):
            pts |= set(stack_points(t, key))
    sizes = sorted({e[key].get('open_bb', 2.0) for t in ('vs_open_full', 'vs_open_full_o25')
                    for e in d[t].values() if key in e} or {2.0})
    if len(sizes) == 2:
        sizes.insert(1, sum(sizes) / 2.0)                # 두 오픈 크기 사이 보간
    for x in sorted(pts):
        for ob in sizes:
            a = {'aggressor_pos': o, 'pos': dfn, 'seats': SEATS, 'eff': x, 'ante': True, 'open_bb': ob}
            covered += check_spot('vs_open', a, dfn, o, ob, 1)
for key in sorted(set(pairs('vs_3bet')) | set(pairs('vs_3bet_full'))):
    o, tb = key.split('>')
    pts = set()
    for t in ('vs_3bet', 'vs_3bet_full'):
        if key in pairs(t):
            pts |= set(stack_points(t, key))
    sizes = sorted({e[key]['threebet_bb'] for e in d['vs_3bet_full'].values() if key in e} or {8.0})
    for x in sorted(pts):
        for tsz in sizes:
            a = {'aggressor_pos': tb, 'pos': o, 'seats': SEATS, 'eff': x, 'ante': True, 'open_bb': tsz}
            covered += check_spot('vs_3bet', a, o, tb, tsz, 2)
for x in stack_points('vs_limp_full', 'SB>BB'):
    a = {'seats': SEATS, 'eff': x, 'ante': True}
    covered += check_spot('vs_limp', a, 'BB', 'SB', 1.0, 1)
print('covered spots %d, class comparisons %d' % (n_spots, n_cmp))
if n_spots < 50:
    fail('too few covered spots exercised: %d' % n_spots)


# ---------------- 3) 기준 밖 ----------------
hand = ['Ah', 'Kd']
P.take_gto_spot()
outside = [
    ('8bb first-in', lambda r: P.gto_pf_first_in_choice(PROF, 'CO', 8.0, hand, r, None, 1.0, 9, True)),
    ('no ante', lambda r: P.gto_pf_first_in_choice(PROF, 'CO', 30.0, hand, r, None, 1.0, 9, False)),
    ('5-handed', lambda r: P.gto_pf_first_in_choice(PROF, 'CO', 30.0, hand, r, None, 1.0, 5, True)),
    ('ICM bf 1.3', lambda r: P.gto_pf_first_in_choice(PROF, 'CO', 30.0, hand, r, None, 1.3, 9, True)),
    ('degenerate money range_factor', lambda r: P.gto_pf_first_in_choice(
        PROF, 'CO', 30.0, hand, r, None, 1.0, 9, True, money_open={'range_factor': 50.0})),
    ('caller in pot', lambda r: P.gto_pf_aggr_choice(PROF, 'CO', 'BB', hand, r, 30.0, 2.0, 1.0, 1,
                                                     other_live_actors=1, actor_acted=False)),
    ('vs_3bet 100bb jam table empty', lambda r: P.gto_pf_aggr_choice(
        PROF, 'BTN', 'UTG', hand, r, 100.0, 7.0, 5.0, 2, other_live_actors=0, actor_acted=True)),
]
for name, f in outside:
    out = f(_Roll(1))
    sp = P.take_gto_spot()
    if out is not None or sp is not None:
        fail('outside coverage %s: hook=%r spot=%r' % (name, out, sp))
for act, opener in (('open', None), ('call', 'CO'), ('3bet', 'CO'), ('limp', None)):
    pfo = {'pf_gto_spot': None, 'pf_act': act, 'pf_vs': opener, 'pf_open_bb': 2.5,
           'pf_level': 1, 'pf_n_callers': 0}
    rr, meta = SE._preflop_story_range(PROF, 'BB' if opener else 'CO', 30.0, {'Ah'}, 9, True, act, pfo=pfo)
    old = R.preflop_range(PROF, 'BB' if opener else 'CO', act, 30.0, {'Ah'}, n_callers=0,
                          opener_pos=opener, open_bb=2.5, seats=9, ante=True, raise_level=1)
    if R.weighted_range(rr) != R.weighted_range(old) or meta.get('source') != 'standard_preflop_range':
        fail('uncovered %s: story range differs from old path' % act)


# ---------------- 4) 배선 ----------------
a, sz, seed = PL.preflop_plan(PROF, 'CO', ['As', 'Ad'], 29.9, random.Random(3), seats=9, ante=True)
want = {'fn': 'first_in', 'args': {'pos': 'CO', 'seats': 9, 'eff': 29.9 + SHARE, 'ante': True}}
if seed.get('pf_gto_spot') != want:
    fail('preflop_plan seed pf_gto_spot %r != %r' % (seed.get('pf_gto_spot'), want))
a2, _sz, seed2 = PL.preflop_plan(PROF, 'CO', ['As', 'Ad'], 5.0, random.Random(3), seats=9, ante=True)
if seed2.get('pf_gto_spot') is not None:
    fail('preflop_plan uncovered seed has pf_gto_spot')
# 오픈 → 3벳 받고 콜: 줄에 두 spot, 질량 = 오픈 빈도 × 콜 빈도
op = dict(seed, pf_act='raise')
s1 = SE._merge_pf_seed(None, op)
vs = {'fn': 'vs_3bet', 'args': {'aggressor_pos': 'BTN', 'pos': 'CO', 'seats': 9, 'eff': 30.0,
                                'open_bb': 6.0, 'ante': True}}
s2 = SE._merge_pf_seed(s1, {'pf_role': 'defend', 'pf_act': 'call', 'pf_vs': 'BTN', 'pf_level': 2,
                            'pf_open_bb': 6.0, 'pf_n_callers': 0, 'pf_gto_spot': vs})
if [x.get('gto_spot') for x in s2['pf_line']] != [want, vs]:
    fail('_merge_pf_seed does not carry gto_spot into pf_line')
w, meta = range_cls(s2, 'CO', 30.0, 'call')
for k in ('AKs', 'QJs', 'T9s', '72o'):
    f1 = P.gto_pf_spot_freqs(want, REP[k])[0]['open']
    r2 = P.gto_pf_spot_freqs(vs, REP[k])
    f2 = r2[0]['call'] if r2 and r2[1] == 'full' else None
    if f2 is None:
        continue
    if abs(w.get(k, 0.0) - f1 * f2) > TOL:
        fail('chain open x call %s: %.4f != %.4f' % (k, w.get(k, 0.0), f1 * f2))
    n_cmp += 1

if fails:
    print('range sync: %d FAIL (covered spots %d)' % (len(fails), n_spots))
    sys.exit(1)
print('range sync ok: covered spots %d, class comparisons %d' % (n_spots, n_cmp))
