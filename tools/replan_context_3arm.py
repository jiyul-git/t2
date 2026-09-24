#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A5 4-B: focused A6 replan provenance re-measurement for three fields.

Keeps the original A6 board_changed/replan fixture and original paired-replay
definition, but measures only:

  oop_vs_aggr
  oop_legacy_abs
  initiative

Two capture modes are run:

R1 replication
  Exact A6 tournament order in one process. No cache clearing between
  tournaments. This is the apples-to-apples comparison with the frozen A6
  result.

R2 clean
  Same fixture/order, but clears persona._TILT_VIEW_CACHE immediately before
  each tournament. Production code is not modified.

For each captured board_changed event:
  baseline = production revise_plan behavior
  arm      = the same event replayed with exactly one current-context field
             forwarded into make_plan

Primary comparison stays identical to A6: plan / intent act / intent size.
The block gate is conjunctive: (_oop_a AND not initiative). Therefore the
three single-field arms are insufficient by construction when replay starts
from A6 defaults (oop=None, legacy=None, initiative=True). This revision keeps
the singles for continuity and adds:
  oop_vs_aggr + initiative
  oop_legacy_abs + initiative
  all three position fields together

An extra chip_target_changed count is also reported. It is the raw
act_with_plan bet target implied by pot*intent_size rounded to 100 and capped by
stack; it is NOT the later runner.shape_size result.

Usage:
  python3 tools/replan_context_3arm.py
"""
from __future__ import print_function

import argparse
import copy
import importlib.util
import inspect
import os
import sys
import time
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persona as PS

RP_PATH = os.path.join(ROOT, 'tools', 'replan_provenance.py')
_spec = importlib.util.spec_from_file_location('t2_replan_provenance', RP_PATH)
RP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RP)

FS = RP.FS
PL = RP.PL
RU = RP.RU

FIELDS = ('oop_vs_aggr', 'oop_legacy_abs', 'initiative')
ARMS = OrderedDict([
    ('oop_vs_aggr', ('oop_vs_aggr',)),
    ('oop_legacy_abs', ('oop_legacy_abs',)),
    ('initiative', ('initiative',)),
    ('oop_vs+initiative', ('oop_vs_aggr', 'initiative')),
    ('legacy+initiative', ('oop_legacy_abs', 'initiative')),
    ('position3', ('oop_vs_aggr', 'oop_legacy_abs', 'initiative')),
])
BLOCK_MSG = '블락벳으로 가격 통제'

OLD_A6 = {
    'oop_vs_aggr': {'different': 520, 'changed': 0},
    'oop_legacy_abs': {'different': 810, 'changed': 0},
    'initiative': {'different': 562, 'changed': 0},
}


class Heartbeat(object):
    def __init__(self, every=10.0):
        self.every = float(every)
        self.t0 = time.time()
        self.last = 0.0

    def hit(self, label, force=False):
        now = time.time()
        if force or now - self.last >= self.every:
            self.last = now
            print('[%7.1fs] %s' % (now - self.t0, label), flush=True)


def clear_tilt_cache():
    cache = getattr(PS, '_TILT_VIEW_CACHE', None)
    if hasattr(cache, 'clear'):
        cache.clear()
        return True
    return False


def capture_events(clean=False, hb=None):
    """Original A6 fixture. clean=True adds only tournament-boundary cache clear."""
    orig_update = PL.update_plan
    sig_update = inspect.signature(orig_update)
    events = []
    counts = Counter()
    errors = []

    def wrapped(*a, **k):
        b = sig_update.bind_partial(*a, **k)
        b.apply_defaults()

        state = b.arguments.get('state')
        first = bool(b.arguments.get('first'))
        prev_board = b.arguments.get('prev_board')
        board = b.arguments.get('board')

        counts['update_plan'] += 1
        if state is not None and not first:
            counts['revise_path'] += 1
            if RU.board_changed(prev_board, board):
                counts['board_changed'] += 1
                events.append({
                    'args': copy.deepcopy(a),
                    'kwargs': copy.deepcopy(k),
                    'current': {
                        'oop_vs_aggr': copy.deepcopy(
                            b.arguments.get('oop_vs_aggr')),
                        'oop_legacy_abs': copy.deepcopy(
                            b.arguments.get('oop_legacy_abs')),
                        'initiative': copy.deepcopy(
                            b.arguments.get('initiative')),
                        'tilt': copy.deepcopy(b.arguments.get('tilt')),
                        'bb_chips': copy.deepcopy(b.arguments.get('bb_chips')),
                        'opp_est': copy.deepcopy(b.arguments.get('opp_est')),
                        'opp_stack_bb': copy.deepcopy(
                            b.arguments.get('opp_stack_bb')),
                    },
                    'snapshot': {
                        'opp_est': copy.deepcopy(
                            (state or {}).get('opp_est')),
                        'opp_stack_bb': copy.deepcopy(
                            (state or {}).get('opp_stack_bb')),
                    },
                    'street': b.arguments.get('street'),
                    'pot': copy.deepcopy(b.arguments.get('pot')),
                    'stack': copy.deepcopy(b.arguments.get('stack')),
                })
        return orig_update(*a, **k)

    old_bot_log = getattr(FS.Field, 'BOT_LOG', None)
    PL.update_plan = wrapped
    try:
        if hasattr(FS.Field, 'BOT_LOG'):
            FS.Field.BOT_LOG = 0

        for fmt in RP.FMTS:
            for seed in RP.SEEDS:
                if clean:
                    clear_tilt_cache()
                f = FS.Field(entries=RP.ENTRIES, seed=seed, fmt=fmt)
                for _ in range(RP.HANDS):
                    if f.remaining() <= 8:
                        break
                    f.hand_no += 1
                    f.advance_level()
                    for tb in list(f.tables.values()):
                        if tb.n() >= 2:
                            f._play_table(tb)
                    f._collect_busts()
                    f._balance()
                    if hb is not None:
                        hb.hit('%s capture %s/%d hand %d events=%d'
                               % ('R2' if clean else 'R1',
                                  fmt, seed, f.hand_no, len(events)))
                errors.extend(getattr(f, 'errors', ()) or [])
    finally:
        PL.update_plan = orig_update
        if old_bot_log is not None:
            FS.Field.BOT_LOG = old_bot_log

    counts['engine_errors'] = len(errors)
    return events, counts, errors


def chip_target(st, ev):
    """Raw plan->act_with_plan bet target before runner.shape_size."""
    intent = PL.intent_of(st, ev['street']) or {}
    if intent.get('act') != 'bet':
        return None
    size = float(intent.get('size', 0) or 0)
    pot = float(ev.get('pot') or 0)
    stack = float(ev.get('stack') or 0)
    if size <= 0 or pot <= 0 or stack <= 0:
        return None
    return min(stack, int(round(pot * size / 100.0)) * 100)


def _arm_context(ev, selected):
    """make_plan에서 이 arm이 실제로 보게 되는 세 context 값."""
    ctx = {
        'oop_vs_aggr': RP.BASELINE_DEFAULT['oop_vs_aggr'],
        'oop_legacy_abs': RP.BASELINE_DEFAULT['oop_legacy_abs'],
        'initiative': RP.BASELINE_DEFAULT['initiative'],
    }
    for field in selected:
        ctx[field] = ev['current'][field]
    return ctx


def _block_gate(ctx):
    oop_a = (ctx['oop_vs_aggr'] if ctx['oop_vs_aggr'] is not None
             else bool(ctx['oop_legacy_abs']))
    return bool(oop_a) and not bool(ctx['initiative'])


def analyze(events, hb=None):
    out = OrderedDict()
    baseline = []

    for i, ev in enumerate(events):
        baseline.append(RP._replay(ev, ()))
        if hb is not None:
            hb.hit('baseline replay %d/%d' % (i + 1, len(events)))

    for arm_name, selected in ARMS.items():
        effective = 0
        gate_true = 0
        changed = 0
        chip_changed = 0
        plan_block = 0
        block_msg = 0
        kinds = Counter()
        samples = []

        for i, ev in enumerate(events):
            if any(not RP._same(ev['current'][f],
                                RP._effective_baseline(ev, f))
                   for f in selected):
                effective += 1

            ctx = _arm_context(ev, selected)
            if _block_gate(ctx):
                gate_true += 1

            alt = RP._replay(ev, selected)
            a = RP._intent_sig(baseline[i], ev['street'])
            b = RP._intent_sig(alt, ev['street'])
            dk = RP._diff_kind(a, b)

            if (alt or {}).get('plan') == 'block':
                plan_block += 1
            if any(BLOCK_MSG in str(x) for x in ((alt or {}).get('why') or [])):
                block_msg += 1

            ca = chip_target(baseline[i], ev)
            cb = chip_target(alt, ev)
            if ca != cb:
                chip_changed += 1

            if dk:
                changed += 1
                kinds['+'.join(dk)] += 1
                if len(samples) < 8:
                    samples.append({
                        'event': i,
                        'street': ev['street'],
                        'selected': list(selected),
                        'arm_context': ctx,
                        'baseline_output': a,
                        'current_output': b,
                        'baseline_chip_target': ca,
                        'current_chip_target': cb,
                        'diff': list(dk),
                    })

            if hb is not None:
                hb.hit('%s replay event %d/%d'
                       % (arm_name, i + 1, len(events)))

        out[arm_name] = {
            'selected': list(selected),
            'effective_events': effective,
            'block_gate_true': gate_true,
            'changed': changed,
            'chip_target_changed': chip_changed,
            'plan_block': plan_block,
            'block_msg': block_msg,
            'diff_kinds': dict(kinds),
            'samples': samples,
        }

    return out


def print_mode(name, events, counts, errors, result):
    print()
    print('## %s' % name)
    print('capture: update_plan=%d revise_path=%d board_changed=%d errors=%d'
          % (counts['update_plan'], counts['revise_path'],
             counts['board_changed'], counts['engine_errors']))
    if errors:
        print('ENGINE ERRORS — 이 mode 결과 무효')
        for e in errors[:8]:
            print('  %s' % e)
        return

    print('%-22s %9s %8s %8s %8s %8s %8s  %s'
          % ('arm', 'effective', 'gate', 'changed', 'chip', 'block', 'blkmsg',
             'diff_kinds'))
    for arm_name in ARMS:
        r = result[arm_name]
        print('%-22s %9d %8d %8d %8d %8d %8d  %s'
              % (arm_name, r['effective_events'], r['block_gate_true'],
                 r['changed'], r['chip_target_changed'], r['plan_block'],
                 r['block_msg'], r['diff_kinds']))

    print()
    print('samples:')
    for arm_name in ARMS:
        ss = result[arm_name]['samples']
        if not ss:
            print('  %s: none' % arm_name)
            continue
        print('  %s:' % arm_name)
        for s in ss:
            print('    event %(event)d %(street)s selected=%(selected)r '
                  'ctx=%(arm_context)r  out %(baseline_output)r -> '
                  '%(current_output)r  chip %(baseline_chip_target)r -> '
                  '%(current_chip_target)r  diff=%(diff)r' % s)


def verdict_line(r):
    return (
        r['effective_events'],
        r['block_gate_true'],
        r['changed'],
        r['chip_target_changed'],
        r['plan_block'],
        r['block_msg'],
        tuple(sorted(r['diff_kinds'].items())),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--heartbeat', type=float, default=10.0)
    ap.add_argument('--mode', choices=('both', 'r1', 'r2'), default='both')
    a = ap.parse_args()

    hb = Heartbeat(a.heartbeat)
    print('# A5 4-B focused replan context re-measurement')
    print('fixture: entries=%d hands=%d seeds=%s fmts=%s'
          % (RP.ENTRIES, RP.HANDS, list(RP.SEEDS), list(RP.FMTS)))
    print('fields:', ', '.join(FIELDS))
    print('arms:', ', '.join(ARMS))
    print('primary diff = plan/intent act/intent size (same as A6)')
    print('IMPORTANT: block gate is (_oop_a AND not initiative), so single-field')
    print('arms cannot activate it from A6 defaults; pair/position3 arms are required.')
    print('chip_target = raw pre-shape bet target only')
    print()

    modes = []
    if a.mode in ('both', 'r1'):
        modes.append(('R1 replication', False))
    if a.mode in ('both', 'r2'):
        modes.append(('R2 clean', True))

    results = {}
    for label, clean in modes:
        hb.hit('%s capture start' % label, force=True)
        events, counts, errors = capture_events(clean=clean, hb=hb)
        hb.hit('%s capture done events=%d' % (label, len(events)), force=True)
        result = analyze(events, hb=hb) if not errors else OrderedDict()
        results[label] = (events, counts, errors, result)
        print_mode(label, events, counts, errors, result)

    print()
    print('## frozen A6 comparison')
    print('%-22s %12s %10s' % ('field', 'old different', 'old changed'))
    for field in FIELDS:
        x = OLD_A6[field]
        print('%-22s %12d %10d'
              % (field, x['different'], x['changed']))

    if len(results) == 2:
        r1 = results['R1 replication']
        r2 = results['R2 clean']
        print()
        print('## R1 vs R2 aggregate agreement')
        if r1[2] or r2[2]:
            print('engine error가 있어 판정 보류')
        else:
            for arm_name in ARMS:
                a1 = verdict_line(r1[3][arm_name])
                a2 = verdict_line(r2[3][arm_name])
                print('  %-22s %s'
                      % (arm_name, 'SAME' if a1 == a2 else 'DIFFERENT'))
            print('SAME이면 cache-clean 여부와 무관하게 같은 aggregate 결론.')
            print('DIFFERENT이면 cache contamination 영향을 명시하고 계약 판정 보류.')

    print()
    print('이 도구는 production을 수정하지 않는다.')
    print('세 필드 중 무엇을 revise_plan 계약에 넣을지는 이 결과와 4-A를 합쳐 결정한다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
