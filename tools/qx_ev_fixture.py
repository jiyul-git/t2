#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QX_EV_VALIDATION decision-state fixture + paired continuation-EV. 읽기 전용.

사전등록 QX_EV_VALIDATION_PREREG.md 1·2·3·4절.

상태마다 상대의 **진짜 정책**(b_true 등)을 fixture 가 정하고, 봇에게는 같은
파라미터에서 표본 n 으로 만든 **공개 opp_est** 만 준다. oracle 만 b_true 를 쓴다.

EV 는 showdown equity 가 아니다 — fold equity · 리버 베팅 · 스택 이동을 넣고,
한 상태의 모든 후보 행동이 같은 난수 표본을 공유한다(common random numbers).
"""
from __future__ import print_function

import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import bot
import plan as PL
import persona as PS
import ranges as R
import reads as RD

FIX_SEED = 20260925
MC = 240                 # 상태당 연속구간 표본
EQ_SIMS = 400

HERO_HANDS = (['Ah', 'Jd'], ['Qs', 'Qc'], ['9h', '8h'])
BOARDS = (['Kc', '7d', '2s', '5h'], ['Jh', 'Th', '4c', '2d'])
POT = 1000.0
STACK = 6000.0


def _cache():
    if not hasattr(_cache, 'd'):
        _cache.d = {}
    return _cache.d


def ranges_for(board):
    """공개 정보로 만든 상대 레인지를 밸류/블러프로 가른다."""
    key = tuple(board)
    c = _cache()
    if key not in c:
        base = R.preflop_range('TAG', 'BTN', 'open', 40, set(board))
        b3 = board[:3]
        val = R.narrow(base, b3, 0.25, 'top')
        blf = R.narrow(base, b3, 0.25, 'bottom')
        c[key] = (val, blf)
    return c[key]


def hero_equities(hero, board):
    """히어로의 쇼다운 승률 — 밸류 레인지 대비 / 블러프 레인지 대비.
    실제 카드 평가에서 나온다."""
    key = (tuple(sorted(hero)), tuple(board))
    c = _cache()
    k2 = ('eq',) + key
    if k2 not in c:
        val, blf = ranges_for(board)
        ev = bot.equity_vs_combos(hero, board, [val], sims=EQ_SIMS, seed=FIX_SEED)
        eb = bot.equity_vs_combos(hero, board, [blf], sims=EQ_SIMS, seed=FIX_SEED + 1)
        c[k2] = (float(ev), float(eb))
    return c[k2]


class State(object):
    """decision-state 하나. 공개 상태 + 상대의 진짜 정책 + 공개 추정치."""

    def __init__(self, sid, channel, group, hero, board, sz, b_true, n_obs,
                 barrel_true=0.45, f_bluff=0.78, f_value=0.18, sz_river=0.62):
        self.sid = sid
        self.channel = channel          # 'D' or 'A'
        self.group = group              # 'GEN' or 'READ'
        self.hero = hero
        self.board = board
        self.sz = sz                    # 벳 크기 (팟 대비)
        self.b_true = b_true            # 상대 벳의 진짜 블러프 비율
        self.n_obs = n_obs              # 공개 표본 크기
        self.barrel_true = barrel_true
        self.f_bluff = f_bluff          # 내가 치면 블러프가 접을 확률
        self.f_value = f_value
        self.sz_river = sz_river
        self.tocall = POT * sz
        self.pot_live = POT + self.tocall
        self.eq_val, self.eq_blf = hero_equities(hero, board)

    # ---------- 공개 추정치 ----------
    def book(self):
        """진짜 정책과 정합한 합성 관측 장부. 관찰자 구분 없이 동일 기록."""
        bk = RD.Book()
        r = bk.rec(1, 2)
        n = self.n_obs
        r['hands'] = n
        r['facing_bet'] = n
        # 상대가 '접는 빈도' — 블러프를 많이 치는 사람은 적게 접는다
        ftb = max(0.05, min(0.95, 1.0 - self.b_true))
        r['fold_to_bet'] = int(round(n * ftb))
        for st in ('flop', 'turn', 'river'):
            r['fb_' + st] = n
            r['f2b_' + st] = int(round(n * ftb))
        r['cbet_opp'] = n
        r['cbet'] = int(round(n * (0.40 + 0.40 * self.b_true)))
        r['barrel_opp'] = n
        r['barrel'] = int(round(n * self.barrel_true))
        r['vpip'] = int(round(n * 0.26))
        r['pfr'] = int(round(n * 0.15))
        r['showdowns'] = max(2, n // 4)
        r['sd_weak'] = int(round(r['showdowns'] * self.b_true))
        r['sd_strong'] = r['showdowns'] - r['sd_weak']
        r['sz_n'] = n
        r['sz_sum'] = n * self.sz
        r['sz_sq'] = n * self.sz * self.sz
        r['sz_big'] = int(round(n * (0.5 if self.sz >= 1.0 else 0.1)))
        return bk

    def est_for(self, prof, rng):
        return RD.perceived_profile(self.book(), 1, 2, prof, rng)

    # ---------- 연속구간 ----------
    def _rollout(self, u_bet, u_win, pot_after, hero_paid, is_bluff, hero_eq_now):
        """리버 한 스트리트. 히어로 정책은 모든 arm 에서 동일하다.

        난수를 인자로 받는다 — 같은 상태의 모든 후보 행동이 같은 표본을 쓰게
        하려면 RNG 객체를 공유하는 것으로는 부족하다(행동마다 소비 횟수가 다르면
        스트림이 어긋난다). 뽑아 둔 값을 그대로 넘긴다.
        """
        p_bet = (self.barrel_true if not is_bluff else self.b_true)
        if u_bet < p_bet:
            bet = self.sz_river * pot_after
            if bet > STACK - hero_paid:
                bet = max(0.0, STACK - hero_paid)
            need = bet / (pot_after + 2.0 * bet) if (pot_after + bet) > 0 else 1.0
            if hero_eq_now >= need:                    # 고정 정책: 팟오즈 콜
                return ((pot_after + bet) if u_win < hero_eq_now
                        else -(hero_paid + bet))
            return -hero_paid                          # 폴드
        return pot_after if u_win < hero_eq_now else -hero_paid

    def ev_actions(self):
        """후보 행동별 EV (팟 대비 비율). common random numbers."""
        draws = []
        rng = random.Random(FIX_SEED * 7919 + self.sid)
        for _ in range(MC):
            draws.append((rng.random(), rng.random(), rng.random(), rng.random()))

        def run(action):
            tot = 0.0
            for u_type, u_r1, u_r2, u_r3 in draws:
                is_bluff = u_type < self.b_true
                eq = self.eq_blf if is_bluff else self.eq_val
                if action == 'fold':
                    tot += 0.0
                elif action == 'call':
                    tot += self._rollout(u_r2, u_r3, self.pot_live + self.tocall,
                                         self.tocall, is_bluff, eq)
                elif action == 'check':
                    tot += self._rollout(u_r2, u_r3, POT, 0.0, is_bluff, eq)
                elif action == 'bet':
                    bet = POT * self.sz
                    folds = self.f_bluff if is_bluff else self.f_value
                    if u_r1 < folds:
                        tot += POT
                    else:
                        tot += self._rollout(u_r2, u_r3, POT + 2.0 * bet, bet,
                                             is_bluff, eq)
            return tot / (MC * POT)

        if self.channel == 'D':
            return {'fold': run('fold'), 'call': run('call')}
        return {'check': run('check'), 'bet': run('bet')}


def build_states():
    """GEN / READ x D / A."""
    out = []
    sid = 0
    prior_b = RD.PRIOR['bluff'] / 10.0
    for ch in ('D', 'A'):
        for hero in HERO_HANDS:
            for board in BOARDS:
                # GEN — 상대는 모집단 기준, 가격만 흔든다
                for sz in (0.30, 0.60, 1.00):
                    out.append(State(sid, ch, 'GEN', hero, board, sz,
                                     prior_b, 40))
                    sid += 1
                # READ — 가격 고정, 진짜 블러프 비율을 극단으로
                for b in (0.15, 0.35, 0.55, 0.75):
                    for n in (6, 40):
                        out.append(State(sid, ch, 'READ', hero, board, 0.66,
                                         b, n))
                        sid += 1
    return out


def bot_action(state, prof, rng):
    """production 판단으로 이 상태에서의 행동(또는 혼합 확률)을 정한다."""
    est = state.est_for(prof, rng)
    if state.channel == 'D':
        rv = PL.line_bluff_prior(est, 'turn', 1, state.sz, state.board, False)
        need = float(PL.calldown_need(prof, state.hero, state.board, 'turn',
                                      state.pot_live, state.tocall, 1.0, rv, 0,
                                      est, n_opp=1, rng=rng))
        eq_true = (state.b_true * state.eq_blf
                   + (1.0 - state.b_true) * state.eq_val)
        return {'call': 1.0 if eq_true >= need else 0.0,
                'fold': 0.0 if eq_true >= need else 1.0}, need
    p, _ = PL.decide_aggression(prof, state.board, 'turn', 'giveup', 0.20, 1,
                                False, True, 0, rng, opp_est=est, outs=0)
    p = max(0.0, min(1.0, float(p)))
    return {'bet': p, 'check': 1.0 - p}, p


def regret_of(state, mix, evs):
    best = max(evs.values())
    return sum(w * (best - evs[a]) for a, w in mix.items())


if __name__ == '__main__':
    import json
    import time
    import fieldsim as FS
    t0 = time.time()
    sts = build_states()
    print('states: %d  (D %d / A %d, GEN %d / READ %d)'
          % (len(sts), sum(1 for s in sts if s.channel == 'D'),
             sum(1 for s in sts if s.channel == 'A'),
             sum(1 for s in sts if s.group == 'GEN'),
             sum(1 for s in sts if s.group == 'READ')))
    evs = {s.sid: s.ev_actions() for s in sts}
    print('EV 계산 %.1fs' % (time.time() - t0))
    import statistics as st
    spread = [max(v.values()) - min(v.values()) for v in evs.values()]
    print('상태별 EV 격차(팟 대비): mean %.4f  sd %.4f  min %.4f  max %.4f'
          % (st.mean(spread), st.pstdev(spread), min(spread), max(spread)))
    flips = {}
    for s in sts:
        if s.group != 'READ':
            continue
        best = max(evs[s.sid], key=lambda a: evs[s.sid][a])
        flips.setdefault((s.channel, s.hero[0] + s.hero[1], tuple(s.board)), set()).add(best)
    nflip = sum(1 for v in flips.values() if len(v) > 1)
    print('READ 에서 b_true 에 따라 최적 행동이 뒤집힌 조합: %d/%d' % (nflip, len(flips)))
    f = FS.Field(entries=100, seed=999601, fmt='standard')
    prof = f.players[3]['prof']
    t1 = time.time()
    tot = 0.0
    for s in sts:
        mix, _ = bot_action(s, prof, random.Random(FIX_SEED + s.sid))
        tot += regret_of(s, mix, evs[s.sid])
    print('프로필 1개 regret 합 %.4f  (%.2fs)' % (tot / len(sts), time.time() - t1))
