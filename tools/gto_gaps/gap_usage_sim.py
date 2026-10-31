#!/usr/bin/env python3
"""GTO 표의 빈 자리 빈도 — 봇 전용 예약 대회(고정 시드)에서 프리플랍 결정이 GTO 표로 정해졌는지,
표가 없어 예전 판단으로 떨어졌는지를 결정마다 센다.

  python3 tools/gto_gaps/gap_usage_sim.py <fmt> <seed_day> <out_json> [max_active_seconds]

읽기 전용 측정(런타임·데이터는 바꾸지 않는다). 대회 경로는 tools/gto_precision/spot_usage_sim.py
(precision_prep 브랜치)와 같다: scheduled_runtime.advance, 표준 프로필, 봇만, field_backend='real'.

결정마다 plan.preflop_plan 의 인자로 상황을 나누고(첫 진입 / 림프 팟 / 단독 오픈 받음 / 콜러 있는 오픈 받음 /
3벳 받은 오프너 / 콜드 3벳 / 4벳 받음 …), preflop.gto_pf_spot_freqs 를 감싸 그 결정에서 봇 훅(*_choice)이
GTO 값을 썼는지(full = 행동 전체, partial = 공격 빈도만, none = 표 없음)를 함께 남긴다.
키 = 상황 | 스택 버킷 | 자리(공격자>나) | 오픈 크기 구간. 스택 버킷 몫은 gto_pf 보간 규칙과 같다
(버킷 사이 결정은 두 버킷에 직선 몫으로 나눈다 — 그 버킷 기록이 생기면 쓰일 몫).
"""
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'

import gto_pf as G                     # noqa: E402
import live2 as L                      # noqa: E402
import play as PLY                     # noqa: E402
import plan as PL                      # noqa: E402
import preflop as PF                   # noqa: E402
import scheduled_runtime as SR         # noqa: E402
import tournament_store as TS          # noqa: E402

CUR = [None]                 # 지금 결정의 GTO 조회 결과들
ROWS = defaultdict(lambda: Counter())   # key → {'n','full','partial','none','pass_w','fold','icm', ...}
SIZES = defaultdict(Counter)            # key → 오픈/3벳 크기 분포
HANDS = [0]
DECS = Counter()


def _buckets(eff):
    b = G._load()['buckets']
    x = float(eff)
    if x < b[0] - G.EDGE_BB:
        return [('<10', 1.0)]
    x = max(b[0], min(b[-1], x))
    hi = next(i for i, v in enumerate(b) if v >= x)
    lo = max(0, hi - 1) if b[hi] > x else hi
    t = 0.0 if hi == lo else (x - b[lo]) / (b[hi] - b[lo])
    out = [(str(b[lo]), 1 - t)]
    if hi != lo:
        out.append((str(b[hi]), t))
    return [(k, w) for k, w in out if w > 0]


_orig_sf = PF.gto_pf_spot_freqs


def _wrapped_sf(spot, hand):
    r = _orig_sf(spot, hand)
    caller = sys._getframe(1).f_code.co_name
    if CUR[0] is not None and caller.startswith('gto_pf_') and caller.endswith('_choice'):
        CUR[0].append((spot['fn'], None if r is None else r[1],
                       None if r is None else dict(r[0])))
    return r


def _p9(pos, seats):
    try:
        return G.pos9(pos, seats) or ('%s@%d' % (pos, seats))
    except Exception:
        return '%s@%s' % (pos, seats)


def _sz(x):
    x = float(x or 0)
    return '%.2f' % (round(x * 4) / 4.0)


def _classify(k):
    """preflop_plan 인자 → (상황, 유효 스택, 공격자 자리 또는 None, 크기)."""
    pos, agg = k['pos'], k.get('aggressor_pos')
    bb = float(k['bb'])
    ante = k.get('ante', True)
    share = (1.0 / 9.0) if ante else 0.0
    nl = int(k.get('n_limpers') or 0)
    rl = int(k.get('raise_level') or 1)
    others = k.get('pf_other_live_actors')
    acted = k.get('pf_actor_acted')
    obb = float(k.get('open_bb') or 0)
    tc = float(k.get('to_call_bb') or 0)
    if agg is None and not nl:
        eff = PF.gto_pf_open_eff_bb(pos, bb, k.get('behind_stacks'), ante)
        return 'first_in', eff, None, None
    if agg is None:
        lim = k.get('pf_limper_pos')
        ltot = k.get('pf_limper_total_bb')
        eff = (min(bb + 1.0, float(ltot)) if ltot is not None else bb) + share
        if nl == 1 and lim == 'SB' and pos == 'BB' and others == 1:
            return 'limp_sb_vs_bb', eff, 'SB', None
        if nl == 1 and others == 1:
            return 'limp_single_behind', eff, lim, None      # 림퍼 1명 뒤에서(아이소/오버림프)
        return 'limp_multi', eff, None, '%d' % nl
    own_total = bb + max(0.0, obb - tc)
    eff = own_total
    if k.get('pf_aggressor_total_bb') is not None:
        eff = min(eff, float(k['pf_aggressor_total_bb']))
    eff += share
    if k.get('opener_allin'):
        if rl == 1 and not acted:
            sit = 'vs_jam' if not others and not nl else 'vs_jam_multi'
        elif rl == 2 and acted:
            sit = 'vs_3bjam' if not others else 'vs_3bjam_multi'
        else:
            sit = 'vs_allin_other_r%d' % rl
        return sit, eff, agg, None
    if acted is None or others is None:
        return 'unknown_ctx', eff, agg, _sz(obb)
    if rl == 1 and not acted:
        if nl:
            return 'vs_iso_after_limp', eff, agg, _sz(obb)       # 림프가 있었고 누가 레이즈 → 아직 행동 안 한 나
        if others:
            return 'vs_open_with_callers', eff, agg, _sz(obb)    # 오픈 + 콜러(스퀴즈/오버콜 자리)
        return 'vs_open', eff, agg, _sz(obb)
    if rl == 1 and acted:
        return 'limper_vs_raise', eff, agg, _sz(obb)             # 내가 림프 → 뒤에서 레이즈
    if rl == 2 and acted:
        return ('vs_3bet' if not others else 'vs_3bet_multi'), eff, agg, _sz(obb)
    if rl == 2:
        return 'cold_vs_3bet', eff, agg, _sz(obb)                # 행동 안 한 채로 오픈+3벳을 받음
    if rl == 3 and acted:
        return ('vs_4bet' if not others else 'vs_4bet_multi'), eff, agg, _sz(obb)
    if rl == 3:
        return 'cold_vs_4bet', eff, agg, _sz(obb)
    return 'vs_5bet_plus', eff, agg, _sz(obb)


_orig_pp = PL.preflop_plan


def _wrapped_pp(profile, pos, hand, bb, rng, **k):
    CUR[0] = []
    out = _orig_pp(profile, pos, hand, bb, rng, **k)
    looks, CUR[0] = CUR[0], None
    try:
        _record(dict(k, pos=pos, bb=bb, hand=hand), looks, out)
    except Exception as exc:                                 # 측정이 대회를 죽이면 안 된다
        DECS['record_error'] += 1
        if DECS['record_error'] <= 3:
            print('[gap] record error %r' % (exc,), file=sys.stderr)
    return out


def _record(k, looks, out):
    seats = int(k.get('seats') or 8)
    sit, eff, agg, size = _classify(k)
    me = _p9(k['pos'], seats)
    pk = me if agg is None else '%s>%s' % (_p9(agg, seats), me)
    src = 'none'
    pass_w = 0.0
    for fn, s, f in looks:
        if s == 'full':
            src = 'full'
        elif s == 'partial' and src != 'full':
            src = 'partial'
            pass_w = float(f.get('pass', 0.0))
    icm = (float(k.get('bf') or 1.0) > PF.GTO_PF_BF_MAX
           or (sit == 'first_in' and not PF._gto_pf_icm_free(k.get('bf'), k.get('money_open'))))
    act = out[0] if out else None
    tbl = None                    # 첫 진입: 관문(ICM·머니점프)과 상관없이 표에 값이 있는가
    if sit == 'first_in':
        tbl = G.first_in(k['pos'], seats, eff, k['hand'], k.get('ante', True)) is not None
    DECS['all'] += 1
    DECS[src] += 1
    for bk, w in _buckets(eff):
        key = '|'.join((sit, bk, pk, size or '-'))
        r = ROWS[key]
        r['n'] += w
        r[src] += w
        if src == 'partial':
            r['pass_w'] += w * pass_w
        if icm:
            r['icm'] += w
        if tbl is not None:
            r['tbl_yes' if tbl else 'tbl_no'] += w
        if act == 'fold':
            r['fold'] += w
        if seats not in G.SEATS_OK:
            r['seats_le5'] += w
        if not k.get('ante', True):
            r['no_ante'] += w


def main():
    fmt, day, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    limit = float(sys.argv[4]) if len(sys.argv) > 4 else 30 * 3600
    PF.gto_pf_spot_freqs = _wrapped_sf
    PL.preflop_plan = _wrapped_pp
    _orig_init = PLY.Hand.__init__

    def _count(self, *a, **kw):
        HANDS[0] += 1
        return _orig_init(self, *a, **kw)
    PLY.Hand.__init__ = _count
    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    store = TS.Store(tempfile.mkdtemp(), 10000, [dict(spec, minute=0)])
    base = 1790000000 - 1790000000 % 3600 + day * 86400
    store.ensure_schedule(base - 60)
    ev = store.event('%s:%d' % (fmt, base))
    ev['rules']['field_backend'] = 'real'
    late = TS.active_seconds(spec['late_minutes'] * 60)
    t = 0.0
    while True:
        t += 300
        ev['closed'] = t >= late
        r = SR.advance(ev, t, budget=10 ** 9, parallel=False)
        ev['state'] = r['state']
        f = L._load_field(ev['state']['field'])
        done = f.remaining() <= 1
        _dump(out, fmt, day, t, done)
        if done or t >= limit:
            break
    print(json.dumps({'fmt': fmt, 'day': day, 'hands': HANDS[0], 'decisions': dict(DECS),
                      'finished': done}))


def _dump(out, fmt, day, t, finished):
    res = {'fmt': fmt, 'day': day, 'active_seconds': t, 'hands': HANDS[0], 'finished': finished,
           'decisions': dict(DECS),
           'rows': {k: {a: round(b, 3) for a, b in v.items()} for k, v in sorted(ROWS.items())}}
    tmp = out + '.tmp'
    json.dump(res, open(tmp, 'w'), indent=0, ensure_ascii=False)
    os.replace(tmp, out)


if __name__ == '__main__':
    main()
