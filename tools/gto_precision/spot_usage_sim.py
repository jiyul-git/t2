#!/usr/bin/env python3
"""GTO 기록별 실제 사용 빈도 — 봇 전용 예약 대회(고정 시드)에서 프리플랍 GTO 조회가 어느 기록을 썼는지 센다.

  python3 tools/gto_precision/spot_usage_sim.py <fmt> <seed_day> <out_json> [max_active_seconds]

읽기 전용 측정. bot_sanity.py 와 같은 실제 서비스 경로(scheduled_runtime.advance, 표준 프로필,
대회 스택 흐름 그대로)로 대회를 돌리고, preflop.gto_pf_spot_freqs 를 감싸 봇 결정(*_choice)에서
나온 조회만 센다(레인지 동기화 등 다른 호출은 제외). 조회 결과가 None 이 아니면(=GTO 값을 실제로 씀)
gto_pf 의 보간 규칙을 그대로 따라 기여한 기록에 가중치(버킷·오픈 크기 보간 몫)를 나눠 준다.
계산기(솔버)는 돌리지 않는다.
"""
import json
import os
import re
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
import preflop as PF                   # noqa: E402
import scheduled_runtime as SR         # noqa: E402
import tournament_store as TS          # noqa: E402

_REV = {'UTG+1': 'utg1', 'UTG+2': 'utg2'}
low = lambda p: _REV.get(p, p.lower())
PARENT = {10: 'pf10', 15: 'pf15', 20: 'pf20', 25: 'pf25', 30: 's30', 40: 's40', 60: 's60', 100: 's100'}


def _buckets(eff):
    b = G._load()['buckets']
    x = max(b[0], min(b[-1], float(eff)))
    hi = next(i for i, v in enumerate(b) if v >= x)
    lo = max(0, hi - 1) if b[hi] > x else hi
    t = 0.0 if hi == lo else (x - b[lo]) / (b[hi] - b[lo])
    return [(b[lo], 1 - t), (b[hi], t)] if hi != lo else [(b[lo], 1.0)]


def _ids_full(table, key, S):
    """표·키·버킷 → 기록 id (빌더 규칙의 역)."""
    a, b = key.split('>')
    if table == 'vs_open_full':
        return 'p%d_flat_%s_vs_%s' % (S, low(a), low(b))
    if table == 'vs_open_full_o25':
        return 'p%d_flat_%s_vs_%s_o25' % (S, low(a), low(b))
    if table == 'vs_limp_full':
        return 'p%d_flat_sb_limp_vs_bb' % S
    raise KeyError(table)


V3_IDS = {}       # (S, key) → vs_3bet_full 기록 id(접미사가 기록마다 달라 기록 목록에서 찾는다)


def _attr(spot, hand):
    """이 조회에 기여한 기록 {id: 몫}."""
    d = G._load()
    fn, a = spot['fn'], spot['args']
    out = Counter()
    bk = _buckets(a['eff'])
    if fn in ('first_in', 'vs_jam', 'vs_3bjam'):
        for S, w in bk:
            out['%s#%s' % (PARENT[S], fn)] += w
        return out
    if fn == 'vs_limp':
        for S, w in bk:
            out[_ids_full('vs_limp_full', 'SB>BB', S) + '#root'] += w
        return out
    seats = a['seats']
    if fn == 'vs_open':
        key = G.pos9(a['aggressor_pos'], seats) + '>' + G.pos9(a['pos'], seats)
        o = float(a['open_bb'])
        lo = G._full_open('vs_open_full', key, a['eff'], hand, None)
        hi = G._full_open('vs_open_full_o25', key, a['eff'], hand, None)
        tabs = None
        if lo and hi and lo[1] < hi[1] and lo[1] <= o <= hi[1]:
            t = (o - lo[1]) / (hi[1] - lo[1])
            tabs = [('vs_open_full', 1 - t), ('vs_open_full_o25', t)]
        else:
            for tbl in ('vs_open_full', 'vs_open_full_o25'):
                if G._full_open(tbl, key, a['eff'], hand, o):
                    tabs = [(tbl, 1.0)]
                    break
        if tabs:
            for tbl, wt in tabs:
                for S, w in bk:
                    if wt * w > 0:
                        out[_ids_full(tbl, key, S) + '#root'] += wt * w
            return out
        for S, w in bk:
            out['%s#vs_open_partial' % PARENT[S]] += w
        return out
    if fn == 'vs_3bet':
        key = G.pos9(a['pos'], seats) + '>' + G.pos9(a['aggressor_pos'], seats)
        f = G.defend_vs_3bet(a['pos'], a['aggressor_pos'], seats, a['eff'], hand, a['open_bb'], a['ante'])
        if f is not None:
            for S, w in bk:
                if w > 0:
                    out[V3_IDS.get((S, key), 'p%dv1_%s_vs_%s?' % (S, low(key.split('>')[0]), low(key.split('>')[1])))
                        + '#root'] += w
            return out
        for S, w in bk:
            out['%s#vs_3bet_partial' % PARENT[S]] += w
        return out
    raise ValueError(fn)


USE = Counter()          # 기록 id → 가중 사용 수(결정 수)
BLOCKED = Counter()      # 첫 진입이 ICM·머니점프 관문에 막혀 GTO 를 못 쓴 결정 → 그 스택의 부모 기록(반사실 집계)
BLOCK_N = Counter()
USE_BY_FN = defaultdict(Counter)
TRY = Counter()          # fn → 조회 시도
HIT = Counter()          # fn → 값 있음
EFF = defaultdict(list)
_orig_sf = PF.gto_pf_spot_freqs


def _wrapped(spot, hand, prof=None):
    r = _orig_sf(spot, hand, prof)
    caller = sys._getframe(1).f_code.co_name
    if caller.startswith('gto_pf_') and caller.endswith('_choice'):
        fn = spot['fn']
        TRY[fn] += 1
        if r is not None:
            HIT[fn] += 1
            EFF[fn].append(round(float(spot['args']['eff']), 1))
            for k, w in _attr(spot, hand).items():
                USE[k.split('#')[0]] += w
                USE_BY_FN[k.split('#')[0]][k.split('#')[1]] += w
    return r


_orig_fi = PF.gto_pf_first_in_choice


def _wrapped_fi(prof, pos, bb, hand, rng, behind_stacks=None, bf=1.0, seats=8, ante=True, money_open=None):
    if PF.GTO_PF_ON and not PF._gto_pf_icm_free(bf, money_open):
        eff = PF.gto_pf_open_eff_bb(pos, bb, behind_stacks, ante)
        BLOCK_N['bf' if float(bf or 1.0) > PF.GTO_PF_BF_MAX else 'money_open'] += 1
        spot = {'fn': 'first_in', 'args': {'pos': pos, 'seats': seats, 'eff': eff, 'ante': ante}}
        if _orig_sf(spot, hand) is not None:
            BLOCK_N['would_hit'] += 1
            for k, w in _attr(spot, hand).items():
                BLOCKED[k.split('#')[0]] += w
    return _orig_fi(prof, pos, bb, hand, rng, behind_stacks, bf, seats, ante, money_open)


def main():
    fmt, day, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    limit = float(sys.argv[4]) if len(sys.argv) > 4 else 30 * 3600
    for e in G._load()['source']:
        m = re.match(r'p(\d+)v1_([a-z0-9]+)_vs_([a-z0-9]+)', e['id'])
        if m:
            nm = lambda s: {'utg1': 'UTG+1', 'utg2': 'UTG+2'}.get(s, s.upper())
            V3_IDS[(int(m.group(1)), nm(m.group(2)) + '>' + nm(m.group(3)))] = e['id']
    PF.gto_pf_spot_freqs = _wrapped
    PF.gto_pf_first_in_choice = _wrapped_fi
    hands = [0]
    _orig_init = PLY.Hand.__init__

    def _count(self, *a, **k):
        hands[0] += 1
        return _orig_init(self, *a, **k)
    PLY.Hand.__init__ = _count
    spec = next(s for s in TS.LEGACY_SCHEDULE if s['fmt'] == fmt)
    store = TS.Store(tempfile.mkdtemp(), 10000, [dict(spec, minute=0)])
    base = 1790000000 - 1790000000 % 3600 + day * 86400
    store.ensure_schedule(base - 60)
    ev = store.event('%s:%d' % (fmt, base))
    ev['rules']['field_backend'] = 'real'      # 기본 'hybrid' 는 관찰 안 되는 테이블을 간이 모델로 돌린다(실제 엔진·GTO 조회 없음)
    late = TS.active_seconds(spec['late_minutes'] * 60)
    t = 0.0
    while True:
        t += 300
        ev['closed'] = t >= late
        r = SR.advance(ev, t, budget=10 ** 9, parallel=False)
        ev['state'] = r['state']
        f = L._load_field(ev['state']['field'])
        _dump(out, fmt, day, t, hands[0], f.remaining() <= 1)        # 중간 저장(끊겨도 그때까지 집계가 남게)
        if f.remaining() <= 1 or t >= limit:
            break
    print(json.dumps(_dump(out, fmt, day, t, hands[0], True if f.remaining() <= 1 else False)))


def _dump(out, fmt, day, t, n_hands, finished):
    effs = {fn: Counter(_bin(x) for x in v) for fn, v in EFF.items()}
    res = {'fmt': fmt, 'day': day, 'active_seconds': t, 'hands': n_hands, 'finished': finished,
           'tries': dict(TRY), 'hits': dict(HIT), 'eff_bins': {k: dict(v) for k, v in effs.items()},
           'use': {k: round(v, 3) for k, v in USE.most_common()},
           'first_in_blocked': dict(BLOCK_N), 'first_in_blocked_use': {k: round(v, 3) for k, v in BLOCKED.most_common()},
           'use_by_part': {k: {p: round(x, 3) for p, x in v.items()} for k, v in USE_BY_FN.items()}}
    json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
    return {k: res[k] for k in ('fmt', 'day', 'hands', 'finished', 'tries', 'hits')}


def _bin(x):
    for b in (10, 15, 20, 25, 30, 40, 60, 100):
        if x <= b:
            return '<=%d' % b
    return '>100'


if __name__ == '__main__':
    main()
