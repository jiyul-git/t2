#!/usr/bin/env python3
"""P8 independent review of P9 MC contract on integrated PR18 SHA 69e55fc.

NO production changes; this tests representation, provenance, RNG, and P5
consumer semantics. The historical HAND130 288-combo opponent weights are
unavailable; NONE of these cases is claimed to replay that original posterior.
"""
import json
import math
import os
import random
import sys
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bot
import plan as PL
import ranges as R
import reads as RD
import range_posterior_v1 as RP
import session as S
from tools.verify_pr16_p5_provenance import fixture
from tools.verify_hand130_b37_replay import original


def weighted_conditional_and_seed():
    run, rnd = fixture()
    prev = os.environ.get('T2_RANGE_CONDITIONAL_V1')
    old_global = random.getstate()
    try:
        os.environ['T2_RANGE_CONDITIONAL_V1'] = '1'
        with patch.object(RD, 'perceived_profile', return_value=None):
            pool, meta = run._preflop_perceived_range(
                3, 9, {'concepts': {}}, rnd, 9, 8, True)
        assert isinstance(pool, dict) and pool and meta['complete']
        assert meta['source'] == RP.MODEL
        assert meta['model_calibrated'] is False
        assert meta['posterior_support'] == len(pool)
        assert math.isclose(meta['posterior_mass'], R.range_mass(pool))
        assert len(set(pool.values())) > 1, 'posterior unexpectedly uniform'
        assert random.getstate() == old_global

        # Serializer must preserve double-precision weight and source fields,
        # not flatten dict support to an equal-weight list.
        layer = [{'level':73442, 'amount':161884,
                  'hero_eligible':True, 'eligible_seats':[3,9]}]
        a = S.layer_equities_by_pot_layer(
            3, ['Ac','Kh'], [], layer, {}, {9:pool},
            sims=120, seed=271828, capture_sampling=True,
            range_metadata={9:meta})
        b = S.layer_equities_by_pot_layer(
            3, ['Ac','Kh'], [], layer, {}, {9:pool},
            sims=120, seed=271828, capture_sampling=False,
            range_metadata={9:meta})
        row, same = a[0], b[0]
        assert row['complete'] and row['equity'] is not None, row
        assert row['equity'] == same['equity']
        assert (row['requested_samples'], row['valid_samples'],
                row['rejected_samples']) == (120,120,0)
        assert row['sampling']['seed'] == row['seed']
        assert row['sampling']['accepted'] == row['valid_samples']
        assert row['sampling']['requested'] == row['requested_samples']
        assert row['sampling']['rejected'] == row['rejected_samples']
        assert row['sampling']['sample_variance'] == row['sample_variance']
        assert row['sampling']['split_pot_draws'] == row['split_pot_draws']
        assert row['sampling']['complete'] and row['sampling']['reason'] == 'computed'
        assert row['sample_variance'] >= 0
        assert 0 <= row['split_pot_draws'] <= 120
        assert random.getstate() == old_global

        record = RP.replay_record(
            {9:pool}, {9:meta}, layers=a,
            event_tag='P8-P9|synthetic|conditional-3bet-shove')
        reconstructed = json.loads(json.dumps(record, allow_nan=False))
        pp = reconstructed['opponents']['9']
        reloaded = {(c0,c1):float(w) for c0,c1,w in pp['weights']}
        assert reloaded == pool
        assert pp['support'] == len(pool)
        assert pp['mass'] == R.range_mass(pool)
        assert pp['source_metadata']['source'] == RP.MODEL
        assert pp['source_metadata']['posterior_mass'] == R.range_mass(pool)
        assert len(pp['sha256']) == 64
        saved_layer = reconstructed['layer_sampling'][0]
        assert saved_layer['seed'] == row['seed']
        assert saved_layer['sampling']['accepted'] == 120
        assert saved_layer['sampling']['split_pot_draws'] == row['split_pot_draws']
        assert saved_layer['sample_variance'] == row['sample_variance']
        print(json.dumps({
            'posterior_support':len(pool),
            'posterior_mass':R.range_mass(pool),
            'seed':row['seed'], 'requested':120,'accepted':row['valid_samples'],
            'sample_variance':row['sample_variance'],
            'split_pot_draws':row['split_pot_draws'],
            'range_sha256':pp['sha256'], 'range_source':meta['source'],
            'exact_original_288_reconstructed':False,
            'valid_sampled_estimate_not_range_truth':True,
        }, sort_keys=True))
    finally:
        if prev is None:
            os.environ.pop('T2_RANGE_CONDITIONAL_V1', None)
        else:
            os.environ['T2_RANGE_CONDITIONAL_V1'] = prev
    print('PASS P8 conditioned weighted posterior / replay weights / seed / variance / ties / RNG')


def evidence_fails_closed_at_p5():
    hand = original()
    pf = hand['actor_pf_seed']
    layer = [{'idx':0,'level':5000,'amount':161884,
              'hero_eligible':True,'eligible_seats':[3,9]}]
    invalid_cases = [
        (None, {}, None, 'missing_opponent_range'),
        ({('As','Ad'):1.0},
         {'source':RP.MODEL,'complete':False,
          'missing':['action_class_not_supported'],
          'failure_kind':'model_unavailable'},
         None, 'unsupported_opponent_model'),
        ({('As','Ad'):1.0},
         {'source':'legacy_fallback','complete':False,
          'missing':['action_class_not_supported'],
          'failure_kind':'model_unavailable',
          'equity_model_status':'unvalidated_legacy_proxy'},
         None, 'unsupported_opponent_model'),
        ({('As','Ad'):1.0},
         {'source':RP.MODEL,'complete':False,
          'missing':['unknown_actor_stack'],
          'failure_kind':'missing_evidence'},
         None, 'missing_opponent_range'),
    ]
    out = []
    for pool,meta,eq,reason in invalid_cases:
        pools={9:pool} if pool else {}
        provenance={9:meta} if meta else {}
        rows=S.layer_equities_by_pot_layer(
            3,['Ac','Kh'],[],layer,{},pools,
            range_metadata=provenance,sims=8,seed=99,
            capture_sampling=True)
        item=rows[0]
        assert item['equity'] is None and not item['complete']
        assert item['reason']==reason,(item,reason)
        if meta:
            assert item['missing_range_details']['9'] == meta
        summary=S._layer_call_summary(53442,layer,rows)
        assert not summary['complete'] and summary['effective_equity'] is None
        assert summary['call_chip_ev'] is None
        assert summary['incomplete_reasons'][0]['reason']==reason
        shadow = dict(pf['pf_call_ev_shadow'])
        shadow.update({
            'complete':False, 'effective_equity':None,
            'call_chip_ev':None, 'gross_return':None,
            'missing_equity_layers':summary['missing_equity_layers'],
            'incomplete_reasons':summary['incomplete_reasons'],
            'layer_equities':rows,
            'exact_hu_icm':None,
        })
        shared=random.Random(919)
        before=shared.getstate()
        act,sz,record=PL.preflop_plan(
            hand['actor_profile'],'LJ',['Kh','Ac'],
            pf['pf_stack_bb'],shared,aggressor_pos='BB',
            open_bb=pf['pf_open_bb'],n_callers=0,n_limpers=0,raise_level=2,
            bf=pf['pf_calloff_consumer']['objective_bubble_factor'],
            seats=8,ante=True,bb_chips=10000,
            opener_allin=True,can_raise=False,
            pot_bb=pf['pf_pot_bb'],to_call_bb=pf['pf_to_call_bb'],
            prior_pf={'pf_act':'raise','pf_role':'open'},
            call_ev_shadow=shadow,calloff_decision_seed=3365551903,
            cold_context=pf['pf_cold_context'])
        assert shared.getstate()==before
        used=record['pf_calloff_consumer']
        assert act=='fold' and sz==0
        assert used['equity_status']=='unavailable_not_negative_ev'
        assert used['mathematically_justified'] is False
        assert used['strategy_consumer'] is False
        assert used['incomplete_reasons'][0]['reason']==reason
        out.append(reason)

    # Shared valid zero is not an unavailable estimate. The P9 producer
    # fixture independently checks this with all valid draws and 0% pot share.
    print(json.dumps({'incomplete_cases':out,'last_resort_fold':
                      'unavailable_not_negative_ev','global_rng_preserved':True},
                     sort_keys=True))
    print('PASS P8 -> P5: missing/unsupported/fallback distinctions and no fictitious -EV fold')


if __name__=='__main__':
    weighted_conditional_and_seed()
    evidence_fails_closed_at_p5()
