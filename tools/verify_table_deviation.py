#!/usr/bin/env python3
"""reads.table_deviation: table-baseline ± deviation (compute only).

U1  baseline pools the other table opponents (observer and target excluded).
U2  sign follows rate - base; magnitude shrinks with sample size n/(n+K).
U3  no target sample -> dev 0; no baseline sample -> dev/base None.
U4  memory window uses the recent record (same as estimate).
N1  nothing in the decision code consumes table_deviation yet (shadow).
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import reads as RD


def book():
    b = RD.Book()
    for t, (h, v) in {1: (20, 10), 2: (20, 4), 3: (20, 2), 9: (100, 90)}.items():
        r = b.rec(0, t); r['hands'] = h; r['vpip'] = v
    b.rec(5, 1)['hands'] = 50; b.rec(5, 1)['vpip'] = 0       # other observer: ignored
    return b


def u1_u2():
    b = book()
    d = RD.table_deviation(b, 0, 1, [0, 1, 2, 3])['loose']
    base = 6 / 40.0
    exp = (20 / 32.0) * (0.5 - base)
    ok = abs(d['base'] - base) < 1e-12 and abs(d['dev'] - exp) < 1e-12 and d['n'] == 20 and d['base_n'] == 40
    d3 = RD.table_deviation(b, 0, 3, [1, 2, 3])['loose']
    ok &= d3['dev'] < 0
    # table membership: 9 is not at this table, so it does not enter the baseline
    ok &= RD.table_deviation(b, 0, 1, [1, 2, 3])['loose']['base_n'] == 40
    # more sample, same rates -> larger magnitude
    b2 = book(); r = b2.rec(0, 1); r['hands'] = 80; r['vpip'] = 40
    ok &= RD.table_deviation(b2, 0, 1, [1, 2, 3])['loose']['dev'] > d['dev']
    return {'pass': bool(ok), 'dev': round(d['dev'], 4), 'dev_tight': round(d3['dev'], 4)}


def u3():
    b = book()
    none_t = RD.table_deviation(b, 0, 7, [1, 2, 7])
    none_b = RD.table_deviation(b, 0, 1, [1])
    ok = (none_t['loose']['dev'] == 0.0 and none_t['loose']['rate'] is None
          and none_b['loose']['dev'] is None and none_b['loose']['base'] is None
          and none_t['fold']['dev'] is None)        # nobody faced a bet yet
    return {'pass': bool(ok)}


def u4():
    b = RD.Book()
    r = b.rec(0, 1)
    for i in range(30):                 # 20 loose hands then 10 tight ones
        r['hands'] += 1
        if i < 20: r['vpip'] += 1
        RD._append_hand_snapshot(r)
    o = b.rec(0, 2)
    for i in range(30):
        o['hands'] += 1
        if i % 2: o['vpip'] += 1
        RD._append_hand_snapshot(o)
    full = RD.table_deviation(b, 0, 1, [1, 2])['loose']
    rec = RD.table_deviation(b, 0, 1, [1, 2], memory=10)['loose']
    ok = full['dev'] > 0 and rec['dev'] < 0 and rec['n'] == 10
    return {'pass': bool(ok), 'full': round(full['dev'], 4), 'recent10': round(rec['dev'], 4)}


def n1():
    out = subprocess.run(['git', '-C', ROOT, 'grep', '-n', 'table_deviation', '--', '*.py'],
                         capture_output=True, text=True).stdout.splitlines()
    users = [l for l in out if not l.startswith(('reads.py', 'tools/', 'docs/'))]
    return {'pass': not users, 'consumers': users}


def main():
    checks = {'U1_U2_baseline_sign_shrink': u1_u2(), 'U3_missing_samples': u3(),
              'U4_memory_window': u4(), 'N1_shadow_only': n1()}
    ok = all(v['pass'] for v in checks.values())
    print(json.dumps({'pass': ok, 'checks': checks}, indent=1))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
