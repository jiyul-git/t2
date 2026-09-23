#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ_USE_SEPARATION — 상태 집합과 2x2 arm 개입. 읽기 전용.

사전등록 READ_USE_SEPARATION_PREREG.md 2절.

production 무수정. 개입은 전부 여기서 contextmanager 로 걸고 푼다.
  R (읽기 정확도)  reads.estimate 반환값을 모집단 사전분포로 블렌드
  U (적용 강도)    calldown_need 의 두 적용 지점에만 배수

EV 엔진과 State 는 tools/qx_ev_fixture.py 를 그대로 쓴다 — 그쪽은 건드리지
않는다. QX_EV_VALIDATION 의 재현성이 거기 걸려 있다.
"""
from __future__ import print_function

import contextlib
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import persona as PS
import plan as PL
import reads as RD
import qx_ev_fixture as QF

SEED = 20260930

# ---------- 상태 집합 (사전등록 2-4) ----------
BOARDS = (['Kc', '7d', '2s', '5h'], ['Jh', 'Th', '4c', '2d'],
          ['Qd', '8s', '3h', 'Tc'], ['9c', '6d', '2h', 'Kd'],
          ['As', 'Kd', '9h', '4c'], ['8d', '7c', '3s', 'Qh'])
HEROS = (['Ah', 'Jd'], ['Qs', 'Qc'], ['9h', '8h'], ['7h', '6c'],
         ['Ad', '3c'], ['Kh', 'Qd'], ['Js', '9d'], ['Ac', 'Ts'],
         ['5s', '5d'], ['Kd', '7s'], ['Th', '9c'], ['Qh', '5h'],
         ['6s', '4d'], ['8c', '2h'], ['Jc', '3d'], ['Tc', '7h'])
# 2.0 팟을 넘기지 않는다. persona.size_read 는 2.0 이하에서 항등이고
# (CLAUDE.md: 아카이브 포스트플랍 sz 최대 0.915) 그 위는 정의역 밖 분기다.
# 이번 실험의 축은 사이즈 인식이 아니므로 그 분기를 켜지 않는다.
SZ_GRID = (0.30, 0.42, 0.55, 0.70, 0.90, 1.15, 1.45, 1.80)
B_LEVELS = (0.15, 0.27, 0.39, 0.51, 0.63, 0.75)
N_LEVELS = (6, 40)
# 셀은 '이 격자에서 최적 call 이 되는 수준 수'(1~5)로 층화한다.
# QF._flip_point 의 0.05 스캔 격자는 B_LEVELS 와 어긋나서, 뒤집힘점이
# 격자 안에 있어도 실제로는 6수준 전부 한쪽이 되는 셀이 섞였다(20셀 중 1).
# 여기서는 쓰는 격자 위에서 직접 센다 — 층 k 의 셀은 정확히 k 개 수준이
# call 최적이므로, 각 층 4셀이면 전체 call 비율이 (1+2+3+4+5)*4/120 = 0.500 이다.
N_CALL_STRATA = (1, 2, 3, 4, 5)
PER_BAND = 4

# ---------- arm 수준 (사전등록 2-1 / 2-2) ----------
A_LO, A_HI = 0.20, 1.00
U_LO, U_HI = 0.40, 1.60
U_LADDER = (0.0, 0.4, 0.7, 1.0, 1.3, 1.6, 2.0)

# 블렌드 대상 채널과 그 모집단 중립값 (사전등록 2-1)
_P = RD.PRIOR
NEUTRAL = {
    'vpip': _P['vpip'], 'pfr': _P['pfr'], 'cbet': _P['cbet'],
    'barrel': _P['barrel'],
    'ftb': _P['fold_to_bet'], 'ftb_flop': _P['fold_to_bet'],
    'ftb_turn': _P['fold_to_bet'], 'ftb_river': _P['fold_to_bet'],
    'pf_3bet': _P['pf_3bet'], 'pf_fold_to_3bet': _P['pf_fold_to_3bet'],
    'pf_4bet': _P['pf_4bet'], 'pf_fold_to_4bet': _P['pf_fold_to_4bet'],
    'pf_limp': _P['pf_limp'], 'rfi_rel': 1.0,
    'sz_mean': _P['sz_mean'], 'sz_sd': _P['sz_sd'],
    'sz_big': 0.15, 'sz_river': _P['sz_mean'],
    'aggr': _P['aggr'], 'bluff': _P['bluff'], 'tight': _P['tight'],
}
# 제외: n, confidence, sz_n, rfi_n, type — 표본 사실이지 믿음이 아니다.
# 이 제외가 'R 은 w 를 안 바꾼다'를 보장한다 (read_opponent 의 data 는
# confidence 와 n 에서만 나온다).
EXCLUDED = ('n', 'confidence', 'sz_n', 'rfi_n', 'type')


def blend_to_prior(est, a):
    """공개 증거로 만든 믿음을 모집단 사전분포 쪽으로 블렌드한다."""
    if a >= 1.0:
        return est
    out = dict(est)
    for k, pr in NEUTRAL.items():
        v = est.get(k)
        if v is None:
            continue
        out[k] = pr * (1.0 - a) + float(v) * a
    return out


@contextlib.contextmanager
def read_arm(a):
    """축 R. reads.estimate 의 반환값에만 건다 — estimate_concepts 와
    perceived_profile 의 나머지가 블렌드된 믿음과 정합해진다.
    난수 소비 횟수는 값과 무관하므로 paired 설계가 유지된다."""
    orig = RD.estimate

    def patched(book, observer, target, observer_type, rng=None):
        return blend_to_prior(orig(book, observer, target, observer_type, rng), a)

    RD.estimate = patched
    try:
        yield
    finally:
        RD.estimate = orig


@contextlib.contextmanager
def use_arm(u):
    """축 U. read_opponent 의 w 에만 배수를 걸고, opp_size_norm 은
    원래 w(_w0)로 되돌려 계산한다 — 사이즈 인식은 적용 강도가 아니다."""
    orig_ro = PS.read_opponent
    orig_osn = PS.opp_size_norm

    def ro(prof, opp_est):
        d = orig_ro(prof, opp_est)
        w = d.get('w', 0.0) or 0.0
        if w > 0.0:
            d = dict(d)
            d['_w0'] = w
            d['w'] = max(0.0, min(0.85, u * w))
        return d

    def osn(rd, size_frac, street=None):
        if rd and '_w0' in rd:
            rd = dict(rd)
            rd['w'] = rd['_w0']
        return orig_osn(rd, size_frac, street)

    PS.read_opponent = ro
    PS.opp_size_norm = osn
    try:
        yield
    finally:
        PS.read_opponent = orig_ro
        PS.opp_size_norm = orig_osn


# ---------- 상태 ----------
def _scan_cells():
    """(보드, 히어로, 가격) 후보마다 B_LEVELS 에서 최적 행동을 직접 센다."""
    out = []
    for board in BOARDS:
        for hero in HEROS:
            for sz in SZ_GRID:
                best = []
                for bt in B_LEVELS:
                    ev = QF.State(-1, 'D', 'READ', hero, board, sz, bt,
                                  40).ev_actions()
                    best.append(max(ev, key=lambda k: ev[k]))
                k = sum(1 for x in best if x == 'call')
                if 1 <= k <= 5:
                    out.append((k, tuple(board), tuple(hero), sz, tuple(best)))
    return out


def pick_cells():
    """층(call 최적 수준 수)별 균등 추출. (보드,히어로) 쌍당 최대 1셀.

    후보가 적은 층부터 채운다. 흔한 층이 먼저 (보드,히어로) 쌍을 소비하면
    희귀 층이 굶는다 — 처음 시도에서 한 층이 0셀이 됐다.
    """
    cand = _scan_cells()
    per = {k: [] for k in N_CALL_STRATA}
    for k, board, hero, sz, best in cand:
        per[k].append((board, hero, sz, best))
    order = sorted(N_CALL_STRATA, key=lambda k: len(per[k]))
    cells, used = [], set()
    for k in order:
        # 보드 라운드로빈. 이름순으로만 정렬하면 알파벳이 빠른 보드가
        # 한 층을 독식한다(첫 시도에서 20셀이 보드 2개에 몰렸다).
        by_board = {}
        for t in sorted(per[k], key=lambda t: (t[0], t[1], t[2])):
            by_board.setdefault(t[0], []).append(t)
        ranked = []
        for i in range(max((len(v) for v in by_board.values()), default=0)):
            for bd in sorted(by_board):
                if i < len(by_board[bd]):
                    ranked.append(by_board[bd][i])
        got = 0
        for board, hero, sz, best in ranked:
            if got >= PER_BAND:
                break
            if (board, hero) in used:
                continue
            used.add((board, hero))
            cells.append((list(board), list(hero), sz, k))
            got += 1
    cells.sort(key=lambda c: (c[3], c[0], c[1], c[2]))
    return cells


def build_states():
    sts, sid = [], 0
    for board, hero, sz, ncall in pick_cells():
        for b in B_LEVELS:
            for n in N_LEVELS:
                s = QF.State(sid, 'D', 'READ', hero, board, sz, b, n)
                s.ncall = ncall
                sts.append(s)
                sid += 1
    return sts


# ---------- 행동 ----------
def est_for_arm(state, prof, seed, a):
    with read_arm(a):
        return state.est_for(prof, random.Random(seed))


def decide(state, prof, est, seed, u):
    """수비 채널 한 결정. est 는 R arm 에서 이미 고정된 값이다.

    **use_arm(u) 안에서 불러야 한다.** 호출부가 컨텍스트를 들고 있게 한 것은
    상태 240개마다 patch 를 걸고 푸는 비용을 피하기 위해서다.
    """
    rv = PL.line_bluff_prior(est, 'turn', 1, state.sz, state.board, False)
    rv_u = 0.35 + u * (rv - 0.35)          # trust *= u 와 대수적으로 동일
    need = float(PL.calldown_need(
        prof, state.hero, state.board, 'turn', state.pot_live,
        state.tocall, 1.0, rv_u, 0, est, n_opp=1, rng=random.Random(seed)))
    eq = state.b_true * state.eq_blf + (1.0 - state.b_true) * state.eq_val
    return ('call' if eq >= need else 'fold'), need, rv


def act_for_arm(state, prof, est, seed, u):
    with use_arm(u):
        return decide(state, prof, est, seed, u)


def seeds_for(pi, sid):
    """est 용과 need 용을 분리한다. arm 사이에서는 동일하다."""
    return (SEED + 7919 * pi + 31 * sid, SEED + 104729 * pi + 97 * sid + 1)


def regret(state, act, evs):
    e = evs[state.sid]
    return max(e.values()) - e[act]


if __name__ == '__main__':
    import time
    t0 = time.time()
    cells = pick_cells()
    print('cells %d' % len(cells))
    for board, hero, sz, k in cells:
        print('  k=%d  %-10s %-5s sz %.2f'
              % (k, ''.join(board), ''.join(hero), sz))
    sts = build_states()
    evs = {s.sid: s.ev_actions() for s in sts}
    flips = {}
    for s in sts:
        best = max(evs[s.sid], key=lambda k: evs[s.sid][k])
        flips.setdefault((tuple(s.board), tuple(s.hero), s.sz), set()).add(best)
    nf = sum(1 for v in flips.values() if len(v) > 1)
    ncall = sum(1 for s in sts
                if max(evs[s.sid], key=lambda k: evs[s.sid][k]) == 'call')
    print('states %d   뒤집힘 셀 %d/%d   최적=call 비율 %.3f   %.1fs'
          % (len(sts), nf, len(flips), ncall / float(len(sts)),
             time.time() - t0))
