#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A5 reachability instrumentation.

Production 코드를 바꾸지 않고 "있다"와 "실제로 살아 있다"를 분리해 센다.

각 probe는 같은 공용 schema를 낸다.

  eligible   모집단
  entered    해당 함수/계층까지 실제 진입
  gate_true  핵심 gate 조건이 참
  taken      branch가 실제 선택됨
  changed    최종 반환/행동까지 영향이 살아남음

중요:
- 숫자를 맞추기 위해 production을 바꾸지 않는다.
- wrapper는 원본을 정확히 한 번 호출하고 반환값을 그대로 돌려준다.
- RNG 계측을 위해 random.Random을 subclass/override하지 않는다.
- 옛 OOP 8/771은 pre-0d202c5 역사값이다. 현재 acceptance는
  verify_oop_semantics와 같은 fixture의 586 -> 120 -> 1이다.

기본 실행:
  python3 tools/reachability.py
  python3 tools/reachability.py --json
  python3 tools/reachability.py --check

현재 고정 fixture:
  field_4x22
    fieldsim, entries=100, fmt=standard,
    seeds=5150,9001,4242,7301, 각 22 global hands.
    blockbet / sk fallback의 역사 기지값을 재현한다.

  synth_river_250
    tools/axis_freq.py의 post_sit 생성기를 그대로 사용.
    n=250, street=river, n_opp=1, seed=20260915, overbet axis level=5.

  oop_5150_18
    verify_oop_semantics.py와 같은 fieldsim fixture.
    entries=100, fmt=standard, seed=5150, 18 global hands.
"""
from __future__ import print_function

import argparse
import copy
import inspect
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import fieldsim as FS
import persona as PS
import plan as PL
import session as SE
import axis_freq as AF


FIELD_SEEDS = (5150, 9001, 4242, 7301)
FIELD_HANDS = 22
OOP_SEED = 5150
OOP_HANDS = 18
OVERBET_SEED = 20260915
OVERBET_N = 250
OVERBET_K = 20

# 현재 코드(3cc75a9 계열)의 acceptance reference.
# historical 8/771은 OOP 교정 전 민감도이며 현재 acceptance가 아니다.
EXPECTED = {
    'blockbet': {
        'eligible': 2800,
        'changed': 0,
    },
    'sk_fallback': {
        'eligible': 1190,
        'entered': 0,
    },
    'overbet': {
        'entered': 102,   # 실제 무저항 bet 수
        'taken': 2,       # 그중 >1pot
        'qualifying_plans': 56,
        'k20_rate_pct': 2.95,
    },
    'oop_sensitive': {
        'eligible': 586,
        'entered': 120,   # old/new positional semantics가 다른 결정
        'changed': 1,
        'unexplained': 0,
    },
}


def _rate(num, den):
    if num is None or not den:
        return None
    return num / float(den)


def _row(concept, fixture, eligible, entered=None, gate_true=None,
         taken=None, changed=None, denominator_kind='', meta=None):
    # 공용 필드는 일부 probe에서 의미가 없을 수 있다. 그때 None을 유지한다.
    return {
        'concept': concept,
        'fixture': fixture,
        'eligible': eligible,
        'entered': entered,
        'gate_true': gate_true,
        'taken': taken,
        'changed': changed,
        'denominator_kind': denominator_kind,
        'rate': _rate(changed if changed is not None else taken,
                      eligible),
        'meta': meta or {},
    }


def _run_field(seed, hands, entries=100, fmt='standard'):
    """verify_oop_semantics와 같은 global-hand loop."""
    f = FS.Field(entries=entries, seed=seed, fmt=fmt)
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
    return f


def probe_field_gates():
    """field_4x22 한 번으로 blockbet과 sk fallback을 함께 센다."""
    orig_update = PL.update_plan
    orig_make = PL.make_plan
    sig_make = inspect.signature(orig_make)

    c = {
        'update': 0,
        'make': 0,
        'fallback': 0,
        'mid': 0,
        'block_condition': 0,
        'block_gate': 0,
        'block_taken': 0,
        'block_survived': 0,
        'errors': 0,
    }

    def wrap_update(*a, **k):
        c['update'] += 1
        return orig_update(*a, **k)

    def wrap_make(*a, **k):
        b = sig_make.bind_partial(*a, **k)
        b.apply_defaults()
        profile = b.arguments.get('profile') or {}
        if not profile.get('concepts'):
            c['fallback'] += 1

        out = orig_make(*a, **k)
        c['make'] += 1

        why = [str(x) for x in ((out or {}).get('why') or [])]
        mid = any('중간강도' in x for x in why)
        if mid:
            c['mid'] += 1

        rel = (out or {}).get('rel')
        vs = b.arguments.get('oop_vs_aggr')
        legacy = b.arguments.get('oop_legacy_abs')
        oop_a = vs if vs is not None else bool(legacy)
        initiative = bool(b.arguments.get('initiative'))
        cond = bool(
            mid and oop_a and not initiative and rel is not None
            and 0.25 <= rel <= 0.80
        )
        if cond:
            c['block_condition'] += 1

        # make_plan 안의 sk()는 concepts가 있으면 PS.sk/3.33.
        # fallback profile은 별도 row가 잡으므로 여기서는 concepts 경로만
        # 정확히 재현한다.
        sk_gate = bool(profile.get('concepts')) and (
            PS.sk(profile, 'blockbet') / 3.33 >= 1.0
        )
        if cond and sk_gate:
            c['block_gate'] += 1

        if any('블락벳으로 가격 통제' in x for x in why):
            c['block_taken'] += 1
        if (out or {}).get('plan') == 'block':
            c['block_survived'] += 1
        return out

    PL.update_plan = wrap_update
    PL.make_plan = wrap_make
    old_bot_log = getattr(FS.Field, 'BOT_LOG', None)
    try:
        # 읽기 전용 계측이 bot log side effect를 만들지 않게 한다.
        if hasattr(FS.Field, 'BOT_LOG'):
            FS.Field.BOT_LOG = 0
        for sd in FIELD_SEEDS:
            f = _run_field(sd, FIELD_HANDS)
            c['errors'] += len(getattr(f, 'errors', ()) or ())
    finally:
        PL.update_plan = orig_update
        PL.make_plan = orig_make
        if old_bot_log is not None:
            FS.Field.BOT_LOG = old_bot_log

    block = _row(
        'blockbet',
        'field_4x22',
        eligible=c['update'],
        entered=c['make'],
        gate_true=c['block_gate'],
        taken=c['block_taken'],
        changed=c['block_survived'],
        denominator_kind='changed/update_plan decisions; funnel in meta',
        meta={
            'seeds': list(FIELD_SEEDS),
            'hands_per_seed': FIELD_HANDS,
            'entries': 100,
            'fmt': 'standard',
            'make_plan': c['make'],
            'mid_branch': c['mid'],
            'block_condition': c['block_condition'],
            'engine_errors': c['errors'],
            'meaning': {
                'eligible': 'postflop update_plan decisions',
                'entered': 'make_plan calls',
                'gate_true': 'mid branch + oop/no-initiative/rel + blockbet skill gate',
                'taken': 'block branch assigned (why message survives)',
                'changed': 'make_plan returns plan==block',
            },
        },
    )

    fallback = _row(
        'sk_fallback',
        'field_4x22',
        eligible=c['make'],
        entered=c['fallback'],
        gate_true=c['fallback'],
        taken=c['fallback'],
        changed=None,
        denominator_kind='entered/make_plan calls',
        meta={
            'seeds': list(FIELD_SEEDS),
            'hands_per_seed': FIELD_HANDS,
            'entries': 100,
            'fmt': 'standard',
            'engine_errors': c['errors'],
            'meaning': 'profile lacks concepts, so make_plan uses legacy constant/archetype sk path',
        },
    )
    return [block, fallback]


def _build_overbet_fixture():
    """axis_freq main()의 situation stream을 그대로 만든다."""
    spec = AF.AXES['overbet']
    base = PS.make_player(random.Random(OVERBET_SEED), 0.78, 0)
    prof = AF.build(base, 'overbet', 5, spec['hold'])
    rng = random.Random(OVERBET_SEED)
    sits = []

    for _ in range(OVERBET_N):
        s = AF.post_sit(rng, 'river', n_opp=1, est_kind='mixed')
        # 아래 값 중 일부는 overbet 자체에 쓰이지 않지만 axis_freq의
        # 다음 situation RNG 위치를 보존하려면 같은 순서로 소비해야 한다.
        s['pos'] = rng.choice(AF.POS)
        s['seats'] = rng.choice([6, 8, 9])
        s['def_pos'] = rng.choice(['BB', 'SB', 'BTN'])
        s['bb'] = rng.uniform(15, 60)
        s['open_bb'] = rng.choice([2.0, 2.5, 3.0])
        s['stack_commit'] = int(s['pot'] * rng.uniform(0.4, 1.1))
        try:
            s['plan_fixed'] = PL.make_plan(
                s['hero'], s['board'], s['my_range'], s['opp_range'], prof,
                s['pot'], s['stack'], s['street'], seed=s['seed'],
                n_opp=s['n_opp'], to_act_behind=s['to_act_behind'],
                oop_vs_aggr=s['oop'], initiative=s['initiative'],
                opp_est=s['est'])
        except Exception:
            s['plan_fixed'] = None
        sits.append(s)
    return sits, prof


def probe_overbet():
    sits, prof = _build_overbet_fixture()
    qual_names = {
        'value_3street', 'trap', 'bluff_2street', 'semibluff', 'river_bluff'
    }
    qual = 0
    pol_gate = 0
    k_hits = 0
    k_trials = 0

    # 직접 overbet_frac의 hard-domain과 stochastic activation을 분리한다.
    for s in sits:
        ps = s.get('plan_fixed')
        if ps is None or ps.get('plan') not in qual_names:
            continue
        qual += 1
        rel = ps.get('rel', 0.5)
        value_line = ps.get('plan') in ('value_3street', 'trap')
        pol = (max(0.0, (rel - 0.62) / 0.30) if value_line
               else max(0.0, (0.42 - rel) / 0.30))
        pol = min(1.0, pol)
        if pol > 0.02:
            pol_gate += 1

        for k in range(OVERBET_K):
            try:
                ob = PL.overbet_frac(
                    prof, s['hero'], s['board'], s['opp_range'], s['my_range'],
                    s['street'], ps['plan'], rel,
                    random.Random(s['seed'] + k), s['est'])
            except Exception:
                continue
            k_trials += 1
            if ob is not None:
                k_hits += 1

    # axis_freq L_noresist_size와 같은 최종 행동 경로.
    decisions = 0
    bets = 0
    overbets = 0
    exec_errors = 0
    for s in sits:
        ps = s.get('plan_fixed')
        if ps is None:
            continue
        ps = copy.deepcopy(ps)
        ps.pop('intents', None)
        try:
            ps = PL.attach_intent(
                ps, s['hero'], s['board'], s['my_range'], s['opp_range'],
                prof, s['pot'], s['stack'], s['street'],
                random.Random(s['seed']), s['n_opp'], s['to_act_behind'],
                s['oop'], s['initiative'], s['est'])
            (act, amt), _eq, _need = PL.act_with_plan(
                s['hero'], s['board'], prof, copy.deepcopy(ps),
                s['pot'], 0, s['stack'], s['street'],
                initiative=s['initiative'], opp_range=s['opp_range'],
                seed=s['seed'], n_opp=s['n_opp'], bf=1.0,
                to_act_behind=s['to_act_behind'], opp_est=s['est'],
                read=s['read'])
        except Exception:
            exec_errors += 1
            continue
        decisions += 1
        if act == 'bet' and amt:
            bets += 1
            if amt / float(s['pot']) > 1.0:
                overbets += 1

    return _row(
        'overbet',
        'synth_river_250',
        eligible=decisions,
        entered=bets,
        gate_true=qual,
        taken=overbets,
        changed=overbets,
        denominator_kind='taken/bets; K=20 activation in meta',
        meta={
            'seed': OVERBET_SEED,
            'n': OVERBET_N,
            'street': 'river',
            'n_opp': 1,
            'axis_level': 5,
            'qualifying_plans': qual,
            'polarization_gate': pol_gate,
            'k20_hits': k_hits,
            'k20_trials': k_trials,
            'k20_rate_pct': round(100.0 * k_hits / max(1, k_trials), 2),
            'execution_errors': exec_errors,
            'meaning': {
                'eligible': 'successful no-resistance synthetic decisions',
                'entered': 'final action is bet',
                'gate_true': 'plan is in overbet-eligible polarized plan family',
                'taken': 'final bet size > 1.0 pot',
                'changed': 'same as taken: overbet reaches final action',
            },
        },
    )


def _intent_sig(st, street):
    it = PL.intent_of(st, street) or {}
    return (
        (st or {}).get('plan'),
        it.get('act'),
        round(it.get('size', 0) or 0, 6),
    )


def probe_oop_sensitive():
    """verify_oop_semantics B1와 같은 old-vs-new replay."""
    orig = PL.update_plan
    sig = list(inspect.signature(orig).parameters)
    oop_i = sig.index('oop')
    records = []

    def probe(*a, **k):
        fr = sys._getframe(1).f_locals
        h = fr.get('h')
        seat = fr.get('s')
        rnd = fr.get('r2')
        ag = fr.get('aggressor')
        ctx = None
        if h is not None and seat is not None and rnd is not None and seat in rnd.order:
            order = list(rnd.order)
            live_ag = (
                ag is not None and ag != seat and ag in order
                and ag not in rnd.folded and ag not in rnd.allin
            )
            ctx = {
                'field': SE.oop_field(order, seat, rnd.folded, rnd.allin),
                'vs_aggr': SE.oop_vs(order, seat, ag) if live_ag else None,
                'legacy': h.POST.index(h.pos[seat]) < 3,
            }
        records.append({
            'a': copy.deepcopy(a),
            'k': copy.deepcopy(k),
            'ctx': ctx,
        })
        return orig(*a, **k)

    PL.update_plan = probe
    old_bot_log = getattr(FS.Field, 'BOT_LOG', None)
    try:
        if hasattr(FS.Field, 'BOT_LOG'):
            FS.Field.BOT_LOG = 0
        f = _run_field(OOP_SEED, OOP_HANDS)
        engine_errors = len(getattr(f, 'errors', ()) or ())
    finally:
        PL.update_plan = orig
        if old_bot_log is not None:
            FS.Field.BOT_LOG = old_bot_log

    pairs = 0
    flag_diff = 0
    out_diff = 0
    unexplained = 0

    def run_arm(rec, oop, vs_aggr, legacy):
        a = list(copy.deepcopy(rec['a']))
        k = copy.deepcopy(rec['k'])
        if len(a) <= oop_i:
            return None, None
        a[oop_i] = oop
        k['oop_vs_aggr'] = vs_aggr
        k['oop_legacy_abs'] = legacy
        bound = inspect.signature(orig).bind_partial(*a, **k)
        street = bound.arguments.get('street')
        out = orig(*a, **k)
        return out, street

    for rec in records:
        ctx = rec['ctx']
        if ctx is None or len(rec['a']) <= oop_i:
            continue

        old, street = run_arm(rec, ctx['legacy'], None, ctx['legacy'])
        new, street2 = run_arm(rec, ctx['field'], ctx['vs_aggr'], ctx['legacy'])
        if street is None:
            street = street2
        pairs += 1

        fd = (
            ctx['field'] != ctx['legacy']
            or (ctx['vs_aggr'] is not None and ctx['vs_aggr'] != ctx['legacy'])
        )
        if fd:
            flag_diff += 1

        od = _intent_sig(old, street) != _intent_sig(new, street)
        if od:
            out_diff += 1
            if not fd:
                unexplained += 1

    return _row(
        'oop_sensitive',
        'oop_5150_18',
        eligible=pairs,
        entered=flag_diff,
        gate_true=None,
        taken=flag_diff,
        changed=out_diff,
        denominator_kind='changed/replayable update_plan decisions',
        meta={
            'seed': OOP_SEED,
            'hands': OOP_HANDS,
            'entries': 100,
            'fmt': 'standard',
            'unexplained': unexplained,
            'engine_errors': engine_errors,
            'historical_reference': (
                '8/771 was the pre-0d202c5 sensitivity characterization; '
                'current acceptance is the post-fix 586->120->1 fixture.'
            ),
            'meaning': {
                'eligible': 'replayable update_plan decisions',
                'entered': 'old/new positional flags differ',
                'taken': 'same as entered: corrected positional semantics are exercised',
                'changed': 'plan or intent act/size differs',
            },
        },
    )


def collect():
    rows = []
    rows.extend(probe_field_gates())
    rows.append(probe_overbet())
    rows.append(probe_oop_sensitive())
    return rows


def _check_row(row):
    name = row['concept']
    exp = EXPECTED[name]
    mismatches = []

    for key in ('eligible', 'entered', 'changed', 'taken'):
        if key in exp and row.get(key) != exp[key]:
            mismatches.append('%s expected=%r got=%r' % (
                key, exp[key], row.get(key)))

    if name == 'overbet':
        q = row['meta'].get('qualifying_plans')
        if q != exp['qualifying_plans']:
            mismatches.append('qualifying_plans expected=%r got=%r' % (
                exp['qualifying_plans'], q))
        got = row['meta'].get('k20_rate_pct')
        if got is None or abs(got - exp['k20_rate_pct']) > 0.06:
            mismatches.append('k20_rate_pct expected~=%r got=%r' % (
                exp['k20_rate_pct'], got))

    if name == 'oop_sensitive':
        u = row['meta'].get('unexplained')
        if u != exp['unexplained']:
            mismatches.append('unexplained expected=%r got=%r' % (
                exp['unexplained'], u))

    return mismatches


def _human(rows, check=False):
    print('A5 reachability — production diff 0')
    print()
    for r in rows:
        print('[%s] %s' % (r['concept'], r['fixture']))
        print('  eligible=%s entered=%s gate_true=%s taken=%s changed=%s'
              % (r['eligible'], r['entered'], r['gate_true'],
                 r['taken'], r['changed']))
        if r['rate'] is not None:
            print('  rate=%.6f  denominator=%s'
                  % (r['rate'], r['denominator_kind']))
        else:
            print('  rate=-  denominator=%s' % r['denominator_kind'])

        if r['concept'] == 'blockbet':
            m = r['meta']
            print('  funnel: make_plan=%s mid=%s condition=%s gate=%s '
                  'branch=%s survived=%s'
                  % (m['make_plan'], m['mid_branch'], m['block_condition'],
                     r['gate_true'], r['taken'], r['changed']))
        elif r['concept'] == 'overbet':
            m = r['meta']
            print('  qualifying=%s pol_gate=%s K20=%s/%s (%.2f%%)'
                  % (m['qualifying_plans'], m['polarization_gate'],
                     m['k20_hits'], m['k20_trials'], m['k20_rate_pct']))
        elif r['concept'] == 'oop_sensitive':
            print('  unexplained=%s; %s'
                  % (r['meta']['unexplained'],
                     r['meta']['historical_reference']))

        if check:
            mm = _check_row(r)
            print('  %s%s' % ('PASS' if not mm else 'MISMATCH',
                              '' if not mm else ' — ' + '; '.join(mm)))
        print()


def main():
    ap = argparse.ArgumentParser(description='공용 reachability 계측')
    ap.add_argument('--json', action='store_true',
                    help='사람용 표 대신 JSON 출력')
    ap.add_argument('--check', action='store_true',
                    help='현재 acceptance reference와 대조하고 mismatch면 rc=1')
    a = ap.parse_args()

    rows = collect()
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _human(rows, check=a.check)

    if a.check:
        bad = [(r['concept'], _check_row(r)) for r in rows]
        bad = [(n, m) for n, m in bad if m]
        if bad:
            print('FAIL reachability mismatch')
            for name, mm in bad:
                print('  %s: %s' % (name, '; '.join(mm)))
            return 1
        print('PASS reachability references')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
