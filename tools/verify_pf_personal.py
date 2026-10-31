"""프리플랍 개인 층(GTO 표 → 그 사람의 빈도) 보장 검사 (2026-10-31).

  python3 tools/verify_pf_personal.py

1) 최상 숙련(차트·수비·포지션 8 이상) = 표 그대로: 훅이 쓴 빈도가 gto_pf 조회값과 비트까지 같다.
2) 이탈 0 이면 personalize 가 표를 그대로 돌려준다.
3) 모든 프로필(숙련 × 기질 × 도박 × 포지션) × 표본 spot:
   - 표가 0.95 이상 치는 클래스는 접지 않는다(> 0), 그리고 표 × (목표 폭 / 표 폭) 아래로 내려가지 않는다.
   - 넓힐 때 새로 들어온(표 0) 클래스는 감각 순서(_PLAY)의 앞부분이다(마지막 하나만 일부).
   - 좁힐 때 줄어든 순수 클래스는 감각 순서의 끝부분이다(마지막 하나만 일부). 섞인 클래스는 같은 비율.
   - 쓰레기 구간(PF_TRASH)은 표가 0 이면 도박 기질 극단·지식 낮음(trash > 0)일 때만, PF_TRASH_MAX 이하.
   - 행동 몫 합 1, 음수 없음. 루즈할수록 폭이 넓다(같은 숙련).
"""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import gto_pf as G
import preflop as P
import persona as PS

G._load()
fails = []
n = 0


def check(name, cond):
    global n
    n += 1
    if not cond:
        fails.append(name)
        if len(fails) <= 20:
            print('FAIL', name)


def mk(skill, loose, gamble=5.0, positional=None, aggr=None):
    p = PS.make_player(random.Random(5), pid=3)
    for c in p['concepts']:
        p['concepts'][c] = skill
    if positional is not None:
        p['concepts']['positional'] = positional
    p['temper'].update(looseness=loose, aggression=loose if aggr is None else aggr, gamble=gamble)
    return p


SPOTS = []
for pos in ('UTG', 'LJ', 'CO', 'BTN', 'SB'):
    for x in (10.2, 15.0, 22.0, 30.0, 45.0, 100.0):
        SPOTS.append(('first_in', {'pos': pos, 'seats': 9, 'eff': x, 'ante': True}))
for agg, pos, x in (('BTN', 'BB', 12.0), ('SB', 'BB', 10.0), ('CO', 'BTN', 15.0)):
    SPOTS.append(('vs_jam', {'aggressor_pos': agg, 'pos': pos, 'seats': 9, 'eff': x, 'ante': True}))
for o, dfn, x, ob in (('BTN', 'BB', 30.0, 2.0), ('CO', 'BB', 35.0, 2.25), ('UTG', 'BTN', 60.0, 2.0),
                      ('HJ', 'BB', 20.0, 2.0)):
    SPOTS.append(('vs_open', {'aggressor_pos': o, 'pos': dfn, 'seats': 9, 'eff': x, 'ante': True,
                              'open_bb': ob}))
for o, tb, x, tsz in (('CO', 'SB', 30.0, 8.0), ('UTG', 'BTN', 40.0, 6.0), ('CO', 'BTN', 25.0, 6.0)):
    SPOTS.append(('vs_3bet', {'aggressor_pos': tb, 'pos': o, 'seats': 9, 'eff': x, 'ante': True,
                              'open_bb': tsz}))
SPOTS.append(('vs_limp', {'seats': 9, 'eff': 35.0, 'ante': True}))
REP = {c: P._cls_rep(c) for c in P.PCT}

# ---- 1) 최상 숙련 = 표 그대로(비트) ----
for top in (mk(8, 5), mk(10, 0), mk(10, 10, gamble=10), mk(9, 3, aggr=9)):
    check('top profile has no personal deviation', all(P.gto_pf_personal(top, f) is None
                                                       for f in P.GTO_PF_SPOT_TABLES))
    for fn, a in SPOTS:
        for c, h in REP.items():
            r0 = P._raw_class(G, fn, a, h)
            r1 = P.gto_pf_spot_freqs({'fn': fn, 'args': a}, h, top)
            check('top = table exact %s %s %s' % (fn, a, c), r0 == r1)
    # 훅 경로(첫 진입): 시간 기록의 빈도가 조회값과 같다
    for pos in ('UTG', 'BTN'):
        for c in ('AA', 'T9s', 'K5o', '72o'):
            P.take_timing_bound()
            P.gto_pf_first_in_choice(top, pos, 25.0, REP[c], random.Random(1), None, 1.0, 9, True)
            tb = P.take_timing_bound()
            g = G.first_in(pos, 9, P.gto_pf_open_eff_bb(pos, 25.0, None), REP[c])
            check('top hook = table %s %s' % (pos, c), tb['gto'] == {k: round(v, 4) for k, v in g.items()})

# ---- 2) 이탈 0 ----
base = P._raw_table(G, 'first_in', SPOTS[0][1])
check('zero deviation returns table', P.personalize(base, 'first_in', (0.0, 0.0, 0.0, 0.0, 0.0)) == base)

# ---- 3) 프로필 격자 ----
PROFS = []
for skill in (0, 2, 4, 6, 7):
    for loose in (0, 2.5, 5, 7.5, 10):
        for gamble in (5, 10):
            for positional in (None, 0, 10):
                PROFS.append(((skill, loose, gamble, positional), mk(skill, loose, gamble, positional)))
ins_of = {'first_in': ('jam', 'open', 'limp'), 'vs_jam': ('call',), 'vs_open': ('jam', 'r3', 'call'),
          'vs_3bet': ('jam', 'r4', 'call'), 'vs_limp': ('raise',)}
trash_hits = {}
for fn, a in SPOTS:
    raw = P._raw_table(G, fn, a, with_src=True)
    for tag, prof in PROFS:
        pp = P.gto_pf_personal(prof, fn)
        if pp is None:
            continue
        t = P._personal_table(G, fn, a, pp)
        rows = []
        for c in P.PCT:
            if raw[c] is None:
                check('no record stays none %s %s' % (fn, c), t[c] is None)
                continue
            g0, src = raw[c]
            g1 = t[c]
            ins = ('jam', 'r3') if src == 'partial' else ins_of[fn]
            out = 'pass' if src == 'partial' else ('check' if fn == 'vs_limp' else 'fold')
            p0 = sum(g0.get(k, 0.0) for k in ins)
            p1 = sum(g1.get(k, 0.0) for k in ins)
            s = sum(g1.get(k, 0.0) for k in ins) + g1.get(out, 0.0)
            check('sums to 1 %s %s %s' % (fn, tag, c), abs(s - 1.0) < 1e-9 and min(
                g1.get(k, 0.0) for k in ins + (out,)) >= -1e-12)
            rows.append((c, p0, p1, src))
        full = [r for r in rows if r[3] != 'partial' or all(x[3] == 'partial' for x in rows)]
        W0 = sum(P._NCOMBO[c] * p0 for c, p0, p1, _s in full)
        W1 = sum(P._NCOMBO[c] * p1 for c, p0, p1, _s in full)
        ratio = W1 / W0 if W0 > 0 else 1.0
        for c, p0, p1, _s in full:
            if p0 >= P.PF_PURE:
                check('pure never folded %s %s %s' % (fn, tag, c), p1 > 0.0)
                check('pure >= table x width ratio %s %s %s (%.4f < %.4f x %.4f)' % (fn, tag, c, p1, p0, ratio),
                      p1 >= p0 * min(1.0, ratio) - 1e-9)
            if c in P.PF_TRASH and p0 == 0.0:
                check('trash only for extreme gambler %s %s %s' % (fn, tag, c),
                      p1 == 0.0 if pp[4] <= 0 else p1 <= pp[4] + 1e-12)
                if p1 > 0:
                    trash_hits[tag] = max(trash_hits.get(tag, 0.0), p1)
        order = {c: i for i, c in enumerate(P._PLAY)}
        if W1 > W0 + 1e-9:
            newc = sorted((order[c], p1) for c, p0, p1, _s in full if p0 == 0.0 and c not in P.PF_TRASH)
            seen_partial = seen_zero = False
            okp = True
            for _i, p1 in newc:
                if p1 == 0.0:
                    seen_zero = True
                elif seen_zero or seen_partial:
                    okp = False
                elif p1 < 1.0 - 1e-9:
                    seen_partial = True
            check('loosen: new classes enter in playability order %s %s' % (fn, tag), okp)
            # 섞인 클래스는 같은 비율로 1 쪽으로
            ss = {round((p1 - p0) / (1.0 - p0), 6) for c, p0, p1, _s in full
                  if 0.0 < p0 < P.PF_PURE and c not in P.PF_TRASH}
            check('loosen: mixed scaled by one factor %s %s %s' % (fn, tag, ss), len(ss) <= 1)
        elif W1 < W0 - 1e-9:
            ss = {round(p1 / p0, 6) for c, p0, p1, _s in full if 0.0 < p0 < P.PF_PURE}
            check('tighten: mixed scaled by one factor %s %s' % (fn, tag), len(ss) <= 1)
            cut = sorted((order[c], p1 < p0 - 1e-12) for c, p0, p1, _s in full if p0 >= P.PF_PURE)
            flags = [f for _i, f in cut]
            first = flags.index(True) if True in flags else len(flags)
            # 잘린 순수 클래스는 감각 순서의 끝부분(연속)
            check('tighten: pure cut from the bottom of playability %s %s' % (fn, tag),
                  all(flags[first:]))

# 루즈할수록 넓다(같은 숙련·포지션)
for fn, a in SPOTS[:30]:
    for skill in (0, 4):
        ws = []
        for loose in (0, 5, 10):
            t = P._personal_table(G, fn, a, P.gto_pf_personal(mk(skill, loose), fn))
            ws.append(sum(P._NCOMBO[c] * (1.0 - g['fold']) for c, g in t.items() if g))
        check('looser is wider %s %s %s' % (fn, a, skill), ws[0] <= ws[1] + 1e-9 <= ws[2] + 2e-9)

print('trash reach (profile (skill, loose, gamble, positional) -> max freq):',
      {k: round(v, 4) for k, v in sorted(trash_hits.items(), key=str)})
if fails:
    print('pf personal: %d FAIL of %d' % (len(fails), n))
    sys.exit(1)
print('pf personal ok: %d checks' % n)
