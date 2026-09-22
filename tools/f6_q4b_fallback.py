#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4-B: hero_no_seed 폴백 불일치가 하류에 도달하는가.

  python3 tools/f6_q4b_fallback.py --seeds 3000,3001,3002 --hands 20

바꾸는 것은 `_act_o` 하나뿐이다. 소비 지점(session.py:717)의
R.preflop_range(oax, h.pos[o], _act_o, ...) 에서 **히어로 좌석에 한해**
현재 production 폴백값 대신 공개 로그 재구성값을 쓴다.

히어로의 포지션은 핸드마다 유일하므로 pos 로 그 호출을 정확히 가른다.
봇 자신의 my_r 호출(session.py:688)은 관찰자가 봇이라 히어로 포지션으로
들어올 수 없다.

Tier 1  레인지 층 — 같은 인자로 두 role 을 각각 호출해 count/서명 비교
Tier 2  결정 층 — 같은 fixture 를 두 팔로 돌려 plan/act/size/칩 비교.
        두 팔은 **최초 divergence 이후 자연 진행이 갈리므로** 그 지점까지만
        인과로 읽는다 (PHASE 2 와 같은 규약).

읽기 전용. production 무수정.
"""
from __future__ import print_function

import argparse
import hashlib
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import plan as PL
import ranges as R
import tourney as TOURNEY
import pf_role_boundary as PB

HERO_SEAT = 7


def sig(combos):
    s = '|'.join(sorted(''.join(c) for c in combos))
    return hashlib.sha256(s.encode()).hexdigest()[:12]


class Arm(object):
    """한 팔. swap=True 면 히어로 사이트의 role 을 공개 재구성값으로 바꾼다."""

    def __init__(self, swap, tier1=None):
        self.swap = swap
        self.tier1 = tier1          # Counter/list 를 공유해 Tier1 기록
        self.decisions = []
        self.hero_pos = None
        self.hero_public = None
        self.run = None
        self.hand = None
        self.swaps = 0
        self.oppr = []
        self._pr = None
        self._up = None

    def __enter__(self):
        self._pr = R.preflop_range
        self._up = PL.update_plan
        arm = self

        def preflop_range(ax, pos, role, bbs, dead, **kw):
            # **여기서 lazily 계산한다.** 바깥 루프에서 계산하면 포스트플랍
            # 첫 결정들이 이미 지나간 뒤라 그 사이트를 통째로 놓친다.
            if arm.hero_public is None and arm.run is not None \
                    and arm.hand is not None:
                full = list(getattr(arm.run, 'full_log', []) or [])
                pre = [(r[1], r[2], r[3]) for r in full if r[0] == 'preflop']
                if pre:
                    pub, _ = PB.reconstruct_public(
                        pre, dict(getattr(arm.hand, 'pos', {}) or {}))
                    arm.hero_public = pub.get(HERO_SEAT, '')
            hit = (arm.hero_pos is not None and pos == arm.hero_pos
                   and arm.hero_public
                   and role != arm.hero_public)
            if hit and arm.tier1 is not None:
                a = arm._pr(ax, pos, role, bbs, dead, **kw)
                b = arm._pr(ax, pos, arm.hero_public, bbs, dead, **kw)
                arm.tier1.append({'pos': pos, 'internal_role': role,
                                  'public_role': arm.hero_public,
                                  'n_internal': len(a), 'n_public': len(b),
                                  'sig_internal': sig(a), 'sig_public': sig(b),
                                  'same': sig(a) == sig(b)})
            if hit and arm.swap:
                arm.swaps += 1
                role = arm.hero_public
            return arm._pr(ax, pos, role, bbs, dead, **kw)

        def update_plan(*a, **k):
            out = arm._up(*a, **k)
            try:
                street = k.get('street') or a[8]
                pot = k.get('pot') or a[6]
                stack = k.get('stack') or a[7]
                oppr = k.get('opp_range')
                if oppr is None and len(a) > 4:
                    oppr = a[4]
            except Exception:
                street = pot = stack = oppr = None
            arm.oppr.append((street, len(oppr or []), sig(oppr or [])))
            it = (PL.intent_of(out, street) or {}) if street else {}
            size = round(it.get('size', 0) or 0, 6)
            chips = 0
            if it.get('act') == 'bet' and size and pot and stack:
                chips = min(stack, int(round(pot * size / 100)) * 100)
            arm.decisions.append((street, (out or {}).get('plan'),
                                  it.get('act'), size, chips))
            return out

        R.preflop_range = preflop_range
        PL.update_plan = update_plan
        return self

    def __exit__(self, *e):
        R.preflop_range = self._pr
        PL.update_plan = self._up
        return False


def play(seed, hands, swap, tier1=None):
    with Arm(swap, tier1) as arm:
        t = TOURNEY.Tournament(entries=100, start_stack=30000,
                               hero_seat=HERO_SEAT, seed=seed,
                               hands_per_level=200)
        for i in range(hands):
            if sum(1 for x in t.seats if t.stacks[x] > 0) < 3:
                break
            st = t.next_hand()
            h = getattr(t, 'hand', None)
            arm.hero_pos = (getattr(h, 'pos', {}) or {}).get(HERO_SEAT)
            arm.hero_public = None
            arm.run = getattr(t, 'run', None)
            arm.hand = h
            g = 0
            while st and not st.get('done') and g < 400:
                g += 1
                tc = st.get('tocall', 0) or 0
                st = t.submit('check' if tc <= 0 else 'call')
            t.finish_hand()
            if getattr(t, 'busted_hero', False):
                break
    return arm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='3000,3001,3002')
    ap.add_argument('--hands', type=int, default=20)
    ap.add_argument('--heartbeat', type=float, default=10.0)
    a = ap.parse_args()
    seeds = tuple(int(x) for x in a.seeds.split(','))
    t0 = time.time()
    last = [0.0]

    def hb(m):
        now = time.time()
        if now - last[0] >= a.heartbeat:
            last[0] = now
            sys.stderr.write('[%6.1fs] %s\n' % (now - t0, m))
            sys.stderr.flush()

    tier1 = []
    print('Q4-B  seeds=%s hands=%d' % (','.join(map(str, seeds)), a.hands))
    rows = []
    for sd in seeds:
        hb('seed %d INTERNAL' % sd)
        ia = play(sd, a.hands, swap=False, tier1=tier1)
        hb('seed %d PUBLIC' % sd)
        pa = play(sd, a.hands, swap=True)
        d_i, d_p = ia.decisions, pa.decisions
        first = None
        for i, (x, y) in enumerate(zip(d_i, d_p)):
            if x != y:
                first = {'idx': i, 'internal': x, 'public': y}
                break
        if first is None and len(d_i) != len(d_p):
            first = {'idx': min(len(d_i), len(d_p)), 'internal': None,
                     'public': None, 'note': '길이 다름'}
        n = min(len(d_i), len(d_p))
        # 결정에 실제로 들어간 opp_range 가 달라지기는 했는가
        oi, op = ia.oppr, pa.oppr
        oppr_diff = sum(1 for x, y in zip(oi, op) if x != y)
        cnt = Counter()
        for x, y in zip(d_i, d_p):
            if x[1] != y[1]: cnt['plan'] += 1
            if x[2] != y[2]: cnt['act'] += 1
            if x[3] != y[3]: cnt['size'] += 1
            if x[4] != y[4]: cnt['chips'] += 1
        rows.append({'seed': sd, 'decisions': (len(d_i), len(d_p)),
                     'first': first, 'counts': dict(cnt), 'swaps': pa.swaps,
                     'oppr_diff': oppr_diff, 'oppr_n': len(oi)})
        print('seed %d  결정 %s  role 교체 %d회  update_plan 에 들어간 '
              'opp_range 다른 결정 %d/%d  첫 divergence %s  누적차이 %s'
              % (sd, (len(d_i), len(d_p)), pa.swaps, oppr_diff, len(oi),
                 first, dict(cnt)))

    print()
    print('=== Tier 1  레인지 층 (같은 인자, role 만 교체) ===')
    if not tier1:
        print('  히어로 mismatch 사이트 0건 — 이 fixture 에서 폴백 불일치가 '
              '소비되지 않았다')
    else:
        same = sum(1 for r in tier1 if r['same'])
        print('  사이트 %d,  레인지 동일 %d,  다름 %d'
              % (len(tier1), same, len(tier1) - same))
        for r in tier1[:8]:
            print('   %s' % r)
    print()
    print('=== Tier 2  결정 층 ===')
    for r in rows:
        print('  seed %d  %s' % (r['seed'], r['counts'] or '차이 없음'))
    print()
    print('경과 %.1fs' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
