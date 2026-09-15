#!/usr/bin/env python3
"""**인식 정확도 축**이 이름값을 하는가. 읽기 전용이다.

  python3 tools/axis_accuracy.py
  python3 tools/axis_accuracy.py --n 600 --axis sizing_tell

성향 축은 성격이 둘로 갈린다.

  빈도 축   "이 행동을 더 한다"      → 뒤집힘·빈도로 잰다 (cf_* 도구들)
  정확도 축 "이걸 더 잘 읽는다"      → **오차**로 재야 한다        ← 이 도구

정확도 축은 뒤집힘 비율로 재면 안 된다. 잘 읽는 사람과 못 읽는 사람의
행동이 **같아도** 축은 제대로 작동할 수 있고(상황이 쉬우면 둘 다 맞힌다),
반대로 행동이 갈려도 그게 정확도 때문인지 알 수 없다.
그래서 각 축의 **호출 지점에서** |인식값 − 참값| 을 직접 잰다.

판정
  ● 작동    축이 오를수록 오차가 단조 감소하고, 9에서 1의 절반 이하
  ◐ 부분    단조 감소하지만 9에서도 오차가 절반 초과
  ○ 무반응  오차가 축과 무관 (이름값을 못 한다)

각 축의 참값/인식값이 어느 줄에서 나오는지는 아래 SITES 에 적어 두었다.
"""
import argparse, os, random, statistics as ST, sys
from collections import OrderedDict

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, D)

import bot, depth, persona as PS, plan as PL, ranges as RG, texture as TX

RANKS = '23456789TJQKA'; SUITS = 'cdhs'
DECK = [r+s for r in RANKS for s in SUITS]
LEVELS = [1, 3, 5, 7, 9]


def prof_at(base, axis, v):
    p = {'concepts': dict(base['concepts']), 'temper': dict(base['temper']),
         'latent': dict(base.get('latent') or {}), 'id': base.get('id')}
    if axis in p['concepts']: p['concepts'][axis] = float(v)
    elif axis in p['temper']: p['temper'][axis] = float(v)
    else: raise KeyError(axis)
    p.update(PS.derive(p))
    return p


def deal(rng, nb):
    d = DECK[:]; rng.shuffle(d)
    return d[:2], d[2:2+nb]


# ---------------------------------------------------------------- 축별 정의
# 반환: (참값, 인식값). 호출 지점을 주석에 적는다.

def site_outs(rng, p, v):
    """plan.py:277  outs = outs_true * calc_noise(prof,'outs',rng)

    아웃이 0인 핸드는 곱셈이라 오차가 구조적으로 0 이다. 빼고 잰다 —
    안 그러면 표본의 대부분이 0 이라 중앙값이 전부 0 으로 나온다."""
    for _ in range(40):
        hero, board = deal(rng, rng.choice([3, 4]))
        t = PL.draw_strength(hero, board)
        if t > 0:
            break
    else:
        raise ValueError('아웃 있는 핸드 없음')
    q = int(round(t * PS.calc_noise(prof_at(p, 'outs', v), 'outs', rng)))
    return t, q


def site_potodds(rng, p, v):
    """plan.py:620  nz = clamp(calc_noise(prof,'potodds',rng), 0.65, 1.55)"""
    nz = PS.calc_noise(prof_at(p, 'potodds', v), 'potodds', rng)
    return 1.0, max(0.65, min(1.55, nz))


def site_blocker(rng, p, v):
    """plan.py:283  blk = blk_true * clamp((sk('blocker')-1)/7, 0, 1)"""
    # **상대 레인지에서 히어로 카드를 빼면 안 된다.** blocker_score 는
    # '상대 강한 콤보 중 내 카드를 쓰는 것'을 세므로, 히어로를 dead 로 넣어
    # 만든 레인지에서는 구조적으로 항상 0 이 나온다. 엔진은 그렇게 만들지
    # 않는다 — session.py:370 의 preflop_range 는 dead 가 set(board) 뿐이다.
    for _ in range(40):
        hero, board = deal(rng, 3)
        rngo = bot.range_combos(rng.uniform(0.15, 0.45), board)
        t = RG.blocker_score(hero, rngo, board)
        if t > 0:
            break               # 0 이면 곱셈이라 오차가 구조적으로 0 이다
    else:
        raise ValueError('블로커 점수 0 아닌 핸드 없음')
    g = max(0.0, min(1.0, (PS.sk(prof_at(p, 'blocker', v), 'blocker') - 1.0)/7.0))
    return t, t * g


def site_board_texture(rng, p, v):
    """texture.perceived — cbet_multiplier 를 1.0 쪽으로 눌러 읽는다"""
    _, board = deal(rng, 3)
    t = TX.cbet_multiplier(board)
    q = TX.perceived(board, PS.sk(prof_at(p, 'board_texture', v), 'board_texture'),
                     rng, TX.cbet_multiplier)
    return t, q


def _sz_seen(prof, sz_true, street, est):
    rd = PS.read_opponent(prof, est)
    return PS.size_read(prof, PS.opp_size_norm(rd, sz_true, street))


def _fake_est(rng):
    ftb = rng.uniform(0.30, 0.75)
    return {'confidence': rng.uniform(0.4, 0.9), 'n': rng.randint(15, 60),
            'ftb': ftb, 'fold': ftb, 'bluff': rng.uniform(2, 8),
            'aggr': rng.uniform(2, 8), 'sizing_tell': rng.uniform(1, 9),
            'range_read': rng.uniform(1, 9), 'sz_mean': rng.uniform(0.4, 0.9),
            'sz_sd': rng.uniform(0.10, 0.35), 'sz_n': rng.randint(4, 20),
            'sz_big': rng.uniform(0.0, 0.4), 'type': None}


def site_size_read_in(rng, p, v):
    """persona.size_read **단독**, 실전 구간. 여기서 0 이면 이름값을 못 한다.
    (persona.py:755  `if s <= 2.0: return s`)"""
    sz = rng.choice([0.40, 0.55, 0.66, 0.75, 1.0, 1.1])
    return sz, PS.size_read(prof_at(p, 'sizing_tell', v), sz)


def site_sizing_tell(rng, p, v):
    """opp_size_norm 경유, 실전 구간. 이건 오차가 아니라 **상대 기준 보정**이다.
    '항상 크게 치는 사람의 1팟'을 1팟으로 안 보는 것 — 커질수록 정상이다."""
    sz = rng.choice([0.40, 0.55, 0.66, 0.75, 1.0, 1.1])
    est = _fake_est(rng)
    return sz, _sz_seen(prof_at(p, 'sizing_tell', v), sz, 'flop', est)


def site_sizing_tell_ob(rng, p, v):
    """같은 자리, **정의역 밖**(2.5~9팟). size_read 가 여기서만 작동한다.

    이 축의 주장은 "실제 사이즈를 정확히 본다"가 **아니다.**
    docstring 은 "개념이 높을수록 정의역 밖임을 인식해 2.0 쪽으로 되돌려
    해석한다" 고 말한다. 그러니 참값은 실제 사이즈가 아니라 **경계 2.0** 이다.
    실제 사이즈와의 거리로 재면 잘하는 사람이 더 틀리는 것처럼 보인다."""
    sz = rng.choice([2.5, 3.0, 4.0, 6.0, 9.0])
    return 2.0, PS.size_read(prof_at(p, 'sizing_tell', v), sz)


def site_range_read(rng, p, v):
    """ranges.perceived_range — 액션 반영을 얼마나 하는가.
    오차 = 반영 못 하고 남긴 콤보 비율 (0 이면 완전 반영)"""
    hero, board = deal(rng, rng.choice([3, 4]))
    base = bot.range_combos(rng.uniform(0.25, 0.50), board)
    acts = [('flop', 'bet', rng.choice([0.4, 0.66, 1.0]))]
    if len(board) > 3:
        acts.append(('turn', 'bet', rng.choice([0.5, 0.75, 1.2])))
    full = RG.narrow_by_actions(base, board, acts, None, None)
    q = RG.perceived_range(base, board, acts, prof_at(p, 'range_read', v), None)
    span = max(1, len(base) - len(full))
    return 0.0, (len(q) - len(full))/float(span)


def site_spr(rng, p, v):
    """depth.depth_feel — acc = 0.10 + 0.80*min(1, sk('spr')/8)
    참값 = 왜곡 없는 base_feel. edge 를 줘야 축이 보인다"""
    bb = rng.uniform(8, 80)
    edge = rng.choice([-0.5, 0.5])
    t = depth.depth_feel(bb, None)
    q = depth.depth_feel(bb, prof_at(p, 'spr', v), sk_fn=PS.sk,
                         temper_fn=PS.temper, edge=edge)
    return t, q


def _open_err(rng, p, axis, v, hold):
    """open_pct 는 축이 셋 섞여 있다 — pf_range(폭), positional(곡선),
    adapt_mult(별도). 하나를 재려면 나머지를 9 로 고정해야 한다."""
    import gto
    pos = rng.choice(['UTG', 'LJ', 'HJ', 'CO', 'BTN'])
    seats = rng.choice([6, 8, 9])
    q0 = prof_at(p, axis, v)
    for k, kv in hold.items():
        q0 = prof_at(q0, k, kv)
    return gto.rfi(pos, seats), PS.open_pct(q0, pos, seats=seats)


def site_pf_range(rng, p, v):
    """persona.open_pct 의 폭 정확도. positional 은 9 로 고정한다"""
    return _open_err(rng, p, 'pf_range', v, {'positional': 9})


def site_positional(rng, p, v):
    """persona.open_pct 의 포지션 곡선. pf_range 는 9 로 고정한다"""
    return _open_err(rng, p, 'positional', v, {'pf_range': 9})


SITES = OrderedDict([
    ('outs',              (site_outs,              '아웃 개수')),
    ('potodds',           (site_potodds,           'need 배수 (1.0 이 정확)')),
    ('blocker',           (site_blocker,           '블로커 점수')),
    ('board_texture',     (site_board_texture,     'cbet 배수')),
    ('sizing_tell·size_read', (site_size_read_in,  '실전 구간 ≤1.1팟')),
    ('sizing_tell·정의역밖',   (site_sizing_tell_ob, '2.5~9팟, 참값은 경계 2.0')),
    ('sizing_tell·opp_norm',  (site_sizing_tell,   '상대 기준 보정폭(오차 아님)')),
    ('range_read',        (site_range_read,        '미반영 콤보 비율')),
    ('spr',               (site_spr,               '깊이 인식 0~1')),
    ('pf_range',          (site_pf_range,          '오픈 폭 (positional=9 고정)')),
    ('positional',        (site_positional,        '오픈 폭 (pf_range=9 고정)')),
])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=600)
    ap.add_argument('--axis', default=None, help='하나만 본다')
    ap.add_argument('--seed', type=int, default=20260914)
    a = ap.parse_args()

    base = PS.make_player(random.Random(a.seed), 0.78, 0)
    names = [a.axis] if a.axis else list(SITES)
    print('# 인식 정확도 축 — 호출 지점에서 |인식값 − 참값| 을 잰다')
    print('# n=%d, 축을 1/3/5/7/9 로 고정하고 같은 상황을 다시 푼다\n' % a.n)
    print('%-22s %-24s %s' % ('축', '무엇의 오차인가',
                              '  '.join('%5d' % L for L in LEVELS) + '   판정'))
    rows = []
    for nm in names:
        fn, what = SITES[nm]
        errs = []
        for L in LEVELS:
            rng = random.Random(a.seed)          # 레벨마다 같은 상황
            e = []
            for _ in range(a.n):
                try:
                    t, q = fn(rng, base, L)
                except Exception:
                    continue
                e.append(abs(q - t))
            errs.append(ST.median(e) if e else float('nan'))
        e1, e9 = errs[0], errs[-1]
        mono = all(errs[i] >= errs[i+1] - 1e-12 for i in range(len(errs)-1))
        rise = all(errs[i] <= errs[i+1] + 1e-12 for i in range(len(errs)-1))
        if e1 <= 1e-12 and e9 <= 1e-12:
            mark = '○ 무반응 (양끝 오차 0)'
        elif e1 <= 1e-12 and rise:
            mark = '▲ 반대 — 축이 오를수록 오차가 는다'
        elif mono and e9 <= 0.5*e1:
            mark = '● 작동'
        elif e9 <= 0.9*e1:
            mark = '◐ 부분'
        else:
            mark = '○ 무반응'
        rows.append((nm, what, errs, mark))
        print('%-22s %-24s %s   %s'
              % (nm, what, '  '.join('%5.3f' % x for x in errs), mark))
    print()
    print('● 단조 감소 + 9에서 1의 절반 이하   ◐ 절반까지는 못 감   ○ 축과 무관')
    print('오차는 중앙값이다. 레벨마다 같은 시드로 같은 상황을 다시 푼다.')


if __name__ == '__main__':
    main()
