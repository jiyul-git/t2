#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V7 paired counterfactual.

CONTROL: persona.read_opponent
V7     : reads.hierarchical_read_v7 (이 프로세스 안에서만 monkeypatch)

production 파일은 바꾸지 않는다. 사전등록 HIERARCHICAL_READ_V7_PREREG.md 7절.

V6 계측에서 얻은 교훈 둘을 반영한다.
- bin 축을 detail_access 로 쓰지 않는다. V7 구간(tier)으로 직접 집계한다.
- divergence 를 핸드 수가 아니라 **독립 원인 수**로 센다. 핸드마다 읽기 이전의
  사전 상태(스택·버튼·레벨) 서명을 남기고, 사전 상태가 같은데 갈라진 핸드만
  독립 원인으로 센다.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import persona as PS
import reads as RD
import tourney as T

HANDS = 30
N_BUCKETS = ((0, 6), (6, 12), (12, 30), (30, 10 ** 9))


def _bucket(n):
    for i, (lo, hi) in enumerate(N_BUCKETS):
        if lo <= n < hi:
            return i
    return len(N_BUCKETS) - 1


def _hash_hands(hands):
    rows = [';'.join('%s:%s:%s:%s' % tuple(x) for x in log) for log in hands]
    return hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]


def _state_sig(t):
    stacks = tuple(sorted((int(s), int(t.stacks[s])) for s in t.seats))
    return hashlib.sha256(json.dumps(
        [stacks, int(getattr(t, 'button', -1)), int(getattr(t, 'level', -1))],
        sort_keys=True).encode()).hexdigest()[:12]


def _blank_tier():
    return {'calls': 0, 'w_positive': 0, 'sum_w': 0.0, 'sum_s': 0.0,
            'sum_data': 0.0, 'sum_mag': 0.0,
            'by_n': [{'calls': 0, 'sum_data': 0.0, 'sum_mag': 0.0}
                     for _ in N_BUCKETS]}


def _inner(seed, arm, entries):
    orig = PS.read_opponent
    stats = {str(t): _blank_tier() for t in range(1, 6)}
    gap_keys = [k for k in RD.V7_ALL_KEYS if k != 'size_river']

    if arm == 'v7':
        def wrapped(prof, opp_est):
            o = RD.hierarchical_read_v7(prof, opp_est)
            t = stats[str(o.get('tier', 1))]
            t['calls'] += 1
            w = float(o.get('w', 0.0) or 0.0)
            if w > 0:
                t['w_positive'] += 1
            mag = sum(abs(float(o.get(k, 0.0) or 0.0)) for k in gap_keys)
            t['sum_w'] += w
            t['sum_s'] += float(o.get('s', 0.0) or 0.0)
            t['sum_data'] += float(o.get('data', 0.0) or 0.0)
            t['sum_mag'] += mag
            b = t['by_n'][_bucket(float((opp_est or {}).get('n', 0) or 0))]
            b['calls'] += 1
            b['sum_data'] += float(o.get('data', 0.0) or 0.0)
            b['sum_mag'] += mag
            return o
        PS.read_opponent = wrapped

    hands, pre, errors = [], [], []
    try:
        t = T.Tournament(entries=entries, start_stack=30000, hero_seat=7,
                         seed=seed, hands_per_level=200)
        for hi in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            pre.append(_state_sig(t))
            try:
                st = t.next_hand()
                guard = 0
                while st and not st.get('done') and guard < 200:
                    st = t.submit('fold')
                    guard += 1
                if guard >= 200:
                    errors.append('guard:%d' % hi)
                    break
                hands.append([list(x) for x in
                              (getattr(t.run, 'full_log', []) or [])])
                t.finish_hand()
            except Exception as e:
                errors.append('%s:%s' % (type(e).__name__, str(e)))
                break
    finally:
        PS.read_opponent = orig

    return {'seed': seed, 'arm': arm, 'entries': entries,
            'hands_n': len(hands), 'hash': _hash_hands(hands),
            'hands': hands, 'pre': pre,
            'engine_errors': len(errors), 'errors': errors,
            'tier_stats': stats}


def _spawn(seed, arm, entries):
    cp = subprocess.run(
        [sys.executable, os.path.abspath(__file__), '--inner', '--seed',
         str(seed), '--arm', arm, '--entries', str(entries)],
        cwd=ROOT, text=True, capture_output=True, timeout=1800)
    if cp.returncode != 0:
        raise RuntimeError('%s rc=%s %s' % (arm, cp.returncode, cp.stderr[-1200:]))
    line = next((x for x in cp.stdout.splitlines()
                 if x.startswith('INNER_JSON=')), None)
    if not line:
        raise RuntimeError('%s missing INNER_JSON' % arm)
    return json.loads(line.split('=', 1)[1])


def _outer(seed, entries):
    c = _spawn(seed, 'control', entries)
    v = _spawn(seed, 'v7', entries)
    n = max(len(c['hands']), len(v['hands']))
    diff_hands, diff_entries, first = 0, 0, None
    indep_hands, indep_entries, chain_entries = [], 0, 0
    for i in range(n):
        a = c['hands'][i] if i < len(c['hands']) else []
        b = v['hands'][i] if i < len(v['hands']) else []
        if a == b:
            continue
        diff_hands += 1
        cnt = 0
        for j in range(max(len(a), len(b))):
            xa = a[j] if j < len(a) else None
            xb = b[j] if j < len(b) else None
            if xa != xb:
                cnt += 1
                if first is None:
                    first = {'hand': i, 'entry': j, 'control': xa, 'v7': xb}
        diff_entries += cnt
        same_pre = (i < len(c['pre']) and i < len(v['pre'])
                    and c['pre'][i] == v['pre'][i])
        if same_pre:
            indep_hands.append(i)
            indep_entries += cnt
        else:
            chain_entries += cnt

    pre_first = next((i for i in range(min(len(c['pre']), len(v['pre'])))
                      if c['pre'][i] != v['pre'][i]), None)
    out = {
        'seed': seed, 'entries': entries,
        'control_hash': c['hash'], 'v7_hash': v['hash'],
        'hands_control': c['hands_n'], 'hands_v7': v['hands_n'],
        'diff_hands': diff_hands, 'diff_entries': diff_entries,
        'independent_hands': indep_hands,
        'independent_entries': indep_entries, 'chain_entries': chain_entries,
        'pre_state_first_diff_hand': pre_first,
        'first_diff': first,
        'engine_errors': c['engine_errors'] + v['engine_errors'],
        'control_errors': c['errors'], 'v7_errors': v['errors'],
        'tier_stats': v['tier_stats'],
    }
    print('V7_CF_JSON=' + json.dumps(out, separators=(',', ':'), sort_keys=True))
    return 0 if out['engine_errors'] == 0 else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--entries', type=int, default=100)
    ap.add_argument('--arm', choices=['control', 'v7'])
    ap.add_argument('--inner', action='store_true')
    a = ap.parse_args()
    if a.inner:
        if not a.arm:
            raise SystemExit('--inner requires --arm')
        print('INNER_JSON=' + json.dumps(_inner(a.seed, a.arm, a.entries),
                                         separators=(',', ':'), sort_keys=True))
        return 0
    return _outer(a.seed, a.entries)


if __name__ == '__main__':
    raise SystemExit(main())
