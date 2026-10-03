#!/usr/bin/env python3
"""Verify the equal-share ante and the single forced-bet posting order.

Rules (runner.post_forced_bets is the one implementation):
  * the ante total (1bb) is split equally among dealt-in seats, SB/BB included;
    integer chips: ante // n each, the remainder one chip each to the earliest
    seats in preflop order (total exact, max 1 chip spread);
  * order: antes -> SB -> BB; blinds come out of the post-ante stack;
  * a seat shorter than its share pays what it has; zero stack => all-in;
  * the ante is dead money (never in contrib).

Checks: share arithmetic for 5..9 seats, short-stack boundaries, chip
conservation, both callers (session engine, live2 opening replay) use the one
function, and a live engine run over tables of varying size.
"""
import inspect, json, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('T2_BOT_LOG', '0')
import runner as RU


def main():
    checks = {}

    # A: share arithmetic, 5..9 seats, divisible and non-divisible amounts.
    rows = []
    ok = True
    for n in range(5, 10):
        for ante in (100, 150, 200, 300, 400, 600, 1000, 1200, 7):
            sh = RU.ante_shares(ante, list(range(n)))
            vals = [sh[i] for i in range(n)]
            good = (sum(vals) == ante and max(vals) - min(vals) <= 1
                    and vals == sorted(vals, reverse=True))
            ok &= good
            if ante in (300, 7):
                rows.append({'n': n, 'ante': ante, 'shares': vals})
    checks['A_equal_shares_exact_total'] = {'pass': bool(ok), 'examples': rows}

    # B: order ante -> SB -> BB on short stacks (bb=300, sb=150, 9 seats).
    seats = list(range(9)); sbs, bbs = 7, 8
    st = {s: 30000 for s in seats}; st[bbs] = 315; st[sbs] = 100
    blinds, ante_paid, ante_pot, allin = RU.post_forced_bets(
        st, seats, sbs, bbs, 150, 300, 300)
    checks['B_short_blinds_pay_ante_first'] = {
        'pass': (ante_paid[bbs] == 33 and blinds[bbs] == 282
                 and ante_paid[sbs] == 33 and blinds[sbs] == 67
                 and ante_pot == 300 and allin == {sbs, bbs}),
        'blinds': blinds, 'ante_bb': ante_paid[bbs], 'ante_sb': ante_paid[sbs]}

    # C: seat shorter than its share; ante never enters contrib.
    st = {0: 10, 1: 5000, 2: 5000, 3: 5000, 4: 5000}
    before = sum(st.values())
    blinds, ante_paid, ante_pot, allin = RU.post_forced_bets(
        st, [0, 1, 2, 3, 4], 3, 4, 50, 100, 100)
    paid = before - sum(st.values())
    checks['C_short_share_and_conservation'] = {
        'pass': (ante_paid[0] == 10 and ante_pot == 90 and 0 in allin
                 and paid == ante_pot + sum(blinds.values())
                 and set(blinds) == {3, 4}),
        'ante_paid': ante_paid, 'blinds': blinds}

    # D: no ante level -> nothing collected, blinds unchanged.
    st = {s: 1000 for s in range(6)}
    blinds, ante_paid, ante_pot, _ = RU.post_forced_bets(st, list(range(6)), 4, 5, 50, 100, 0)
    checks['D_no_ante_level'] = {'pass': ante_pot == 0 and not ante_paid
                                 and blinds == {4: 50, 5: 100}}

    # E: single implementation used by both callers.
    import session as SE, live2 as L2
    src_s = inspect.getsource(SE.HandRun)
    src_l = inspect.getsource(L2._opening_raw)
    checks['E_single_posting_function'] = {
        'pass': ('RU.post_forced_bets(' in src_s and 'RU.post_forced_bets(' in src_l
                 and 'ante_pot = a' not in src_s and 'ante_pot = a' not in src_l)}

    # F: live engine, tables of varying size, ante levels.
    import fieldsim as FS
    cap = []
    orig = RU.post_forced_bets

    def spy(stacks, seats_, sbs_, bbs_, sb, bb, ante):
        b = sum(stacks[s] for s in seats_)
        r = orig(stacks, seats_, sbs_, bbs_, sb, bb, ante)
        cap.append({'n': len(seats_), 'ante': ante,
                    'conserved': b - sum(stacks[s] for s in seats_) == r[2] + sum(r[0].values()),
                    'bb_blind_only': (bbs_ is None or r[0].get(bbs_, 0) <= bb)})
        return r
    RU.post_forced_bets = spy
    try:
        f = FS.Field(entries=31, start_stack=4000, hero_pid=-1, seed=17, hands_per_level=3)
        for _ in range(40):
            if f.remaining() <= 1:
                break
            f.hand_no += 1
            f.advance_level()
            for tid, tb in list(f.tables.items()):
                if tb.n() >= 2:
                    f._play_table(tb)
            f._collect_busts()
            f._balance(notify=False)
            f.notes = []
        errors = len(f.errors)
    finally:
        RU.post_forced_bets = orig
    sizes = sorted({c['n'] for c in cap if c['ante'] > 0})
    checks['F_live_engine'] = {
        'pass': (errors == 0 and cap and all(c['conserved'] and c['bb_blind_only'] for c in cap)
                 and any(c['ante'] > 0 for c in cap)),
        'posts': len(cap), 'ante_posts': sum(1 for c in cap if c['ante'] > 0),
        'table_sizes_with_ante': sizes, 'engine_errors': errors}

    out = {'pass': all(v['pass'] for v in checks.values()), 'checks': checks}
    print(json.dumps(out, indent=1, sort_keys=True, default=str))
    raise SystemExit(0 if out['pass'] else 1)


if __name__ == '__main__':
    main()
