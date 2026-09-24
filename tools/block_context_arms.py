#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A5 4-A: block context arms, end-to-end funnel.

Production code is not modified.  We rerun the same fixed tournament fixture four
ways and override exactly one make_plan context input per arm, using the same
baseline/default values that A6 used:

  current                 no override
  oop_vs_aggr_default     oop_vs_aggr=None
  oop_legacy_abs_default  oop_legacy_abs=None
  initiative_default      initiative=True

This is intentionally a live-arm / end-to-end diagnostic.  Once an arm changes an
action, later states may diverge; therefore the arm deltas are not interpreted as
paired-event causal counts.  The purpose is to see whether a context change can
propagate through:

  S1 block_p>0 condition
  S3 block opportunity (S1 ∩ middle-strength branch)
  S4 block selected
  S6 attach_intent sees plan=block
  S8 actual bet

Do not call an arm behaviorally effective from S4 alone.  S8 is reported
separately.

Known harness issue:
  persona._TILT_VIEW_CACHE leaks across tournaments because pid is reused.  This
  tool runs single-process and clears only that analysis-time cache before each
  tournament.  Production code is untouched.

Usage:
  python3 tools/block_context_arms.py --seeds 5000-5007
"""
from __future__ import print_function

import argparse
import collections
import os
import statistics as stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import plan as PL
import persona as PS

BLOCK_MSG = '블락벳으로 가격 통제'
MID_MSG = '중간강도'

ARMS = (
    'current',
    'oop_vs_aggr_default',
    'oop_legacy_abs_default',
    'initiative_default',
)


def parse_seeds(spec):
    spec = str(spec).strip()
    if ',' in spec:
        return [int(x.strip()) for x in spec.split(',') if x.strip()]
    if '-' in spec:
        lo, hi = spec.split('-', 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(spec)]


def clear_tilt_cache():
    cache = getattr(PS, '_TILT_VIEW_CACHE', None)
    if hasattr(cache, 'clear'):
        cache.clear()
        return True
    return False


def override_context(arm, oop_vs_aggr, oop_legacy_abs, initiative):
    if arm == 'oop_vs_aggr_default':
        oop_vs_aggr = None
    elif arm == 'oop_legacy_abs_default':
        oop_legacy_abs = None
    elif arm == 'initiative_default':
        initiative = True
    return oop_vs_aggr, oop_legacy_abs, initiative


def run_one(seed, arm, entries, hpl, stack, cap):
    clear_tilt_cache()
    FS.Field.BOT_LOG = 0

    f = FS.Field(entries=entries, start_stack=stack, hero_pid=0, seed=seed,
                 hands_per_level=hpl)
    mk, ai = [], []

    original_make = PL.make_plan
    original_attach = PL.attach_intent

    def wrap_make(hero, board, my_range, opp_range, profile, pot, stack_, street,
                  seed=None, n_opp=1, to_act_behind=0, oop_vs_aggr=None,
                  initiative=True, opp_est=None, opp_stack_bb=None, tilt=0.0,
                  bb_chips=None, oop_legacy_abs=None):
        orig_ctx = (oop_vs_aggr, oop_legacy_abs, initiative)
        oop_vs_aggr, oop_legacy_abs, initiative = override_context(
            arm, oop_vs_aggr, oop_legacy_abs, initiative)

        st = original_make(
            hero, board, my_range, opp_range, profile, pot, stack_, street,
            seed=seed, n_opp=n_opp, to_act_behind=to_act_behind,
            oop_vs_aggr=oop_vs_aggr, initiative=initiative,
            opp_est=opp_est, opp_stack_bb=opp_stack_bb, tilt=tilt,
            bb_chips=bb_chips, oop_legacy_abs=oop_legacy_abs)

        why = ' | '.join(st.get('why') or [])
        rel = st.get('rel')
        oop_effective = (
            oop_vs_aggr if oop_vs_aggr is not None else bool(oop_legacy_abs)
        )
        mk.append({
            'pid': profile.get('id'),
            'street': street,
            'orig_oop_vs_aggr': orig_ctx[0],
            'orig_oop_legacy_abs': orig_ctx[1],
            'orig_initiative': bool(orig_ctx[2]),
            'oop_vs_aggr': oop_vs_aggr,
            'oop_legacy_abs': oop_legacy_abs,
            'initiative': bool(initiative),
            'oop': bool(oop_effective),
            'rel': rel,
            'plan': st.get('plan'),
            'mid': MID_MSG in why,
            'blkmsg': BLOCK_MSG in why,
            'cond': bool(oop_effective) and not bool(initiative)
                    and rel is not None and 0.25 <= rel <= 0.80,
        })
        return st

    def wrap_attach(st, hero, board, my_range, opp_range, profile, pot, stack_,
                    street, rng, n_opp, to_act_behind, oop, initiative,
                    opp_est=None, oop_vs_aggr=None, oop_legacy_abs=None):
        # attach_intent receives its own context inputs.  Keep the arm internally
        # consistent here as well; the plan state itself comes from the arm's
        # make_plan/update_plan path.
        oop_vs_aggr, oop_legacy_abs, initiative = override_context(
            arm, oop_vs_aggr, oop_legacy_abs, initiative)

        out = original_attach(
            st, hero, board, my_range, opp_range, profile, pot, stack_,
            street, rng, n_opp, to_act_behind, oop, initiative, opp_est,
            oop_vs_aggr=oop_vs_aggr, oop_legacy_abs=oop_legacy_abs)

        trace = None
        for t in reversed((out or {}).get('trace') or []):
            if t.get('kind') == 'aggression' and t.get('street') == street:
                trace = t
                break

        intent = ((out or {}).get('intents') or {}).get(street) or {}
        why_now = list((out or {}).get('why') or [])
        linked = any(
            BLOCK_MSG in str(x) and str(x).startswith(street + ': ')
            for x in why_now
        )
        ai.append({
            'pid': profile.get('id'),
            'street': street,
            'plan': (out or {}).get('plan'),
            'f': (trace or {}).get('p'),
            'bet': 1 if intent.get('act') == 'bet' else 0,
            'linked': linked,
        })
        return out

    PL.make_plan = wrap_make
    PL.attach_intent = wrap_attach
    try:
        while f.remaining() > 1 and f.hand_no < cap:
            f.hand_no += 1
            f.advance_level()
            for _tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
    finally:
        PL.make_plan = original_make
        PL.attach_intent = original_attach

    s1 = [r for r in mk if r['cond']]
    s3 = [r for r in mk if r['cond'] and r['mid']]
    s4 = [r for r in mk if r['blkmsg']]
    s5 = [r for r in mk if r['plan'] == 'block']
    s6 = [r for r in ai if r['plan'] == 'block']
    s6_linked = [r for r in ai if r['linked'] and r['plan'] == 'block']

    return {
        'seed': seed,
        'arm': arm,
        's0': len(mk),
        's1': len(s1),
        's3': len(s3),
        's4': len(s4),
        's5': len(s5),
        's6': len(s6),
        's8': sum(r['bet'] for r in s6),
        's6_linked': len(s6_linked),
        's8_linked': sum(r['bet'] for r in s6_linked),
        'errors': len(getattr(f, 'errors', ()) or []),
        'error_samples': list((getattr(f, 'errors', ()) or []))[:3],
    }


def aggregate(rows):
    keys = ('s0', 's1', 's3', 's4', 's5', 's6', 's8',
            's6_linked', 's8_linked', 'errors')
    return {k: sum(r[k] for r in rows) for k in keys}


def signed(n):
    return ('+%d' % n) if n > 0 else str(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--stack', type=int, default=30000)
    ap.add_argument('--seeds', default='5000-5007')
    ap.add_argument('--cap', type=int, default=3000)
    a = ap.parse_args()

    seeds = parse_seeds(a.seeds)
    by_arm = {}

    print('# A5 4-A block context arms')
    print('entries=%d hpl=%d stack=%d seeds=%s cap=%d'
          % (a.entries, a.hpl, a.stack, a.seeds, a.cap))
    print('single-process; each tournament clears _TILT_VIEW_CACHE; production unchanged')
    print('A6-compatible defaults: oop_vs_aggr=None / oop_legacy_abs=None / initiative=True')
    print()

    for arm in ARMS:
        arm_rows = []
        print('## arm %s' % arm)
        for i, seed in enumerate(seeds, 1):
            row = run_one(seed, arm, a.entries, a.hpl, a.stack, a.cap)
            arm_rows.append(row)
            print(
                '  [%d/%d] seed %d  S1=%d S3=%d S4=%d S6=%d S8=%d errors=%d'
                % (i, len(seeds), seed, row['s1'], row['s3'], row['s4'],
                   row['s6'], row['s8'], row['errors']),
                flush=True)
            if row['errors']:
                for e in row['error_samples']:
                    print('    ERROR: %s' % e)
        by_arm[arm] = aggregate(arm_rows)
        print()

    if any(by_arm[a]['errors'] for a in ARMS):
        print('ENGINE ERRORS — 결과 무효')
        return 1

    print('## funnel totals')
    print('%-24s %7s %7s %7s %7s %7s %7s'
          % ('arm', 'S1', 'S3', 'S4', 'S5', 'S6', 'S8'))
    for arm in ARMS:
        x = by_arm[arm]
        print('%-24s %7d %7d %7d %7d %7d %7d'
              % (arm, x['s1'], x['s3'], x['s4'], x['s5'], x['s6'], x['s8']))

    cur = by_arm['current']
    print()
    print('## delta vs current')
    print('%-24s %7s %7s %7s %7s %7s'
          % ('arm', 'ΔS1', 'ΔS3', 'ΔS4', 'ΔS6', 'ΔS8'))
    for arm in ARMS[1:]:
        x = by_arm[arm]
        print('%-24s %7s %7s %7s %7s %7s'
              % (arm,
                 signed(x['s1'] - cur['s1']),
                 signed(x['s3'] - cur['s3']),
                 signed(x['s4'] - cur['s4']),
                 signed(x['s6'] - cur['s6']),
                 signed(x['s8'] - cur['s8'])))

    print()
    print('## linked current-street block path (diagnostic)')
    print('%-24s %12s %12s'
          % ('arm', 'S6_linked', 'S8_linked'))
    for arm in ARMS:
        x = by_arm[arm]
        print('%-24s %12d %12d'
              % (arm, x['s6_linked'], x['s8_linked']))

    print()
    print('판정 규칙:')
    print('- S1/S3 변화: block opportunity 입력 효과')
    print('- S4 변화: block 선택 효과, 이것만으로 행동 효과 판정 금지')
    print('- S6 변화: attach_intent까지 전달')
    print('- S8 변화: 실제 bet까지 전달')
    print('- 이 도구는 live-arm이라 행동이 갈린 뒤 후속 상태도 갈릴 수 있다.')
    print('  4-B의 paired replan fixture와 합쳐서 최종 context 계약을 정한다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
