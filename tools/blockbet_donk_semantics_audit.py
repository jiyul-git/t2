#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only audit of blockbet/donk no-aggressor legacy fallback."""

import argparse
import collections
import inspect
import random
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import persona as PS
import plan as PL


def parse_seeds(spec):
    s = str(spec).strip()
    if ',' in s:
        return [int(x.strip()) for x in s.split(',') if x.strip()]
    if '-' in s:
        a,b = s.split('-',1)
        return list(range(int(a), int(b)+1))
    return [int(s)]


def bind(sig, args, kwargs):
    b = sig.bind_partial(*args, **kwargs)
    b.apply_defaults()
    return dict(b.arguments)


def call_from_bound(fn, d):
    return fn(**d)


def clear_tilt_cache():
    c = getattr(PS, '_TILT_VIEW_CACHE', None)
    if hasattr(c, 'clear'):
        c.clear()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='6300-6315')
    ap.add_argument('--entries', type=int, default=24)
    ap.add_argument('--hpl', type=int, default=12)
    ap.add_argument('--start-stack', type=int, default=30000)
    ap.add_argument('--cap', type=int, default=3000)
    ap.add_argument('--fmt', default='standard')
    ap.add_argument('--top', type=int, default=30)
    a = ap.parse_args()

    seeds = parse_seeds(a.seeds)
    orig_make = PL.make_plan
    orig_aggr = PL.decide_aggression
    sig_make = inspect.signature(orig_make)
    sig_aggr = inspect.signature(orig_aggr)

    block_rows = []
    aggr_rows = []
    errors = []
    field_hands = 0

    def make_wrap(*args, **kwargs):
        d = bind(sig_make, args, kwargs)
        out = orig_make(*args, **kwargs)

        ova = d.get('oop_vs_aggr')
        ola = bool(d.get('oop_legacy_abs'))
        if ova is None and ola:
            # Removing the legacy fallback can only REMOVE block eligibility; it
            # cannot create a block plan.  Replaying every fallback call is very
            # expensive because make_plan runs equity simulations.  Therefore
            # only replay actual block outcomes, which are the only rows whose
            # block membership can change under this one-way intervention.
            if out.get('plan') == 'block':
                cf = dict(d)
                cf['oop_legacy_abs'] = False
                out_cf = call_from_bound(orig_make, cf)
                block_rows.append({
                    'street': d.get('street'),
                    'initiative': bool(d.get('initiative')),
                    'actual': out.get('plan'),
                    'cf': out_cf.get('plan'),
                    'actual_why': ' / '.join(out.get('why') or []),
                    'cf_why': ' / '.join(out_cf.get('why') or []),
                    'actual_block': True,
                    'cf_block': out_cf.get('plan') == 'block',
                })
            else:
                block_rows.append({
                    'street': d.get('street'),
                    'initiative': bool(d.get('initiative')),
                    'actual': out.get('plan'),
                    'cf': out.get('plan'),
                    'actual_why': ' / '.join(out.get('why') or []),
                    'cf_why': '(not replayed: removing fallback cannot create block)',
                    'actual_block': False,
                    'cf_block': False,
                })
        return out

    def aggr_wrap(*args, **kwargs):
        d = bind(sig_aggr, args, kwargs)
        rng = d.get('rng')
        state = rng.getstate() if hasattr(rng, 'getstate') else None

        out = orig_aggr(*args, **kwargs)

        plan = d.get('plan')
        if plan not in ('bluff_2street','semibluff','river_bluff'):
            return out

        ova = d.get('oop_vs_aggr')
        ola = bool(d.get('oop_legacy_abs'))
        init = bool(d.get('initiative'))
        ps = d.get('plan_state') or {}

        kind = (
            'true_donk' if (not init and ova is True) else
            'legacy_no_aggressor' if (not init and ova is None and ola) else
            'other'
        )
        row = {
            'street': d.get('street'),
            'plan': plan,
            'kind': kind,
            'p_actual': float(out[0]),
            'why': out[1],
            'opp_checked_prev': bool(ps.get('opp_checked_prev')),
            'outs': d.get('outs'),
        }

        if kind == 'legacy_no_aggressor':
            cf = dict(d)
            cf['oop_legacy_abs'] = False
            if state is not None:
                rr = random.Random()
                rr.setstate(state)
                cf['rng'] = rr
            out_cf = call_from_bound(orig_aggr, cf)
            row['p_cf_no_legacy'] = float(out_cf[0])
            row['delta'] = float(out[0]) - float(out_cf[0])
            row['why_cf'] = out_cf[1]
        aggr_rows.append(row)
        return out

    old_make = PL.make_plan
    old_aggr = PL.decide_aggression
    old_bot_log = getattr(FS.Field, 'BOT_LOG', None)
    PL.make_plan = make_wrap
    PL.decide_aggression = aggr_wrap
    if old_bot_log is not None:
        FS.Field.BOT_LOG = 0

    try:
        for i, seed in enumerate(seeds, 1):
            print('[%d/%d] seed %d start' % (i, len(seeds), seed), flush=True)
            clear_tilt_cache()
            kw = dict(entries=a.entries, start_stack=a.start_stack,
                      hero_pid=0, seed=seed, hands_per_level=a.hpl)
            if a.fmt:
                kw['fmt'] = a.fmt
            f = FS.Field(**kw)
            while f.remaining() > 1 and f.hand_no < a.cap:
                f.hand_no += 1
                f.advance_level()
                for _tid, tb in list(f.tables.items()):
                    if tb.n() >= 2:
                        f._play_table(tb)
                f._collect_busts()
                f._balance()
                f.notes = []
            field_hands += f.hand_no
            errors.extend(list(getattr(f, 'errors', ()) or []))
            print('[%d/%d] seed %d hands %d errors %d'
                  % (i, len(seeds), seed, f.hand_no, len(getattr(f,'errors',()) or [])))
    finally:
        PL.make_plan = old_make
        PL.decide_aggression = old_aggr
        if old_bot_log is not None:
            FS.Field.BOT_LOG = old_bot_log

    print()
    print('# blockbet / donk semantic audit')
    print('seeds=%d field_hands=%d engine_errors=%d'
          % (len(seeds), field_hands, len(errors)))

    print()
    print('## no-aggressor legacy fallback at make_plan')
    print('calls:', len(block_rows))
    changed = [r for r in block_rows if r['actual'] != r['cf']]
    block_changed = [r for r in block_rows if r['actual_block'] != r['cf_block']]
    print('plan changed:', len(changed))
    print('block membership changed:', len(block_changed))
    cnt = collections.Counter((r['actual'], r['cf']) for r in changed)
    for k,n in cnt.most_common():
        print('  %s -> %s : %d' % (k[0], k[1], n))
    if block_changed:
        print('  block-change examples:')
        for r in block_changed[:a.top]:
            print('    street=%s initiative=%s actual=%s cf=%s'
                  % (r['street'], r['initiative'], r['actual'], r['cf']))

    print()
    print('## bluff-family aggression contexts')
    kc = collections.Counter(r['kind'] for r in aggr_rows)
    for k in ('true_donk','legacy_no_aggressor','other'):
        print('  %-22s %d' % (k, kc.get(k,0)))

    legacy = [r for r in aggr_rows if r['kind']=='legacy_no_aggressor']
    material = [r for r in legacy if abs(r.get('delta',0.0)) > 1e-12]
    print()
    print('## no-aggressor legacy donk-suppression counterfactual')
    print('legacy rows:', len(legacy))
    print('p changed:', len(material))
    if legacy:
        ds = [r.get('delta',0.0) for r in legacy]
        print('delta p actual-minus-no-legacy: min=%.4f mean=%.4f max=%.4f'
              % (min(ds), sum(ds)/len(ds), max(ds)))
        print('suppressed rows (delta<0):', sum(1 for x in ds if x < -1e-12))
        print('increased rows (delta>0):', sum(1 for x in ds if x > 1e-12))
    for r in sorted(material, key=lambda x: abs(x.get('delta',0.0)), reverse=True)[:a.top]:
        print('  %s %s p=%.3f cf=%.3f delta=%+.3f checked_prev=%s outs=%s'
              % (r['street'], r['plan'], r['p_actual'], r['p_cf_no_legacy'],
                 r['delta'], r['opp_checked_prev'], r['outs']))

    print()
    print('No production behavior was changed by this audit.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
