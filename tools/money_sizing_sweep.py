#!/usr/bin/env python3
"""Multi-seed validation for unopened money-jump raise-size shadow.

No behavior is changed.  The tool runs natural-state tournaments, keeps only
near-ladder unopened non-all-in raises with an actual legal applied size, and
checks mechanical invariants required before sizing can be considered for
promotion.
"""
import argparse, collections, json, os, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fieldsim as FS
import money_pressure as MP

STAGES = ('approach', 'bubble', 'itm', 'final9')
POSITIONS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB')


def stage(r):
    rem, itm = r.get('remaining'), r.get('itm')
    if not rem or not itm:
        return 'na'
    if rem <= 9:
        return 'final9'
    if rem <= itm:
        return 'itm'
    x = float(rem) / float(itm)
    if x <= 1.2:
        return 'bubble'
    if x <= 1.5:
        return 'approach'
    return 'pre'


def q(xs, p):
    xs = sorted(float(x) for x in xs if x is not None)
    if not xs:
        return None
    return xs[min(len(xs) - 1, max(0, int((len(xs) - 1) * p)))]


def fmtq(x, digits=3):
    return '-' if x is None else ('%.*f' % (digits, x))


def simulate(seed, args):
    f = FS.Field(entries=args.entries, seed=seed, fmt=args.fmt)
    rows = []

    def capture(tb, h, run):
        for x in getattr(h, 'money_jump_obs', []) or []:
            if x.get('street') != 'preflop' or x.get('decision_kind') != 'unopened':
                continue
            m = x.get('unopened_modifiers') or {}
            if m.get('applied_open_size_bb') is None:
                continue
            st = stage(x)
            if st not in STAGES:
                continue
            y = dict(x)
            y['seed'] = seed
            y['hand_no'] = f.hand_no
            y['table'] = tb.id
            y['_sizing_stage'] = st
            rows.append(y)

    f._log_bot_hand = capture

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

    return rows, list(f.errors), f.hand_no, f.remaining()


def size_values(r):
    m = r.get('unopened_modifiers') or {}
    base = float(m['applied_open_size_bb'])
    shadow = float(m['applied_money_size_bb_shadow'])
    sf = float(m.get('size_factor_shadow', 1.0))
    expected = round(max(2.0, base * sf), 3)
    return base, shadow, sf, expected


def skill_counterfactual(r, skill):
    base, _, _, _ = size_values(r)
    s = dict(r)
    s['open_size_skill'] = float(skill)
    m = MP.unopened_modifiers(s)
    return round(max(2.0, base * float(m['size_factor_shadow'])), 3)


def summarize(label, rows):
    if not rows:
        print('%-10s n=0' % label)
        return
    bases, shadows, shrink = [], [], []
    changed = at2 = 0
    for r in rows:
        b, s, _, _ = size_values(r)
        bases.append(b)
        shadows.append(s)
        shrink.append(b - s)
        if s < b - 1e-9:
            changed += 1
        if abs(s - 2.0) < 1e-9:
            at2 += 1
    n = len(rows)
    print(
        '%-10s n=%-5d changed=%-5d(%5.1f%%) at2bb=%-5d(%5.1f%%) '
        'base p50/p90=%s/%s shadow=%s/%s shrink p50/p90/max=%s/%s/%s'
        % (
            label, n, changed, 100.0 * changed / n,
            at2, 100.0 * at2 / n,
            fmtq(q(bases, .5), 2), fmtq(q(bases, .9), 2),
            fmtq(q(shadows, .5), 2), fmtq(q(shadows, .9), 2),
            fmtq(q(shrink, .5)), fmtq(q(shrink, .9)),
            fmtq(max(shrink) if shrink else None),
        )
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--rounds', type=int, default=260)
    ap.add_argument('--until-remaining', type=int, default=8)
    ap.add_argument('--fmt', default='standard')
    ap.add_argument('--seed-start', type=int, default=92100)
    ap.add_argument('--seeds', type=int, default=20)
    ap.add_argument('--out', default='money_sizing_sweep.jsonl')
    args = ap.parse_args()

    all_rows = []
    engine_errors = []
    seed_counts = []

    for seed in range(args.seed_start, args.seed_start + args.seeds):
        rows, errors, hands, remaining = simulate(seed, args)
        all_rows.extend(rows)
        seed_counts.append((seed, len(rows), hands, remaining, len(errors)))
        engine_errors.extend((seed, e) for e in errors)
        print('seed %d  sizing_rows=%d  rounds=%d  remaining=%d  errors=%d'
              % (seed, len(rows), hands, remaining, len(errors)))

    with open(args.out, 'w', encoding='utf-8') as fp:
        for r in all_rows:
            fp.write(json.dumps(r, ensure_ascii=False) + '\n')

    violations = []
    if not all_rows:
        violations.append('no near-ladder sizing rows were collected')
    skill_strict = 0
    skill_equal = 0
    skill_deltas = []

    for r in all_rows:
        b, s, sf, expected = size_values(r)
        ident = 'seed=%s H%s T%s %s %s' % (
            r.get('seed'), r.get('hand_no'), r.get('table'),
            r.get('_sizing_stage'), r.get('pos'))

        if s < 2.0 - 1e-9:
            violations.append('%s shadow<2BB: %.3f' % (ident, s))
        if s > b + 1e-9:
            violations.append('%s shadow>base: %.3f>%.3f' % (ident, s, b))
        if abs(s - expected) > 0.0011:
            violations.append(
                '%s formula mismatch: logged=%.3f expected=%.3f base=%.3f sf=%.6f'
                % (ident, s, expected, b, sf))

        lo = skill_counterfactual(r, 1.0)
        hi = skill_counterfactual(r, 9.0)
        if hi > lo + 1e-9:
            violations.append(
                '%s skill monotonic violation: skill1=%.3f skill9=%.3f'
                % (ident, lo, hi))
        elif hi < lo - 1e-9:
            skill_strict += 1
        else:
            skill_equal += 1
        skill_deltas.append(lo - hi)

    print('\n=== money sizing promotion check ===')
    print('seeds %d..%d  rows=%d  engine_errors=%d'
          % (args.seed_start, args.seed_start + args.seeds - 1,
             len(all_rows), len(engine_errors)))

    print('\n[by stage]')
    for st in STAGES:
        summarize(st, [r for r in all_rows if r.get('_sizing_stage') == st])

    print('\n[by position]')
    for pos in POSITIONS:
        x = [r for r in all_rows if r.get('pos') == pos]
        if x:
            summarize(pos, x)

    print('\n[same-state open_size skill 1 -> 9]')
    print('rows=%d strict_smaller=%d equal_after_2bb_floor_or_zero_effect=%d '
          'delta p50/p90/max=%s/%s/%s'
          % (
              len(all_rows), skill_strict, skill_equal,
              fmtq(q(skill_deltas, .5)),
              fmtq(q(skill_deltas, .9)),
              fmtq(max(skill_deltas) if skill_deltas else None),
          ))

    print('\n[structural checks]')
    if engine_errors:
        for seed, e in engine_errors[:10]:
            print('ENGINE ERROR seed=%s %s' % (seed, e))
    if violations:
        print('FAIL violations=%d' % len(violations))
        for v in violations[:30]:
            print(' -', v)
    elif engine_errors:
        print('FAIL engine_errors=%d' % len(engine_errors))
    else:
        print('PASS no structural violations')

    print('\nWROTE', args.out)
    return 1 if violations or engine_errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
