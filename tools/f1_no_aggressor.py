#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F-1: aggressor 없는 팟에서 blockbet / donk 의미를 같은 결정 입력으로 비교한다.

Production 코드는 바꾸지 않는다. fieldsim 기준 궤적에서 PL.update_plan 호출을
캡처한 뒤 같은 입력을 세 팔로 재생한다.

  current  현재 production: oop_vs_aggr is None 이면 oop_legacy_abs fallback
  strict   live aggressor가 없으면 blockbet/donk의 aggressor-relative OOP=False
  field    진단용: live aggressor가 없으면 generic oop_field 를 fallback으로 사용

주 비교는 current vs strict 다. field arm은 "어그레서는 없지만 필드 기준 OOP"
라는 별도 해석의 크기만 보기 위한 진단이다.

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


def _get_arg(args, kwargs, sig, name):
    b = sig.bind_partial(*args, **kwargs)
    b.apply_defaults()
    return b.arguments.get(name)


def _aggr_trace(st, street):
    for t in reversed((st or {}).get('trace') or []):
        if t.get('kind') == 'aggression' and t.get('street') == street:
            return {
                'p': t.get('p'),
                'roll': t.get('roll'),
                'why': t.get('why'),
            }
    return {'p': None, 'roll': None, 'why': None}


def _view(st, street):
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


def _sig(v):
    return (
        v.get('plan'),
        v.get('act'),
        v.get('size'),
    )


def _run_arm(orig, args, kwargs, sig, sig_names, arm, ctx):
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
    return _view(out, street), _RNG_COUNT['n']


def capture_seed(seed, hands):
    FS.Field.BOT_LOG = 0
    orig = PL.update_plan
    rec = []
    call_no = {'n': 0}

    def probe(*args, **kwargs):
        fr = sys._getframe(1).f_locals
        h = fr.get('h')
        s = fr.get('s')
        r2 = fr.get('r2')
        ag = fr.get('aggressor')

        call_no['n'] += 1
        ctx = {
            'seed': seed,
            'call_no': call_no['n'],
            'seat': s,
            'pos': (h.pos.get(s) if h is not None and s is not None else None),
            'hand_hash': getattr(h, 'hash', None),
            'reason': 'unknown',
            'legacy_abs': None,
            'field_oop': None,
            'vs_aggr': None,
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

        rec.append({
            'args': copy.deepcopy(args),
            'kwargs': copy.deepcopy(kwargs),
            'ctx': ctx,
        })
        return orig(*args, **kwargs)

    PL.update_plan = probe
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
        PL.update_plan = orig

    return rec, errors


def run(seeds, hands):
    orig = PL.update_plan
    sig = inspect.signature(orig)
    sig_names = list(sig.parameters)

    records = []
    engine_errors = 0
    for seed in seeds:
        rr, ee = capture_seed(seed, hands)
        records.extend(rr)
        engine_errors += ee

    summary = collections.Counter()
    by_reason = collections.Counter()
    divergences = []

    for r in records:
        c = r['ctx']
        summary['captured'] += 1
        by_reason[c['reason']] += 1

        # F-1 모집단: live aggressor가 없어서 oop_vs_aggr가 None인 결정.
        if c['vs_aggr'] is not None:
            continue

        summary['no_live_aggressor'] += 1
        if c['reason'] == 'none':
            summary['aggressor_none'] += 1
        if c['legacy_abs']:
            summary['legacy_true'] += 1
        if c['field_oop']:
            summary['field_oop_true'] += 1
        if c['legacy_abs'] != c['field_oop']:
            summary['legacy_field_disagree'] += 1

        cur, cur_rng = _run_arm(orig, r['args'], r['kwargs'], sig, sig_names, 'current', c)
        strict, strict_rng = _run_arm(orig, r['args'], r['kwargs'], sig, sig_names, 'strict', c)
        field, field_rng = _run_arm(orig, r['args'], r['kwargs'], sig, sig_names, 'field', c)

        for name, v in [('current', cur), ('strict', strict), ('field', field)]:
            if v['plan'] == 'block':
                summary[name + '_block'] += 1
            if v['act'] == 'bet':
                summary[name + '_bet'] += 1

        cur_strict = _sig(cur) != _sig(strict)
        cur_field = _sig(cur) != _sig(field)
        if cur_strict:
            summary['current_vs_strict_output_diff'] += 1
        if cur['plan'] != strict['plan']:
            summary['current_vs_strict_plan_diff'] += 1
        if cur['act'] != strict['act']:
            summary['current_vs_strict_act_diff'] += 1
        if cur['size'] != strict['size']:
            summary['current_vs_strict_size_diff'] += 1
        if cur.get('aggr_p') != strict.get('aggr_p'):
            summary['current_vs_strict_aggr_p_diff'] += 1
        if cur_rng != strict_rng:
            summary['current_vs_strict_rng_count_diff'] += 1
        if (not cur_strict) and cur_rng != strict_rng:
            summary['same_output_rng_count_diff'] += 1

        if cur_field:
            summary['current_vs_field_output_diff'] += 1

        if cur_strict or cur.get('aggr_p') != strict.get('aggr_p'):
            block_related = (cur['plan'] == 'block' or strict['plan'] == 'block')
            p_only = (
                cur['plan'] == strict['plan']
                and cur.get('aggr_p') != strict.get('aggr_p')
            )
            if block_related:
                summary['diff_block_related'] += 1
            if p_only:
                summary['diff_donk_probability_only'] += 1
            divergences.append({
                'seed': c['seed'],
                'call_no': c['call_no'],
                'hand_hash': c['hand_hash'],
                'seat': c['seat'],
                'pos': c['pos'],
                'reason': c['reason'],
                'legacy_abs': c['legacy_abs'],
                'field_oop': c['field_oop'],
                'current': cur,
                'strict': strict,
                'field': field,
                'rng_current': cur_rng,
                'rng_strict': strict_rng,
                'rng_field': field_rng,
            })

    return {
        'fixture': {
            'seeds': list(seeds),
            'hands_per_seed': hands,
            'entries': 100,
            'fmt': 'standard',
        },
        'engine_errors': engine_errors,
        'reason_counts_all_captured': dict(by_reason),
        'summary': dict(summary),
        'divergences': divergences[:100],
        'divergence_count': len(divergences),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='5150,9001,4242')
    ap.add_argument('--hands', type=int, default=20)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    seeds = [int(x) for x in a.seeds.split(',') if x.strip()]
    out = run(seeds, a.hands)

    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    print('F-1 no-aggressor semantics')
    print('fixture:', out['fixture'])
    print('engine_errors:', out['engine_errors'])
    print('reasons:', out['reason_counts_all_captured'])
    for k in sorted(out['summary']):
        print('  %-38s %s' % (k, out['summary'][k]))
    print('divergences:', out['divergence_count'])
    for d in out['divergences'][:20]:
        print(json.dumps(d, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
