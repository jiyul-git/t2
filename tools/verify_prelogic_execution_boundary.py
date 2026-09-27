#!/usr/bin/env python3
"""Behavior-neutral F7-D judgment -> execution boundary gate.

Runs real all-bot final-table hands and verifies that every observed bet/raise
can be traced through calculated judgment, execution input, expression shaping,
legal clamp, effective-all-in conversion and the final Round.apply target.

This test does not require any strategic coefficient change.
"""
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('T2_BOT_LOG', '0')

import fieldsim as FS
import play
import session as SE


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def make_run(seed):
    f = FS.Field(
        entries=9, start_stack=30000, hero_pid=0, seed=seed,
        hands_per_level=12, itm_frac=0.15, fmt='standard')
    tb = f.hero_table()
    alive = tb.ordered_alive()
    layout = tb.hand_layout()
    seats = [tb.seat_of(p['pid']) for p in alive]
    profs = {str(tb.seat_of(p['pid'])): p['prof'] for p in alive}
    stacks = {tb.seat_of(p['pid']): p['stack'] for p in alive}
    sb, bb = f.blinds()

    h = play.Hand(
        seats, profs, stacks, layout['button'], sb, bb, hero=None,
        seed=seed + 1000000,
        position_map=layout['pos'],
        pre_seats=layout['pre_seats'],
        post_seats=layout['post_seats'],
        sb_seat=layout['sb'],
        bb_seat=layout['bb'])
    h.seat_pid = {
        tb.seat_of(p['pid']): p['pid'] for p in alive
    }
    h.table_id = tb.id
    h.table_max_seat = tb.max_seat
    f.stamp(h)

    run = SE.HandRun(h)
    r = run.start()
    need(r.get('done'), 'hero=None all-bot hand did not finish')
    return h, run


def make_targeted_run(mode, seed):
    """Drive rare execution branches without changing production code."""
    f = FS.Field(
        entries=3, start_stack=30000, hero_pid=0, seed=seed,
        hands_per_level=12, itm_frac=0.15, fmt='standard')
    tb = f.hero_table()
    alive = tb.ordered_alive()
    layout = tb.hand_layout()
    seats = [tb.seat_of(p['pid']) for p in alive]
    profs = {str(tb.seat_of(p['pid'])): p['prof'] for p in alive}
    stacks = {tb.seat_of(p['pid']): p['stack'] for p in alive}
    sb, bb = f.blinds()

    h = play.Hand(
        seats, profs, stacks, layout['button'], sb, bb, hero=None,
        seed=seed + 2000000,
        position_map=layout['pos'],
        pre_seats=layout['pre_seats'],
        post_seats=layout['post_seats'],
        sb_seat=layout['sb'],
        bb_seat=layout['bb'])
    h.seat_pid = {
        tb.seat_of(p['pid']): p['pid'] for p in alive
    }
    h.table_id = tb.id
    h.table_max_seat = tb.max_seat
    f.stamp(h)

    orig_pf = SE.PL.preflop_plan
    orig_act = SE.PL.act_with_plan
    orig_shape = SE.RU.shape_size
    state = {'opened': False, 'raised': False}

    def pf_stub(*args, **kwargs):
        # Limp/call to guarantee a postflop street; BB checks.
        act = 'check' if kwargs.get('can_check') else 'call'
        return act, 0.0, {}

    def act_stub(*args, **kwargs):
        # positional contract:
        # hero, board, profile, plan_state, pot, tocall, stack, street, ...
        tocall = float(args[5] or 0)
        stack = float(args[6] or 0)
        street = args[7]
        if street != 'flop':
            return (('fold', 0) if tocall > 0 else ('check', 0)), 0.5, 0.5

        if mode == 'effective_allin':
            if tocall <= 0 and not state['opened']:
                state['opened'] = True
                # Identity shaping below preserves this 97% strategic target.
                return ('bet', int(stack * 0.97)), 0.5, 0.5
            return (('fold', 0) if tocall > 0 else ('check', 0)), 0.5, 0.5

        if mode == 'min_raise_clamp':
            if tocall <= 0 and not state['opened']:
                state['opened'] = True
                return ('bet', 1000), 0.5, 0.5
            if tocall > 0 and not state['raised']:
                state['raised'] = True
                # Below current + min_raise; session execution must clamp it.
                return ('raise', 1200), 0.5, 0.5
            return (('fold', 0) if tocall > 0 else ('check', 0)), 0.5, 0.5

        raise AssertionError('unknown targeted mode %r' % mode)

    try:
        SE.PL.preflop_plan = pf_stub
        SE.PL.act_with_plan = act_stub
        # Keep targeted numbers exact; shape behavior itself is covered by the
        # natural fixture above.
        SE.RU.shape_size = lambda amount, *_a, **_k: amount
        run = SE.HandRun(h)
        out = run.start()
        need(out.get('done'), '%s targeted hand did not finish' % mode)
        return h
    finally:
        SE.PL.preflop_plan = orig_pf
        SE.PL.act_with_plan = orig_act
        SE.RU.shape_size = orig_shape


rows = []
for seed in range(20260927, 20260947):
    h, run = make_run(seed)
    for rec in getattr(h, 'intents', []) or []:
        # F7-D target pipeline only applies to engine-side bet/raise execution.
        if rec.get('execution_input_act') not in ('bet', 'raise'):
            continue
        rows.append(rec)

need(rows, 'no postflop bet/raise provenance reached in fixture')

required = (
    'calculated_act',
    'calculated_target',
    'execution_input_act',
    'execution_input_target',
    'execution_input_source',
    'shape_called',
    'shape_changed',
    'shaped_target',
    'min_raise_floor',
    'min_raise_clamped',
    'legal_target',
    'final_target',
    'applied_target',
)
for i, rec in enumerate(rows):
    missing = [k for k in required if k not in rec]
    need(not missing, 'row %d missing F7-D keys %r' % (i, missing))
    need(rec['execution_input_source'] == 'judgment',
         'fresh all-bot fixture unexpectedly used replay')
    need(rec['execution_input_act'] in ('bet', 'raise'),
         'bad execution input action')
    need(rec['shaped_target'] is not None,
         'bet/raise lost shaped target')
    need(rec['legal_target'] is not None,
         'bet/raise lost legal target')
    need(rec['final_target'] is not None,
         'bet/raise lost final target')
    need(rec['applied_target'] is not None,
         'bet/raise lost Round.apply target')
    need(float(rec['amt']) == float(rec['final_target']),
         'recorded execution amount differs from final target')
    need(float(rec['applied_target']) == float(rec['final_target']),
         'Round.apply target differs from final target')
    if rec['min_raise_clamped']:
        need(rec['min_raise_floor'] is not None,
             'min-raise clamp has no recorded floor')
        need(float(rec['legal_target']) >= float(rec['shaped_target']),
             'legal clamp moved target downward')
    if rec.get('effective_allin_applied'):
        need(rec.get('actor_cap') is not None,
             'effective all-in has no actor cap')
        need(float(rec['final_target']) == float(rec['actor_cap']),
             'effective all-in did not finish at actor cap')

# Rare branches: force them through the real HandRun execution pipeline.
h_ea = make_targeted_run('effective_allin', 20261001)
ea_rows = [
    r for r in (getattr(h_ea, 'intents', []) or [])
    if r.get('effective_allin_applied')
]
need(ea_rows, 'targeted effective-all-in branch was not reached')
for rec in ea_rows:
    need(float(rec['legal_target']) < float(rec['actor_cap']),
         'effective-all-in fixture started at full actor cap')
    need(float(rec['final_target']) == float(rec['actor_cap']),
         'effective-all-in did not promote final target to actor cap')
    need(float(rec['applied_target']) == float(rec['actor_cap']),
         'effective-all-in actor cap was not applied')

h_clamp = make_targeted_run('min_raise_clamp', 20261002)
clamp_rows = [
    r for r in (getattr(h_clamp, 'intents', []) or [])
    if r.get('min_raise_clamped')
]
need(clamp_rows, 'targeted min-raise clamp branch was not reached')
for rec in clamp_rows:
    need(rec['min_raise_floor'] is not None, 'clamp has no floor')
    need(float(rec['shaped_target']) < float(rec['min_raise_floor']),
         'targeted clamp input was not below floor')
    need(float(rec['legal_target']) == float(rec['min_raise_floor']),
         'legal target did not clamp to min-raise floor')
    need(float(rec['applied_target']) == float(rec['final_target']),
         'clamped final target differs from Round.apply target')

src = (ROOT / 'session.py').read_text(encoding='utf-8')
order = [
    "_calculated_target = a2[1]",
    "_execution_input_target = amt",
    "_shape_called = True",
    "_legal_target = _sent",
    "_final_target = _sent",
    "_applied_target = (",
]
positions = [src.find(x) for x in order]
need(all(x >= 0 for x in positions), 'F7-D source stage marker missing')
need(positions == sorted(positions), 'F7-D execution stages are not ordered')

# Planning layer must not call expression jitter itself.
plan_src = (ROOT / 'plan.py').read_text(encoding='utf-8')
act_start = plan_src.index('def act_with_plan(')
act_end = plan_src.index('\ndef checkraise_decision', act_start)
act_src = plan_src[act_start:act_end]
need('shape_size(' not in act_src,
     'plan.act_with_plan performs execution expression jitter')

shape_n = sum(1 for r in rows if r.get('shape_called'))
shape_changed_n = sum(1 for r in rows if r.get('shape_changed'))
clamp_n = sum(1 for r in rows if r.get('min_raise_clamped'))
ea_n = sum(1 for r in rows if r.get('effective_allin_applied'))

print({
    'natural_bet_raise_rows': len(rows),
    'natural_shape_called': shape_n,
    'natural_shape_changed': shape_changed_n,
    'natural_min_raise_clamped': clamp_n,
    'natural_effective_allin_applied': ea_n,
    'targeted_min_raise_clamped': len(clamp_rows),
    'targeted_effective_allin_applied': len(ea_rows),
})
print('PASS F7-D behavior-neutral judgment/execution provenance boundary')
