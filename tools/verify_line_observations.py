#!/usr/bin/env python3
"""Exploit observations: lead / probe lines, their follow-up and showdown link.

C1  session.line_spot_kind classification cases (lead / probe / none).
S1  a tournament with the persistent book records lead and probe spots; counts
    are consistent: bets <= opportunities, raise responses <= bets.
S2  showdown links exist and strong/weak <= shown.
R1  plan.opp_bet_prob: 'aggressor' uses c-bet/barrel, 'probe' uses the probe
    rate shrunk toward the same base; no probe sample -> base; None -> legacy.
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault('T2_BOT_LOG', '0')
import session as SE
import plan as PL
import reads as RD
import fieldsim as FS


def c1():
    k = SE.line_spot_kind
    cases = [
        ((2, 5, True, set(), set(), False), 'lead'),          # aggressor 5 still to act
        ((2, 5, True, {5}, {5}, False), 'probe'),              # aggressor checked
        ((2, None, False, set(), set(), False), 'probe'),      # no aggressor
        ((2, 5, False, set(), set(), False), 'probe'),         # aggressor folded / all-in
        ((5, 5, True, set(), set(), False), None),             # aggressor's own spot
        ((2, 5, True, set(), set(), True), None),              # a bet already made
        ((2, 5, True, {2}, set(), False), None),               # not the first action
        ((2, 5, True, {5}, set(), False), None),               # aggressor acted (not a check) without a bet
    ]
    got = [k(*a) for a, _ in cases]
    return {'pass': got == [e for _, e in cases], 'got': got}


def sim():
    FS.Field._log_bot_hand = lambda *a, **k: None
    f = FS.Field(entries=27, start_stack=30000, hero_pid=-1, seed=21, hands_per_level=12)
    for _ in range(30):
        if f.remaining() <= 1:
            break
        f.hand_no += 1
        f.advance_level()
        for tid, tb in list(f.tables.items()):
            if tb.n() >= 2:
                f._play_table(tb)
        f._collect_busts(); f._balance(notify=False); f.notes = []
    tot = {}
    ok = True
    for r in f.book.d.values():
        for kind in ('lead', 'probe'):
            for st in ('flop', 'turn', 'river'):
                o, b = r.get('%s_opp_%s' % (kind, st), 0), r.get('%s_%s' % (kind, st), 0)
                ok &= b <= o
                tot['%s_opp' % kind] = tot.get('%s_opp' % kind, 0) + o
                tot['%s_bet' % kind] = tot.get('%s_bet' % kind, 0) + b
            fr, f2r = r.get('%s_fr' % kind, 0), r.get('%s_f2r' % kind, 0)
            ok &= f2r <= fr
            tot['%s_fr' % kind] = tot.get('%s_fr' % kind, 0) + fr
            sd, sw, ss = (r.get('sd_%s' % kind, 0), r.get('sd_%s_weak' % kind, 0),
                          r.get('sd_%s_strong' % kind, 0))
            ok &= sw + ss <= sd
            tot['sd_%s' % kind] = tot.get('sd_%s' % kind, 0) + sd
    s1 = {'pass': bool(ok and tot.get('lead_opp', 0) > 0 and tot.get('probe_opp', 0) > 0
                       and tot.get('lead_bet', 0) > 0 and tot.get('probe_bet', 0) > 0),
          'totals': tot}
    s2 = {'pass': bool(ok and (tot.get('sd_lead', 0) + tot.get('sd_probe', 0)) > 0)}
    return s1, s2


def r1():
    est = {'cbet': 0.80, 'barrel': 0.70, 'aggr': 5.0,
           'probe_flop': 0.10, 'probe_flop_n': 40, 'probe_turn': None, 'probe_turn_n': 0}
    w = 1.0
    agg = PL.opp_bet_prob(est, w, 'flop', opp_role='aggressor')
    leg = PL.opp_bet_prob(est, w, 'flop')
    prb = PL.opp_bet_prob(est, w, 'flop', opp_role='probe')
    prb_none = PL.opp_bet_prob(est, w, 'turn', opp_role='probe')
    base_turn = 0.65 * 0.38 + 0.35 * 0.5
    ok = (abs(agg - leg) < 1e-12 and prb < agg and abs(prb_none - base_turn) < 1e-9
          and PL.opp_bet_prob(est, 0.0, 'flop', opp_role='probe') == 0.45)
    return {'pass': bool(ok), 'aggressor': round(agg, 4), 'probe': round(prb, 4),
            'probe_no_sample_turn': round(prb_none, 4)}


def main():
    s1, s2 = sim()
    checks = {'C1_classification': c1(), 'S1_counts_consistent': s1,
              'S2_showdown_link': s2, 'R1_role_rates': r1()}
    ok = all(v['pass'] for v in checks.values())
    print(json.dumps({'pass': ok, 'checks': checks}, indent=1))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
