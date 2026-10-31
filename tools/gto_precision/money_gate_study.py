#!/usr/bin/env python3
"""첫 진입 GTO 관문(머니점프·BF) 측정 — 봇 전용 예약 대회(실제 경로, 고정 시드).

  python3 tools/gto_precision/money_gate_study.py <fmt> <seed_day> <out_json> [mode] [max_active_seconds]

mode
  current   : 지금 코드 그대로(기본).
  magnitude : 실험만(배포 아님). 관문을 '의미 있는 크기'로 바꿔 본다 —
              BF > 1.05 이거나 brake > 0.02 이거나 |range_factor - 1| > 0.05 일 때만 막는다.
              (2026-10-31 이전 코드, 관문이 _gto_pf_icm_free(bf, money_open) 이던 때만 뜻이 있다.)
  compose   : 지금 코드(첫 진입 = GTO × 머니점프 배수 합성) 그대로. current 와 같고 이름표만 다르다.

첫 진입 결정(preflop.open_decision)마다 단계(남은 인원 / 상금 인원), 스택 분류(내 스택 / 필드 평균),
BF, 머니점프 값(pressure, brake, drive, danger_fraction, range_factor, urgency, self_preservation),
관문 통과·막힘 이유, GTO(칩 기준) 오픈 확률(1 - fold), 실제로 들어갔는지를 기록한다.
spot_usage_sim.py 와 같은 대회 경로(field_backend='real', scheduled_runtime.advance)를 쓴다.
"""
import json
import os
import re
import sys
import tempfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ['T2_BOT_LOG'] = '0'
os.environ['T2_TELEMETRY'] = '0'

import live2 as L                      # noqa: E402
import preflop as PF                   # noqa: E402
import scheduled_runtime as SR         # noqa: E402
import session as SES                  # noqa: E402
import tournament_store as TS          # noqa: E402

KEYS = ('pressure', 'max_pressure', 'brake', 'drive', 'danger_fraction',
        'range_factor', 'limp_pull_shadow')
ROWS = []
_LAST = [None]


def stage_of(rem, itm):
    if not rem or not itm:
        return 'unknown'
    x = float(rem) / float(itm)
    if x <= 1.0:
        return 'itm'
    if x <= 1.3:
        return 'bubble'
    if x <= 2.0:
        return 'approach'
    return 'early'


def stack_class(stack_bb, avg_bb):
    if not avg_bb:
        return 'unknown'
    r = float(stack_bb) / float(avg_bb)
    return 'short' if r < 0.6 else 'deep' if r > 1.5 else 'medium'


def _block_reason(bf, mo):
    if float(bf or 1.0) > PF.GTO_PF_BF_MAX:
        return 'bf'
    if mo:
        for k in ('pressure', 'max_pressure', 'brake', 'danger_fraction', 'limp_pull_shadow'):
            if float(mo.get(k, 0.0) or 0.0) > 1e-9:
                return 'money:' + k
    return None


def _gate_magnitude(bf, money_open=None):
    if float(bf or 1.0) > PF.GTO_PF_BF_MAX:
        return False
    if money_open:
        if float(money_open.get('brake', 0.0) or 0.0) > 0.02:
            return False
        if abs(float(money_open.get('range_factor', 1.0) or 1.0) - 1.0) > 0.05:
            return False
    return True


def main():
    fmt, day, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    mode = sys.argv[4] if len(sys.argv) > 4 else 'current'
    limit = float(sys.argv[5]) if len(sys.argv) > 5 else 30 * 3600
    if mode == 'magnitude':
        PF._gto_pf_icm_free = _gate_magnitude

    _orig_obs = SES._money_jump_observe

    def _obs(*a, **k):
        o = _orig_obs(*a, **k)
        _LAST[0] = o
        return o
    SES._money_jump_observe = _obs

    _orig_open = PF.open_decision
    _orig_fic = PF.gto_pf_first_in_choice
    _used = [False]

    def _fic(*a, **k):
        r = _orig_fic(*a, **k)
        _used[0] = r is not None
        return r
    PF.gto_pf_first_in_choice = _fic

    def _open(prof, pos, bb, hand, rng, behind_stacks=None, tilt=0.0, field_q=0.6, bf=1.0,
              seats=8, ante=True, field_avg_bb=None, *a, **k):
        mo = k.get('money_open')
        o = _LAST[0]
        if o is None or o.get('unopened_modifiers') is not mo:
            o = {}
        ms = o.get('money_signals') or {}
        eff = PF.gto_pf_open_eff_bb(pos, bb, behind_stacks, ante)
        g = PF.gto_pf_spot_freqs({'fn': 'first_in', 'args': {
            'pos': pos, 'seats': seats, 'eff': eff, 'ante': ante}}, hand)
        _used[0] = False
        res = _orig_open(prof, pos, bb, hand, rng, behind_stacks, tilt, field_q, bf,
                         seats, ante, field_avg_bb, *a, **k)
        passed = _used[0]
        row = {
            'stage': stage_of(o.get('remaining'), o.get('itm')),
            'cls': stack_class(bb, field_avg_bb),
            'pos': pos, 'bb': round(float(bb), 2), 'eff': round(eff, 2),
            'bf': round(float(bf or 1.0), 4),
            'gate': 'pass' if passed else 'block',
            'reason': None if passed else (_block_reason(bf, mo) or 'no_record'),
            'gto_open': (round(1.0 - g[0]['fold'], 4) if g else None),
            'gto_used': bool(passed),
            'gto_in_composed': ((mo or {}).get('gto_compose') or {}).get('composed_in'),
            'bf_pos': o.get('bf_pos'), 'risk_frac': o.get('bf_risk_frac'),
            'act': res[0],
            'urgency': ms.get('urgency'), 'preserve': ms.get('self_preservation'),
        }
        for kk in KEYS:
            row[kk] = (mo or {}).get(kk)
        ROWS.append(row)
        return res
    PF.open_decision = _open

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
        json.dump({'fmt': fmt, 'day': day, 'mode': mode, 'finished': done, 'rows': ROWS},
                  open(out, 'w'))
        if done or t >= limit:
            break
    print(json.dumps({'fmt': fmt, 'day': day, 'mode': mode, 'rows': len(ROWS), 'finished': done}))


if __name__ == '__main__':
    main()
