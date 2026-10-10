"""P10 decision-consumer regression for PR27 MC None / zero / valid equity."""
import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
import bot
import plan

H = ['3c', '4d']
B = ['As', 'Ks', 'Qs', 'Js', '9s']
POOL = [('Ts', '2h')]
PROFILE = {'type': 'reg', 'aggr': 5, 'bluff': 5, 'concepts': {}}
CTX = {'facing_seat': 1, 'facing_contrib': 100, 'facing_stack': 1000,
       'facing_target': 100}

def gate():
    return plan._nonvalue_raise_ev_gate(
        PROFILE, H, B, 'river', POOL, {1: POOL}, 1,
        pot=300, tocall=100, stack=1000, hero_contrib=0,
        response_context=CTX, mult=1.0)

def stub_equity(value, reason='no_valid_mc_samples', accepted=0):
    def f(*args, **kwargs):
        audit = kwargs.get('audit')
        if audit is not None:
            audit.update(requested=kwargs.get('sims', 400), accepted=accepted,
                         complete=value is not None, reason=reason)
        return value
    return f

def run():
    before = random.getstate()

    # Raw producer: invalid opponent cards prevent all samples.
    audit = {}
    impossible = bot.equity_vs_combos(H, B, [[('3c', '2d')]], sims=13, audit=audit)
    assert impossible is None
    assert audit['accepted'] == 0 and not audit['complete']
    assert audit['reason'] == 'missing_opponent_range', audit

    # P17-B2 exact fixture from 17 release audit:
    # Hero A-clubs K-hearts, flop 2-clubs 7-diamonds 9-hearts.
    # Both opponents are independently assigned only Q-spades J-diamonds,
    # hence individually nonempty but jointly incompatible range evidence.
    hero17, board17 = ['Ac', 'Kh'], ['2c', '7d', '9h']
    singleton17 = [('Qs', 'Jd')]
    audit17 = {}
    mc17 = bot.equity_vs_combos(hero17, board17,
                                [singleton17, singleton17], sims=600,
                                audit=audit17)
    assert mc17 is None and audit17['requested'] == 600, audit17
    assert audit17['accepted'] == 0 and audit17['rejected'] == 600
    assert audit17['reason'] == 'no_valid_mc_samples', audit17

    state17 = {'plan': 'value_2street', 'eq': .65, 'rel': .8,
               'outs': 0, 'made': 1}
    act17, eq17, need17 = plan.act_with_plan(
        hero17, board17, PROFILE, state17, 300, 100, 1000, 'flop',
        opp_range=singleton17,
        opp_ranges={1: singleton17, 2: singleton17}, n_opp=2,
        response_context=CTX, response_kind='face_bet', seed=11)
    assert act17 == ('fold', 0) and eq17 is None and need17 is None, act17
    assert state17['equity_unavailable']['reason'] == 'no_valid_mc_samples', state17
    assert state17['equity_unavailable']['accepted'] == 0, state17
    assert state17['_last_response_boundary']['mathematically_justified'] is False
    assert state17['response_plans']['flop'][-1]['equity_status'] == (
        'unavailable_not_negative_ev'), state17
    print('PASS P17-B2 original two incompatible nonempty pools -> None, safe response')

    # A real computed equity of exactly zero is numeric and fully accepted.
    audit = {}
    true_zero = bot.equity_vs_combos(H, B, [POOL], sims=37, audit=audit)
    assert true_zero == 0.0, (true_zero, audit)
    assert audit['complete'] and audit['accepted'] == audit['requested'] == 37

    # Restrict continue subset to known witness; do not let fold estimates vary.
    with patch.object(plan.R, 'perceived_continue_range', lambda *a, **k: POOL):
        # Simulates P9 explicit zero-valid/partial-valid unavailable contract.
        for reason, accepted in (('no_valid_mc_samples', 0),
                                 ('insufficient_valid_samples', 17),
                                 ('missing_opponent_range', 0)):
            with patch.object(bot, 'equity_vs_combos',
                              stub_equity(None, reason=reason, accepted=accepted)):
                g = gate()
                assert g['allow'] is False and g['known'] is False, g
                assert g['ev'] is None and g['continue_eq'] is None, g
                assert g['mc_audit']['accepted'] == accepted, g
                assert g['mc_audit']['reason'] == reason, g
                assert g['equity_status'] == 'unavailable_not_negative_ev', g
        # An actual computed zero must remain a mathematical -EV, not 'unknown'.
        g0 = gate()
        assert g0['known'] and g0['continue_eq'] == 0.0, g0
        assert g0['allow'] is False and g0['ev'] < 0, g0
        with patch.object(bot, 'equity_vs_combos', stub_equity(.9, 'computed', 400)):
            gp = gate()
            assert gp['known'] and gp['allow'] and gp['ev'] > 0, gp

    # Do not drop one missing opponent and report fictitious HU equity.
    with patch.object(bot, '_filter_pool', side_effect=lambda p, dead, sort_legacy=True:
                      [] if p == [('2d', '3h')] else p):
        assert plan._eq_current(H, B, POOL, 2, sims=12,
                                opp_ranges={1: POOL, 2: [('2d', '3h')]}) is None
        audit_missing = {}
        eq_missing = plan.response_equity(
            H, B, PROFILE, POOL, {1: POOL, 2: [('2d', '3h')]},
            2, None, 300, 100, 'river', CTX, 17, audit=audit_missing)
        assert eq_missing is None, eq_missing
        assert audit_missing['reason'] == 'missing_opponent_range', audit_missing

    # Value raise: unknown continue equity cannot justify a raise.
    with patch.object(plan.R, 'perceived_continue_range', lambda *a, **k: POOL):
        with patch.object(bot, 'equity_vs_combos', stub_equity(None)):
            ok, eq, fair = plan.value_raise_qualification(
                H, B, 'river', .7, 1, POOL, CTX, 0, 1000, 300, 100, 1.0,
                PROFILE)
            assert not ok and eq is None and fair == .5
            ok, eq, fair = plan.value_raise_qualification(
                H, B, 'river', None, 1, POOL, CTX, 0, 1000, 300, 100, 1.0,
                PROFILE)
            assert not ok and eq is None
        with patch.object(bot, 'equity_vs_combos', stub_equity(.7, 'computed', 400)):
            ok, eq, fair = plan.value_raise_qualification(
                H, B, 'river', .7, 1, POOL, CTX, 0, 1000, 300, 100, 1.0,
                PROFILE)
            assert ok and eq == .7

    # Empty continue slice must not silently keep the initial fair-share raise approval.
    with patch.object(plan.R, 'perceived_continue_range', lambda *a, **k: []):
        ok, eq, fair = plan.value_raise_qualification(
            H, B, 'river', .7, 1, POOL, CTX, 0, 1000, 300, 100, 1.0, PROFILE)
        assert not ok and eq is None and fair == .5

    # Value-raise MC incompleteness includes exact producer reason and sample counts.
    vr_audit = {}
    with patch.object(plan.R, 'perceived_continue_range', lambda *a, **k: POOL):
        with patch.object(bot, 'equity_vs_combos',
                          stub_equity(None, 'insufficient_valid_samples', 19)):
            ok, eq, fair = plan.value_raise_qualification(
                H, B, 'river', .7, 1, POOL, CTX, 0, 1000, 300, 100, 1.0,
                PROFILE, audit=vr_audit)
    assert not ok and eq is None, (ok, eq)
    assert vr_audit['status'] == 'continue_mc_unavailable', vr_audit
    assert vr_audit['mc_audit']['accepted'] == 19, vr_audit

    # Gate failure survives to the final response record, not only transient state.
    provenance_state = {
        '_last_nonvalue_raise_gate': {
            'allow': False, 'ev': None, 'known': False,
            'equity_status': 'unavailable_not_negative_ev',
            'mc_audit': {'reason': 'insufficient_valid_samples', 'accepted': 19}},
        '_last_value_raise_gate': {
            'ok': False, 'continue_eq': None, 'continue_eq_status': vr_audit['status'],
            'continue_mc_audit': vr_audit['mc_audit']},
    }
    plan.record_response_plan(provenance_state, 'river',
                              {'act': 'fold', 'source': 'generic_response'})
    rec = provenance_state['response_plans']['river'][-1]
    assert rec['nonvalue_raise_gate']['mc_audit']['accepted'] == 19, rec
    assert rec['value_raise_gate']['continue_mc_audit']['accepted'] == 19, rec
    assert rec['value_raise_gate']['continue_eq'] is None, rec

    # Existing neutral field fallback remains legitimate when it calculates
    # an actual number (even if the original narrow range failed).
    with patch.object(bot, 'equity_vs_combos', side_effect=[None, .37]):
        eq_fallback, used_fallback = plan._plan_eq(H, B, POOL, 1, 13)
    assert eq_fallback == .37 and used_fallback is True, (
        eq_fallback, used_fallback)

    # Both primary and neutral field-estimate failing must stay unknown.
    with patch.object(bot, 'equity_vs_combos', stub_equity(None)):
        audit = {}
        eq, fallback = plan._plan_eq(H, B, POOL, 1, 13, audit=audit)
        assert eq is None and fallback and audit['source'] == 'plan_and_field_equity_unavailable'
        st = plan.update_plan(
            None, H, B, [], POOL, PROFILE, 300, 1000, 'river',
            seed=7, n_opp=1, behind=0, prev_board=B[:-1],
            oop=False, initiative=True, first=True)
        assert st['eq'] is None and st['equity_status'] == 'unavailable_not_negative_ev', st
        assert plan.intent_of(st, 'river')['act'] == 'check', st
        act, equity, need = plan.act_with_plan(
            H, B, PROFILE, st, 300, 100, 1000, 'river',
            opp_range=POOL, opp_ranges={1: POOL}, response_context=CTX,
            response_kind='face_bet', seed=11)
        assert act == ('fold', 0) and equity is None and need is None, act
        rec = st['response_plans']['river'][-1] if isinstance(
            st['response_plans']['river'], list) else st['response_plans']['river']
        assert rec['equity_status'] == 'unavailable_not_negative_ev', rec
        assert rec['equity_unavailable']['plan']['original']['accepted'] == 0, rec

    # Even with an existing numeric plan, a newly failed response MC is not a call/fold EV.
    st = {'plan': 'showdown', 'eq': .7, 'rel': .5, 'outs': 0, 'made': 0}
    with patch.object(bot, 'equity_vs_combos', stub_equity(None)):
        act, eq, need = plan.act_with_plan(
            H, B, PROFILE, st, 300, 100, 1000, 'river',
            opp_range=POOL, opp_ranges={1: POOL}, response_context=CTX,
            response_kind='face_bet', seed=11)
    assert act == ('fold', 0) and eq is None and need is None
    assert st['equity_status'] == 'unavailable_not_negative_ev'
    assert st['equity_unavailable']['reason'] == 'no_valid_mc_samples'
    assert not st['_last_response_boundary']['mathematically_justified']

    # Direct public decision helper is also protected against None > float.
    dstate = {'plan': 'value_2street', 'rel': .8, 'made': 1}
    decision = plan.decide_response(
        PROFILE, H, B, 'river', 'value_2street', dstate, None, .25,
        1, POOL, 300, 100, 1000, False, random.Random(4),
        response_context=CTX)
    assert decision[0] == 'fold' and decision[2] == .25, decision
    assert dstate['equity_status'] == 'unavailable_not_negative_ev', dstate

    # No accepted samples in same-board current showdown cannot become zero.
    with patch.object(bot, '_sample_pool_combo', lambda rng, pool: ('3c', '2h')):
        current = plan._eq_current(H, B, POOL, 1, sims=10)
        assert current is None, current
    # Partial acceptance of the independent current-showdown MC must also
    # remain unavailable (producer bot.equity_vs_pools uses the same rule).
    attempts = {'count': 0}
    def one_then_invalid(rng, pool):
        attempts['count'] += 1
        return ('Ts', '2h') if attempts['count'] == 1 else ('3c', '2h')
    current_audit = {}
    with patch.object(bot, '_sample_pool_combo', one_then_invalid):
        partial_current = plan._eq_current(
            H, B, POOL, 1, sims=2, audit=current_audit)
    assert partial_current is None and current_audit['accepted'] == 1
    assert current_audit['requested'] == 2
    assert current_audit['reason'] == 'insufficient_current_samples'
    assert current_audit['complete'] is False

    # Exact zero with two fully accepted current-showdown trials remains 0.
    full_audit = {}
    current_zero = plan._eq_current(
        H, B, POOL, 1, sims=2, audit=full_audit)
    assert current_zero == 0.0 and full_audit['complete'] is True
    assert full_audit['accepted'] == full_audit['requested'] == 2

    assert random.getstate() == before, 'postflop MC consumed global RNG'
    print('PASS P10 unavailable 0/partial, true zero, raise EV, value, plan, response, logging, RNG')

if __name__ == '__main__':
    run()
