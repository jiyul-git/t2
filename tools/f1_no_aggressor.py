#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-1: aggressor 없는 팟에서 blockbet / donk 의미를 같은 결정 입력으로 비교.

Production 코드는 바꾸지 않는다. fieldsim 기준 궤적에서 세 층을 캡처한다.

  1) make_plan          blockbet 생성 의미
  2) attach_intent      donk 억제 확률 의미
  3) update_plan        두 효과가 합쳐진 최종 plan/intent

팔:
  current  현재 production: oop_vs_aggr is None 이면 oop_legacy_abs fallback
  strict   live aggressor가 없으면 aggressor-relative OOP=False
  field    진단용: live aggressor가 없으면 generic oop_field fallback

주 비교는 current vs strict. field는 "어그레서는 없지만 필드 기준 OOP"라는
별도 해석의 크기를 보기 위한 진단이다.

같은 입력 재생이라 trajectory 전파는 측정하지 않는다.
"""
from __future__ import print_function

import argparse
import collections
import copy
import inspect
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import plan as PL
import session as SE

BLOCK_MSG = '블락벳으로 가격 통제'

_BASE_RANDOM = random.Random
_COUNTED = (
    'random', 'uniform', 'gauss', 'choice', 'randrange', 'randint',
    'shuffle', 'betavariate', 'sample', 'triangular', 'choices',
)
_RNG_COUNT = {'n': 0}


class _ProxyRandom:
    __slots__ = ('_r',)

    def __init__(self, *a, **k):
        object.__setattr__(self, '_r', _BASE_RANDOM(*a, **k))

    def __getattr__(self, name):
        f = getattr(object.__getattribute__(self, '_r'), name)
        if name in _COUNTED:
            def g(*a, **k):
                _RNG_COUNT['n'] += 1
                return f(*a, **k)
            return g
        return f


def _set_arg(args, kwargs, sig_names, name, value):
    a = list(args)
    k = dict(kwargs)
    idx = sig_names.index(name)
    if idx < len(a):
        a[idx] = value
    else:
        k[name] = value
    return a, k


def _bound(args, kwargs, sig):
    b = sig.bind_partial(*args, **kwargs)
    b.apply_defaults()
    return b.arguments


def _get_arg(args, kwargs, sig, name):
    return _bound(args, kwargs, sig).get(name)


def _aggr_trace(st, street):
    for t in reversed((st or {}).get('trace') or []):
        if t.get('kind') == 'aggression' and t.get('street') == street:
            return {
                'p': t.get('p'),
                'roll': t.get('roll'),
                'why': t.get('why'),
            }
    return {'p': None, 'roll': None, 'why': None}


def _update_view(st, street):
    it = PL.intent_of(st, street) or {}
    tr = _aggr_trace(st, street)
    return {
        'plan': (st or {}).get('plan'),
        'act': it.get('act'),
        'size': round(float(it.get('size') or 0.0), 6),
        'aggr_p': tr.get('p'),
        'aggr_roll': tr.get('roll'),
        'aggr_why': tr.get('why'),
        'rel': (st or {}).get('rel'),
        'made': (st or {}).get('made'),
        'why': list((st or {}).get('why') or []),
    }


def _make_view(st):
    why = list((st or {}).get('why') or [])
    return {
        'plan': (st or {}).get('plan'),
        'rel': (st or {}).get('rel'),
        'made': (st or {}).get('made'),
        'block_msg': any(BLOCK_MSG in str(x) for x in why),
        'why': why,
    }


def _out_sig(v):
    return (v.get('plan'), v.get('act'), v.get('size'))


def _run_update_arm(orig, args, kwargs, sig, sig_names, arm):
    a = copy.deepcopy(args)
    k = copy.deepcopy(kwargs)

    if arm == 'strict':
        a, k = _set_arg(a, k, sig_names, 'oop_legacy_abs', False)
    elif arm == 'field':
        field_oop = bool(_get_arg(a, k, sig, 'oop'))
        a, k = _set_arg(a, k, sig_names, 'oop_legacy_abs', field_oop)
    elif arm != 'current':
        raise ValueError(arm)

    _RNG_COUNT['n'] = 0
    random.Random = _ProxyRandom
    try:
        out = orig(*a, **k)
    finally:
        random.Random = _BASE_RANDOM

    street = _get_arg(a, k, sig, 'street')
    return _update_view(out, street), _RNG_COUNT['n']


def _run_make_arm(orig, args, kwargs, sig, sig_names, arm):
    a = copy.deepcopy(args)
    k = copy.deepcopy(kwargs)
    if arm == 'strict':
        a, k = _set_arg(a, k, sig_names, 'oop_legacy_abs', False)
    elif arm == 'field':
        # make_plan에는 generic oop 인자가 없다. field arm 값은 캡처 시
        # caller update_plan의 oop_field를 따로 저장해 넣는다.
        raise RuntimeError('field arm requires explicit legacy value')
    elif arm != 'current':
        raise ValueError(arm)
    out = orig(*a, **k)
    return _make_view(out)


def _run_make_with_legacy(orig, args, kwargs, sig_names, legacy_value):
    a = copy.deepcopy(args)
    k = copy.deepcopy(kwargs)
    a, k = _set_arg(a, k, sig_names, 'oop_legacy_abs', bool(legacy_value))
    return _make_view(orig(*a, **k))


def _aggr_p(orig_da, rec, legacy_value):
    return orig_da(
        copy.deepcopy(rec['profile']),
        copy.deepcopy(rec['board']),
        rec['street'],
        rec['plan'],
        rec['rel'],
        rec['n_opp'],
        rec['oop'],
        rec['initiative'],
        rec['behind'],
        random.Random(0),
        copy.deepcopy(rec['opp_est']),
        rec['outs'],
        copy.deepcopy(rec['plan_state']),
        oop_vs_aggr=None,
        oop_legacy_abs=bool(legacy_value),
    )[0]


def capture_seed(seed, hands):
    FS.Field.BOT_LOG = 0

    orig_update = PL.update_plan
    orig_make = PL.make_plan
    orig_attach = PL.attach_intent
    orig_da = PL.decide_aggression

    update_sig = inspect.signature(orig_update)
    make_sig = inspect.signature(orig_make)
    attach_sig = inspect.signature(orig_attach)

    update_rec = []
    make_rec = []
    intent_rec = []
    call_no = {'update': 0, 'make': 0, 'intent': 0}

    # update_plan wrapper: caller frame에서 실제 aggressor 상태까지 기록.
    def wrap_update(*args, **kwargs):
        fr = sys._getframe(1).f_locals
        h = fr.get('h')
        s = fr.get('s')
        r2 = fr.get('r2')
        ag = fr.get('aggressor')

        call_no['update'] += 1
        b = _bound(args, kwargs, update_sig)
        ctx = {
            'seed': seed,
            'call_no': call_no['update'],
            'seat': s,
            'pos': (h.pos.get(s) if h is not None and s is not None else None),
            'hand_hash': getattr(h, 'hash', None),
            'reason': 'unknown',
            'legacy_abs': b.get('oop_legacy_abs'),
            'field_oop': b.get('oop'),
            'vs_aggr': b.get('oop_vs_aggr'),
        }

        if h is not None and s is not None and r2 is not None and s in r2.order:
            order = list(r2.order)
            live_aggr = (
                ag is not None
                and ag != s
                and ag in order
                and ag not in r2.folded
                and ag not in r2.allin
            )
            if ag is None:
                reason = 'none'
            elif ag == s:
                reason = 'self'
            elif ag not in order:
                reason = 'not_in_order'
            elif ag in r2.folded:
                reason = 'folded'
            elif ag in r2.allin:
                reason = 'allin'
            else:
                reason = 'live'
            ctx.update({
                'reason': reason,
                'legacy_abs': bool(h.POST.index(h.pos[s]) < 3),
                'field_oop': bool(SE.oop_field(order, s, r2.folded, r2.allin)),
                'vs_aggr': (SE.oop_vs(order, s, ag) if live_aggr else None),
            })

        update_rec.append({
            'args': copy.deepcopy(args),
            'kwargs': copy.deepcopy(kwargs),
            'ctx': ctx,
        })
        return orig_update(*args, **kwargs)

    # make_plan wrapper: blockbet consumer를 직접 격리.
    def wrap_make(*args, **kwargs):
        call_no['make'] += 1
        b = _bound(args, kwargs, make_sig)
        out = orig_make(*args, **kwargs)
        if b.get('oop_vs_aggr') is None:
            # update_plan caller의 generic oop을 직접 알 수 없으므로 같은 stack
            # 안에서 wrap_update의 현재 호출 context를 사용한다.
            field_oop = None
            if update_rec:
                field_oop = update_rec[-1]['ctx'].get('field_oop')
            make_rec.append({
                'seed': seed,
                'call_no': call_no['make'],
                'args': copy.deepcopy(args),
                'kwargs': copy.deepcopy(kwargs),
                'field_oop': bool(field_oop),
                'current_actual': _make_view(out),
            })
        return out

    # attach_intent wrapper: donk suppression consumer를 현재 plan 고정 상태에서 격리.
    def wrap_attach(*args, **kwargs):
        call_no['intent'] += 1
        b = _bound(args, kwargs, attach_sig)
        out = orig_attach(*args, **kwargs)
        if b.get('oop_vs_aggr') is None:
            st = b['st']
            street = b['street']
            tr = _aggr_trace(out, street)
            if tr.get('roll') is not None:
                intent_rec.append({
                    'seed': seed,
                    'call_no': call_no['intent'],
                    'profile': copy.deepcopy(b['profile']),
                    'board': copy.deepcopy(b['board']),
                    'street': street,
                    'plan': st.get('plan'),
                    'rel': st.get('rel', 0.5),
                    'n_opp': b['n_opp'],
                    'oop': bool(b['oop']),
                    'initiative': bool(b['initiative']),
                    'behind': b['to_act_behind'],
                    'opp_est': copy.deepcopy(b.get('opp_est')),
                    'outs': st.get('outs', 0),
                    'plan_state': copy.deepcopy(st),
                    'legacy_abs': bool(b.get('oop_legacy_abs')),
                    'roll': float(tr['roll']),
                    'current_trace_p': tr.get('p'),
                })
        return out

    PL.update_plan = wrap_update
    PL.make_plan = wrap_make
    PL.attach_intent = wrap_attach
    try:
        f = FS.Field(entries=100, seed=seed, fmt='standard')
        for _ in range(hands):
            if f.remaining() <= 8:
                break
            f.hand_no += 1
            f.advance_level()
            for tb in list(f.tables.values()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
            f.notes = []
        errors = len(f.errors)
    finally:
        PL.update_plan = orig_update
        PL.make_plan = orig_make
        PL.attach_intent = orig_attach

    return update_rec, make_rec, intent_rec, errors


def run(seeds, hands):
    orig_update = PL.update_plan
    orig_make = PL.make_plan
    orig_da = PL.decide_aggression

    update_sig = inspect.signature(orig_update)
    update_names = list(update_sig.parameters)
    make_sig = inspect.signature(orig_make)
    make_names = list(make_sig.parameters)

    updates = []
    makes = []
    intents = []
    engine_errors = 0
    for seed in seeds:
        ur, mr, ir, ee = capture_seed(seed, hands)
        updates.extend(ur)
        makes.extend(mr)
        intents.extend(ir)
        engine_errors += ee

    summary = collections.Counter()
    reason_counts = collections.Counter()
    update_div = []
    make_div = []
    intent_div = []

    # ---------- final update_plan level ----------
    for r in updates:
        c = r['ctx']
        summary['update_captured'] += 1
        reason_counts[c['reason']] += 1
        if c['vs_aggr'] is not None:
            continue

        summary['update_no_live_aggressor'] += 1
        if c['reason'] == 'none':
            summary['update_aggressor_none'] += 1
        if c['legacy_abs']:
            summary['update_legacy_true'] += 1
        if c['field_oop']:
            summary['update_field_oop_true'] += 1
        if bool(c['legacy_abs']) != bool(c['field_oop']):
            summary['update_legacy_field_disagree'] += 1

        cur, cur_rng = _run_update_arm(
            orig_update, r['args'], r['kwargs'], update_sig, update_names, 'current')
        strict, strict_rng = _run_update_arm(
            orig_update, r['args'], r['kwargs'], update_sig, update_names, 'strict')

        out_diff = _out_sig(cur) != _out_sig(strict)
        p_diff = cur.get('aggr_p') != strict.get('aggr_p')
        if out_diff:
            summary['update_output_diff'] += 1
        if cur['plan'] != strict['plan']:
            summary['update_plan_diff'] += 1
        if cur['act'] != strict['act']:
            summary['update_act_diff'] += 1
        if cur['size'] != strict['size']:
            summary['update_size_diff'] += 1
        if p_diff:
            summary['update_aggr_p_diff'] += 1
        if cur_rng != strict_rng:
            summary['update_rng_count_diff'] += 1
        if (not out_diff) and cur_rng != strict_rng:
            summary['update_same_output_rng_count_diff'] += 1
        if cur['plan'] == 'block':
            summary['update_current_block'] += 1
        if strict['plan'] == 'block':
            summary['update_strict_block'] += 1

        if out_diff or p_diff:
            update_div.append({
                'ctx': c,
                'current': cur,
                'strict': strict,
                'rng_current': cur_rng,
                'rng_strict': strict_rng,
            })

    # ---------- make_plan / blockbet isolation ----------
    for r in makes:
        summary['make_no_relative_aggressor'] += 1
        b = _bound(r['args'], r['kwargs'], make_sig)
        legacy = bool(b.get('oop_legacy_abs'))
        field_oop = bool(r.get('field_oop'))
        if legacy:
            summary['make_legacy_true'] += 1
        if field_oop:
            summary['make_field_oop_true'] += 1

        cur = _run_make_arm(orig_make, r['args'], r['kwargs'], make_sig, make_names, 'current')
        strict = _run_make_with_legacy(orig_make, r['args'], r['kwargs'], make_names, False)
        field = _run_make_with_legacy(orig_make, r['args'], r['kwargs'], make_names, field_oop)

        if cur != r['current_actual']:
            summary['make_current_replay_mismatch'] += 1

        for name, v in [('current', cur), ('strict', strict), ('field', field)]:
            if v['plan'] == 'block':
                summary['make_' + name + '_block'] += 1
            if v['block_msg']:
                summary['make_' + name + '_block_msg'] += 1

        if cur['plan'] != strict['plan']:
            summary['make_current_vs_strict_plan_diff'] += 1
        if cur['block_msg'] != strict['block_msg']:
            summary['make_current_vs_strict_block_msg_diff'] += 1
        if (cur['plan'] == 'block') != (strict['plan'] == 'block'):
            summary['make_current_vs_strict_block_survival_diff'] += 1
        if cur['plan'] != field['plan']:
            summary['make_current_vs_field_plan_diff'] += 1

        if (cur['plan'] != strict['plan']
                or cur['block_msg'] != strict['block_msg']):
            make_div.append({
                'seed': r['seed'],
                'call_no': r['call_no'],
                'legacy_abs': legacy,
                'field_oop': field_oop,
                'current': cur,
                'strict': strict,
                'field': field,
            })

    # ---------- decide_aggression / donk suppression isolation ----------
    by_plan = collections.Counter()
    for r in intents:
        summary['intent_no_relative_aggressor'] += 1
        if r['legacy_abs']:
            summary['intent_legacy_true'] += 1
        if r['oop']:
            summary['intent_field_oop_true'] += 1

        p_cur = _aggr_p(orig_da, r, r['legacy_abs'])
        p_strict = _aggr_p(orig_da, r, False)
        p_field = _aggr_p(orig_da, r, r['oop'])

        # trace p는 3자리 반올림이므로 0.001 허용.
        if r['current_trace_p'] is not None and abs(
                float(r['current_trace_p']) - float(p_cur)) > 0.0011:
            summary['intent_current_replay_mismatch'] += 1

        cur_bet = r['roll'] < p_cur
        strict_bet = r['roll'] < p_strict
        field_bet = r['roll'] < p_field

        if abs(p_cur - p_strict) > 1e-12:
            summary['intent_current_vs_strict_p_diff'] += 1
            by_plan[r['plan']] += 1
        if cur_bet != strict_bet:
            summary['intent_projected_action_diff'] += 1
        if abs(p_cur - p_field) > 1e-12:
            summary['intent_current_vs_field_p_diff'] += 1

        if abs(p_cur - p_strict) > 1e-12:
            intent_div.append({
                'seed': r['seed'],
                'call_no': r['call_no'],
                'street': r['street'],
                'plan': r['plan'],
                'rel': r['rel'],
                'oop_field': r['oop'],
                'legacy_abs': r['legacy_abs'],
                'initiative': r['initiative'],
                'outs': r['outs'],
                'roll': r['roll'],
                'p_current': round(p_cur, 6),
                'p_strict': round(p_strict, 6),
                'p_field': round(p_field, 6),
                'bet_current': cur_bet,
                'bet_strict': strict_bet,
                'bet_field': field_bet,
            })

    return {
        'fixture': {
            'seeds': list(seeds),
            'hands_per_seed': hands,
            'entries': 100,
            'fmt': 'standard',
        },
        'engine_errors': engine_errors,
        'reason_counts_all_update_calls': dict(reason_counts),
        'summary': dict(summary),
        'intent_p_diff_by_plan': dict(by_plan),
        'update_divergence_count': len(update_div),
        'make_divergence_count': len(make_div),
        'intent_divergence_count': len(intent_div),
        'update_divergences': update_div[:100],
        'make_divergences': make_div[:100],
        'intent_divergences': intent_div[:100],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='5150,9001,4242')
    ap.add_argument('--hands', type=int, default=20)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--verify', action='store_true')
    a = ap.parse_args()

    seeds = [int(x) for x in a.seeds.split(',') if x.strip()]
    out = run(seeds, a.hands)

    if a.verify:
        sm = out['summary']
        checks = {
            'engine_errors': out['engine_errors'] == 0,
            'population': sm.get('update_no_live_aggressor', 0) > 0,
            'update_output': sm.get('update_output_diff', 0) == 0,
            'update_plan': sm.get('update_plan_diff', 0) == 0,
            'update_act': sm.get('update_act_diff', 0) == 0,
            'update_size': sm.get('update_size_diff', 0) == 0,
            'update_aggr_p': sm.get('update_aggr_p_diff', 0) == 0,
            'update_rng': sm.get('update_rng_count_diff', 0) == 0,
            'make_plan': sm.get('make_current_vs_strict_plan_diff', 0) == 0,
            'make_block_msg': sm.get('make_current_vs_strict_block_msg_diff', 0) == 0,
            'make_block_survival': sm.get('make_current_vs_strict_block_survival_diff', 0) == 0,
            'intent_p': sm.get('intent_current_vs_strict_p_diff', 0) == 0,
            'intent_action': sm.get('intent_projected_action_diff', 0) == 0,
            'make_replay': sm.get('make_current_replay_mismatch', 0) == 0,
            'intent_replay': sm.get('intent_current_replay_mismatch', 0) == 0,
        }
        for name, ok in checks.items():
            print('%-24s %s' % (name, 'PASS' if ok else 'FAIL'))
        if not all(checks.values()):
            return 1
        print('PASS F-1 strict no-live-aggressor semantics')
        return 0

    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    print('F-1 no-aggressor semantics')
    print('fixture:', out['fixture'])
    print('engine_errors:', out['engine_errors'])
    print('reasons:', out['reason_counts_all_update_calls'])
    print('intent p-diff by plan:', out['intent_p_diff_by_plan'])
    for k in sorted(out['summary']):
        print('  %-46s %s' % (k, out['summary'][k]))
    print('update divergences:', out['update_divergence_count'])
    print('make divergences:', out['make_divergence_count'])
    print('intent divergences:', out['intent_divergence_count'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
