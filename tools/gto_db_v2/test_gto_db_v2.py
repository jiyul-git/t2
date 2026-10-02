#!/usr/bin/env python3
"""Tests for the canonical spot_key and the legacy+v2 index.  python3 tools/gto_db_v2/test_gto_db_v2.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index as IX  # noqa: E402
import spot_key as SK  # noqa: E402

BASE = {'table_players': 4, 'stacks_bb': 30, 'ante': {'model': 'none'}, 'format': 'MTT'}


def k(**kw):
    return SK.key_of({**BASE, **kw})[0]


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def main():
    res = {}
    # equivalent descriptions -> one key
    res['implicit_vs_explicit_folds'] = k(hero='BB', history=[{'pos': 'SB', 'act': 'raise', 'to_bb': 2.5}]) == \
        k(hero='BB', history=[{'pos': 'CO', 'act': 'fold'}, {'pos': 'BTN', 'act': 'fold'}, {'pos': 'SB', 'act': 'raise', 'to_bb': 2.5}])
    res['number_format'] = k(hero='BB', stacks_bb=30.0, history=[{'pos': 'SB', 'act': 'raise', 'to_bb': '2.50'}]) == \
        k(hero='BB', stacks_bb=30, history=[{'pos': 'SB', 'act': 'raise', 'to_bb': 2.5}])
    res['per_seat_equal_stacks'] = k(hero='BTN', stacks_bb={'CO': 30, 'BTN': 30, 'SB': 30, 'BB': 30}) == k(hero='BTN')
    res['alias_positions'] = SK.key_of({'table_players': 9, 'stacks_bb': 10, 'hero': 'BB', 'history': [{'pos': 'UTG+1', 'act': 'allin'}]})[0] == \
        SK.key_of({'table_players': 9, 'stacks_bb': 10, 'hero': 'BB', 'history': [{'pos': 'UTG1', 'act': 'allin'}]})[0]
    res['raise_to_stack_is_allin'] = k(hero='BB', history=[{'pos': 'BTN', 'act': 'raise', 'to_bb': 30}]) == k(hero='BB', history=[{'pos': 'BTN', 'act': 'allin'}])
    res['hero_first_in_implicit'] = k(hero='SB') == k(hero='SB', history=[{'pos': 'CO', 'act': 'fold'}, {'pos': 'BTN', 'act': 'fold'}])
    # different spots -> different keys
    res['distinct_hero'] = k(hero='SB') != k(hero='BTN')
    res['distinct_stack'] = k(hero='SB') != k(hero='SB', stacks_bb=25)
    res['distinct_ante'] = k(hero='SB') != k(hero='SB', ante={'model': 'bb_ante', 'amount_bb': 1})
    res['distinct_size'] = k(hero='BB', history=[{'pos': 'SB', 'act': 'raise', 'to_bb': 2.5}]) != k(hero='BB', history=[{'pos': 'SB', 'act': 'raise', 'to_bb': 3}])
    res['distinct_table'] = k(hero='SB') != SK.key_of({**BASE, 'table_players': 5, 'hero': 'SB'})[0]
    # uniform ante, hand_start_players: a 9-max hand with 5 folds is not a 4-max hand; N enters the key
    ua = {'model': 'uniform_total', 'amount_bb': 1}
    k9 = SK.key_of({'table_players': 9, 'stacks_bb': 30, 'ante': ua, 'hero': 'CO'})[0]
    k9b = SK.key_of({'hand_start_players': 9, 'stacks_bb': 30, 'ante': ua, 'hero': 'CO',
                     'history': [{'pos': p, 'act': 'fold'} for p in ('UTG', 'UTG1', 'MP', 'LJ', 'HJ')]})[0]
    k4 = SK.key_of({'table_players': 4, 'stacks_bb': 30, 'ante': ua, 'hero': 'CO'})[0]
    k8 = SK.key_of({'table_players': 8, 'stacks_bb': 30, 'ante': ua, 'hero': 'CO'})[0]
    res['uniform_ante_hand_start_players'] = k9 == k9b and len({k9, k4, k8}) == 3
    res['uniform_vs_bba_distinct'] = k9 != SK.key_of({'table_players': 9, 'stacks_bb': 30, 'ante': {'model': 'bb_ante', 'amount_bb': 1}, 'hero': 'CO'})[0]
    # invalid states rejected
    res['reject_hero_not_next'] = raises(lambda: k(hero='CO', history=[{'pos': 'BTN', 'act': 'raise', 'to_bb': 2.5}]))
    res['reject_overstack'] = raises(lambda: k(hero='BB', history=[{'pos': 'BTN', 'act': 'raise', 'to_bb': 31}]))
    res['reject_small_raise'] = raises(lambda: k(hero='BB', history=[{'pos': 'BTN', 'act': 'raise', 'to_bb': 1.5}]))
    res['reject_unknown_pos'] = raises(lambda: k(hero='UTG'))
    res['bb_option_check_closes'] = raises(lambda: k(hero='CO', history=[{'pos': 'CO', 'act': 'call'}, {'pos': 'BTN', 'act': 'fold'},
                                                                         {'pos': 'SB', 'act': 'call'}, {'pos': 'BB', 'act': 'check'}]))
    res['reraise_reopens'] = bool(k(hero='CO', history=[{'pos': 'CO', 'act': 'raise', 'to_bb': 2.5}, {'pos': 'SB', 'act': 'raise', 'to_bb': 9}]))
    # legacy: read in place / from pinned blob, untouched, 616 unique keys
    ix = IX.Index(v2_path=os.path.join(tempfile.mkdtemp(), 'solutions.jsonl'))
    res['legacy_rows_unique_keys'] = sum(len(v) for v in ix.by_key.values()) == 616 == len(ix.by_key)
    res['legacy_source'] = ix.legacy_where
    leg = {'table_players': 9, 'stacks_bb': 10, 'ante': {'model': 'none'}, 'hero': 'BB', 'history': [{'pos': 'BTN', 'act': 'allin'}], 'format': 'MTT'}
    b = ix.lookup(leg)
    res['legacy_lookup_by_state'] = b is not None and b['source']['legacy_spot_id'] == 'hm_9max_no_ante_10bb_bb_vs_btn'
    # skip / append rules on a temp v2 store
    need, key, _ = ix.need_compute(leg, {'tier': 4, 'exploitability_pct_pot': None})
    res['skip_existing_legacy_spot'] = need is False
    res['target_quality_required'] = raises(lambda: ix.need_compute(leg, None))
    need2, _, _ = ix.need_compute(leg, {'tier': 2, 'exploitability_pct_pot': 0.3})
    res['upgrade_target_allowed'] = need2 is True
    strat = {'actions': ['fold', 'call'], 'hands': {'AA': {'freq': {'fold': 0.0, 'call': 1.0}}}}
    added, _, why = ix.add_solution(leg, strat, {'tier': 4, 'exploitability_pct_pot': None}, {'run': 'test'})
    res['reject_not_better'] = added is False
    added, _, why = ix.add_solution(leg, strat, {'tier': 2, 'exploitability_pct_pot': 0.3}, {'run': 'test'})
    res['append_better'] = added is True and len(ix.all(key)) == 2 and ix.best(key)['quality']['tier'] == 2
    added, _, _ = ix.add_solution(leg, strat, {'tier': 2, 'exploitability_pct_pot': 0.3}, {'run': 'test'})
    res['no_duplicate'] = added is False
    added, _, _ = ix.add_solution(leg, strat, {'tier': 2, 'exploitability_pct_pot': 0.2}, {'run': 'test2'})
    ix2 = IX.Index(v2_path=ix.v2_path)
    res['reload_keeps_all_and_best'] = len(ix2.all(key)) == 3 and ix2.best(key)['quality']['exploitability_pct_pot'] == 0.2
    new_state = {**BASE, 'hero': 'SB'}
    need, _, _ = ix2.need_compute(new_state, {'tier': 3, 'exploitability_pct_pot': 0.3})
    added, _, _ = ix2.add_solution(new_state, strat, {'tier': 3, 'exploitability_pct_pot': 0.3}, {'run': 'test'})
    res['new_spot_then_skip'] = need is True and added is True and ix2.need_compute(new_state, {'tier': 3, 'exploitability_pct_pot': 0.3})[0] is False \
        and ix2.need_compute(new_state, {'tier': 2, 'exploitability_pct_pot': 0.3})[0] is True
    # comparable secondary metric: only within one family
    q = lambda v, fam='gtopen|cfgA': {'tier': 3, 'exploitability_pct_pot': None, 'comparable': {'family': fam, 'metric': 'gap_total', 'value': v}}
    res['comparable_same_family'] = IX.better(q(0.1), q(0.3)) and not IX.better(q(0.3), q(0.1)) and not IX.better(q(0.3), q(0.3))
    res['comparable_other_family_incomparable'] = not IX.better(q(0.01, 'other'), q(0.3)) and not IX.better(q(0.3), q(0.01, 'other'))
    res['comparable_missing_incomparable'] = not IX.better(q(0.1), {'tier': 3, 'exploitability_pct_pot': None})
    res['tier_dominates'] = IX.better({'tier': 2, 'exploitability_pct_pot': None}, q(0.0001))
    s3 = {**BASE, 'hero': 'BTN'}
    a1 = ix2.add_solution(s3, strat, q(0.3), {'run': 'seed1'})[0]
    a2 = ix2.add_solution(s3, strat, q(0.3), {'run': 'seed2'})[0]          # equal replicate: skipped
    a3 = ix2.add_solution(s3, strat, q(0.1, 'other'), {'run': 'x'})[0]     # other family: incomparable, skipped
    a4 = ix2.add_solution(s3, strat, q(0.1), {'run': 'seed3'})[0]          # same family, better: appended
    k3 = SK.key_of(s3)[0]
    res['upgrade_within_family'] = a1 and not a2 and not a3 and a4 and len(ix2.all(k3)) == 2 and ix2.best(k3)['source']['run'] == 'seed3'
    res['need_compute_family_target'] = ix2.need_compute(s3, q(0.05))[0] is True and ix2.need_compute(s3, q(0.1))[0] is False \
        and ix2.need_compute(s3, q(0.01, 'other'))[0] is False
    # tamper detection
    lines = open(ix.v2_path).read().splitlines()
    rec = json.loads(lines[0])
    rec['canonical_state']['hero'] = 'SB'
    p3 = os.path.join(tempfile.mkdtemp(), 'solutions.jsonl')
    open(p3, 'w').write(json.dumps(rec) + '\n')
    try:
        IX.Index(v2_path=p3)
        res['tamper_detected'] = False
    except SystemExit:
        res['tamper_detected'] = True
    ok = all(v for kk, v in res.items() if kk != 'legacy_source')
    print(json.dumps(res, indent=1))
    print('ALL PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
