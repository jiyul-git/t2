#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4-C: 히어로의 **거부된** 첫 요청이 뒤 봇의 프리플랍 행동을 바꾸는가.

  python3 tools/f6_q4c_live.py --selftest
  python3 tools/f6_q4c_live.py --seeds 3000,3001,3002,3003,3004 --hands 6

session.py:436-448 은 첫 요청이 ValueError 면 두 번째 act 를 적용하는데,
aggressor/limpers/callers 갱신은 **첫 변수 a** 를 본다. 그래서 실제 적용된
액션이 call/check 인데도 내부 aggressor 가 히어로가 될 수 있다.

두 팔을 같은 seed·같은 카드·같은 스택으로 돌리고 **히어로가 최종적으로
적용한 액션을 동일하게** 맞춘다.

  CONTROL  히어로가 처음부터 합법 액션 하나만 제출
  RETRY    히어로가 먼저 불법 raise 를 제출해 ValueError 경로를 밟고,
           두 번째 제출에서 CONTROL 과 **정확히 같은** 합법 액션을 낸다

비교는 히어로 적용 직후부터다.

분류
  C0  runtime 입력만 다르고 뒤 실제 행동은 동일
  C1  pf_seed 만 달라짐
  C2  뒤 봇의 실제 프리플랍 action/amount 가 달라짐

읽기 전용. production 무수정.
"""
from __future__ import print_function

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import plan as PL
import runner as RU
import tourney as TOURNEY

# 봇 결정 입력에서 비교할 키. session.py:489-494 가 넘기는 것들이다.
IN_KEYS = ('aggressor_pos', 'open_bb', 'n_callers', 'n_limpers', 'raise_level')


class Trace(object):
    """preflop_plan 입력/출력과 Round.apply 적용 결과를 기록한다."""

    def __init__(self):
        self.decisions = []      # 봇 결정 입력 + 출력
        self.applied = []        # 실제 적용된 액션 (Round.apply 통과분)
        self._pp = None
        self._ap = None

    def __enter__(self):
        self._pp = PL.preflop_plan
        self._ap = RU.Round.apply
        tr = self

        def preflop_plan(ax, pos, hand, bbs, rng, **kw):
            rec = {'pos': pos, 'bbs': round(bbs, 3)}
            rec.update({k: kw.get(k) for k in IN_KEYS})
            out = tr._pp(ax, pos, hand, bbs, rng, **kw)
            a, sz, seed_info = out
            rec['out_action'] = a
            rec['out_size'] = None if sz is None else round(float(sz), 6)
            rec['pf_role'] = seed_info.get('pf_role')
            rec['pf_act'] = seed_info.get('pf_act')
            tr.decisions.append(rec)
            return out

        def apply(self_r, seat, action, amount=0):
            n0 = len(self_r.log)
            out = tr._ap(self_r, seat, action, amount)
            if len(self_r.log) > n0:
                tr.applied.append(tuple(self_r.log[-1]))
            return out

        PL.preflop_plan = preflop_plan
        RU.Round.apply = apply
        return self

    def __exit__(self, *e):
        PL.preflop_plan = self._pp
        RU.Round.apply = self._ap
        return False


def play(seed, hands, inject, entries=100):
    """한 팔을 돌린다. inject=True 면 히어로의 첫 프리플랍 결정에서
    불법 raise 를 먼저 제출한다. 반환: (trace, meta)"""
    meta = {'injected': 0, 'error_seen': 0, 'hero_applied': [], 'hands': 0,
            'pf_seed': []}
    with Trace() as tr:
        t = TOURNEY.Tournament(entries=entries, start_stack=30000, hero_seat=7,
                               seed=seed, hands_per_level=200)
        for i in range(hands):
            if sum(1 for x in t.seats if t.stacks[x] > 0) < 3:
                break
            st = t.next_hand()
            g = 0
            used = False
            while st and not st.get('done') and g < 400:
                g += 1
                tc = st.get('tocall', 0) or 0
                legal = 'check' if tc <= 0 else 'call'
                if (inject and not used and st.get('stage') == 'preflop'
                        and st.get('can_raise')):
                    used = True
                    meta['injected'] += 1
                    st2 = t.submit('raise', 1)      # 최소 레이즈 미달
                    if st2 and st2.get('error'):
                        meta['error_seen'] += 1
                        tc2 = st2.get('tocall', 0) or 0
                        legal2 = 'check' if tc2 <= 0 else 'call'
                        meta['hero_applied'].append((i, legal2))
                        st = t.submit(legal2)
                        continue
                    # 불법이 아니었다 — fixture 실패로 기록한다
                    meta.setdefault('not_illegal', []).append(i)
                    st = st2
                    continue
                if st.get('stage') == 'preflop':
                    meta['hero_applied'].append((i, legal))
                st = t.submit(legal)
            h = getattr(t, 'hand', None)
            meta['pf_seed'].append(
                {k: v.get('pf_role') for k, v in
                 (getattr(h, 'pf_seed', {}) or {}).items()} if h else {})
            meta['hands'] += 1
            t.finish_hand()
            if getattr(t, 'busted_hero', False):
                break
    return tr, meta


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    if len(a) != len(b):
        i = min(len(a), len(b))
        return i, (a[i] if i < len(a) else None), (b[i] if i < len(b) else None)
    return None, None, None


def compare(tag, seed, ctl, ctl_m, rty, rty_m):
    res = {'seed': seed, 'tag': tag}
    res['hero_applied_same'] = ctl_m['hero_applied'] == rty_m['hero_applied']
    res['injected'] = rty_m['injected']
    res['error_seen'] = rty_m['error_seen']
    res['not_illegal'] = len(rty_m.get('not_illegal', []) or [])

    ci = [tuple(d.get(k) for k in IN_KEYS) for d in ctl.decisions]
    ri = [tuple(d.get(k) for k in IN_KEYS) for d in rty.decisions]
    res['n_decisions'] = (len(ci), len(ri))
    i_in, x_in, y_in = first_diff(ci, ri)
    res['first_input_divergence'] = None if i_in is None else {
        'idx': i_in, 'control': dict(zip(IN_KEYS, x_in)) if x_in else None,
        'retry': dict(zip(IN_KEYS, y_in)) if y_in else None}

    co = [(d['out_action'], d['out_size']) for d in ctl.decisions]
    ro = [(d['out_action'], d['out_size']) for d in rty.decisions]
    i_out, x_out, y_out = first_diff(co, ro)
    res['first_bot_output_divergence'] = None if i_out is None else {
        'idx': i_out, 'control': x_out, 'retry': y_out}
    res['bot_output_diff_count'] = sum(
        1 for x, y in zip(co, ro) if x != y) + abs(len(co) - len(ro))

    ca = ctl.applied
    ra = rty.applied
    i_ap, x_ap, y_ap = first_diff(ca, ra)
    res['first_applied_divergence'] = None if i_ap is None else {
        'idx': i_ap, 'control': x_ap, 'retry': y_ap}
    res['applied_diff_count'] = sum(
        1 for x, y in zip(ca, ra) if x != y) + abs(len(ca) - len(ra))

    cs = [d['pf_role'] for d in ctl.decisions]
    rs = [d['pf_role'] for d in rty.decisions]
    res['pf_role_diff_count'] = sum(
        1 for x, y in zip(cs, rs) if x != y) + abs(len(cs) - len(rs))

    if res['applied_diff_count'] or res['bot_output_diff_count']:
        res['class'] = 'C2'
    elif res['pf_role_diff_count'] or res['first_input_divergence']:
        res['class'] = 'C1' if res['pf_role_diff_count'] else 'C0'
    else:
        res['class'] = 'none'
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='3000,3001,3002,3003,3004')
    ap.add_argument('--hands', type=int, default=6)
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--verify', action='store_true',
                    help='CONTROL/RETRY 동등성을 invariant 로 검사한다. 하나라도 다르면 rc=1')
    ap.add_argument('--heartbeat', type=float, default=10.0)
    a = ap.parse_args()
    seeds = tuple(int(x) for x in a.seeds.split(','))
    t0 = time.time()
    last = [0.0]

    def hb(msg):
        now = time.time()
        if now - last[0] >= a.heartbeat:
            last[0] = now
            sys.stderr.write('[%6.1fs] %s\n' % (now - t0, msg))
            sys.stderr.flush()

    if a.selftest:
        print('=== 음성 대조: CONTROL vs CONTROL 은 완전 일치해야 한다 ===')
        bad = 0
        for sd in seeds[:3]:
            c1, m1 = play(sd, a.hands, inject=False)
            c2, m2 = play(sd, a.hands, inject=False)
            r = compare('ctl-vs-ctl', sd, c1, m1, c2, m2)
            ok = (r['class'] == 'none' and r['hero_applied_same'])
            bad += (not ok)
            print('  seed %d  class=%-5s applied_diff=%d bot_out_diff=%d '
                  'pf_role_diff=%d input_div=%s  %s'
                  % (sd, r['class'], r['applied_diff_count'],
                     r['bot_output_diff_count'], r['pf_role_diff_count'],
                     r['first_input_divergence'] is not None,
                     'PASS' if ok else 'FAIL'))
        print('  음성 대조 %s' % ('FAIL' if bad else 'PASS'))
        return 1 if bad else 0

    print('Q4-C  CONTROL vs RETRY   seeds=%s hands=%d'
          % (','.join(map(str, seeds)), a.hands))
    print()
    rows = []
    for sd in seeds:
        hb('seed %d CONTROL' % sd)
        ctl, cm = play(sd, a.hands, inject=False)
        hb('seed %d RETRY' % sd)
        rty, rm = play(sd, a.hands, inject=True)
        r = compare('ctl-vs-retry', sd, ctl, cm, rty, rm)
        rows.append(r)
        print('seed %d' % sd)
        print('  히어로 적용 액션 동일   %s   (주입 %d, ValueError 확인 %d, '
              '불법 아니었던 것 %d)'
              % (r['hero_applied_same'], r['injected'], r['error_seen'],
                 r['not_illegal']))
        print('  봇 결정 수            %s' % (r['n_decisions'],))
        print('  첫 입력 divergence     %s' % (r['first_input_divergence'],))
        print('  첫 봇 출력 divergence  %s' % (r['first_bot_output_divergence'],))
        print('  첫 적용 divergence     %s' % (r['first_applied_divergence'],))
        print('  적용 차이 %d / 봇출력 차이 %d / pf_role 차이 %d  -> %s'
              % (r['applied_diff_count'], r['bot_output_diff_count'],
                 r['pf_role_diff_count'], r['class']))
        print()

    print('=== 요약 ===')
    for k in ('none', 'C0', 'C1', 'C2'):
        n = sum(1 for r in rows if r['class'] == k)
        print('  %-5s %d' % (k, n))
    bad_meta = [r for r in rows if not r['hero_applied_same'] or r['not_illegal']]
    if bad_meta:
        print('  ** fixture 무효 시드 %s — 히어로 적용 액션이 다르거나 '
              '첫 요청이 불법이 아니었다' % [r['seed'] for r in bad_meta])
        return 2
    print('  경과 %.1fs' % (time.time() - t0))

    if a.verify:
        # invariant: 거부된 첫 요청은 그 뒤 무엇도 바꾸지 않는다.
        exercised = sum(1 for r in rows if r['error_seen'] > 0)
        bad = [r for r in rows if r['class'] != 'none']
        print()
        print('  invariant  ValueError 경로를 실제로 밟은 시드 %d / %d'
              % (exercised, len(rows)))
        if not exercised:
            print('  FAIL 주입이 한 번도 불법이 아니었다 — 시험이 비어 있다')
            return 1
        if bad:
            print('  FAIL CONTROL != RETRY: %s'
                  % [(r['seed'], r['class']) for r in bad])
            return 1
        print('  PASS 전 시드에서 CONTROL == RETRY')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
