#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A6 replan input/provenance characterization.

Production 코드를 바꾸지 않고, board_changed -> revise_plan -> make_plan 경로가
현재 decision context 대신 기본값/옛 plan snapshot을 쓰는 문제를 측정한다.

측정 대상 7개:
  oop_vs_aggr
  oop_legacy_abs
  initiative
  tilt
  bb_chips
  opp_est
  opp_stack_bb

두 질문을 분리한다.

1) provenance mismatch
   현재 update_plan 입력과 revise_plan이 실제 make_plan에 쓰는 값이 몇 번 다른가?

2) behavioral impact
   그 필드 하나만 현재값으로 교체했을 때 최종 update_plan 반환의
   plan / intent act / intent size가 몇 번 달라지는가?

모든 반사실은 live run이 끝난 뒤 deep-copy한 입력을 재생한다.
live 엔진 RNG 스트림을 건드리지 않는다.

고정 fixture:
  seeds 5150,9001,4242
  fmt standard,deep,turbo
  각 16 global hands
  entries=100

과거 조사에서 이 fixture는 board_changed 재계획 make_plan 810건을 냈다.
이 도구는 그 수를 먼저 출력하지만, 숫자를 맞추기 위해 production을
바꾸지 않는다.

실행:
  python3 tools/replan_provenance.py
  python3 tools/replan_provenance.py --json
"""
from __future__ import print_function

import argparse
import copy
import inspect
import json
import os
import sys
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import plan as PL
import runner as RU


SEEDS = (5150, 9001, 4242)
FMTS = ('standard', 'deep', 'turbo')
HANDS = 16
ENTRIES = 100

FIELDS = (
    'oop_vs_aggr',
    'oop_legacy_abs',
    'initiative',
    'tilt',
    'bb_chips',
    'opp_est',
    'opp_stack_bb',
)

# revise_plan 현재 production 의미.
# opp_* 둘은 state snapshot, 나머지 다섯은 make_plan 기본값.
BASELINE_DEFAULT = {
    'oop_vs_aggr': None,
    'oop_legacy_abs': None,
    'initiative': True,
    'tilt': 0.0,
    'bb_chips': None,
}


def _same(a, b):
    """provenance equality. float은 이 경로에서 계산식이 단순하므로 exact 비교."""
    return a == b


def _intent_sig(st, street):
    it = PL.intent_of(st, street) or {}
    return {
        'plan': (st or {}).get('plan'),
        'act': it.get('act'),
        'size': round(it.get('size', 0) or 0, 6),
    }


def _diff_kind(a, b):
    out = []
    for k in ('plan', 'act', 'size'):
        if a.get(k) != b.get(k):
            out.append(k)
    return tuple(out)


def _capture_events():
    """live run에서는 입력만 저장. 반사실 재생은 끝난 뒤 한다."""
    orig_update = PL.update_plan
    sig_update = inspect.signature(orig_update)
    events = []
    counts = Counter()

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
                # update_plan의 완전한 호출 입력을 보존한다.
                # 이후 replay에서 원본 호출과 current-context arm을 동일 입력으로 비교한다.
                events.append({
                    'args': copy.deepcopy(a),
                    'kwargs': copy.deepcopy(k),
                    'current': {
                        'oop_vs_aggr': copy.deepcopy(b.arguments.get('oop_vs_aggr')),
                        'oop_legacy_abs': copy.deepcopy(b.arguments.get('oop_legacy_abs')),
                        'initiative': copy.deepcopy(b.arguments.get('initiative')),
                        'tilt': copy.deepcopy(b.arguments.get('tilt')),
                        'bb_chips': copy.deepcopy(b.arguments.get('bb_chips')),
                        'opp_est': copy.deepcopy(b.arguments.get('opp_est')),
                        'opp_stack_bb': copy.deepcopy(b.arguments.get('opp_stack_bb')),
                    },
                    'snapshot': {
                        'opp_est': copy.deepcopy((state or {}).get('opp_est')),
                        'opp_stack_bb': copy.deepcopy((state or {}).get('opp_stack_bb')),
                    },
                    'street': b.arguments.get('street'),
                })
        return orig_update(*a, **k)

    PL.update_plan = wrapped
    old_bot_log = getattr(FS.Field, 'BOT_LOG', None)
    errors = []
    try:
        if hasattr(FS.Field, 'BOT_LOG'):
            FS.Field.BOT_LOG = 0

        for fmt in FMTS:
            for seed in SEEDS:
                f = FS.Field(entries=ENTRIES, seed=seed, fmt=fmt)
                for _ in range(HANDS):
                    if f.remaining() <= 8:
                        break
                    f.hand_no += 1
                    f.advance_level()
                    for tb in list(f.tables.values()):
                        if tb.n() >= 2:
                            f._play_table(tb)
                    f._collect_busts()
                    f._balance()
                errors.extend(getattr(f, 'errors', ()) or ())
    finally:
        PL.update_plan = orig_update
        if old_bot_log is not None:
            FS.Field.BOT_LOG = old_bot_log

    counts['engine_errors'] = len(errors)
    return events, counts, errors


def _effective_baseline(event, field):
    if field in ('opp_est', 'opp_stack_bb'):
        return event['snapshot'][field]
    return BASELINE_DEFAULT[field]


def _candidate_revise_factory(current, selected):
    """선택한 필드만 current context를 쓰는 revise_plan."""
    def candidate(state, hero, board, my_range, opp_range, profile, pot, stack, street,
                  seed, n_opp, behind, prev_board):
        if not RU.board_changed(prev_board, board):
            return state

        kw = {
            'seed': seed,
            'n_opp': n_opp,
            'to_act_behind': behind,
            # production baseline은 snapshot을 쓴다.
            'opp_est': state.get('opp_est'),
            'opp_stack_bb': state.get('opp_stack_bb'),
        }

        # 누락 5개는 선택되지 않으면 아예 넘기지 않아 make_plan 기본값을 유지한다.
        if 'oop_vs_aggr' in selected:
            kw['oop_vs_aggr'] = current.get('oop_vs_aggr')
        if 'oop_legacy_abs' in selected:
            kw['oop_legacy_abs'] = current.get('oop_legacy_abs')
        if 'initiative' in selected:
            kw['initiative'] = current.get('initiative')
        if 'tilt' in selected:
            kw['tilt'] = current.get('tilt')
        if 'bb_chips' in selected:
            kw['bb_chips'] = current.get('bb_chips')

        # snapshot 두 필드는 선택되면 current로 교체한다.
        if 'opp_est' in selected:
            kw['opp_est'] = current.get('opp_est')
        if 'opp_stack_bb' in selected:
            kw['opp_stack_bb'] = current.get('opp_stack_bb')

        new = PL.make_plan(
            hero, board, my_range, opp_range, profile, pot, stack, street, **kw)
        new['revised'] = True
        for key in ('intents', 'deviations', 'streets', 'refreshed', 'bet_streets',
                    'plan_since', '_rsig'):
            if state.get(key) is not None:
                new[key] = state[key]
        return new
    return candidate


def _replay(event, selected=()):
    """한 event를 production arm 또는 selected-current arm으로 재생."""
    orig_revise = RU.revise_plan
    try:
        if selected:
            RU.revise_plan = _candidate_revise_factory(
                event['current'], set(selected))
        args = copy.deepcopy(event['args'])
        kwargs = copy.deepcopy(event['kwargs'])
        return PL.update_plan(*args, **kwargs)
    finally:
        RU.revise_plan = orig_revise


def _sample_value(v):
    if isinstance(v, dict):
        # 큰 opponent estimate 전체를 출력하지 않는다.
        keys = ('type', 'n', 'confidence', 'vpip', 'pfr', 'ftb', 'aggr', 'bluff')
        return {k: v.get(k) for k in keys if k in v}
    return v


def analyze(events):
    prov = OrderedDict()
    for field in FIELDS:
        diff = 0
        samples = []
        for i, ev in enumerate(events):
            cur = ev['current'][field]
            base = _effective_baseline(ev, field)
            if not _same(cur, base):
                diff += 1
                if len(samples) < 4:
                    samples.append({
                        'event': i,
                        'street': ev['street'],
                        'baseline': _sample_value(base),
                        'current': _sample_value(cur),
                    })
        prov[field] = {
            'different': diff,
            'total': len(events),
            'samples': samples,
        }

    # baseline output은 event마다 한 번만 계산한다.
    base_out = []
    for ev in events:
        base_out.append(_replay(ev, ()))

    impact = OrderedDict()
    for field in FIELDS:
        changed = 0
        kinds = Counter()
        samples = []
        for i, ev in enumerate(events):
            # 값이 동일한 event는 재생할 필요가 없다.
            if _same(ev['current'][field], _effective_baseline(ev, field)):
                continue
            alt = _replay(ev, (field,))
            a = _intent_sig(base_out[i], ev['street'])
            b = _intent_sig(alt, ev['street'])
            dk = _diff_kind(a, b)
            if dk:
                changed += 1
                kinds['+'.join(dk)] += 1
                if len(samples) < 4:
                    samples.append({
                        'event': i,
                        'street': ev['street'],
                        'baseline_context': _sample_value(
                            _effective_baseline(ev, field)),
                        'current_context': _sample_value(ev['current'][field]),
                        'baseline_output': a,
                        'current_output': b,
                        'diff': list(dk),
                    })
        impact[field] = {
            'changed': changed,
            'different_input': prov[field]['different'],
            'diff_kinds': dict(kinds),
            'samples': samples,
        }

    # 전체 7개를 한 번에 current로 넘긴 경우.
    all_changed = 0
    all_kinds = Counter()
    all_samples = []
    for i, ev in enumerate(events):
        alt = _replay(ev, FIELDS)
        a = _intent_sig(base_out[i], ev['street'])
        b = _intent_sig(alt, ev['street'])
        dk = _diff_kind(a, b)
        if dk:
            all_changed += 1
            all_kinds['+'.join(dk)] += 1
            if len(all_samples) < 6:
                all_samples.append({
                    'event': i,
                    'street': ev['street'],
                    'baseline_output': a,
                    'all_current_output': b,
                    'diff': list(dk),
                })

    # interaction attribution. 단독 합보다 all-current가 크면 어떤 조합에서
    # 새 divergence가 생기는지 arm별 event set으로 분해한다.
    arms = OrderedDict([
        ('bb+opp_est', ('bb_chips', 'opp_est')),
        ('bb+opp_stack', ('bb_chips', 'opp_stack_bb')),
        ('opp_est+opp_stack', ('opp_est', 'opp_stack_bb')),
        ('context_core3', ('bb_chips', 'opp_est', 'opp_stack_bb')),
        ('core+initiative', ('bb_chips', 'opp_est', 'initiative')),
        ('core+oop_vs', ('bb_chips', 'opp_est', 'oop_vs_aggr')),
        ('core+oop_legacy', ('bb_chips', 'opp_est', 'oop_legacy_abs')),
        ('core+position', ('bb_chips', 'opp_est', 'oop_vs_aggr',
                           'oop_legacy_abs', 'initiative')),
        ('all7', FIELDS),
    ])
    arm_out = OrderedDict()
    arm_sets = {}
    for name, selected in arms.items():
        changed_idx = []
        kinds = Counter()
        for i, ev in enumerate(events):
            alt = _replay(ev, selected)
            a = _intent_sig(base_out[i], ev['street'])
            b = _intent_sig(alt, ev['street'])
            dk = _diff_kind(a, b)
            if dk:
                changed_idx.append(i)
                kinds['+'.join(dk)] += 1
        arm_sets[name] = set(changed_idx)
        arm_out[name] = {
            'fields': list(selected),
            'changed': len(changed_idx),
            'event_ids': changed_idx,
            'diff_kinds': dict(kinds),
        }

    # leave-one-out from all7. all7에서 한 필드를 빼서 변화 수/사건이 줄면
    # 그 필드는 단독 효과가 0이어도 interaction에는 기여한다.
    loo = OrderedDict()
    allset = arm_sets['all7']
    for field in FIELDS:
        selected = tuple(x for x in FIELDS if x != field)
        changed_idx = []
        kinds = Counter()
        for i, ev in enumerate(events):
            alt = _replay(ev, selected)
            a = _intent_sig(base_out[i], ev['street'])
            b = _intent_sig(alt, ev['street'])
            dk = _diff_kind(a, b)
            if dk:
                changed_idx.append(i)
                kinds['+'.join(dk)] += 1
        aset = set(changed_idx)
        loo[field] = {
            'all_without_changed': len(changed_idx),
            'removed_from_all': len(allset - aset),
            'added_vs_all': len(aset - allset),
            'removed_event_ids': sorted(allset - aset),
            'added_event_ids': sorted(aset - allset),
            'diff_kinds': dict(kinds),
        }

    return {
        'provenance': prov,
        'impact': impact,
        'all_current': {
            'changed': all_changed,
            'total': len(events),
            'diff_kinds': dict(all_kinds),
            'samples': all_samples,
        },
        'interaction_arms': arm_out,
        'leave_one_out': loo,
    }


def human(events, counts, result):
    print('A6 replan provenance characterization')
    print('fixture: entries=%d, hands=%d, seeds=%s, fmts=%s'
          % (ENTRIES, HANDS, ','.join(map(str, SEEDS)), ','.join(FMTS)))
    print()
    print('update_plan=%d  revise_path=%d  board_changed/replan=%d  engine_errors=%d'
          % (counts['update_plan'], counts['revise_path'],
             counts['board_changed'], counts['engine_errors']))
    print()

    print('## 1. provenance mismatch')
    print('  %-18s %10s %10s %8s' % ('field', 'different', 'total', 'rate'))
    for field in FIELDS:
        r = result['provenance'][field]
        rate = 100.0 * r['different'] / max(1, r['total'])
        print('  %-18s %10d %10d %7.1f%%'
              % (field, r['different'], r['total'], rate))
    print()

    print('## 2. one-field current-context counterfactual')
    print('  %-18s %12s %10s %12s' %
          ('field', 'input differs', 'changed', 'changed/diff'))
    for field in FIELDS:
        r = result['impact'][field]
        pct = 100.0 * r['changed'] / max(1, r['different_input'])
        print('  %-18s %12d %10d %11.2f%%  %s'
              % (field, r['different_input'], r['changed'], pct,
                 r['diff_kinds']))
    print()

    a = result['all_current']
    print('## 3. all seven current together')
    print('  changed %d / %d = %.3f%%   %s'
          % (a['changed'], a['total'],
             100.0*a['changed']/max(1, a['total']), a['diff_kinds']))
    print()

    print('## 4. interaction arms')
    for name, r in result['interaction_arms'].items():
        print('  %-20s changed=%3d  events=%s'
              % (name, r['changed'], r['event_ids']))
    print()

    print('## 5. leave-one-out from all7')
    print('  %-18s %12s %12s %10s'
          % ('field', 'without', 'removed', 'added'))
    for field, r in result['leave_one_out'].items():
        print('  %-18s %12d %12d %10d'
              % (field, r['all_without_changed'],
                 r['removed_from_all'], r['added_vs_all']))
        if r['removed_event_ids'] or r['added_event_ids']:
            print('    removed=%s added=%s'
                  % (r['removed_event_ids'], r['added_event_ids']))
    print()

    # 행동이 실제로 바뀐 샘플만 짧게.
    any_sample = False
    for field in FIELDS:
        ss = result['impact'][field]['samples']
        if not ss:
            continue
        any_sample = True
        print('## sample: %s' % field)
        for x in ss:
            print('  event %(event)d %(street)s  %(baseline_context)r -> '
                  '%(current_context)r' % x)
            print('    %(baseline_output)r -> %(current_output)r  diff=%(diff)s' % x)
        print()
    if not any_sample:
        print('행동 변화 샘플 없음')


def main():
    ap = argparse.ArgumentParser(description='replan current-vs-snapshot provenance')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    events, counts, errors = _capture_events()
    result = analyze(events)

    payload = {
        'fixture': {
            'entries': ENTRIES,
            'hands': HANDS,
            'seeds': list(SEEDS),
            'fmts': list(FMTS),
        },
        'counts': dict(counts),
        'result': result,
        'engine_error_samples': list(errors[:5]),
    }

    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        human(events, counts, result)
        if errors:
            print()
            print('ENGINE ERRORS — 결과 해석 중단')
            for e in errors[:5]:
                print('  ' + str(e))
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
