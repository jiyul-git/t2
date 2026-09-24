#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATTACK_FIXTURE_FIX — 게이트(--check)와 본 측정. 읽기 전용.

사전등록 ATTACK_FIXTURE_FIX_PREREG.md 3·4절.
게이트와 본 측정은 **분리된 실행**으로 돌린다 (SYNTH Amendment C1-4 반성).
production 무수정. qx_ev_fixture.py 무수정.
"""
from __future__ import print_function

import argparse
import collections
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import persona as PS
import plan as PL
import attack_fixture as AF
import qx_ev_fixture as QF
import tier5_axis_validate as T5
import v7_num_battery as B
import v7_num_intervention as IV

FLOOR = 0.002
BOOT = 4000
# SYNTH_CHANNEL_SPLIT 이 같은 프로필 150 에서 측정한 수비 채널 값. G5 기준.
DEFEND_REF = {'calc_only': 0.03323, 'pipe_only': 0.02796, 'diff': 0.00527}


def pear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def boot_ci(v, seed=B.SEED, iters=BOOT):
    v = np.asarray(v, float)
    rng = np.random.RandomState(seed & 0x7fffffff)
    m = v[rng.randint(0, len(v), size=(iters, len(v)))].mean(axis=1)
    m.sort()
    return float(m[int(0.025 * iters)]), float(m[int(0.975 * iters)])


def profiles(seeds, entries, n, k):
    lo, hi = (int(x) for x in seeds.split('-'))
    return IV.base_profiles(range(lo, hi + 1), entries, n)[:k]


def arm_regret(profs, states, evs):
    """arm 별 프로필당 평균 regret."""
    out = {'calc': [], 'pipe': []}
    for prof in profs:
        c_only, p_only = T5.make_arms(prof)
        for arm, key in ((c_only, 'calc'), (p_only, 'pipe')):
            out[key].append(float(np.mean([
                QF.regret_of(s, QF.bot_action(
                    s, arm, random.Random(QF.FIX_SEED + s.sid))[0], evs[s.sid])
                for s in states])))
    return out


def contrast(acc):
    d = [x - y for x, y in zip(acc['calc'], acc['pipe'])]
    ci = boot_ci(d)
    return {'calc_only': float(np.mean(acc['calc'])),
            'pipe_only': float(np.mean(acc['pipe'])),
            'diff': float(np.mean(d)), 'ci': list(ci),
            'sig': bool(ci[0] > 0 or ci[1] < 0)}


# ---------------- 게이트 ----------------
class Census(object):
    def __init__(self):
        self.ro = collections.Counter()
        self.w_pos = collections.Counter()

    def __enter__(self):
        self._ro = PS.read_opponent

        def ro(prof, est):
            f = sys._getframe(1)
            k = (os.path.basename(f.f_code.co_filename), f.f_lineno)
            self.ro[k] += 1
            d = self._ro(prof, est)
            if (d.get('w', 0) or 0) > 0:
                self.w_pos[k] += 1
            return d
        PS.read_opponent = ro
        PL.PS.read_opponent = ro
        return self

    def __exit__(self, *a):
        PS.read_opponent = self._ro
        PL.PS.read_opponent = self._ro
        return False


def run_gates(a):
    A = AF.build_attack_states()
    D = AF.build_defend_states()
    evsA = {s.sid: s.ev_actions() for s in A}
    profs = profiles(a.set_a, a.entries, a.n, a.synth_n)
    small = profs[:a.census_n]
    ok = {}
    print('공격 상태 %d   수비 상태 %d   프로필 %d (계측용 %d)'
          % (len(A), len(D), len(profs), len(small)))

    # G1 독립성
    r_ind = pear([s.ftb_true for s in A], [s.b_true for s in A])
    ok['G1'] = abs(r_ind) < 1e-12
    print('\n[G1] r(ftb_true, b_true) = %+.3e   -> %s'
          % (r_ind, 'OK' if ok['G1'] else 'FAIL'))

    # G3 오라클 방향 + 항등
    resid = max(abs(s.p_fold_oracle() - s.ftb_true) for s in A)
    r_or = pear([s.ftb_true for s in A], [s.p_fold_oracle() for s in A])
    ok['G3'] = (r_or > 0.99 and resid < 1e-9)
    print('[G3] r(ftb_true, 오라클 P(fold)) = %+.4f   항등 잔차 %.2e   -> %s'
          % (r_or, resid, 'OK' if ok['G3'] else 'FAIL'))

    # G2 장부 추적 + 옛 결함 소멸  /  G4b 행동 추적
    rows = {'calc': [], 'pipe': []}
    for prof in small:
        arms = T5.make_arms(prof)
        for arm, key in ((arms[0], 'calc'), (arms[1], 'pipe')):
            for s in A:
                rng = random.Random(QF.FIX_SEED + s.sid)
                est = s.est_for(arm, rng)
                rd = PS.read_opponent(arm, est)
                mix, _ = QF.bot_action(s, arm, random.Random(QF.FIX_SEED + s.sid))
                rows[key].append((s.ftb_true, s.b_true,
                                  float(est.get('ftb') or 0.52),
                                  float(PS.street_gap(rd, 'turn')),
                                  float(mix.get('bet', 0.0))))
    P = rows['pipe']
    r_ftb = pear([x[0] for x in P], [x[2] for x in P])
    r_gap = pear([x[0] for x in P], [x[3] for x in P])
    r_bad = pear([x[1] for x in P], [x[2] for x in P])
    ok['G2'] = (r_ftb > 0.5 and r_gap > 0.5 and abs(r_bad) < 0.2)
    print('[G2] r(ftb_true, 믿는 ftb) %+.4f   r(ftb_true, fold_gap) %+.4f'
          % (r_ftb, r_gap))
    print('     r(b_true, 믿는 ftb) %+.4f   (옛 결함은 −1.000 이었다)   -> %s'
          % (r_bad, 'OK' if ok['G2'] else 'FAIL'))
    rp = pear([x[0] for x in P], [x[4] for x in P])
    rc = pear([x[0] for x in rows['calc']], [x[4] for x in rows['calc']])
    ok['G4b'] = (rp > 0.1 and abs(rc) < 0.02)
    print('[G4b] r(ftb_true, 벳확률)  PIPE %+.4f   CALC %+.4f   -> %s'
          % (rp, rc, 'OK' if ok['G4b'] else 'FAIL'))

    # G4 소비 지점
    print('[G4] read_opponent 활성 비율')
    cen = {}
    for nm, pick in (('CALC_ONLY', 0), ('PIPE_ONLY', 1)):
        c = Census()
        with c:
            for prof in small:
                arm = T5.make_arms(prof)[pick]
                for s in A:
                    QF.bot_action(s, arm, random.Random(QF.FIX_SEED + s.sid))
        cen[nm] = {'%s:%d' % k: (c.ro[k], c.w_pos[k]) for k in c.ro}
        for k in sorted(c.ro):
            print('     %-10s %s:%-5d  호출 %6d  w>0 %6d (%.1f%%)'
                  % (nm, k[0], k[1], c.ro[k], c.w_pos[k],
                     100.0 * c.w_pos[k] / max(1, c.ro[k])))
    def frac(nm):
        v = cen[nm]
        return [w / float(max(1, t)) for t, w in v.values()]
    ok['G4'] = (all(abs(x - 1.0) < 1e-9 for x in frac('PIPE_ONLY'))
                and all(x == 0.0 for x in frac('CALC_ONLY'))
                and len(cen['PIPE_ONLY']) == 2)
    print('     -> %s' % ('OK' if ok['G4'] else 'FAIL'))

    # G5 수비 대조 — 옛 결과 정확 재현
    dref = contrast(arm_regret(profs, D, {s.sid: s.ev_actions() for s in D}))
    ok['G5'] = all(abs(dref[k] - DEFEND_REF[k]) < 5e-6 for k in DEFEND_REF)
    print('[G5] 수비 재현  calc %.5f (기준 %.5f)   pipe %.5f (기준 %.5f)   '
          'd %+.5f (기준 %+.5f)   -> %s'
          % (dref['calc_only'], DEFEND_REF['calc_only'],
             dref['pipe_only'], DEFEND_REF['pipe_only'],
             dref['diff'], DEFEND_REF['diff'], 'OK' if ok['G5'] else 'FAIL'))

    # G6 판별력
    nbet = sum(1 for s in A
               if max(evsA[s.sid], key=lambda k: evsA[s.sid][k]) == 'bet')
    flip = {}
    for s in A:
        flip.setdefault((tuple(s.board), tuple(s.hero), s.sz, s.b_true),
                        set()).add(max(evsA[s.sid],
                                       key=lambda k: evsA[s.sid][k]))
    nf = sum(1 for v in flip.values() if len(v) > 1)
    frac_bet = nbet / float(len(A))
    ok['G6'] = (0.45 <= frac_bet <= 0.55 and nf >= 30)
    print('[G6] 최적=bet 비율 %.3f   ftb 뒤집힘 %d/%d   -> %s'
          % (frac_bet, nf, len(flip), 'OK' if ok['G6'] else 'FAIL'))

    print('\n게이트 전체: %s'
          % ('통과' if all(ok.values())
             else '실패 — ' + ', '.join(k for k, v in ok.items() if not v)))
    if a.out:
        json.dump({'gates': {k: bool(v) for k, v in ok.items()},
                   'r_independence': r_ind, 'r_oracle': r_or,
                   'r_ftb_seen': r_ftb, 'r_fold_gap': r_gap,
                   'r_b_ftb_seen': r_bad, 'r_bet_pipe': rp,
                   'r_bet_calc': rc, 'defend': dref, 'sites': cen,
                   'frac_bet': frac_bet, 'n_flip': nf},
                  open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0 if all(ok.values()) else 1


# ---------------- 본 측정 ----------------
def measure(a):
    A = AF.build_attack_states()
    D = AF.build_defend_states()
    evs = {}
    evs.update({s.sid: s.ev_actions() for s in D})
    aoff = 100000
    for s in A:
        s.sid += aoff                       # 수비와 sid 충돌 방지
    evs.update({s.sid: s.ev_actions() for s in A})
    print('공격 상태 %d   수비 상태 %d' % (len(A), len(D)))
    out = {}
    for label, seeds in (('SET_A', a.set_a), ('SET_B', a.set_b)):
        profs = profiles(seeds, a.entries, a.n, a.synth_n)
        accA = arm_regret(profs, A, evs)
        accD = arm_regret(profs, D, evs)
        # 합산은 상태 수 가중이다 — 채널별 프로필 평균을 그대로 섞으면 안 된다.
        wA, wD = len(A) / float(len(A) + len(D)), len(D) / float(len(A) + len(D))
        accP = {k: [wA * x + wD * y for x, y in zip(accA[k], accD[k])]
                for k in ('calc', 'pipe')}
        res = {'attack': contrast(accA), 'defend': contrast(accD),
               'pooled': contrast(accP),
               'weights': {'attack': len(A), 'defend': len(D)}}
        for nn in (6, 40):
            sub = [s for s in A if s.n_obs == nn]
            res['attack_n%d' % nn] = contrast(arm_regret(profs, sub, evs))
        out[label] = res
        print('\n=== %s %s (프로필 %d) ===' % (label, seeds, len(profs)))
        print('%-12s %6s %10s %10s %11s %24s'
              % ('채널', '상태', 'CALC', 'PIPE', 'd', '95%CI'))
        for k, nm, ns in (('attack', '공격', len(A)), ('defend', '수비', len(D)),
                          ('pooled', '합산(가중)', len(A) + len(D))):
            r = res[k]
            print('%-12s %6d %10.5f %10.5f %+11.5f   [%+.5f, %+.5f] %s'
                  % (nm, ns, r['calc_only'], r['pipe_only'], r['diff'],
                     r['ci'][0], r['ci'][1],
                     '유의' if r['sig'] else '유의하지 않음'))
        for nn in (6, 40):
            r = res['attack_n%d' % nn]
            print('  공격 n_obs=%-3d              %10.5f %10.5f %+11.5f   '
                  '[%+.5f, %+.5f]'
                  % (nn, r['calc_only'], r['pipe_only'], r['diff'],
                     r['ci'][0], r['ci'][1]))

    def okp(lab):
        return all(out[s][lab]['diff'] >= FLOOR and out[s][lab]['sig']
                   for s in ('SET_A', 'SET_B'))

    def okm(lab):
        return all(out[s][lab]['diff'] <= -FLOOR and out[s][lab]['sig']
                   for s in ('SET_A', 'SET_B'))
    v = ('ATTACK_READ_HELPS' if okp('attack')
         else ('ATTACK_READ_HURTS' if okm('attack') else 'ATTACK_READ_NULL'))
    print('\n========== 판정: %s ==========' % v)
    print('  (게이트는 --check 로 별도 실행. 실패했으면 INCONCLUSIVE 다.)')
    out['verdict'] = v
    out['floor'] = FLOOR
    if a.out:
        json.dump(out, open(a.out, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--set-a', default='940001-940010')
    ap.add_argument('--set-b', default='950001-950010')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--synth-n', type=int, default=150)
    ap.add_argument('--census-n', type=int, default=20)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    return run_gates(a) if a.check else measure(a)


if __name__ == '__main__':
    raise SystemExit(main())
