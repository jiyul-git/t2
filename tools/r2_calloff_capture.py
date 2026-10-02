"""Read-only capture of all-in-facing preflop decisions on top of tools/r2_baseline_sim.py.

Usage: python tools/r2_calloff_capture.py SEED   (writes calloff_cap_SEED.json next to this file)
The extra wrapper frame blanks the base harness's hash/seat fields, so its sha differs from the seal;
hand and decision counts are unchanged.
"""
import sys, json, os
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(_R, 'tools')); sys.path.insert(0, _R)
import r2_baseline_sim as BS
import plan as PL
CAP = []
_inner = PL.preflop_plan
def wrap(ax, pos, hand, bbs, rng, **kw):
    r = _inner(ax, pos, hand, bbs, rng, **kw)
    sd = r[2] or {}
    if sd.get('pf_calloff_consumer') or sd.get('pf_calloff_compare') or sd.get('pf_facing_allin') or \
       (kw.get('open_bb') and kw.get('open_bb') >= 0.92 * bbs):
        CAP.append({'pos': pos, 'hand': list(hand), 'bbs': bbs, 'open_bb': kw.get('open_bb'),
                    'to_call_bb': kw.get('to_call_bb'), 'can_raise': kw.get('can_raise'),
                    'opener_allin': kw.get('opener_allin'), 'act': r[0], 'sz': r[1],
                    'kind': sd.get('pf_decision_kind'), 'shadow': bool(kw.get('call_ev_shadow')),
                    'shadow_complete': bool((kw.get('call_ev_shadow') or {}).get('complete')),
                    'consumer': sd.get('pf_calloff_consumer'), 'compare': sd.get('pf_calloff_compare'),
                    'n_opp_ranges': len(kw.get('opp_ranges') or {})})
    return r
BS.PL.preflop_plan = wrap
PL.preflop_plan = wrap
seed = int(sys.argv[1]); sys.argv = [sys.argv[0], str(seed), '60']
BS.main()
json.dump(CAP, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'calloff_cap_%d.json' % seed), 'w'), default=str)
