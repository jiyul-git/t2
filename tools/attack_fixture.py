#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATTACK_FIXTURE_FIX — 공격 채널 배선을 고친 fixture. 읽기 전용.

**tools/qx_ev_fixture.py 는 건드리지 않는다.** 거기서 파생만 한다.
QX_EV_VALIDATION 과 SYNTH_CHANNEL_SPLIT 의 재현이 그 파일에 걸려 있다.

고치는 것은 하나다 — 공격 채널에서 `ftb`(벳을 마주쳤을 때 접는 빈도)를
`b_true`(벳할 때 블러프 비율)와 **독립 파라미터로 분리**한다.

옛 fixture 의 결함 (SYNTH_CHANNEL_SPLIT_RESULT.md 3-2):
    State.book()        ftb = 1 - b_true              r(b_true, ·) = -1.000
    State.ev_actions()  P(fold) = .18 + .60*b_true    r(b_true, ·) = +1.000
  같은 스칼라에 반대 단조로 걸려 있어 정확히 읽을수록 손해를 본다.

여기서는
    book()        fold_to_bet / f2b_* 를 ftb_true 로 기록
    ev_actions()  f_bluff = ftb_true + (1-b)*D ,  f_value = ftb_true - b*D
                  -> 주변 폴드확률 b*f_bluff + (1-b)*f_value == ftb_true 가
                     **항등**이고, 약한 손이 더 접는다는 구조도 유지된다.

**수비 상태는 옛 State 를 그대로 쓴다.** 수비 경로(calldown_need)는 ftb 를
읽지 않으므로 결함의 영향이 없고, 그래야 옛 수비 결과와 **비트까지 대조**된다.
"""
from __future__ import print_function

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import qx_ev_fixture as QF

# 격자는 교차(crossed)다 — 두 파라미터가 설계상 직교한다.
B_LEVELS = (0.15, 0.35, 0.55, 0.75)
FTB_LEVELS = (0.32, 0.44, 0.56, 0.68)
N_LEVELS = (6, 40)
# 약한 손과 강한 손의 폴드확률 격차. 상수로 둔다 —
# 상태마다 다르면 '손 종류가 주는 정보량'이 ftb_true 와 교락된다.
D_SPREAD = 0.28
# 위 격자에서 f_bluff 최대 0.68+0.85*0.28=0.918, f_value 최소 0.32-0.75*0.28=0.110.
# 둘 다 (0,1) 안이므로 클램프가 걸리지 않고 항등이 정확히 성립한다.

BOARDS = QF.BOARDS + (['Qd', '8s', '3h', 'Tc'], ['9c', '6d', '2h', 'Kd'],
                      ['As', 'Kd', '9h', '4c'], ['8d', '7c', '3s', 'Qh'])
HEROS = QF.HERO_HANDS + (['Js', '9d'], ['Ac', 'Ts'], ['5s', '5d'],
                         ['Kd', '7s'], ['Th', '9c'], ['Qh', '5h'])
SZ_GRID = (0.35, 0.50, 0.66, 0.85, 1.10, 1.40, 1.80)
# 셀 층화: 16개 (ftb,b) 조합 중 벳이 최적인 개수로 나눈다.
STRATA = ((4, 6), (7, 9), (10, 12))
PER_STRATUM = 3


class AttackState(QF.State):
    """공격 상태. ftb_true 가 b_true 와 독립이다."""

    def __init__(self, sid, hero, board, sz, b_true, ftb_true, n_obs,
                 barrel_true=0.45, sz_river=0.62):
        f_bluff = ftb_true + (1.0 - b_true) * D_SPREAD
        f_value = ftb_true - b_true * D_SPREAD
        assert 0.0 < f_value < f_bluff < 1.0, (f_value, f_bluff)
        QF.State.__init__(self, sid, 'A', 'READ', hero, board, sz, b_true,
                          n_obs, barrel_true=barrel_true, f_bluff=f_bluff,
                          f_value=f_value, sz_river=sz_river)
        self.ftb_true = ftb_true

    def book(self):
        """옛 book 을 만든 뒤 폴드 관련 카운터만 ftb_true 로 덮어쓴다.

        블러프 증거(cbet·barrel·sd_weak)는 b_true 가 계속 만든다 —
        이제 장부가 **두 개의 독립 신호**를 싣는다.
        """
        bk = QF.State.book(self)
        r = bk.rec(1, 2)
        n = self.n_obs
        r['fold_to_bet'] = int(round(n * self.ftb_true))
        for st in ('flop', 'turn', 'river'):
            r['f2b_' + st] = int(round(n * self.ftb_true))
        return bk

    def p_fold_oracle(self):
        """EV 엔진이 실제로 쓰는 '내 벳에 접을 확률'의 주변값."""
        return self.b_true * self.f_bluff + (1.0 - self.b_true) * self.f_value


def _optimal_grid(hero, board, sz):
    """(ftb, b) 16조합의 최적 행동. (벳 개수, ftb 로 뒤집히는 b 수준 수)

    두 번째 값이 중요하다 — 공격 채널에서 읽어야 할 것은 ftb 이므로,
    ftb 가 최적을 못 바꾸는 셀은 읽기 능력을 잴 수 없다.
    """
    nbet, nflip = 0, 0
    for b in B_LEVELS:
        seen = set()
        for ftb in FTB_LEVELS:
            ev = AttackState(-1, hero, board, sz, b, ftb, 40).ev_actions()
            a = max(ev, key=lambda k: ev[k])
            seen.add(a)
            if a == 'bet':
                nbet += 1
        if len(seen) > 1:
            nflip += 1
    return nbet, nflip


def pick_cells():
    """층별 균등 추출. (보드,히어로) 쌍당 최대 1셀, 층 안에서 보드 라운드로빈."""
    per = {i: [] for i in range(len(STRATA))}
    for board in BOARDS:
        for hero in HEROS:
            for sz in SZ_GRID:
                k, nf = _optimal_grid(hero, board, sz)
                if nf < 2:
                    continue          # ftb 가 최적을 거의 못 바꾸는 셀은 뺀다
                for i, (lo, hi) in enumerate(STRATA):
                    if lo <= k <= hi:
                        per[i].append((tuple(board), tuple(hero), sz, k, nf))
                        break
    order = sorted(range(len(STRATA)), key=lambda i: len(per[i]))
    cells, used, hero_n = [], set(), {}
    for i in order:
        # 층 안에서는 ftb 뒤집힘이 많은 것부터. 동점은 보드 라운드로빈.
        by_board = {}
        for t in sorted(per[i], key=lambda t: (-t[4], t[0], t[1], t[2])):
            by_board.setdefault(t[0], []).append(t)
        ranked = []
        for j in range(max((len(v) for v in by_board.values()), default=0)):
            for bd in sorted(by_board):
                if j < len(by_board[bd]):
                    ranked.append(by_board[bd][j])
        got = 0
        for board, hero, sz, k, nf in ranked:
            if got >= PER_STRATUM:
                break
            # 한 핸드가 셀을 독식하지 않게 한다 (첫 시도에서 9셀 중 5개가
            # 같은 핸드였다). 보드가 달라도 같은 핸드는 2개까지.
            if (board, hero) in used or hero_n.get(hero, 0) >= 2:
                continue
            used.add((board, hero))
            hero_n[hero] = hero_n.get(hero, 0) + 1
            cells.append((list(board), list(hero), sz, k, i))
            got += 1
    cells.sort(key=lambda c: (c[4], c[0], c[1], c[2]))
    return cells


def build_attack_states():
    sts, sid = [], 0
    for board, hero, sz, k, stratum in pick_cells():
        for ftb in FTB_LEVELS:
            for b in B_LEVELS:
                for n in N_LEVELS:
                    s = AttackState(sid, hero, board, sz, b, ftb, n)
                    s.nbet = k
                    s.stratum = stratum
                    sts.append(s)
                    sid += 1
    return sts


def build_defend_states():
    """옛 fixture 의 수비 READ 상태를 **그대로** 쓴다. 대조군이다."""
    return [s for s in QF.build_states()
            if s.group == 'READ' and s.channel == 'D']


if __name__ == '__main__':
    import time
    t0 = time.time()
    cells = pick_cells()
    print('공격 셀 %d' % len(cells))
    for board, hero, sz, k, st in cells:
        print('  층%d  %-10s %-5s sz %.2f   벳최적 %2d/16'
              % (st, ''.join(board), ''.join(hero), sz, k))
    A = build_attack_states()
    D = build_defend_states()
    evs = {s.sid: s.ev_actions() for s in A}
    nbet = sum(1 for s in A
               if max(evs[s.sid], key=lambda k: evs[s.sid][k]) == 'bet')
    # ftb 에 따라 최적이 뒤집히는 (셀, b) 조합
    flip = {}
    for s in A:
        best = max(evs[s.sid], key=lambda k: evs[s.sid][k])
        flip.setdefault((tuple(s.board), tuple(s.hero), s.sz, s.b_true),
                        set()).add(best)
    nf = sum(1 for v in flip.values() if len(v) > 1)
    print('공격 상태 %d   수비 상태 %d' % (len(A), len(D)))
    print('최적=bet 비율 %.3f   ftb 로 뒤집히는 (셀,b) %d/%d   %.1fs'
          % (nbet / float(len(A)), nf, len(flip), time.time() - t0))
