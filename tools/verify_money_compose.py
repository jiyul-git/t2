"""첫 진입 GTO × 머니점프 합성 + 자리 기준 BF 검사 (2026-10-31).

  python3 tools/verify_money_compose.py

값은 실제 봇 대회(tools/gto_precision/money_gate_study.py, turbo day 1~3, 바꾸기 전 코드)에서 나온
첫 진입 결정의 중앙값 행이다(초반 아주 작은 압력, 버블, 인더머니).
1) 합성 규칙: 배수 1 이면 기준 그대로, 진입 질량(콤보 가중) = 기준 × 배수, 좁히면 모든 패가 기준 이하,
   넓히면 이상, 행동 몫 유지, 확률 범위.
2) 훅: 예전 관문에 막히던 실제 값으로 훅이 GTO 를 쓰고, spot 에 배수가 실리고, 시간 기록 빈도 = spot 빈도.
   퇴화(배수 숫자 아님·범위 밖) → 기존 경로. 머니점프 값 없이 BF > 1.05 → 기존 경로(예전 그대로).
3) 자리 기준 BF: 뒤에 나를 덮는 사람만 남으면 예전 BF 와 같고, 짧은 사람만 남으면 1 쪽으로 내려간다
   (정확 ICM, 곡선 근사 둘 다). 브레이크는 자리 기준 보존 압력을 쓴다.
"""
import math, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import icm as I
import money_pressure as MP
import persona as PS
import preflop as P

fails = []
n = [0]


def check(cond, msg):
    n[0] += 1
    if not cond:
        fails.append(msg)
        print('FAIL', msg)


COMBOS = {k: (6 if len(k) == 2 else 4 if k[2] == 's' else 12) for k in P.PCT}
G = P._gto_pf_mod()

# 실제 대회 값(중앙값 행)
REAL = {
    'early_medium': dict(pos='CO', bb=57.06, bf=1.0099, pressure=0.000611, max_pressure=0.002,
                         brake=0.004137, drive=0.025302, danger_fraction=0.5,
                         range_factor=1.021078, limp_pull_shadow=0.003557),
    'early_short': dict(pos='UTG', bb=10.62, bf=1.0024, pressure=0.0, max_pressure=0.0,
                        brake=0.000204, drive=0.08283, danger_fraction=1.0,
                        range_factor=1.08261, limp_pull_shadow=0.0),
    'bubble_short': dict(pos='LJ', bb=10.17, bf=3.1299, pressure=0.002368, max_pressure=0.01,
                         brake=0.295115, drive=0.178074, danger_fraction=0.75,
                         range_factor=0.909629, limp_pull_shadow=0.138049),
    'bubble_deep': dict(pos='UTG+1', bb=44.69, bf=3.6557, pressure=0.203296, max_pressure=0.3,
                        brake=0.0, drive=0.21597, danger_fraction=0.0,
                        range_factor=1.21597, limp_pull_shadow=0.033984),
    'itm_short': dict(pos='UTG', bb=12.87, bf=1.5982, pressure=0.0, max_pressure=0.0,
                      brake=0.056245, drive=0.109789, danger_fraction=1.0,
                      range_factor=1.050692, limp_pull_shadow=0.0),
}


def base_table(pos, eff):
    return {k: G.first_in(pos, 9, eff, P._cls_rep(k), True) for k in P.PCT}


def mass(t):
    return sum(COMBOS[k] * (1.0 - g['fold']) for k, g in t.items())


# ---------------- 1) 합성 규칙 ----------------
for name, v in REAL.items():
    eff = P.gto_pf_open_eff_bb(v['pos'], v['bb'], None, True)
    base = base_table(v['pos'], eff)
    rf = round(v['range_factor'], 4)
    comp = P.compose_first_in(base, rf)
    W0, W1 = mass(base), mass(comp)
    want = min(1326.0, W0 * rf)
    check(abs(W1 - want) < 1e-6, '%s: composed mass %.3f != base %.3f x rf %.4f' % (name, W1, W0, rf))
    for k in P.PCT:
        b, c = base[k], comp[k]
        check(all(-1e-12 <= c[a] <= 1 + 1e-12 for a in c) and abs(sum(c.values()) - 1) < 1e-9,
              '%s %s: not a distribution' % (name, k))
        bi, ci = 1 - b['fold'], 1 - c['fold']
        if rf < 1:
            check(ci <= bi + 1e-12, '%s %s: tightened but in %.4f > base %.4f' % (name, k, ci, bi))
        else:
            check(ci >= bi - 1e-12, '%s %s: widened but in %.4f < base %.4f' % (name, k, ci, bi))
        if bi > 1e-9 and ci > 1e-9:
            for a in ('jam', 'open', 'limp'):
                check(abs(c[a] / ci - b[a] / bi) < 1e-9, '%s %s: action share %s changed' % (name, k, a))
    same = P.compose_first_in(base, 1.0)
    check(same == base, '%s: rf 1 is not identity' % name)
    print('%-13s eff %5.1f rf %.4f  GTO in %.1f%% -> %.1f%%' % (name, eff, rf, 100 * W0 / 1326, 100 * W1 / 1326))

# ---------------- 2) 훅 ----------------


class _Roll(random.Random):
    def __init__(self, u):
        super().__init__(1)
        self.u = u

    def random(self):
        return self.u


PROF = PS.make_player(random.Random(7), pid=1)
for name, v in REAL.items():
    mo = {k: v[k] for k in ('pressure', 'max_pressure', 'brake', 'drive', 'danger_fraction',
                            'range_factor', 'limp_pull_shadow')}
    # 예전 관문: 이 값이면 막혔다
    old_block = (v['bf'] > P.GTO_PF_BF_MAX or max(mo[k] for k in (
        'pressure', 'max_pressure', 'brake', 'danger_fraction', 'limp_pull_shadow')) > 1e-9)
    check(old_block, '%s: expected the old gate to block this real value' % name)
    P.take_timing_bound(); P.take_gto_spot()
    hand = ['As', 'Kd']
    act = P.gto_pf_first_in_choice(PROF, v['pos'], v['bb'], hand, _Roll(0.5), None, v['bf'], 9, True,
                                   money_open=mo)
    tb = P.take_timing_bound()
    sp = P.take_gto_spot()
    check(act is not None, '%s: hook still falls back to the old path' % name)
    if act is None:
        continue
    check(sp['args'].get('rf') == round(v['range_factor'], 4), '%s: spot rf %r' % (name, sp['args'].get('rf')))
    g = P.gto_pf_spot_freqs(sp, hand)[0]
    check(all(abs(round(g[a], 4) - tb['gto'][a]) < 1e-9 for a in g), '%s: timing gto != spot freqs' % name)
    check('gto_compose' in mo and abs(mo['gto_compose']['composed_in'] - (1 - g['fold'])) < 1e-6,
          '%s: money_open gto_compose not recorded' % name)

for bad in (float('nan'), 50.0, 0.0, 'x'):
    out = P.gto_pf_first_in_choice(PROF, 'CO', 30.0, ['As', 'Kd'], _Roll(0.5), None, 1.0, 9, True,
                                   money_open={'range_factor': bad})
    check(out is None and P.take_gto_spot() is None, 'degenerate range_factor %r used GTO' % (bad,))
out = P.gto_pf_first_in_choice(PROF, 'CO', 30.0, ['As', 'Kd'], _Roll(0.5), None, 1.3, 9, True)
check(out is None, 'no money values and BF 1.3 should keep the old path')
P.take_gto_spot()
out = P.gto_pf_first_in_choice(PROF, 'CO', 30.0, ['As', 'Kd'], _Roll(0.5), None, 1.0, 9, True,
                               money_open={'range_factor': 1.0, 'pressure': 1e-4})
sp = P.take_gto_spot()
check(out is not None and 'rf' not in sp['args'], 'rf 1.0 should be plain GTO (no rf in spot)')

# ---------------- 3) 자리 기준 BF ----------------
pays = [50.0, 30.0, 20.0]
# 4명 남음, 3명 상금(버블). 나는 seat 1(중간 스택).
st = [5000.0, 3000.0, 1500.0, 1200.0]
full = I.table_bf(st, 1, 4, 3, pays)
big_behind = I.table_bf(st, 1, 4, 3, pays, risk_idx=[0], return_details=True)
short_behind = I.table_bf(st, 1, 4, 3, pays, risk_idx=[2, 3], return_details=True)
check(abs(big_behind['value'] - full) < 1e-12, 'exact: coverer behind should equal old BF')
check(1.0 <= short_behind['value'] < full, 'exact: only shorter behind should lower BF (%.3f vs %.3f)'
      % (short_behind['value'], full))
check(abs(short_behind['risk_frac'] - (1500 + 1200) / 2 / 3000) < 1e-12, 'exact: risk_frac')
check(I.table_bf(st, 1, 4, 3, pays, risk_idx=[]) == 1.0, 'nobody behind → BF 1')
# 곡선(큰 필드)
fst = [3000.0, 2000.0, 800.0, 600.0]
f_full = I.table_bf(fst, 1, 60, 45, pays + [10.0] * 42, field_avg=2000.0)
f_short = I.table_bf(fst, 1, 60, 45, pays + [10.0] * 42, field_avg=2000.0, risk_idx=[2, 3],
                     return_details=True)
check(f_full > 1.05, 'field_bf test point should have ICM pressure (%.3f)' % f_full)
check(abs(f_short['value'] - (1 + (f_full - 1) * 0.35)) < 1e-9, 'field_bf scaled by risk_frac')
check(abs(I.table_bf(fst, 1, 60, 45, pays + [10.0] * 42, field_avg=2000.0, risk_idx=[0]) - f_full) < 1e-12,
      'field_bf: coverer behind should equal old BF')
# 브레이크
ms = {'self_preservation': 0.4, 'urgency': 0.1, 'self_preservation_pos': 0.1}
state = {'money_signals': ms, 'players_yet_to_act': 4, 'covered_by_yet_to_act': 2}
m1 = MP.unopened_modifiers(state)
check(abs(m1['brake'] - 0.1 * 0.9) < 1e-6, 'brake should use self_preservation_pos (%r)' % m1['brake'])
m0 = MP.unopened_modifiers({'money_signals': {'self_preservation': 0.4, 'urgency': 0.1},
                            'players_yet_to_act': 4, 'covered_by_yet_to_act': 2})
check(abs(m0['brake'] - 0.4 * 0.9 * 0.5) < 1e-6, 'fallback brake should be the old formula')
st_ladder = {'jump_frac_next': 0.5, 'distance_frac_itm': 0.0, 'n_shorter': 3, 'players_to_jump': 1,
             'median_shorter_ratio': 0.3, 'stack_behind_bb': 20, 'stack_after_next_bb_if_fold_all': 18,
             'bf': 1.0}
p_full = MP.objective_self_preservation(st_ladder)
p_half = MP.objective_self_preservation(dict(st_ladder, risk_frac=0.5))
check(p_half < p_full, 'ladder part should shrink with risk_frac')

if fails:
    print('money compose: %d FAIL / %d' % (len(fails), n[0]))
    sys.exit(1)
print('money compose ok: %d checks' % n[0])
