#!/usr/bin/env python3
"""Paired one-hand counterfactual for money-open sizing.

Natural baseline tournaments continue unchanged. For each qualifying unopened
near-ladder non-all-in raise, a pre-hand deepcopy is replayed and only the
opener's first raise target is replaced by the registered money-sizing target.
All decisions before the interception run normally with the same RNG state;
all decisions after it are recalculated naturally.
"""
import argparse
import copy
import json
import math
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import runner as RU
import session as SE

ORIG_HANDRUN = SE.HandRun
ORIG_APPLY = RU.Round.apply
STAGES = ('approach', 'bubble', 'itm', 'final9')
POSITIONS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB')


def stage_of(remaining, itm):
    if not remaining or not itm:
        return 'na'
    if remaining <= 9:
        return 'final9'
    if remaining <= itm:
        return 'itm'
    x = float(remaining) / float(itm)
    if x <= 1.2:
        return 'bubble'
    if x <= 1.5:
        return 'approach'
    return 'pre'


def q(xs, p):
    xs = sorted(float(x) for x in xs if x is not None)
    if not xs:
        return None
    i = int(round((len(xs) - 1) * p))
    return xs[max(0, min(len(xs) - 1, i))]


def fmt(x, n=3):
    return '-' if x is None else ('%.*f' % (n, x))


def _preflop_rows(run):
    return [(s, a, amt) for st, s, a, amt in (getattr(run, 'full_log', []) or [])
            if st == 'preflop']


def _first_open_index(pre, opener):
    for i, (s, a, amt) in enumerate(pre):
        if s == opener and a == 'raise':
            if not any(xa in ('raise', 'allin') for _, xa, _ in pre[:i]):
                return i
    return None


def _end_preflop(template, initial_stacks, pre):
    order = [template.seat_of[p] for p in template.PRE if p in template.seat_of]
    rnd = RU.Round(None, order, initial_stacks, template.bb)
    sb_s, bb_s = template.seat_of.get('SB'), template.seat_of.get('BB')
    if sb_s:
        pay = min(template.sb, rnd.stacks[sb_s])
        rnd.stacks[sb_s] -= pay
        rnd.contrib[sb_s] = pay
        if rnd.stacks[sb_s] <= 0:
            rnd.allin.add(sb_s)
    ante_pot = 0
    ante = getattr(template, 'ante', None)
    if ante is None:
        ante = template.bb
    if bb_s:
        pay = min(template.bb, rnd.stacks[bb_s])
        rnd.stacks[bb_s] -= pay
        rnd.contrib[bb_s] = pay
        if ante > 0:
            a = min(ante, rnd.stacks[bb_s])
            rnd.stacks[bb_s] -= a
            ante_pot = a
        if rnd.stacks[bb_s] <= 0:
            rnd.allin.add(bb_s)
    rnd.current = template.bb
    rnd.min_raise = template.bb
    for s, a, amt in pre:
        rnd.apply(s, a, amt)
    return rnd, sum(rnd.contrib.values()) + ante_pot


def _metrics(template, initial_stacks, run, opener, open_index):
    bb = float(template.bb)
    pre = _preflop_rows(run)
    downstream = pre[open_index + 1:] if open_index is not None else []
    action_sig = [(s, a) for s, a, _ in downstream]
    amount_sig = [(s, a, round(float(amt) / bb, 3)) for s, a, amt in downstream]
    opp_calls = sum(1 for s, a, _ in downstream if s != opener and a == 'call')
    threebet = any(s != opener and a in ('raise', 'allin')
                   for s, a, _ in downstream)
    opener_response = next(
        (a for s, a, _ in downstream if s == opener),
        None)

    rnd, pot_pre = _end_preflop(template, initial_stacks, pre)
    flop_pot = getattr(run, '_pot_at', {}).get('flop')
    spr = None
    if flop_pot is not None and opener not in rnd.folded and float(flop_pot) > 0:
        spr = float(rnd.stacks.get(opener, 0)) / float(flop_pot)

    res = getattr(run, 'result', None) or {}
    final_stack = float(run.h.stacks.get(opener, 0))
    initial_stack = float(initial_stacks.get(opener, 0))
    return {
        'action_sig': action_sig,
        'amount_sig': amount_sig,
        'opp_calls': opp_calls,
        'threebet': bool(threebet),
        'opener_response': opener_response,
        'flop_pot_bb': (round(float(flop_pot) / bb, 4)
                        if flop_pot is not None else None),
        'flop_spr': round(spr, 4) if spr is not None else None,
        'preflop_pot_bb': round(float(pot_pre) / bb, 4),
        'final_stack': final_stack,
        'gain_bb': round((final_stack - initial_stack) / bb, 6),
        'how': res.get('how'),
        'winners': list(res.get('winners') or []),
        'showdown': bool(res.get('showdown')),
    }


def _same_prefix(got, expected):
    if len(got) != len(expected):
        return False
    for a, b in zip(got, expected):
        if a[0] != b[0] or a[1] != b[1]:
            return False
        try:
            if abs(float(a[2]) - float(b[2])) > 1e-9:
                return False
        except (TypeError, ValueError):
            if a[2] != b[2]:
                return False
    return True


def _run_cf(snapshot, opener, baseline_pre, open_index, base_target, cf_target):
    expected_prefix = baseline_pre[:open_index]
    state = {'used': 0, 'errors': [], 'proposed': None}

    def patched_apply(rnd, seat, action, amount=0):
        if (seat == opener and action == 'raise' and state['used'] == 0
                and not any(a in ('raise', 'allin') for _, a, _ in rnd.log)):
            got_prefix = list(rnd.log)
            if not _same_prefix(got_prefix, expected_prefix):
                state['errors'].append('counterfactual prefix differs before intervention')
                return ORIG_APPLY(rnd, seat, action, amount)
            state['proposed'] = float(amount)
            if abs(float(amount) - float(base_target)) > 1e-9:
                state['errors'].append(
                    'unmodified target differs base: proposed=%s base=%s'
                    % (amount, base_target))
                return ORIG_APPLY(rnd, seat, action, amount)
            state['used'] += 1
            return ORIG_APPLY(rnd, seat, action, cf_target)
        return ORIG_APPLY(rnd, seat, action, amount)

    RU.Round.apply = patched_apply
    try:
        run = ORIG_HANDRUN(snapshot)
        run.start()
    finally:
        RU.Round.apply = ORIG_APPLY
    return run, state


def _row_from_pair(seed, hand_no, table_id, snapshot, base_run, obs):
    errs = []
    m = obs.get('unopened_modifiers') or {}
    opener = obs.get('seat')
    bb = float(snapshot.bb)
    base_target = float(obs.get('amount') or 0)
    sf = max(0.0, min(1.0, float(m.get('size_factor_shadow', 1.0))))
    cf_target = int(round(max(2.0 * bb, base_target * sf)))

    pre = _preflop_rows(base_run)
    oi = _first_open_index(pre, opener)
    if oi is None:
        errs.append('cannot locate baseline unopened raise')
        return {'seed': seed, 'hand_no': hand_no, 'table': table_id,
                'harness_errors': errs}

    if cf_target < 2.0 * bb - 1e-9:
        errs.append('cf target below 2BB')
    if cf_target > base_target + 1e-9:
        errs.append('cf target above baseline')
    expected = max(2.0 * bb, base_target * sf)
    if abs(cf_target - expected) > 1.000001:
        errs.append('cf target differs registered formula by >1 chip')

    initial = dict(snapshot.stacks)
    base_metrics = _metrics(snapshot, initial, base_run, opener, oi)
    initial_total = sum(float(x) for x in initial.values())
    base_total = sum(float(x) for x in base_run.h.stacks.values())
    if abs(base_total - initial_total) > 1e-6:
        errs.append('baseline chips not conserved: %.3f -> %.3f'
                    % (initial_total, base_total))

    changed = abs(cf_target - base_target) > 1e-9
    if changed:
        cf_run, state = _run_cf(snapshot, opener, pre, oi, base_target, cf_target)
        errs.extend(state['errors'])
        if state['used'] != 1:
            errs.append('sizing interception used %d times' % state['used'])
        cf_pre = _preflop_rows(cf_run)
        cf_oi = _first_open_index(cf_pre, opener)
        if cf_oi is None:
            errs.append('cannot locate counterfactual open')
            cf_oi = oi
        cf_metrics = _metrics(snapshot, initial, cf_run, opener, cf_oi)
        cf_total = sum(float(x) for x in cf_run.h.stacks.values())
        if abs(cf_total - initial_total) > 1e-6:
            errs.append('counterfactual chips not conserved: %.3f -> %.3f'
                        % (initial_total, cf_total))
    else:
        state = {'used': 0, 'errors': [], 'proposed': base_target}
        cf_metrics = copy.deepcopy(base_metrics)

    st = stage_of(obs.get('remaining'), obs.get('itm'))
    row = {
        'seed': seed,
        'hand_no': hand_no,
        'table': table_id,
        'stage': st,
        'pos': obs.get('pos'),
        'seat': opener,
        'bb': bb,
        'base_target_bb': round(base_target / bb, 6),
        'cf_target_bb': round(cf_target / bb, 6),
        'size_factor_shadow': sf,
        'changed_size': changed,
        'pressure': m.get('pressure'),
        'restraint_shadow': m.get('restraint_shadow'),
        'base': base_metrics,
        'cf': cf_metrics,
        'paired_chip_delta_bb': round(
            cf_metrics['gain_bb'] - base_metrics['gain_bb'], 6),
        'downstream_action_changed': (
            cf_metrics['action_sig'] != base_metrics['action_sig']),
        'downstream_amount_changed': (
            cf_metrics['amount_sig'] != base_metrics['amount_sig']),
        'winner_path_changed': (
            cf_metrics['how'] != base_metrics['how']
            or cf_metrics['winners'] != base_metrics['winners']),
        'harness_errors': errs,
    }
    return row


def simulate(seed, args):
    f = FS.Field(entries=args.entries, seed=seed, fmt=args.fmt)
    rows = []
    harness_errors = []

    class ProbeHandRun:
        def __init__(self, hand, decisions=None):
            self.h = hand
            self.inner = ORIG_HANDRUN(hand, decisions)
            self.snapshot = None
            st = stage_of(getattr(hand, 'field_remaining', None),
                          getattr(hand, 'field_itm', None))
            if hand.hero is None and st in STAGES:
                try:
                    self.snapshot = copy.deepcopy(hand)
                except Exception as e:
                    harness_errors.append(
                        'deepcopy H%s T%s: %s: %s'
                        % (f.hand_no, getattr(hand, 'table_id', '?'),
                           type(e).__name__, e))

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def start(self):
            out = self.inner.start()
            self.result = self.inner.result
            if self.snapshot is not None:
                candidates = []
                for x in getattr(self.h, 'money_jump_obs', []) or []:
                    if x.get('street') != 'preflop':
                        continue
                    if x.get('decision_kind') != 'unopened':
                        continue
                    m = x.get('unopened_modifiers') or {}
                    if m.get('applied_open_size_bb') is None:
                        continue
                    if stage_of(x.get('remaining'), x.get('itm')) not in STAGES:
                        continue
                    candidates.append(x)
                if len(candidates) > 1:
                    harness_errors.append(
                        'multiple qualifying opens H%s T%s: %d'
                        % (f.hand_no, getattr(self.h, 'table_id', '?'),
                           len(candidates)))
                for obs in candidates:
                    try:
                        row = _row_from_pair(
                            seed, f.hand_no, getattr(self.h, 'table_id', None),
                            self.snapshot, self.inner, obs)
                        rows.append(row)
                        for e in row.get('harness_errors') or []:
                            harness_errors.append(
                                'H%s T%s %s' %
                                (f.hand_no, getattr(self.h, 'table_id', '?'), e))
                    except Exception as e:
                        harness_errors.append(
                            'CF H%s T%s: %s: %s'
                            % (f.hand_no, getattr(self.h, 'table_id', '?'),
                               type(e).__name__, e))
            return out

        def send(self, action, amount=0):
            return self.inner.send(action, amount)

    SE.HandRun = ProbeHandRun
    try:
        for _ in range(args.rounds):
            if f.remaining() <= max(1, args.until_remaining):
                break
            f.hand_no += 1
            f.advance_level()
            for tb in list(f.tables.values()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance()
    finally:
        SE.HandRun = ORIG_HANDRUN
        RU.Round.apply = ORIG_APPLY

    return rows, list(f.errors), harness_errors, f.hand_no, f.remaining()


def _mean(xs):
    return statistics.mean(xs) if xs else None


def _paired(rows, key):
    vals = []
    for r in rows:
        a = (r.get('base') or {}).get(key)
        b = (r.get('cf') or {}).get(key)
        if a is not None and b is not None:
            vals.append(float(b) - float(a))
    return vals


def bootstrap_seed_ci(rows, reps=10000, rng_seed=922002026):
    by = {}
    for r in rows:
        by.setdefault(int(r['seed']), []).append(float(r['paired_chip_delta_bb']))
    seed_means = [statistics.mean(v) for _, v in sorted(by.items()) if v]
    if len(seed_means) < 2:
        return seed_means, None, None
    rng = random.Random(rng_seed)
    boots = []
    n = len(seed_means)
    for _ in range(reps):
        boots.append(statistics.mean(rng.choice(seed_means) for _ in range(n)))
    return seed_means, q(boots, .025), q(boots, .975)


def summarize(rows, engine_errors=None, harness_errors=None):
    engine_errors = list(engine_errors or [])
    harness_errors = list(harness_errors or [])
    row_errs = [e for r in rows for e in (r.get('harness_errors') or [])]
    deltas = [float(r['paired_chip_delta_bb']) for r in rows]
    seed_means, lo, hi = bootstrap_seed_ci(rows)

    print('\n=== money sizing behavioral CF ===')
    print('rows=%d changed_size=%d engine_errors=%d harness_errors=%d' %
          (len(rows), sum(bool(r.get('changed_size')) for r in rows),
           len(engine_errors), len(harness_errors) + len(row_errs)))

    print('\n[primary opener paired chip delta, BB]')
    print('mean=%s median=%s p10/p90=%s/%s seed_means=%d bootstrap95=%s..%s' %
          (fmt(_mean(deltas), 4), fmt(q(deltas, .5), 4),
           fmt(q(deltas, .1), 4), fmt(q(deltas, .9), 4),
           len(seed_means), fmt(lo, 4), fmt(hi, 4)))
    if lo is None or hi is None:
        verdict = 'INCONCLUSIVE insufficient seed clusters'
    elif hi < 0:
        verdict = 'AGAINST_PROMOTION bootstrap interval wholly below 0'
    elif lo > 0:
        verdict = 'SUPPORTS_PROMOTION bootstrap interval wholly above 0'
    else:
        verdict = 'INCONCLUSIVE bootstrap interval overlaps 0'
    print('primary_interpretation:', verdict)

    n = len(rows)
    b3 = sum((r.get('base') or {}).get('threebet', False) for r in rows)
    c3 = sum((r.get('cf') or {}).get('threebet', False) for r in rows)
    bc = [(r.get('base') or {}).get('opp_calls', 0) for r in rows]
    cc = [(r.get('cf') or {}).get('opp_calls', 0) for r in rows]
    print('\n[secondary behavior]')
    print('downstream_action_changed=%d/%d (%.1f%%)' %
          (sum(bool(r.get('downstream_action_changed')) for r in rows), n,
           100.0 * sum(bool(r.get('downstream_action_changed')) for r in rows)
           / max(1, n)))
    print('winner_path_changed=%d/%d (%.1f%%)' %
          (sum(bool(r.get('winner_path_changed')) for r in rows), n,
           100.0 * sum(bool(r.get('winner_path_changed')) for r in rows)
           / max(1, n)))
    print('3bet_after_open base=%d/%d cf=%d/%d delta_pp=%s' %
          (b3, n, c3, n,
           fmt(100.0 * (c3 - b3) / max(1, n), 2)))
    print('opponent_calls mean base=%s cf=%s delta=%s' %
          (fmt(_mean(bc), 3), fmt(_mean(cc), 3),
           fmt((_mean(cc) or 0) - (_mean(bc) or 0), 3)))

    for key, label in [('flop_pot_bb', 'flop_pot_bb'),
                       ('flop_spr', 'opener_flop_spr')]:
        ds = _paired(rows, key)
        print('%s paired_n=%d mean_delta=%s median_delta=%s' %
              (label, len(ds), fmt(_mean(ds), 4), fmt(q(ds, .5), 4)))

    print('\n[paired chip delta by stage]')
    for st in STAGES:
        xs = [float(r['paired_chip_delta_bb']) for r in rows if r.get('stage') == st]
        if xs:
            print('%-9s n=%-4d mean=%s median=%s p10/p90=%s/%s' %
                  (st, len(xs), fmt(_mean(xs), 4), fmt(q(xs, .5), 4),
                   fmt(q(xs, .1), 4), fmt(q(xs, .9), 4)))

    print('\n[paired chip delta by position]')
    for pos in POSITIONS:
        xs = [float(r['paired_chip_delta_bb']) for r in rows if r.get('pos') == pos]
        if xs:
            print('%-6s n=%-4d mean=%s median=%s' %
                  (pos, len(xs), fmt(_mean(xs), 4), fmt(q(xs, .5), 4)))

    print('\n[harness]')
    if engine_errors or harness_errors or row_errs:
        print('FAIL')
        for e in (engine_errors + harness_errors + row_errs)[:40]:
            print(' -', e)
        return 1
    print('PASS no structural harness violations')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--rounds', type=int, default=260)
    ap.add_argument('--until-remaining', type=int, default=8)
    ap.add_argument('--fmt', default='standard')
    ap.add_argument('--seed-start', type=int, default=92200)
    ap.add_argument('--seeds', type=int, default=1)
    ap.add_argument('--out', default='money_sizing_cf.jsonl')
    args = ap.parse_args()

    all_rows = []
    all_engine = []
    all_harness = []
    seed_meta = []
    for seed in range(args.seed_start, args.seed_start + args.seeds):
        rows, eng, har, hands, remaining = simulate(seed, args)
        all_rows.extend(rows)
        all_engine.extend('seed=%d %s' % (seed, x) for x in eng)
        all_harness.extend('seed=%d %s' % (seed, x) for x in har)
        seed_meta.append({
            'seed': seed, 'rows': len(rows), 'hands': hands,
            'remaining': remaining, 'engine_errors': len(eng),
            'harness_errors': len(har),
        })
        print('seed %d rows=%d rounds=%d remaining=%d engine=%d harness=%d' %
              (seed, len(rows), hands, remaining, len(eng), len(har)),
              flush=True)

    with open(args.out, 'w', encoding='utf-8') as fp:
        for r in all_rows:
            fp.write(json.dumps(r, ensure_ascii=False) + '\n')

    meta_path = args.out + '.meta.json'
    with open(meta_path, 'w', encoding='utf-8') as fp:
        json.dump({'seeds': seed_meta,
                   'engine_errors': all_engine,
                   'harness_errors': all_harness},
                  fp, ensure_ascii=False, indent=2)
        fp.write('\n')

    rc = summarize(all_rows, all_engine, all_harness)
    print('\nWROTE', args.out)
    print('WROTE', meta_path)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
