#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NUMERIC_BUNDLE_V7 독립 과제 배터리. 읽기 전용.

사전등록 NUMERIC_BUNDLE_V7_PREREG.md 2절.

production 판단 진입점 두 개를 직접 부른다. 핸드를 돌리지 않는다.
oracle 은 **공개 opp_est 와 게임 상태에서만** 만든다 — target 의 hidden
profile/concepts 를 쓰지 않는다. Q / tier 를 종속변수로 쓰지 않는다.

점수는 격자 위 oracle 과 봇 응답의 Pearson r 이다. 상대를 안 보면 r=0,
수준만 옮기면 r 이 안 오른다.
"""
from __future__ import print_function

import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persona as PS
import plan as PL
import reads as RD

SEED = 20260924
REPS = 4
GRID = 9

HERO = ['Ah', 'Qd']
BOARD3 = ['Kc', '7d', '2s']          # 건조
BOARD3_WET = ['Jh', 'Th', '9c']      # 습윤
BOARD4 = BOARD3 + ['5h']
BOARD4_WET = BOARD3_WET + ['4d']

# QX_E 에 들어가는 군. F7 은 **제외**한다 — 파일럿에서 응답(pc)이 격자 위에서
# 상수였다. spr/blocker 가 읽히는 유일한 경로라 배터리에는 남겨 두고
# 커버리지·응답불변 측정에만 쓴다. 점수에 넣으면 전원 0 을 더해 희석만 된다.
FAMILIES = ('F1_freq', 'F2_street', 'F3_sizing', 'F4_sample',
            'F5_price', 'F6_texture')
FAMILIES_ALL = FAMILIES + ('F7_commit',)

# decide_aggression 은 plan 에 따라 전혀 다른 분기를 탄다.
#   giveup/showdown  -> cbet_freq 이탈 경로 (fold_equity 를 안 읽는다)
#   semibluff 등     -> 블러프 경로 (fold_equity x street_gap 을 곱한다)
# 한쪽만 부르면 fold_equity 가 배터리에서 구조적으로 도달 불가능해진다.
# 두 경로를 다 부르고 평균한다.
AGGR_PLANS = (('giveup', 0),
              ('semibluff', 9))


def base_est(n=60, conf=0.9):
    p = RD.PRIOR
    ftb = p['fold_to_bet']
    return {
        'vpip': p['vpip'], 'pfr': p['pfr'], 'rfi_rel': p['rfi_rel'],
        'pf_limp': p['pf_limp'], 'pf_3bet': p['pf_3bet'], 'pf_4bet': p['pf_4bet'],
        'pf_fold_to_3bet': p['pf_fold_to_3bet'],
        'pf_fold_to_4bet': p['pf_fold_to_4bet'],
        'aggr': p['aggr'], 'cbet': p['cbet'], 'barrel': p['barrel'],
        'bluff': p['bluff'], 'ftb': ftb, 'ftb_flop': ftb, 'ftb_turn': ftb,
        'ftb_river': ftb, 'sz_mean': p['sz_mean'], 'sz_sd': p['sz_sd'],
        'sz_big': 0.15, 'sz_n': 24, 'sz_river': p['sz_mean'],
        'wtsd': p['wtsd'], 'tight': p['tight'],
        'confidence': conf, 'n': n,
    }


def _lin(lo, hi, k=GRID):
    return [lo + (hi - lo) * i / float(k - 1) for i in range(k)]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, sxy / math.sqrt(sxx * syy)))


def _rng(tag, i, r):
    return random.Random((SEED * 1000003 + hash(tag) % 10 ** 6 * 97
                          + i * 131 + r) & 0x7fffffff)


def _aggr(prof, est, board, street, tag, i, plan='giveup', rel=0.18,
          initiative=True, outs=0):
    """무저항에서 칠 확률. REPS 회 평균."""
    tot = 0.0
    for r in range(REPS):
        p, _ = PL.decide_aggression(prof, board, street, plan, rel, 1, False,
                                    initiative, 0, _rng(tag, i, r),
                                    opp_est=est, outs=outs)
        tot += float(p)
    return tot / REPS


def _aggr_both(prof, est, board, street, tag, i, rel=0.18, initiative=True):
    """두 분기(이탈 지속벳 / 블러프)를 다 부르고 평균한다."""
    tot = 0.0
    for pl, outs in AGGR_PLANS:
        tot += _aggr(prof, est, board, street, '%s:%s' % (tag, pl), i,
                     plan=pl, rel=rel, initiative=initiative, outs=outs)
    return tot / len(AGGR_PLANS)


def _need(prof, est, board, street, pot, tocall, tag, i, n_barrels=1):
    """콜 문턱. REPS 회 평균.

    `read` 는 production 이 넘기는 것과 같은 것 — line_bluff_prior 의 스칼라다
    (session.py:924). 이것도 공개 est + 라인/사이즈/보드에서만 나온다.
    """
    tot = 0.0
    sz_frac = tocall / max(1.0, float(pot) - tocall)
    for r in range(REPS):
        rv = PL.line_bluff_prior(est, street, n_barrels, sz_frac, board, False)
        tot += float(PL.calldown_need(prof, HERO, board, street, pot, tocall,
                                      1.0, rv, 0, est, n_opp=1,
                                      rng=_rng(tag, i, r)))
    return tot / REPS


# ------------------------------------------------------------------ families

def f1_freq(prof):
    xs, ys = [], []
    for i, ftb in enumerate(_lin(0.20, 0.80)):
        e = base_est()
        e['ftb'] = e['ftb_flop'] = e['ftb_turn'] = e['ftb_river'] = ftb
        ys.append(_aggr_both(prof, e, BOARD3, 'flop', 'f1', i))
        xs.append(ftb)
    return pearson(xs, ys), sum(ys) / len(ys), ys


def f2_street(prof):
    """플랍과 턴의 fold 성향을 **교차 격자**로 독립하게 흔든다.

    한쪽을 다른 쪽의 함수(1-x)로 두면 r(xf,yt) = -r(xt,yt) 가 되어 판별 점수가
    2*r(xt,yt) 로 퇴화한다. 직교 격자여야 "해당 스트리트만 보는가"를 잰다.
    """
    yt, xt, xf = [], [], []
    i = 0
    for ftb_t in (0.25, 0.50, 0.75):
        for ftb_f in (0.25, 0.50, 0.75):
            e = base_est()
            e['ftb'] = RD.PRIOR['fold_to_bet']
            e['ftb_flop'] = ftb_f
            e['ftb_turn'] = ftb_t
            e['ftb_river'] = RD.PRIOR['fold_to_bet']
            yt.append(_aggr_both(prof, e, BOARD4, 'turn', 'f2', i))
            xt.append(ftb_t)
            xf.append(ftb_f)
            i += 1
    # 해당 스트리트를 보는가 — 다른 스트리트 추종분을 뺀다
    return pearson(xt, yt) - pearson(xf, yt), sum(yt) / len(yt), yt


def f3_sizing(prof):
    """사이즈에서 나온 필요 블러프 비율 alpha 와 관측 블러프 성향 b̂ 의 대비."""
    xs, ys = [], []
    pot = 1000.0
    i = 0
    for sz in (0.33, 0.66, 1.20):
        for bl in (2.0, 4.5, 8.0):
            tocall = pot * sz
            alpha = sz / (1.0 + 2.0 * sz)          # 콜이 본전이 되는 블러프 비율
            bhat = bl / 10.0
            e = base_est()
            e['bluff'] = bl
            e['sz_mean'] = sz
            e['sz_big'] = 0.10 if sz < 0.8 else 0.55
            ys.append(_need(prof, e, BOARD4, 'turn', pot + tocall, tocall,
                            'f3', i))
            xs.append(alpha - bhat)
            i += 1
    return pearson(xs, ys), sum(ys) / len(ys), ys


def f4_sample(prof):
    """같은 극단 관측률에 표본만 키운다. 베이즈 수축만큼만 움직여야 한다."""
    xs, ys = [], []
    prior = RD.PRIOR['fold_to_bet']
    obs = 0.85
    for i, n in enumerate((1, 2, 3, 6, 12, 20, 32, 48, 64)):
        e = base_est(n=n, conf=min(1.0, 0.25 + 0.05 * n))
        e['ftb'] = e['ftb_flop'] = e['ftb_turn'] = e['ftb_river'] = obs
        post = (n * obs + 12.0 * prior) / (n + 12.0)
        ys.append(_aggr_both(prof, e, BOARD3, 'flop', 'f4', i))
        xs.append(post - prior)
    return pearson(xs, ys), sum(ys) / len(ys), ys


def f5_price(prof):
    """가격과 상대 블러프 성향을 같이 본다."""
    xs, ys = [], []
    pot = 1000.0
    i = 0
    for sz in (0.25, 0.60, 1.00):
        for bl in (2.0, 4.5, 8.0):
            tocall = pot * sz
            need_oracle = tocall / (pot + tocall + tocall)
            ys.append(_need(prof, {**base_est(), 'bluff': bl}, BOARD4, 'turn',
                            pot + tocall, tocall, 'f5', i))
            xs.append(need_oracle - bl / 10.0)
            i += 1
    return pearson(xs, ys), sum(ys) / len(ys), ys


def f6_texture(prof):
    xs, ys = [], []
    i = 0
    for dry, board in ((1.0, BOARD3), (-1.0, BOARD3_WET)):
        for ftb in _lin(0.20, 0.80, 5):
            e = base_est()
            e['ftb'] = e['ftb_flop'] = e['ftb_turn'] = e['ftb_river'] = ftb
            ys.append(_aggr_both(prof, e, board, 'flop', 'f6', i))
            xs.append((ftb - 0.5) * dry)
            i += 1
    return pearson(xs, ys), sum(ys) / len(ys), ys


_RANGE = None


def _range():
    """공개 정보로 만든 일반 레인지. hidden profile 을 쓰지 않는다."""
    global _RANGE
    if _RANGE is None:
        import ranges as R
        _RANGE = R.preflop_range('TAG', 'BTN', 'open', 40, set(BOARD3))
    return _RANGE


def f7_commit(prof):
    """스택 깊이(SPR)와 상대 폴드 성향을 같이 본다. make_plan 의 pot commitment.

    make_plan 이 spr 과 blocker 를 읽는 유일한 경로다. decide_aggression /
    calldown_need 만으로는 두 concept 이 배터리에서 도달 불가능하다.
    """
    rr = _range()
    xs, ys = [], []
    pot = 1000.0
    i = 0
    for stack in (1500.0, 3000.0, 6000.0, 12000.0):
        spr = stack / pot
        for ftb in (0.25, 0.50, 0.75):
            e = base_est()
            e['ftb'] = e['ftb_flop'] = e['ftb_turn'] = e['ftb_river'] = ftb
            tot = 0.0
            for r in range(2):
                st = PL.make_plan(HERO, BOARD3, rr, rr, prof, pot, stack,
                                  'flop', seed=SEED + i * 17 + r, n_opp=1,
                                  to_act_behind=0, initiative=True, opp_est=e,
                                  opp_stack_bb=50, tilt=0.0, bb_chips=100)
                tot += float(st.get('pc', 0.0) or 0.0)
            ys.append(tot / 2.0)
            # 얕을수록 커밋, 상대가 덜 접을수록 커밋
            xs.append(1.0 / (1.0 + spr) + 0.5 * (0.5 - ftb))
            i += 1
    return pearson(xs, ys), sum(ys) / len(ys), ys


def g_control(prof):
    """대조군 — 상대 정보가 전혀 안 변한다. 자기 가격/패 계산만."""
    # G1: 순수 팟오즈 추종
    xs, ys = [], []
    pot = 1000.0
    for i, sz in enumerate(_lin(0.15, 1.40)):
        tocall = pot * sz
        ys.append(_need(prof, base_est(), BOARD4, 'turn', pot + tocall,
                        tocall, 'g1', i))
        xs.append(tocall / (pot + tocall + tocall))
    r1 = pearson(xs, ys)
    lvl = sum(ys) / len(ys)
    ys1 = list(ys)
    # G2: 자기 패 강도 추종 (상대는 prior 고정)
    xs, ys = [], []
    for i, rel in enumerate(_lin(0.05, 0.95)):
        ys.append(_aggr(prof, base_est(), BOARD3, 'flop', 'g2', i,
                        plan='value_2street', rel=rel))
        xs.append(rel)
    r2 = pearson(xs, ys)
    return 0.5 * (r1 + r2), 0.5 * (lvl + sum(ys) / len(ys)), ys1 + ys


def response_vector(prof):
    """배터리의 **격자점별** 응답 전체. 개입이 응답을 바꾸는지 보는 용도.

    평균이 아니라 점별 값을 본다 — 도달은 했는데 출력이 한 점도 안 바뀌는
    경우와 바뀌는 경우를 가르기 위해서다.
    """
    v = []
    for _, fn in _FAMILY_FNS:
        v.extend(round(float(x), 9) for x in fn(prof)[2])
    v.extend(round(float(x), 9) for x in g_control(prof)[2])
    return v


def evaluate(prof):
    """한 프로필의 배터리 점수. QX_E, QX_G, 군별 점수, 평균 응답 수준."""
    fam = {}
    lvl = {}
    vec = []
    for name, fn in _FAMILY_FNS:
        s, l, ys = fn(prof)
        fam[name] = s
        lvl[name] = l
        vec.extend(round(float(x), 9) for x in ys)
    g, gl, gys = g_control(prof)
    vec.extend(round(float(x), 9) for x in gys)
    scored = [fam[k] for k in FAMILIES]
    return {
        'QX_E': sum(scored) / len(scored),
        'QX_G': g,
        'families': fam,
        'level': sum(lvl[k] for k in FAMILIES) / len(FAMILIES),
        'levels': lvl,
        'vector': vec,
        'level_G': gl,
    }


_FAMILY_FNS = (('F1_freq', f1_freq), ('F2_street', f2_street),
               ('F3_sizing', f3_sizing), ('F4_sample', f4_sample),
               ('F5_price', f5_price), ('F6_texture', f6_texture),
               ('F7_commit', f7_commit))


if __name__ == '__main__':
    import json
    import time
    import fieldsim as FS
    f = FS.Field(entries=100, seed=999501, fmt='standard')   # 버림 시드
    p = f.players[1]['prof']
    t0 = time.time()
    out = evaluate(p)
    print('one evaluation: %.2fs' % (time.time() - t0))
    print(json.dumps(out, indent=1, sort_keys=True))
