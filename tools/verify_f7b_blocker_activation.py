#!/usr/bin/env python3
"""Verify production matches preregistered F7-B1C11 blocker structure target."""
import inspect
import json
import os
import sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

import plan as PL
import ranges as R
from tools import regress as REG

EXPECTED={
    3000:'12c2daefd7c87cbb',
    3001:'8b83f668c038d002',
    3002:'0badaa6a21474fd3',
    3003:'3aebdd1942b57229',
    3004:'d4295da0aace11ca',
    3005:'2c50d0b71bd16614',
}


def source_check():
    m=inspect.getsource(PL.make_plan)
    r=inspect.getsource(PL.refresh)
    rv=inspect.getsource(PL.river_fix)
    h=inspect.getsource(PL._decision_blocker_effect)

    assert "_decision_blocker_effect(" in m
    assert "'blocker_net_raw': float(_blk_raw)" in m
    assert "_decision_blocker_effect(" in r
    assert "st['blocker_net_raw'] = float(_blk_raw)" in r
    assert "_so['_blk_net'] = round(_blk_net, 3)" in r
    assert "st.get('blocker_net_raw')" in rv
    assert "joint_blocker_effect(" in h
    assert "_blocker_score_bluff_factor(blk)" in m
    return {
        'single_blocker_effect_judgment':True,
        'refreshes_current_state':True,
        'river_reuses_shared_state':True,
        'score_frequency_calibration_preserved':True,
    }


def main():
    print('PASS F7-B1C12 blocker production source check',source_check())
    fp,stats=REG.fingerprint()
    bad=[s for s in EXPECTED if fp.get(s)!=EXPECTED[s]]
    print(json.dumps({
        'expected_fp':EXPECTED,
        'production_fp':fp,
        'stats':stats,
        'mismatch_seeds':bad,
    },indent=2,sort_keys=True))
    if bad:
        raise SystemExit('FAIL F7-B1C12 activation fingerprint mismatch: %s'%bad)
    print('PASS F7-B1C12 production matches preregistered structure-only fingerprints')


if __name__=='__main__':
    main()
