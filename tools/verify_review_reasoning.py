#!/usr/bin/env python3
"""Human-reasoning guards: labels, intended sizing, and limp backaction price.

This checks model contracts, not whether a handcrafted order is solved GTO.
9-max is primary; legacy label-only sizing remains a compatibility path.
"""
import copy
import json
import pathlib
import random
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import persona as PS
import plan as PL
import preflop as PF


def replay_review_hand():
    """Historical 8-handed UI hand, secondary to the 9-max contracts below."""
    import dynamics
    import play
    import reads
    import session
    fixture = pathlib.Path(__file__).parent / 'fixtures' / 'hand99_reasoning.json'
    rec = json.loads(fixture.read_text())
    pos = {int(k): v for k, v in rec['pos'].items()}
    book = reads.Book()
    book.d = copy.deepcopy(rec['book_before'])
    tilt = dynamics.Tilt()
    tilt.state = copy.deepcopy(rec['tilt_before'])
    h = play.Hand(
        sorted(pos), copy.deepcopy(rec['profiles']),
        {int(k): v for k, v in rec['stacks_before'].items()}, rec['button'],
        *rec['blinds'], hero=rec['hero'], seed=rec['hand_seed'],
        book=book, dyn=tilt, position_map=pos, pre_seats=list(pos),
        post_seats=[3, 4, 5, 7, 8, 9, 1, 2], sb_seat=3, bb_seat=4)
    assert h.hash == rec['hash']
    h.seat_pid = {int(k): v for k, v in rec['seat_pid'].items()}
    for k, v in rec['field_context'].items():
        setattr(h, {'remaining': 'field_remaining', 'itm': 'field_itm',
                    'avg_stack': 'field_avg_stack'}.get(k, k), v)
    run = session.HandRun(h)
    state = run.start()
    while not state.get('done'):
        state = run.send('fold', 0)
    assert h.pf_seed[7]['pf_act'] == 'raise'
    assert h.pf_seed[7]['pf_origin_act'] == 'raise'
    assert not run.preflop_errors
    # Hold the original river intention fixed: this isolates sizing from the
    # entirely different hand caused by the corrected preflop decision.
    seed = zlib.crc32((rec['hash'] + '|1|river|size|1').encode())
    target, meta = PL.shape_planned_target(
        5100, rec['profiles']['1'], 15500, 20604, seed=seed)
    assert target == 5500 and meta['mode'] == 'planned_amount_variation'
    return {'hash': h.hash, 'b14_action': h.pf_seed[7]['pf_act'],
            'b14_target': run.result['full_log'][1][3],
            'b13_fixed_river_target': target, 'handedness': 8}


def profile(consistency=5, attention=5):
    c = {k: 10.0 for k in PS.ALL_CONCEPTS}
    c['read_application'] = 10.0
    t = {k: 5.0 for k in PS.TEMPER}
    t.update(consistency=consistency, attention=attention)
    p = {'id': 91, 'concepts': c, 'temper': t,
         'latent': {'study': 8, 'aggro': 5, 'exp': 8}}
    p.update(PS.derive(p))
    return p


def main():
    # Exact cumulative combo accounting, while preserving non-AK relative order.
    n = 0
    for hand, pct in sorted(PF.PCT.items(), key=lambda x: x[1]):
        n += 6 if len(hand) == 2 else (4 if hand.endswith('s') else 12)
        assert pct == round(n / 1326, 4), (hand, pct, n)
    assert n == 1326 and len(PF.PCT) == 169
    assert PF.PCT['QQ'] < PF.PCT['AKs'] < PF.PCT['JJ'] < PF.PCT['AKo'] < PF.PCT['TT']

    cases = 0
    for cons in (0, 5, 10):
        for attention in (0, 5, 10):
            p = profile(cons, attention)
            jitter = PS.profile_sizing_signature(p)['jitter']
            for seed in range(100):
                out = []
                for label in ('MANIAC', 'TAG', 'NIT', 'STUDIED_LAG'):
                    q = dict(p, type=label)
                    v, _ = PL.shape_planned_target(5100, q, 15500, 20604, seed=seed)
                    assert abs(v - 5100) <= 5100*jitter + 50 + 1e-9
                    out.append(v)
                    cases += 1
                assert len(set(out)) == 1
    p = profile()
    assert PL.shape_planned_target(20604, p, 15500, 20604, seed=2)[0] == 20604
    assert PS.profile_sizing_signature(profile(0, 0))['jitter'] > PS.profile_sizing_signature(profile(10, 10))['jitter']

    # The same AK caller should use actual price and both opponents, without
    # an unconditional premium-card continue override. A high price still folds.
    pools = {1: [('Ac', 'Qd')], 3: [('Kh', 'Qc')]}
    def decision(pot, cost, prior=True):
        return PL.preflop_plan(
            p, 'UTG+1', ['As', 'Kd'], 80.0, random.Random(17),
            aggressor_pos='CO', open_bb=4.6, n_callers=1,
            raise_level=1, seats=9, ante=True, can_raise=False,
            pot_bb=pot, to_call_bb=cost, opp_ranges=pools,
            prior_pf={'pf_act': 'limp'} if prior else None,
            cold_decision_seed=31)
    cheap = decision(12.2, 3.6)
    costly = decision(4.6, 80.0)
    audit = cheap[2]['pf_cold_audit']
    assert cheap[0] == 'call', cheap
    assert costly[0] == 'fold', costly
    assert audit['context_kind'] == 'limp_vs_isolation_multiway'
    assert audit['opponent_range_count'] == 2
    assert audit['strategy_consumer']
    assert decision(12.2, 3.6, prior=False)[2]['pf_cold_audit'] is None
    again = decision(12.2, 3.6)
    assert cheap == again
    replay = replay_review_hand()
    print(json.dumps({'pass': True, 'sizing_cases': cases,
                      'rank_classes': len(PF.PCT),
                      'cheap_action': cheap[0], 'costly_action': costly[0],
                      'cheap_price_audit': audit,
                      'historical_review_replay': replay}, indent=2))


if __name__ == '__main__':
    main()
