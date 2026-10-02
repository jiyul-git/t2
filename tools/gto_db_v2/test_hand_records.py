#!/usr/bin/env python3
"""Tests for hand_records_v1.  python3 tools/gto_db_v2/test_hand_records.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hand_records as HR  # noqa: E402

A = ['fold', 'raise', 'jam']


def main():
    res = {}
    # clear pure choice, replicates agree -> stable
    r = HR.record(A, [0, 1, 0], [0, 1.0, 0.2], [[0, 1, 0]] * 60, [[0, 1.0 + 0.01 * (i % 3), 0.2] for i in range(60)])
    res['stable'] = r['status'] == 'stable'
    # EV gap within 2u -> near_indifferent, even if the point is pure
    r2 = HR.record(A, [0, 1, 0], [0, 0.50, 0.49], [[0, 1, 0]] * 60, [[0, 0.5 + 0.02 * ((-1) ** i), 0.49] for i in range(60)])
    res['near_indifferent'] = r2['status'] == 'near_indifferent' and HR.near_indifferent_group(r2) == ['jam', 'raise']
    # clear gap but the modal action flips in 10 / 60 replicates -> unstable
    r3 = HR.record(A, [0, 1, 0], [0, 1.0, 0.2], [[0, 1, 0]] * 50 + [[0, 0, 1]] * 10, [[0, 1.0, 0.2]] * 60)
    res['unstable_modal'] = r3['status'] == 'unstable' and abs(r3['modal_action_consistency'] - 50 / 60) < 1e-12
    # 57 / 60 is enough (a = 0.95)
    r4 = HR.record(A, [0, 1, 0], [0, 1.0, 0.2], [[0, 1, 0]] * 57 + [[0, 0, 1]] * 3, [[0, 1.0, 0.2]] * 60)
    res['modal_57_of_60_stable'] = r4['status'] == 'stable'
    r5 = HR.record(A, [0, 1, 0], [0, 1.0, 0.2], [[0, 1, 0]] * 56 + [[0, 0, 1]] * 4, [[0, 1.0, 0.2]] * 60)
    res['modal_56_of_60_unstable'] = r5['status'] == 'unstable'
    # no replicates -> unassessed
    r6 = HR.record(A, [0, 1, 0], [0, 1.0, 0.2], [], [])
    res['unassessed'] = r6['status'] == 'unassessed'
    # intervals stored separately from status
    res['intervals_stored'] = r2['freq_q05_q50_q95'] is not None and r2['l1_dispersion'] is not None
    # validation: merging actions is rejected
    hands = {'AA': r}
    HR.validate({'format': 'hand_records_v1', 'actions': A, 'hands': hands})
    bad = dict(r)
    bad['freq'] = {'fold': 0, 'raise_or_jam': 1}
    try:
        HR.validate({'format': 'hand_records_v1', 'actions': A, 'hands': {'AA': bad}})
        res['reject_merged'] = False
    except ValueError:
        res['reject_merged'] = True
    ok = all(res.values())
    print(res, 'ALL PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
