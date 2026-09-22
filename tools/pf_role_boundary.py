#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-6: 관찰자가 읽는 상대 프리플랍 역할이 공개 로그로 재구성되는가.

  python3 tools/pf_role_boundary.py --selftest
  python3 tools/pf_role_boundary.py --smoke
  python3 tools/pf_role_boundary.py --fixture A

두 명제를 **분리해서** 본다.

  (1) pf_role 의 공식은 공개 입력만 쓴다        — 코드 독해로 참
  (2) 구현의 pf_role 값이 공개 로그의 함수다     — 이게 검증 대상

(1) 이 참이어도 (2) 는 거짓일 수 있다. runtime 의 aggressor/limpers 가
**실제 적용된 액션**이 아니라 **요청된 액션**으로 갱신되는 자리가 둘 있다.

  session.py:469-472  REPLAY 캐시. apply 가 ValueError 면 call/check 로
                      떨어지는데, aggressor 갱신은 _cached[1](요청)을 본다
  session.py:437-448  히어로 재시도. 첫 요청이 불법이면 두 번째 act 를
                      적용하는데, aggressor/limpers 갱신은 첫 변수 a 를 본다

소비 지점 (session.py:701-707) 이 실제로 쓰는 값은 3값이 아니라 2값이다.

    {'open': 'open', 'iso': 'open', 'defend': 'call'}
    pos == 'BB' and 'open' -> 'call'
    기록 없음              -> 'open' if o == aggressor else 'call'   (다른 규칙)

그 폴백의 `aggressor` 는 **그 순간의** 공격자다. 포스트플랍에서 갱신되므로
프리플랍 공격자가 아닐 수 있다 — session.py:670-675 주석이 스스로
"포스트플랍 공격자에게 프리플랍 오픈 레인지를 매기면 안 된다" 고 적어둔 바로
그 경로가 폴백에는 남아 있다.

**세대 주의.** 이 도구의 소비 지점 matrix 는 E-3 **이전**의 소비 로직
(`pf_seed` 를 읽고 없으면 `'open' if o == aggressor else 'call'`)을 재현한다.
E-3 이후 production 은 공개 로그로 직접 재구성하므로, 수정 후 트리에서 이
matrix 가 내는 mismatch 는 "그때 그 로직이었다면" 의 수치다. 현재
production 이 실제로 무엇을 소비하는지는 tools/f6_q4b_fallback.py --verify
가 본다. 기록 수준 비교(pf_seed vs public)는 두 세대 모두에서 뜻이 같다.

읽기 전용. production 을 수정하지 않는다.
"""
from __future__ import print_function

import argparse
import ast
import collections
import inspect
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import session as SE
import play as PLAY
import tourney as TOURNEY

RAISE_ACTS = ('raise', 'allin')
ROLE_MAP = {'open': 'open', 'iso': 'open', 'defend': 'call'}

# PUBLIC 재구성기가 절대 건드리면 안 되는 이름. 이름 기반 차단이라
# 완전하지는 않지만, 실수로 pf_seed 를 참조하는 것은 확실히 잡는다.
FORBIDDEN = ('pf_seed', 'pf_role', 'pf_act', 'hole', 'axes', 'profile',
             'seed_info', 'h')


# ---------------------------------------------------------------- PUBLIC arm
def reconstruct_public(preflop_entries, pos_by_seat):
    """공개 프리플랍 로그만으로 소비값(_act_o)을 재구성한다.

    인자는 둘뿐이다.
      preflop_entries  실제 적용된 (seat, action, amount) 시간순 목록
      pos_by_seat      seat -> 포지션 문자열

    홀카드·프로필·pf_seed 는 인자로 받지 않는다. 받을 수도 없다.

    규칙
      raised_before 를 False 로 시작해 시간순으로 훑는다.
      각 좌석의 **마지막 실제 액션** 직전의 raised_before 를 그 좌석의 값으로
      쓴다. False -> 'open', True -> 'call'.
      그 뒤 pos == 'BB' 이고 'open' 이면 'call' 로 내린다.
      실제 액션이 한 번도 없으면 결과에 넣지 않는다 (PUBLIC_MISSING).

    open/iso 구분은 소비 지점에서 둘 다 'open' 으로 합쳐지므로 여기서
    나누지 않는다. 3분류는 진단용으로 따로 센다.
    """
    raised_before = False
    last = {}
    counts = collections.Counter()
    for seat, action, _amt in preflop_entries:
        last[seat] = raised_before
        counts[seat] += 1
        if action in RAISE_ACTS:
            raised_before = True
    out = {}
    for seat, was_raised in last.items():
        role = 'call' if was_raised else 'open'
        if pos_by_seat.get(seat) == 'BB' and role == 'open':
            role = 'call'
        out[seat] = role
    return out, dict(counts)


def public_running_aggressor(full_log, upto_street):
    """그 스트리트 시작 시점의 공격자. 공개 로그만 본다."""
    order = ['preflop', 'flop', 'turn', 'river']
    stop = order.index(upto_street)
    aggr = None
    for row in full_log:
        stt = row[0]
        if stt not in order or order.index(stt) >= stop:
            continue
        _, seat, action = row[0], row[1], row[2]
        if action in RAISE_ACTS:
            aggr = seat
    return aggr


def guard_report(fn):
    """PUBLIC 재구성기가 금지된 이름을 건드리는지 정적 검사."""
    src = inspect.getsource(fn)
    tree = ast.parse(src)
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id in FORBIDDEN:
            hits.append(n.id)
        if isinstance(n, ast.Attribute) and n.attr in FORBIDDEN:
            hits.append(n.attr)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                and n.value in ('pf_seed', 'pf_role'):
            hits.append(n.value)
    return sorted(set(hits))


# ---------------------------------------------------------------- INTERNAL arm
def internal_act(pf_seed, seat, pos_by_seat, aggressor_now):
    """session.py:701-707 을 그대로 재현한다."""
    entry = (pf_seed or {}).get(seat) or {}
    act = ROLE_MAP.get(entry.get('pf_role'))
    if pos_by_seat.get(seat) == 'BB' and act == 'open':
        act = 'call'
    if act is None:
        return 'fallback', ('open' if seat == aggressor_now else 'call'), None
    return 'pf_seed', act, entry.get('pf_role')


# ---------------------------------------------------------------- capture
class Capture(object):
    def __init__(self):
        self.pairs = []
        self._orig = None

    def __enter__(self):
        self._orig = SE.HandRun
        outer = self

        class Wrapped(self._orig):
            def __init__(self, hand, decisions=None):
                super(Wrapped, self).__init__(hand, decisions)
                outer.pairs.append((hand, self))
        SE.HandRun = Wrapped
        return self

    def __exit__(self, *e):
        SE.HandRun = self._orig
        return False


def run_fixture(seeds, fmts, hands, entries, hb=None):
    old = getattr(FS.Field, 'BOT_LOG', None)
    errors = []
    with Capture() as cap:
        try:
            FS.Field.BOT_LOG = 0
            for fmt in fmts:
                for seed in seeds:
                    f = FS.Field(entries=entries, seed=seed, fmt=fmt)
                    for _ in range(hands):
                        if f.remaining() <= 8:
                            break
                        f.hand_no += 1
                        f.advance_level()
                        for tb in list(f.tables.values()):
                            if tb.n() >= 2:
                                f._play_table(tb)
                            if hb:
                                hb(len(cap.pairs), 'capture %s/%s h%d'
                                   % (fmt, seed, f.hand_no))
                        f._collect_busts()
                        f._balance()
                    errors.extend(getattr(f, 'errors', ()) or ())
        finally:
            if old is not None:
                FS.Field.BOT_LOG = old
    return cap.pairs, errors


# ---------------------------------------------------------------- analysis
def run_hero_fixture(seed, hands, entries, hb=None):
    """Fixture B — 히어로가 플랍에 남는 deterministic passive 스크립트.

    tocall == 0 이면 check, > 0 이면 call. 엔진이 불법이라고 하면 그 시점의
    실제 legal state(state['tocall'])를 다시 읽어 맞춘다.

    **히어로 홀카드를 보지 않는다.** 승률이 목적이 아니라 히어로가 포스트플랍에
    남아 상대 관찰자에게 보이는 상황을 만드는 것이 목적이다.
    """
    errors = []
    with Capture() as cap:
        t = TOURNEY.Tournament(entries=entries, start_stack=30000, hero_seat=7,
                               seed=seed, hands_per_level=200)
        for i in range(hands):
            if sum(1 for x in t.seats if t.stacks[x] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 400:
                tc = st.get('tocall', 0) or 0
                st = t.submit('check' if tc <= 0 else 'call')
                guard += 1
            if guard >= 400:
                errors.append('hand %d: guard 소진' % i)
            t.finish_hand()
            if hb:
                hb(len(cap.pairs), 'hero fixture hand %d' % i)
            if getattr(t, 'busted_hero', False):
                break
    return cap.pairs, errors


def run_edge_fixture(seed, entries, hb=None):
    """Fixture C — REPLAY 캐시의 요청/적용 불일치 경로 **존재성** 검사.

    효과 크기 측정이 아니다. session.py:469-472 가
      apply(_cached[1]) 가 ValueError 로 떨어져 call/check 가 적용됐는데도
      aggressor 갱신은 _cached[1](요청) 를 본다
    는 경로가 실제로 runtime state 와 공개 로그를 갈라놓는지만 본다.

    production 을 고치지 않는다. 같은 핸드를 두 번 돌리되 두 번째에만
    조작한 REPLAY 항목을 넣는다.
    """
    import random as _r
    rng = _r.Random(seed)
    seats = list(range(1, 7))
    import persona as PS
    profs = {str(i): PS.make_player(_r.Random(seed * 100 + i), 0.78, 0)
             for i in seats}
    stacks = {i: 30000 for i in seats}

    def fresh(decisions=None):
        h = PLAY.Hand(seats, dict(profs), dict(stacks), 1, 100, 200,
                      hero=None, seed=seed)
        h.seat_pid = {i: 'p%d' % i for i in seats}
        run = SE.HandRun(h, decisions=decisions)
        run.start()
        return h, run

    # 1) 조작 없이 한 번 — 첫 프리플랍 행동 좌석을 찾는다
    h0, r0 = fresh()
    pre0 = [(x[1], x[2], x[3]) for x in (getattr(r0, 'full_log', []) or [])
            if x[0] == 'preflop']
    if not pre0:
        return [], ['Fixture C: 프리플랍 로그가 비었다'], None
    first_seat = pre0[0][0]
    # 2) 그 좌석의 결정을 '최소 레이즈 미달' 인 raise 로 바꾼다.
    #    key 는 session._cache_key('pre', seat, len(rnd.log)) 이고 첫 결정이므로 0.
    key = SE._cache_key('pre', first_seat, 0)
    doctored = [(key, 'raise', 1)]        # 1칩 raise -> 최소 레이즈 미달
    h1, r1 = fresh(decisions=doctored)
    pre1 = [(x[1], x[2], x[3]) for x in (getattr(r1, 'full_log', []) or [])
            if x[0] == 'preflop']
    info = {
        'first_seat': first_seat,
        'baseline_first_action': pre0[0][1],
        'doctored_first_action_applied': pre1[0][1] if pre1 else None,
        'doctored_requested': 'raise',
        'public_raise_in_log': any(a in RAISE_ACTS for (_s, a, _m) in pre1),
        'pf_seed_seats_baseline': sorted((getattr(h0, 'pf_seed', {}) or {})),
        'pf_seed_seats_doctored': sorted((getattr(h1, 'pf_seed', {}) or {})),
        'roles_baseline': {k: v.get('pf_role')
                           for k, v in (getattr(h0, 'pf_seed', {}) or {}).items()},
        'roles_doctored': {k: v.get('pf_role')
                           for k, v in (getattr(h1, 'pf_seed', {}) or {}).items()},
    }
    return [(h1, r1)], [], info


def analyze(pairs):
    matrix = collections.Counter()
    # 기록 수준 비교 — 포스트플랍 생존 여부와 무관하게 pf_seed 를 가진 모든
    # 좌석을 본다. 소비 지점 matrix 만 보면 기록이 어긋났는데 그 좌석이
    # 플랍 전에 죽은 경우를 놓친다 (Fixture C 가 정확히 그 모양이다).
    record = collections.Counter()
    record_rows = []
    reasons = collections.Counter()
    rows = []
    diag_roles = collections.Counter()
    n_hands = n_postflop = 0

    for h, run in pairs:
        n_hands += 1
        full = list(getattr(run, 'full_log', []) or [])
        pre = [(r[1], r[2], r[3]) for r in full if r[0] == 'preflop']
        streets = [s for s in ('flop', 'turn', 'river')
                   if any(r[0] == s for r in full)]
        if not streets:
            continue
        n_postflop += 1
        pos = dict(getattr(h, 'pos', {}) or {})
        pf_seed = getattr(h, 'pf_seed', {}) or {}
        pub, act_counts = reconstruct_public(pre, pos)
        folded = {r[1] for r in full if r[0] == 'preflop' and r[2] == 'fold'}
        hero = getattr(h, 'hero', None)

        for seat, entry in pf_seed.items():
            iact = ROLE_MAP.get(entry.get('pf_role'))
            if pos.get(seat) == 'BB' and iact == 'open':
                iact = 'call'
            pact = pub.get(seat, 'missing')
            record[(iact, pact)] += 1
            if iact != pact and len(record_rows) < 20:
                record_rows.append({'seat': seat, 'pos': pos.get(seat),
                                    'raw_role': entry.get('pf_role'),
                                    'internal': iact, 'public': pact,
                                    'n_acts': act_counts.get(seat, 0),
                                    'raise_in_public_log': any(
                                        a in RAISE_ACTS for (_s, a, _m) in pre)})

        for street in streets:
            aggr_now = public_running_aggressor(full, street)
            live = [s for s in pos if s not in folded and s in act_counts]
            for o in live:
                src, iact, iraw = internal_act(pf_seed, o, pos, aggr_now)
                pact = pub.get(o, 'missing')
                matrix[(src, iact, pact)] += 1
                if iraw:
                    diag_roles[iraw] += 1
                if iact != pact:
                    why = classify(h, run, o, src, pre, act_counts, pos,
                                   aggr_now, hero)
                    reasons[why] += 1
                    if len(rows) < 40:
                        rows.append({'street': street, 'seat': o,
                                     'pos': pos.get(o), 'src': src,
                                     'internal': iact, 'public': pact,
                                     'raw_role': iraw, 'reason': why,
                                     'n_acts': act_counts.get(o, 0),
                                     'is_hero': o == hero,
                                     'is_aggr_now': o == aggr_now})
    return {'matrix': matrix, 'record': record, 'record_rows': record_rows,
            'reasons': reasons, 'rows': rows,
            'diag_roles': diag_roles, 'hands': n_hands,
            'postflop_hands': n_postflop}


def classify(h, run, o, src, pre, act_counts, pos, aggr_now, hero):
    if src == 'fallback':
        if o == hero:
            return 'hero_no_seed'
        if act_counts.get(o, 0) == 0:
            return 'never_acted'
        return 'no_seed_other'
    if act_counts.get(o, 0) > 1:
        return 'multi_action_overwrite'
    if pos.get(o) == 'BB':
        return 'BB_override'
    n_raises = sum(1 for (_s, a, _m) in pre if a in RAISE_ACTS)
    if n_raises >= 2:
        return '3bet_or_higher'
    if any(a == 'allin' for (_s, a, _m) in pre):
        return 'short_allin_no_raise'
    return 'other'


# ---------------------------------------------------------------- selftest
def _leaky_reconstructor(preflop_entries, pos_by_seat, h):
    """음성 대조 전용. 일부러 pf_seed 를 만진다 — guard 가 잡아야 한다."""
    return (h.pf_seed or {}), {}


def selftest():
    bad = []
    g = guard_report(reconstruct_public)
    print('  guard(reconstruct_public)  금지 이름 %s' % (g or '없음'))
    if g:
        bad.append('PUBLIC 재구성기가 금지 이름을 참조한다: %s' % g)
    lg = guard_report(_leaky_reconstructor)
    print('  guard(_leaky_reconstructor) 금지 이름 %s' % (lg or '없음'))
    if not lg:
        bad.append('음성 대조 실패 — 일부러 새게 만든 함수를 guard 가 못 잡는다')

    # 재구성 규칙 단위 시험
    pos = {1: 'UTG', 2: 'CO', 3: 'BTN', 4: 'SB', 5: 'BB'}
    log = [(1, 'call', 100), (2, 'raise', 300), (3, 'call', 300),
           (5, 'call', 300)]
    pub, cnt = reconstruct_public(log, pos)
    exp = {1: 'open', 2: 'open', 3: 'call', 5: 'call'}
    print('  단순 케이스 %s (기대 %s)' % (pub, exp))
    if pub != exp:
        bad.append('단순 케이스 불일치')

    # 같은 좌석이 두 번 행동하면 **마지막** 시점을 쓴다
    log2 = [(1, 'raise', 300), (2, 'raise', 900), (1, 'call', 900)]
    pub2, _ = reconstruct_public(log2, {1: 'UTG', 2: 'CO'})
    print('  다중 액션 %s (기대 {1: \'call\', 2: \'call\'})' % pub2)
    if pub2 != {1: 'call', 2: 'call'}:
        bad.append('다중 액션 규칙 불일치')

    # BB override
    pub3, _ = reconstruct_public([(5, 'check', 0)], {5: 'BB'})
    print('  BB override %s (기대 {5: \'call\'})' % pub3)
    if pub3 != {5: 'call'}:
        bad.append('BB override 불일치')

    # 액션 없음 -> missing
    pub4, _ = reconstruct_public([(1, 'fold', 0)], {1: 'UTG', 9: 'BB'})
    print('  미행동 좌석 제외 %s' % pub4)
    if 9 in pub4:
        bad.append('행동하지 않은 좌석이 결과에 들어갔다')

    for b in bad:
        print('  FAIL ' + b)
    print('  selftest %s' % ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


# ---------------------------------------------------------------- 출력
def report(res):
    print()
    print('핸드 %d (포스트플랍 도달 %d)' % (res['hands'], res['postflop_hands']))
    print('내부 raw role 분포 (진단용, primary 아님): %s' % dict(res['diag_roles']))
    print()
    print('observation matrix   source / internal -> public')
    tot = sum(res['matrix'].values())
    print('  %-10s %-9s %-9s %8s' % ('source', 'internal', 'public', 'n'))
    for (src, ia, pa), n in sorted(res['matrix'].items()):
        mark = '' if ia == pa else '   <= MISMATCH'
        print('  %-10s %-9s %-9s %8d%s' % (src, ia, pa, n, mark))
    print('  %-10s %-9s %-9s %8d' % ('', '', '합계', tot))
    mism = sum(n for (s, ia, pa), n in res['matrix'].items() if ia != pa)
    print()
    print('불일치 %d / %d = %.2f%%' % (mism, tot, 100.0*mism/max(1, tot)))
    if res['reasons']:
        print('원인 분류: %s' % dict(res['reasons']))
    print()
    print('기록 수준 (pf_seed 를 가진 전 좌석, 포스트플랍 생존 무관)')
    rt = sum(res['record'].values())
    for (ia, pa), n in sorted(res['record'].items()):
        mark = '' if ia == pa else '   <= MISMATCH'
        print('  internal %-6s public %-8s %6d%s' % (ia, pa, n, mark))
    rm = sum(n for (ia, pa), n in res['record'].items() if ia != pa)
    print('  기록 불일치 %d / %d = %.2f%%' % (rm, rt, 100.0*rm/max(1, rt)))
    for r in res['record_rows'][:10]:
        print('   %s' % r)
    for r in res['rows'][:15]:
        print('   %s' % r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--fixture', choices=['A', 'B', 'C'], default=None)
    ap.add_argument('--hero-seeds', default='3000')
    ap.add_argument('--hero-hands', type=int, default=12)
    ap.add_argument('--heartbeat', type=float, default=10.0)
    a = ap.parse_args()

    t0 = time.time()
    last = [0.0]

    def hb(n, msg):
        now = time.time()
        if now - last[0] >= a.heartbeat:
            last[0] = now
            sys.stderr.write('[%6.1fs] %d hands  %s\n' % (now - t0, n, msg))
            sys.stderr.flush()

    if a.selftest:
        print('=== selftest ===')
        return selftest()

    if a.smoke:
        seeds, fmts, hands, entries = (5150,), ('standard',), 3, 60
    elif a.fixture == 'A':
        seeds, fmts, hands, entries = (5150, 9001, 4242), ('standard',), 8, 100
    elif a.fixture in ('B', 'C'):
        seeds = fmts = None
    else:
        ap.error('--selftest / --smoke / --fixture A|B 중 하나')

    if a.fixture == 'C':
        print('fixture C (REPLAY 요청/적용 불일치 경로 존재성)')
        pairs, errors, info = run_edge_fixture(a.hero_seed if False else 20260922,
                                               60, hb=hb)
        if info:
            print()
            for k in ('first_seat', 'baseline_first_action',
                      'doctored_requested', 'doctored_first_action_applied',
                      'public_raise_in_log'):
                print('  %-32s %r' % (k, info[k]))
            print('  %-32s %r' % ('roles_baseline', info['roles_baseline']))
            print('  %-32s %r' % ('roles_doctored', info['roles_doctored']))
        res = analyze(pairs)
        report(res)
        print()
        print('engine_errors %d   경과 %.1fs' % (len(errors), time.time() - t0))
        return 1 if errors else 0

    if a.fixture == 'B':
        hs = tuple(int(x) for x in a.hero_seeds.split(','))
        print('fixture B (hero passive) seeds=%s hands=%d entries=100'
              % (','.join(map(str, hs)), a.hero_hands))
        pairs, errors = [], []
        for sd in hs:
            pp, ee = run_hero_fixture(sd, a.hero_hands, 100, hb=hb)
            pairs.extend(pp); errors.extend(ee)
    else:
        print('fixture seeds=%s fmts=%s hands=%d entries=%d'
              % (','.join(map(str, seeds)), ','.join(fmts), hands, entries))
        pairs, errors = run_fixture(seeds, fmts, hands, entries, hb=hb)
    res = analyze(pairs)
    report(res)
    print()
    print('engine_errors %d   경과 %.1fs' % (len(errors), time.time() - t0))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
