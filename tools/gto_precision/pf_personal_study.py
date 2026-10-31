#!/usr/bin/env python3
"""프리플랍 개인 층 측정 — 봇 전용 예약 대회(실제 경로, 표준 프로필, 고정 시드).

  python3 tools/gto_precision/pf_personal_study.py <fmt> <seed_day> <out_json> [max_active_seconds]
  python3 tools/gto_precision/pf_personal_study.py --table <out_json> [...]

money_gate_study.py 와 같은 대회 경로(field_backend='real', scheduled_runtime.advance).
첫 진입(open_decision)마다 숙련 층(min(pf_range, positional) 숙련: top ≥ 8, mid 4~8, low < 4), 기질(방향 d:
tight < −1/3 < neutral < 1/3 < loose), 자리, GTO 표 진입 확률(개인 층 전), 개인 진입 확률, 실제 행동을 남긴다.
프리플랍 판단(preflop_plan)마다 그 핸드의 첫 자발 판단인지(pf_actor_acted)와 행동을 남겨 VPIP 를 센다
(BB 가 체크할 수 있는 자리는 뺀다).
"""
import json
import os
import sys
import tempfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'

import preflop as PF                   # noqa: E402
import persona as PS                   # noqa: E402

VOL = {'raise', 'call', 'shove', 'limp', '3bet', '4bet', 'allin', 'bet'}


def tier(prof):
    """첫 진입에 쓰이는 두 숙련(차트 pf_range, 포지션 positional)의 작은 쪽. 8 이상 = 개인 층 이탈 0."""
    s = min(PS.sk(prof, 'pf_range'), PS.sk(prof, 'positional'))
    return 'top' if s >= 8 else 'mid' if s >= 4 else 'low'


def temp(prof):
    d = PS.preflop_temper_direction(0.75 * PS.temper(prof, 'looseness', 5.0)
                                    + 0.25 * PS.temper(prof, 'aggression', 5.0))
    return 'tight' if d < -1 / 3 else 'loose' if d > 1 / 3 else 'neutral'


def run(fmt, day, out, limit):
    import live2 as L
    import plan as PL
    import scheduled_runtime as SR
    import tournament_store as TS
    OPEN, PLAN = [], []
    _orig_open = PF.open_decision

    def _open(prof, pos, bb, hand, rng, behind_stacks=None, tilt=0.0, field_q=0.6, bf=1.0,
              seats=8, ante=True, *a, **k):
        eff = PF.gto_pf_open_eff_bb(pos, bb, behind_stacks, ante)
        sp = {'fn': 'first_in', 'args': {'pos': pos, 'seats': seats, 'eff': eff, 'ante': ante}}
        g0 = PF.gto_pf_spot_freqs(sp, hand)
        g1 = PF.gto_pf_spot_freqs(sp, hand, prof)
        PF.take_gto_spot()
        res = _orig_open(prof, pos, bb, hand, rng, behind_stacks, tilt, field_q, bf, seats, ante, *a, **k)
        used = PF.take_gto_spot()
        PF._GTO_SPOT[0] = used
        c = PF.cls(hand)
        OPEN.append({'tier': tier(prof), 'temp': temp(prof), 'pos': PF._gto_pf_mod().pos9(pos, seats), 'seat': pos, 'seats': seats,
                     'eff': round(eff, 2), 'cls': c, 'trash': c in PF.PF_TRASH,
                     'gto_in': round(1 - g0[0]['fold'], 4) if g0 else None,
                     'pers_in': round(1 - g1[0]['fold'], 4) if g1 else None,
                     'used': used is not None, 'act': res[0]})
        return res
    PF.open_decision = _open
    _orig_plan = PL.preflop_plan

    def _plan(profile, pos, hand, bb, rng, *a, **k):
        r = _orig_plan(profile, pos, hand, bb, rng, *a, **k)
        if not k.get('pf_actor_acted') and not (pos == 'BB' and k.get('can_check')):
            c = PF.cls(hand)
            PLAN.append({'tier': tier(profile), 'temp': temp(profile), 'cls': c,
                         'trash': c in PF.PF_TRASH, 'vol': r[0] in VOL})
        return r
    PL.preflop_plan = _plan

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
        json.dump({'fmt': fmt, 'day': day, 'finished': done, 'open': OPEN, 'plan': PLAN}, open(out, 'w'))
        if done or t >= limit:
            break
    print(json.dumps({'fmt': fmt, 'day': day, 'open': len(OPEN), 'plan': len(PLAN), 'finished': done}))


SEATS9 = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']


def table(paths):
    O, Pn = [], []
    for p in paths:
        d = json.load(open(p))
        O += d['open']
        Pn += d['plan']
    pct = lambda a, b: ('%.1f' % (100.0 * a / b)) if b else '-'
    print('첫 진입(표가 덮는 결정만): 실제 진입% / 개인 층 기대% / GTO 표 기대% — 자리별')
    groups = [('top', None), ('mid', None), ('low', None)] + [(t, m) for t in ('top', 'mid', 'low')
                                                                  for m in ('tight', 'neutral', 'loose')]
    print('| 층 | 기질 | 결정 | ' + ' | '.join(SEATS9) + ' | 전체 |')
    print('|---' * (len(SEATS9) + 4) + '|')
    for t, m in groups:
        rows = [r for r in O if r['used'] and r['tier'] == t and (m is None or r['temp'] == m)]
        cells = []
        for s in SEATS9 + [None]:
            rr = [r for r in rows if s is None or r['pos'] == s]
            if not rr:
                cells.append('-')
                continue
            n = len(rr)
            act = sum(r['act'] != 'fold' for r in rr)
            cells.append('%s/%s/%s' % (pct(act, n), pct(sum(r['pers_in'] for r in rr), n),
                                       pct(sum(r['gto_in'] for r in rr), n)))
        print('| %s | %s | %d | %s |' % (t, m or '전체', len(rows), ' | '.join(cells)))
    print()
    print('| 층 | 기질 | VPIP(첫 자발 판단) | 쓰레기 패 진입%(첫 진입, 표 덮음) | 쓰레기 결정 수 | 쓰레기 GTO 기대% | 쓰레기 VPIP%(전체 경로) |')
    print('|---|---|---|---|---|---|---|')
    for t, m in groups:
        pl = [r for r in Pn if r['tier'] == t and (m is None or r['temp'] == m)]
        tr = [r for r in O if r['used'] and r['trash'] and r['tier'] == t and (m is None or r['temp'] == m)]
        ptr = [r for r in pl if r['trash']]
        print('| %s | %s | %s | %s | %d | %s | %s |' % (
            t, m or '전체', pct(sum(r['vol'] for r in pl), len(pl)),
            pct(sum(r['act'] != 'fold' for r in tr), len(tr)), len(tr),
            pct(sum(r['gto_in'] for r in tr), len(tr)), pct(sum(r['vol'] for r in ptr), len(ptr))))
    top = [r for r in O if r['used'] and r['tier'] == 'top']
    diff = max((abs(r['pers_in'] - r['gto_in']) for r in top), default=0.0)
    print('\ntop 층 개인 진입 − GTO 진입 최대 차이: %.6f (결정 %d)' % (diff, len(top)))


if __name__ == '__main__':
    if sys.argv[1] == '--table':
        table(sys.argv[2:])
    else:
        run(sys.argv[1], int(sys.argv[2]), sys.argv[3],
            float(sys.argv[4]) if len(sys.argv) > 4 else 30 * 3600)
