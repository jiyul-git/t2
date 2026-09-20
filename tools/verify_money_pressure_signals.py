#!/usr/bin/env python3
"""머니점프 연속 신호의 구조적 단조성 회귀검사."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import money_pressure as MP

ACTOR = {
    'money_jump': 7.0, 'icm': 7.0, 'stack_decay': 7.0,
    'fold_equity': 7.0, 'range_read': 7.0, 'attention': 7.0,
    'adaptability': 7.0, 'discipline': 7.0, 'gamble': 3.0,
    'aggression': 7.0,
}

def state(**kw):
    d = dict(
        jump_frac_next=0.20, jump_vs_mincash=0.50,
        distance_frac_itm=0.10, distance_frac_remaining=0.05,
        players_to_jump=2, n_shorter=4, median_shorter_ratio=0.45,
        forced_cost_share_of_stack=0.10,
        stack_start_bb=20.0, stack_behind_bb=20.0,
        stack_after_next_bb_if_fold_all=18.5,
        bf=1.8, covered_by_yet_to_act=0,
    )
    d.update(kw)
    return d

base = state()

small = state(jump_frac_next=0.05, jump_vs_mincash=0.10)
large = state(jump_frac_next=0.50, jump_vs_mincash=1.50)
assert MP.objective_self_preservation(large) >= MP.objective_self_preservation(small)

assert MP.ladder_buffer(state(n_shorter=8)) >= MP.ladder_buffer(state(n_shorter=1))

assert MP.objective_urgency(state(forced_cost_share_of_stack=0.80)) >=        MP.objective_urgency(state(forced_cost_share_of_stack=0.05))

hero = state(stack_start_bb=40.0, covered_by_yet_to_act=0)
target = state(stack_start_bb=20.0)
assert MP.structural_pressure(hero, target) >= 0.0
assert MP.structural_pressure(state(stack_start_bb=10.0), target) == 0.0

safe = MP.structural_pressure(state(stack_start_bb=40.0, covered_by_yet_to_act=0), target)
danger = MP.structural_pressure(state(stack_start_bb=40.0, covered_by_yet_to_act=2), target)
assert danger <= safe

lo = dict(ACTOR, money_jump=1.0)
hi = dict(ACTOR, money_jump=9.0)
assert MP.perceived_self_preservation(base, hi) >= MP.perceived_self_preservation(base, lo)
assert MP.pressure_opportunity(hero, target, hi)['theory_pressure'] >=        MP.pressure_opportunity(hero, target, lo)['theory_pressure']

desperate = state(
    stack_start_bb=1.0, stack_behind_bb=1.0,
    stack_after_next_bb_if_fold_all=0.0,
    forced_cost_share_of_stack=1.5, n_shorter=0)
lo_sd = dict(ACTOR, stack_decay=1.0)
hi_sd = dict(ACTOR, stack_decay=9.0)
assert MP.perceived_urgency(desperate, hi_sd) >= MP.perceived_urgency(desperate, lo_sd)

near = state(distance_frac_itm=0.05, distance_frac_remaining=0.05)
far = state(distance_frac_itm=5.0, distance_frac_remaining=0.8)
assert MP.payout_importance(near) >= MP.payout_importance(far)

low_aggr = dict(ACTOR, aggression=1.0)
high_aggr = dict(ACTOR, aggression=9.0)
assert MP.pressure_opportunity(hero, target, high_aggr)['theory_pressure'] >= \
       MP.pressure_opportunity(hero, target, low_aggr)['theory_pressure']

neutral = MP.pressure_opportunity(hero, target, ACTOR, None)['pressure_opportunity']
over = MP.pressure_opportunity(
    hero, target, ACTOR, {'w': 1.0, 'fold_gap': 0.4})['pressure_opportunity']
station = MP.pressure_opportunity(
    hero, target, ACTOR, {'w': 1.0, 'fold_gap': -0.4})['pressure_opportunity']
assert over >= neutral >= station

pre_over = MP.pressure_opportunity(
    hero, target, ACTOR, {'w': 1.0, 'fold_gap': -0.4, 'f2tb_gap': 0.4},
    read_channel='preflop_3bet')['pressure_opportunity']
pre_station = MP.pressure_opportunity(
    hero, target, ACTOR, {'w': 1.0, 'fold_gap': 0.4, 'f2tb_gap': -0.4},
    read_channel='preflop_3bet')['pressure_opportunity']
assert pre_over >= pre_station

high_pres = dict(ACTOR, money_jump=10.0, icm=10.0, discipline=10.0, gamble=0.0)
low_pres = dict(ACTOR, money_jump=0.0, icm=0.0, discipline=0.0, gamble=10.0)
assert MP.commitment_budget(base, high_pres) <= MP.commitment_budget(base, low_pres)
assert MP.commitment_budget(desperate, hi_sd) >= MP.commitment_budget(base, hi_sd)

def open_state(preserve, urgency, pressures, covering=0, behind=None):
    pressures = list(pressures)
    if behind is None:
        behind = len(pressures)
    return {
        'money_signals': {
            'self_preservation': preserve,
            'urgency': urgency,
        },
        'players_yet_to_act': behind,
        'covered_by_yet_to_act': covering,
        'target_signals': [
            {'pressure': {'pressure_opportunity': p}} for p in pressures
        ],
    }

m_neutral = MP.unopened_modifiers(open_state(0.0, 0.0, [0.0, 0.0]))
m_safe_pres = MP.unopened_modifiers(
    open_state(0.7, 0.0, [0.0, 0.0], covering=0))
m_danger_pres = MP.unopened_modifiers(
    open_state(0.7, 0.0, [0.0, 0.0], covering=2))
m_one_target = MP.unopened_modifiers(
    open_state(0.0, 0.0, [0.7, 0.0], covering=0))
m_two_targets = MP.unopened_modifiers(
    open_state(0.0, 0.0, [0.7, 0.7], covering=0))
m_urgent = MP.unopened_modifiers(
    open_state(0.7, 0.8, [0.0, 0.0], covering=2))

assert abs(m_neutral['range_factor'] - 1.0) < 1e-9
# 자기보존은 실제로 나를 탈락시킬 수 있는 상대가 뒤에 있을 때 range brake가 된다.
assert m_safe_pres['range_factor'] == m_neutral['range_factor']
assert m_danger_pres['range_factor'] < m_neutral['range_factor']
# 취약 상대 한 명보다 뒤 상대 전부가 압박받을 때 오픈 확대가 더 크다.
assert m_two_targets['range_factor'] > m_one_target['range_factor'] > 1.0
# 절박함은 danger가 있어도 보존 brake를 약화한다.
assert m_urgent['range_factor'] > m_danger_pres['range_factor']
# pot-growth shadow는 range danger와 별도로 preservation/pressure를 본다.
assert m_safe_pres['size_factor_shadow'] < m_neutral['size_factor_shadow']
assert m_two_targets['size_factor_shadow'] < m_neutral['size_factor_shadow']

# form shadow: 같은 restraint면 늦은 포지션/높은 개념이 림프 전환을 더 잘 쓴다.
def form_state(behind, table_n=8, pf_skill=8.0, pos_skill=8.0, size_skill=8.0):
    d=open_state(0.6, 0.0, [0.2]*max(1,behind), covering=0, behind=behind)
    d.update({
        'table_n': table_n,
        'pf_range_skill': pf_skill,
        'positional_skill': pos_skill,
        'open_size_skill': size_skill,
    })
    return d

early=MP.unopened_modifiers(form_state(7))
late=MP.unopened_modifiers(form_state(1))
weak_form=MP.unopened_modifiers(form_state(1,pf_skill=1.0,pos_skill=1.0))
weak_size=MP.unopened_modifiers(form_state(1,size_skill=1.0))
strong_size=MP.unopened_modifiers(form_state(1,size_skill=9.0))
assert late['limp_pull_shadow'] > early['limp_pull_shadow']
assert late['limp_pull_shadow'] > weak_form['limp_pull_shadow']
assert strong_size['size_factor_shadow'] < weak_size['size_factor_shadow']

print('OK money-pressure monotonic signals')
