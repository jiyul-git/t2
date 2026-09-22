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
  python3 tools/reachability.py --check                          # post-blockbet
  python3 tools/reachability.py --check --reference pre-blockbet # 보존용 historical

acceptance reference 는 코드 세대로 나뉜다. PRE_BLOCKBET 은 blockbet 제어흐름
수정 이전의 관측이고 숫자를 보존한다 — 현재 production 에 대고 돌리면
mismatch 가 나는 것이 정상이다. POST_BLOCKBET 이 현재 기준이다.

숫자와 별개로 구조 invariant 를 항상 검사한다:
  blockbet changed == taken
굴림을 통과한 block 이 뒤 머지 분기에 다시 덮이면 taken > 0, changed == 0 이
되므로 모집단 총수와 무관하게 FAIL 이다.

현재 고정 fixture:
  field_4x22
    fieldsim, entries=100, fmt=standard,
    seeds=5150,9001,4242,7301, 각 22 global hands.
    blockbet / sk fallback의 **현재 기준점(3cc75a9)** reachability를 고정한다.
    과거 조사에서 나온 다른 분모의 숫자는 provenance 참고값일 뿐 acceptance로
    재사용하지 않는다.

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

# acceptance reference는 **코드 세대별로** 나눠 둔다. 서로 다른 fixture/코드
# 세대의 숫자를 섞지 않는다.
# - 과거 OOP 8/771: pre-0d202c5 역사적 민감도. 현재 acceptance 아님.
# - 과거 sk fallback 0/1190: 다른 모집단. 현재 field_4x22 분모와 비교 금지.
# - 과거 overbet 2/102: 다른 실행 표본. 현재 synth_river_250과 비교 금지.
#
# PRE_BLOCKBET — 3cc75a9/02393f0에서 **이 파일의 정확한 fixture 정의로** 동결한
# 값이다. blockbet 제어흐름 수정 **이전**의 관측이고 숫자는 그대로 보존한다.
# 현재 production에 대고 돌리면 mismatch가 나는 것이 정상이다 (아래 CLI 참조).
PRE_BLOCKBET = {
    'blockbet': {
        'eligible': 2815,
        'entered': 1773,
        'gate_true': 49,
        'taken': 13,
        'changed': 0,
        'mid_branch': 301,
        'block_condition': 61,
        'engine_errors': 0,
    },
    'sk_fallback': {
        'eligible': 1773,
        'entered': 0,
        'engine_errors': 0,
    },
    'overbet': {
        'eligible': 250,
        'entered': 95,    # 현재 fixture의 실제 무저항 bet 수
        'gate_true': 56,  # overbet-eligible plan family
        'taken': 1,       # 그중 최종 >1pot
        'changed': 1,
        'qualifying_plans': 56,
        'polarization_gate': 55,
        'k20_hits': 33,
        'k20_trials': 1120,
        'k20_rate_pct': 2.95,
        'execution_errors': 0,
    },
    'oop_sensitive': {
        'eligible': 586,
        'entered': 120,
        'taken': 120,
        'changed': 1,
        'unexplained': 0,
        'engine_errors': 0,
    },
}

# POST_BLOCKBET — blockbet 제어흐름 수정 이후, **같은 canonical fixture**에서
# 다시 측정한 값이다. PRE_BLOCKBET을 덮어쓴 것이 아니라 세대를 나눈 것이다.
#
# blockbet: 굴림을 통과한 12건이 전부 최종 반환까지 살아남는다(changed 12).
#   수정 전에는 13건이 통과하고 0건이 살아남았다. eligible/mid/condition/gate/
#   taken이 1~13 움직인 것은 수정이 live 진행 자체를 바꿔 같은 seed에서도
#   결정 트리가 달라지기 때문이다. 분모가 고정된 재생이 아니다.
#
# overbet: entered 95 -> 96. **overbet 정책이 바뀐 것이 아니다.**
#   production 차이는 plan.py의 blockbet 제어흐름 하나뿐인 controlled A/B이고,
#   gate_true/taken/changed는 56/1/1로 그대로다. 상류 make_plan의 plan 하나가
#   달라지면서 synthetic fixture의 entered 모집단이 한 건 이동한 downstream
#   consequence로 기록한다. 이 숫자를 근거로 overbet을 튜닝하지 않는다.
#
# sk_fallback / oop_sensitive: 수정 전후 동일. 그대로 기록한다.
POST_BLOCKBET = {
    'blockbet': {
        'eligible': 2803,
        'entered': 1773,
        'gate_true': 48,
        'taken': 12,
        'changed': 12,
        'mid_branch': 300,
        'block_condition': 60,
        'engine_errors': 0,
    },
    'sk_fallback': {
        'eligible': 1773,
        'entered': 0,
        'engine_errors': 0,
    },
    'overbet': {
        'eligible': 250,
        'entered': 96,    # 95 -> 96, blockbet 수정의 downstream consequence
        'gate_true': 56,
        'taken': 1,
        'changed': 1,
        'qualifying_plans': 56,
        'polarization_gate': 55,
        'k20_hits': 33,
        'k20_trials': 1120,
        'k20_rate_pct': 2.95,
        'execution_errors': 0,
    },
    'oop_sensitive': {
        'eligible': 586,
        'entered': 120,
        'taken': 120,
        'changed': 1,
        'unexplained': 0,
        'engine_errors': 0,
    },
}

REFERENCES = {
    'post-blockbet': POST_BLOCKBET,
    'pre-blockbet': PRE_BLOCKBET,
}
CURRENT_REFERENCE = 'post-blockbet'


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


def _check_row(row, reference=CURRENT_REFERENCE):
    name = row['concept']
    exp = REFERENCES[reference][name]
    mismatches = []

    for key in ('eligible', 'entered', 'gate_true', 'taken', 'changed'):
        if key in exp and row.get(key) != exp[key]:
            mismatches.append('%s expected=%r got=%r' % (
                key, exp[key], row.get(key)))

    # fixture-specific funnel/meta도 현재 기준점에 같이 잠근다. 이 값이 바뀌면
    # 단순 최종 count만 보지 말고 어느 단계에서 reachability가 움직였는지 본다.
    for key in ('mid_branch', 'block_condition', 'engine_errors',
                'qualifying_plans', 'polarization_gate',
                'k20_hits', 'k20_trials', 'execution_errors',
                'unexplained'):
        if key in exp:
            got = row.get('meta', {}).get(key)
            if got != exp[key]:
                mismatches.append('%s expected=%r got=%r' % (
                    key, exp[key], got))

    if name == 'overbet':
        got = row['meta'].get('k20_rate_pct')
        if got is None or abs(got - exp['k20_rate_pct']) > 0.06:
            mismatches.append('k20_rate_pct expected~=%r got=%r' % (
                exp['k20_rate_pct'], got))

    return mismatches


def _invariants(rows):
    """reference 숫자와 **별개로** 성립해야 하는 구조 성질.

    blockbet: 선택된 block 이 뒤 머지 분기에 다시 덮이지 않는다.
      taken   = block 분기가 선택됨 (굴림 통과가 기록됨)
      changed = make_plan 최종 반환에서도 plan == 'block'
    둘이 같아야 한다. 특히 taken > 0 인데 changed == 0 이면 덮어쓰기가
    살아 있다는 뜻이므로 모집단 총수와 무관하게 FAIL 이다.
    """
    bad = []
    for r in rows:
        if r['concept'] != 'blockbet':
            continue
        taken, changed = r.get('taken'), r.get('changed')
        if taken is None or changed is None:
            bad.append('blockbet: taken/changed 가 None')
        elif taken > 0 and changed == 0:
            bad.append('blockbet: taken=%d 인데 changed=0 — 선택된 block 이 '
                       'merge fallback 에 덮이고 있다' % taken)
        elif changed != taken:
            bad.append('blockbet: changed(%r) != taken(%r)' % (changed, taken))
    return bad


def _human(rows, check=False, reference=CURRENT_REFERENCE):
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
            mm = _check_row(r, reference)
            print('  %s%s' % ('PASS' if not mm else 'MISMATCH',
                              '' if not mm else ' — ' + '; '.join(mm)))
        print()


def main():
    ap = argparse.ArgumentParser(description='공용 reachability 계측')
    ap.add_argument('--json', action='store_true',
                    help='사람용 표 대신 JSON 출력')
    ap.add_argument('--check', action='store_true',
                    help='acceptance reference와 대조하고 mismatch면 rc=1')
    ap.add_argument('--reference', choices=sorted(REFERENCES),
                    default=CURRENT_REFERENCE,
                    help='대조할 reference 세대 (기본 %s). pre-blockbet 은 '
                         '보존용 historical 이다' % CURRENT_REFERENCE)
    a = ap.parse_args()

    rows = collect()
    if a.json:
        print(json.dumps({'reference': a.reference, 'rows': rows},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _human(rows, check=a.check, reference=a.reference)

    inv = _invariants(rows)
    if inv:
        print('FAIL 구조 invariant')
        for m in inv:
            print('  ' + m)
    else:
        print('PASS 구조 invariant (blockbet changed == taken)')

    rc = 1 if inv else 0
    if a.check:
        print('reference: %s' % a.reference)
        if a.reference != CURRENT_REFERENCE:
            print('  주의: 이것은 보존용 historical reference 다. 현재 '
                  'production 에 대고 돌리면 mismatch 가 나는 것이 정상이고, '
                  '그 불일치는 blockbet 제어흐름 수정에 의한 의도된 것이다.')
        bad = [(r['concept'], _check_row(r, a.reference)) for r in rows]
        bad = [(n, m) for n, m in bad if m]
        if bad:
            print('FAIL reachability mismatch (%s)' % a.reference)
            for name, mm in bad:
                print('  %s: %s' % (name, '; '.join(mm)))
            return 1
        print('PASS reachability references (%s)' % a.reference)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
