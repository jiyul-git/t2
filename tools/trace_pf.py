"""프리플랍 한 핸드를 UTG 부터 좌석 단위로 따라간다.

어느 함수를 지나 어떤 값이 나왔는지만 찍는다. 판단은 안 한다.
  python3 tools/trace_pf.py [seed] [n_hands]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import preflop as PF, plan as PL, tourney as T

TRACE = []

_open_d, _iso_d, _def_d = PF.open_decision, PF.iso_decision, PF.defend_decision
_th, _rf, _rs = PF.defend_thresholds, PF.raise_form, PF.reshove_range
_ss = PF.should_shove

CUR = {}


def open_decision(prof, pos, bb, hand, rng, **kw):
    r = _open_d(prof, pos, bb, hand, rng, **kw)
    CUR['route'] = 'open_decision'
    CUR['thr'] = round(PF._open(prof, pos, bb=bb), 4)
    return r


def iso_decision(prof, pos, hand, n_limpers, bb, rng):
    CUR['route'] = 'iso_decision'
    return _iso_d(prof, pos, hand, n_limpers, bb, rng)


def defend_decision(prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, rng, **kw):
    CUR['route'] = 'defend_decision'
    CUR['lvl'] = kw.get('raise_level', 1)
    return _def_d(prof, def_pos, opener_pos, hand, bb, open_bb, n_callers, rng, **kw)


def defend_thresholds(*a, **k):
    tp, tot = _th(*a, **k)
    CUR['tp'], CUR['tot'] = round(tp, 4), round(tot, 4)
    return tp, tot


def should_shove(band, hand_pct, traits, pos, bb):
    r = _ss(band, hand_pct, traits, pos, bb)
    CUR['should_shove'] = r
    return r


def reshove_range(*a, **k):
    r = _rs(*a, **k)
    CUR['reshove_rs'] = round(r, 4)
    return r


def raise_form(prof, stack_bb, target_bb, pot_bb, rng, **kw):
    r = _rf(prof, stack_bb, target_bb, pot_bb, rng, **kw)
    rem = stack_bb - target_bb
    pot_after = max(1.0, pot_bb + 2.0*target_bb - kw.get('facing_bb', 0.0))
    CUR['raise_form'] = '목표%.1fbb 남은%.1fbb SPR%.2f → %s' % (
        target_bb, rem, rem/pot_after, r[0])
    return r


PF.open_decision, PF.iso_decision, PF.defend_decision = \
    open_decision, iso_decision, defend_decision
PF.defend_thresholds, PF.raise_form, PF.reshove_range = \
    defend_thresholds, raise_form, reshove_range
PF.should_shove = should_shove

_pp = PL.preflop_plan


def preflop_plan(profile, pos, hand, bb, rng, **kw):
    CUR.clear()
    r = _pp(profile, pos, hand, bb, rng, **kw)
    TRACE.append((pos, PF.cls(hand), round(PF.pct(hand), 4), bb,
                  kw.get('aggressor_pos'), kw.get('open_bb'),
                  kw.get('raise_level'), r[0], r[1], dict(CUR),
                  bool(kw.get('opp_est'))))
    return r


PL.preflop_plan = preflop_plan

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 4100
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1

t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                 seed=seed, hands_per_level=int(os.environ.get('HPL','40')))
shown = 0
while shown < n:
    if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
        break
    TRACE.clear()
    st = t.next_hand()
    g = 0
    while st and not st.get('done') and g < 200:
        st = t.submit('fold')
        g += 1
    _want = os.environ.get('WANT','')
    _ok = (len(TRACE) >= 3)
    if _want == 'form':
        _ok = any('raise_form' in c for (*_x, c, _e) in TRACE)
    if _want == 'shove':
        _ok = any('raise_form' in c and c['raise_form'].endswith('shove')
                  for (*_x, c, _e) in TRACE)
    if _ok:
        shown += 1
        print('=' * 74)
        print('핸드 %d   BB=%d   히어로 좌석 %s' % (shown, t.blinds()[1], t.hero))
        print('=' * 74)
        for (pos, hc, r, bb, agg, obb, lvl, a, sz, cur, has_est) in TRACE:
            print('\n[%-5s] %-4s 상위 %5.1f%%   스택 %.1fbb' % (pos, hc, r*100, bb))
            if agg is None:
                print('   상황: 무저항 (레이즈 없음)')
            else:
                print('   상황: %s 가 %.1fbb 로 침 / 레이즈단계 %d / 상대정보 %s'
                      % (agg, obb or 0, lvl or 1, '있음' if has_est else '없음'))
            print('   경로: %s' % cur.get('route', '?'))
            for k in ('thr', 'tp', 'tot', 'should_shove', 'reshove_rs', 'raise_form'):
                if k in cur:
                    print('     %-12s %s' % (k, cur[k]))
            print('   → %s %s' % (a, ('%.2fbb' % sz) if sz else ''))
    t.finish_hand()
