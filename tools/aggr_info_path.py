#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SYNTH_CHANNEL_SPLIT 4절 — decide_aggression 의 상대정보 소비 경로. 읽기 전용.

코드 독해로 끝내지 않는다 (CLAUDE.md 작업원칙 4). PS.sk / PS.read_opponent 를
monkeypatch 해서 합성 arm 두 개가 **공격 상태에서 실제로 읽는 것**을 센다.

production 무수정. fixture 무수정.
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
import qx_ev_fixture as FX
import tier5_axis_validate as T5
import v7_num_intervention as IV


class Census(object):
    """호출 지점(파일:줄)별로 무엇을 읽었는지 센다."""

    def __init__(self):
        self.sk = collections.Counter()
        self.ro = collections.Counter()
        self.w_pos = collections.Counter()

    def __enter__(self):
        self._sk, self._ro = PS.sk, PS.read_opponent

        def sk(prof, c, *a, **k):
            f = sys._getframe(1)
            self.sk[(os.path.basename(f.f_code.co_filename), f.f_lineno, c)] += 1
            return self._sk(prof, c, *a, **k)

        def ro(prof, est):
            f = sys._getframe(1)
            key = (os.path.basename(f.f_code.co_filename), f.f_lineno)
            self.ro[key] += 1
            d = self._ro(prof, est)
            if (d.get('w', 0) or 0) > 0:
                self.w_pos[key] += 1
            return d

        PS.sk, PS.read_opponent = sk, ro
        PL.PS.sk, PL.PS.read_opponent = sk, ro
        return self

    def __exit__(self, *a):
        PS.sk, PS.read_opponent = self._sk, self._ro
        PL.PS.sk, PL.PS.read_opponent = self._sk, self._ro
        return False


def attack_states(states):
    return [s for s in states if s.group == 'READ' and s.channel == 'A']


def census(profs, states):
    """arm 별로 공격 상태에서 읽은 축과 read_opponent 호출 지점."""
    out = {}
    for nm, pick in (('CALC_ONLY', 0), ('PIPE_ONLY', 1)):
        c = Census()
        with c:
            for prof in profs:
                arm = T5.make_arms(prof)[pick]
                for s in states:
                    FX.bot_action(s, arm, random.Random(FX.FIX_SEED + s.sid))
        out[nm] = c
    return out


def direction(profs, states):
    """공개 장부가 말하는 폴드 성향 vs EV 엔진이 쓰는 폴드 확률."""
    rows = []
    for prof in profs:
        arm = T5.make_arms(prof)[1]          # PIPE_ONLY — 잘 읽는 쪽
        for s in states:
            rng = random.Random(FX.FIX_SEED + s.sid)
            est = s.est_for(arm, rng)
            rd = PS.read_opponent(arm, est)
            mix, p = FX.bot_action(s, arm, random.Random(FX.FIX_SEED + s.sid))
            rows.append({
                'b_true': s.b_true,
                'ftb_book': 1.0 - s.b_true,                 # 장부가 기록하는 폴드율
                'ftb_seen': float(est.get('ftb') or 0.52),  # arm 이 믿는 폴드율
                'fold_gap': float(PS.street_gap(rd, 'turn')),
                # EV 엔진이 실제로 쓰는 '내 벳에 접을 확률'
                'p_fold_ev': s.b_true * s.f_bluff + (1.0 - s.b_true) * s.f_value,
                'p_bet': float(mix.get('bet', 0.0)),
            })
    return rows


def defend_control(profs, states):
    """음성 대조 — 수비 채널에도 같은 방향 모순이 있는가.

    있으면 이번 결론('공격 채널만 배선이 뒤집혔다')이 성립하지 않는다.
    """
    rows = []
    for prof in profs:
        arm = T5.make_arms(prof)[1]
        for s in states:
            rng = random.Random(FX.FIX_SEED + s.sid)
            est = s.est_for(arm, rng)
            rv = PL.line_bluff_prior(est, 'turn', 1, s.sz, s.board, False)
            ev = s.ev_actions()
            rows.append({
                'b_true': s.b_true,
                'bluff_seen': float(est.get('bluff') or 4.5),
                'rv': float(rv),
                # 오라클이 말하는 '콜이 폴드보다 나은 정도'
                'edge_call': float(ev['call'] - ev['fold']),
            })
    return rows


def pear(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='940001-940010')
    ap.add_argument('--entries', type=int, default=400)
    ap.add_argument('--n', type=int, default=400)
    ap.add_argument('--synth-n', type=int, default=40)
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split('-'))

    states = attack_states(FX.build_states())
    profs = IV.base_profiles(range(lo, hi + 1), a.entries, a.n)[:a.synth_n]
    print('공격 READ 상태 %d   합성 프로필 %d' % (len(states), len(profs)))

    print('\n=== 1. read_opponent 호출 지점 (공격 상태에서 실측) ===')
    cen = census(profs, states)
    for nm, c in cen.items():
        print('  %s' % nm)
        for k in sorted(c.ro):
            print('    %s:%-5d  호출 %6d   w>0 인 것 %6d (%.1f%%)'
                  % (k[0], k[1], c.ro[k], c.w_pos[k],
                     100.0 * c.w_pos[k] / max(1, c.ro[k])))

    print('\n=== 2. 공격 상태에서 읽힌 성향 축 상위 ===')
    for nm, c in cen.items():
        tot = collections.Counter()
        for (f, ln, cpt), v in c.sk.items():
            tot[cpt] += v
        print('  %-10s %s' % (nm, ', '.join(
            '%s %d' % (k, v) for k, v in tot.most_common(8))))

    print('\n=== 3. 장부와 EV 엔진의 방향 ===')
    rows = direction(profs, states)
    b = [r['b_true'] for r in rows]
    print('  r(b_true, 장부 fold_to_bet)      %+.4f'
          % pear(b, [r['ftb_book'] for r in rows]))
    print('  r(b_true, arm 이 믿는 ftb)       %+.4f'
          % pear(b, [r['ftb_seen'] for r in rows]))
    print('  r(b_true, fold_gap(turn))        %+.4f'
          % pear(b, [r['fold_gap'] for r in rows]))
    print('  r(b_true, EV 엔진의 폴드 확률)    %+.4f'
          % pear(b, [r['p_fold_ev'] for r in rows]))
    print('  r(arm 이 믿는 ftb, EV 폴드 확률)  %+.4f'
          % pear([r['ftb_seen'] for r in rows], [r['p_fold_ev'] for r in rows]))
    print('  r(fold_gap, EV 폴드 확률)        %+.4f'
          % pear([r['fold_gap'] for r in rows], [r['p_fold_ev'] for r in rows]))
    print('  r(b_true, arm 의 벳 확률)        %+.4f'
          % pear(b, [r['p_bet'] for r in rows]))

    print('\n  b_true 별 (평균)')
    print('  %-8s %10s %10s %10s %10s' %
          ('b_true', '장부ftb', 'EV폴드율', 'fold_gap', '벳확률'))
    for bt in sorted(set(b)):
        sel = [r for r in rows if r['b_true'] == bt]
        print('  %-8.2f %10.3f %10.3f %+10.4f %10.3f'
              % (bt, np.mean([r['ftb_book'] for r in sel]),
                 np.mean([r['p_fold_ev'] for r in sel]),
                 np.mean([r['fold_gap'] for r in sel]),
                 np.mean([r['p_bet'] for r in sel])))

    print('\n=== 4. 음성 대조 — 수비 채널은 같은 모순이 있는가 ===')
    dst = [x for x in FX.build_states()
           if x.group == 'READ' and x.channel == 'D']
    drow = defend_control(profs, dst)
    db = [r['b_true'] for r in drow]
    d_corr = {
        'b_bluff_seen': pear(db, [r['bluff_seen'] for r in drow]),
        'b_rv': pear(db, [r['rv'] for r in drow]),
        'b_edge_call': pear(db, [r['edge_call'] for r in drow]),
        'rv_edge_call': pear([r['rv'] for r in drow],
                             [r['edge_call'] for r in drow]),
    }
    print('  수비 상태 %d' % len(dst))
    print('  r(b_true, arm 이 믿는 bluff)      %+.4f' % d_corr['b_bluff_seen'])
    print('  r(b_true, line_bluff_prior)       %+.4f' % d_corr['b_rv'])
    print('  r(b_true, 오라클의 콜 우위)        %+.4f' % d_corr['b_edge_call'])
    print('  r(line_bluff_prior, 콜 우위)      %+.4f  <- 양수면 배선이 맞다'
          % d_corr['rv_edge_call'])

    if a.out:
        json.dump({'defend_corr': d_corr, 'corr': {
            'b_ftb_book': pear(b, [r['ftb_book'] for r in rows]),
            'b_ftb_seen': pear(b, [r['ftb_seen'] for r in rows]),
            'b_fold_gap': pear(b, [r['fold_gap'] for r in rows]),
            'b_p_fold_ev': pear(b, [r['p_fold_ev'] for r in rows]),
            'ftb_seen_p_fold_ev': pear([r['ftb_seen'] for r in rows],
                                       [r['p_fold_ev'] for r in rows]),
            'fold_gap_p_fold_ev': pear([r['fold_gap'] for r in rows],
                                       [r['p_fold_ev'] for r in rows]),
            'b_p_bet': pear(b, [r['p_bet'] for r in rows])},
            'sites': {nm: {'%s:%d' % k: [c.ro[k], c.w_pos[k]] for k in c.ro}
                      for nm, c in cen.items()},
            'n_states': len(states), 'n_profiles': len(profs)},
            open(a.out, 'w', encoding='utf-8'),
            ensure_ascii=False, indent=1, sort_keys=True)
        print('\nwrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
