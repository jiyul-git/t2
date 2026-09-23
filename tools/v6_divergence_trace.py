#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HIERARCHICAL_READ_V6 divergence 추적. 읽기 전용 — production 무수정.

tools/hierarchical_read_v6_cf.py 와 같은 harness(entries 100, 30핸드, hero fold)
를 쓰되 다음을 더 본다.

1. 채널 귀속 — V6 출력에서 freq/line/size 키 묶음을 하나씩 control 값으로
   되돌린 hybrid arm. 최초 divergence 가 사라지는 묶음이 원인 채널이다.
2. 층 귀속 — V6 가 돌려주는 layer_sources 로 coarse/trait/detail 단일층 arm 을
   만든다. 보간 없이 그 층만 쓴다.
3. 연쇄 판정 — 핸드마다 **읽기 이전의** 사전 상태(스택·버튼·레벨) 서명을 남긴다.
   divergence 가 시작된 뒤 사전 상태가 이미 갈라져 있으면 그 뒤 차이는
   새 판단이 아니라 연쇄다.
4. probe — 지정한 (hand, log_len) 에서 control/V6 출력과 층별 기여를 덤프한다.

read_opponent / hierarchical_read_v6 / read_resolution / hierarchical_belief_v3 는
전부 RNG 를 쓰지 않는 순수 함수다. 그래서 arm 사이 차이는 반환값으로만 전파된다.
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

FREQ_KEYS = ('fold_gap', 'fold_gap_flop', 'fold_gap_turn', 'fold_gap_river',
             'open_gap', 'limp_gap', 'tb_gap', 'f2tb_gap', 'fb_gap',
             'f2fb_gap', 'passive')
LINE_KEYS = ('barrel_gap', 'tb_polar', 'bluff_gap')
SIZE_KEYS = ('size_gap', 'size_info', 'size_big', 'size_river')
WSEE_KEYS = ('w', 'see_freq', 'see_line', 'see_size')

ARMS = ('control', 'v6', 'v6_freq_ctl', 'v6_line_ctl', 'v6_size_ctl',
        'v6_wsee_ctl', 'v6_coarse', 'v6_trait', 'v6_detail',
        'v6_only_freq', 'v6_only_line', 'v6_only_size',
        'v6_freq_coarse', 'v6_freq_trait', 'v6_freq_detail',
        'v6_size_coarse', 'v6_size_trait', 'v6_size_detail')

GROUPS = {'freq': FREQ_KEYS, 'line': LINE_KEYS, 'size': SIZE_KEYS,
          'wsee': WSEE_KEYS}


def _clip(x, lo, hi):
    return max(float(lo), min(float(hi), float(x)))


def _v6_final_clip(out):
    """hierarchical_read_v6 끝의 범위 보존을 그대로 적용한다."""
    out['fold_gap'] = _clip(out['fold_gap'], -0.5, 0.5)
    for k in ('fold_gap_flop', 'fold_gap_turn', 'fold_gap_river',
              'f2tb_gap', 'f2fb_gap'):
        out[k] = _clip(out[k], -0.5, 0.5)
    out['open_gap'] = _clip(out['open_gap'], -1.0, 2.0)
    out['limp_gap'] = _clip(out['limp_gap'], -0.5, 1.5)
    for k in ('barrel_gap', 'bluff_gap', 'passive', 'size_gap'):
        out[k] = _clip(out[k], -1.0, 1.0)
    out['tb_gap'] = _clip(out['tb_gap'], -2.0, 2.0)
    out['fb_gap'] = _clip(out['fb_gap'], -3.0, 3.0)
    for k in ('tb_polar', 'size_info', 'size_big'):
        out[k] = _clip(out[k], 0.0, 1.0)
    out['size_river'] = max(0.0, float(out['size_river']))
    return out


def _single_layer(v6out, layer):
    ls = v6out.get('layer_sources') or {}
    src = ls.get(layer) or {}
    if not src:
        return dict(v6out)
    out = dict(v6out)
    for k in FREQ_KEYS + LINE_KEYS + SIZE_KEYS:
        if k in src:
            out[k] = float(src[k])
    return _v6_final_clip(out)


def _state_sig(t):
    stacks = tuple(sorted((int(s), int(t.stacks[s])) for s in t.seats))
    return hashlib.sha256(
        json.dumps([stacks, int(getattr(t, 'button', -1)),
                    int(getattr(t, 'level', -1))],
                   sort_keys=True).encode()).hexdigest()[:12]


def _inner(seed, arm, probe):
    orig = PS.read_opponent
    ctx = {'hand': -1, 't': None}
    probes = []

    def _observer_seat(prof):
        run = getattr(ctx['t'], 'run', None)
        h = getattr(run, 'h', None)
        profs = getattr(h, 'prof', None) or {}
        hits = [k for k, v in profs.items() if v is prof]
        if not hits:
            # tourney 는 같은 dict 객체를 넘기지 않는다. 내용 동일로 찾는다.
            try:
                hits = [k for k, v in profs.items() if v == prof]
            except Exception:
                hits = []
        return hits[0] if len(hits) == 1 else (hits or None)

    def _loglen():
        run = getattr(ctx['t'], 'run', None)
        return len(getattr(run, 'full_log', []) or []) if run else -1

    def _record(prof, est, c_out, v_out):
        if not probe:
            return
        if ctx['hand'] != probe[0]:
            return
        # probe_entry < 0 이면 그 핸드의 모든 read 호출을 덤프한다.
        if probe[1] >= 0 and _loglen() != probe[1]:
            return
        if len(probes) >= 400:
            return
        probes.append({
            'hand': ctx['hand'], 'log_len': _loglen(),
            'observer_seat': _observer_seat(prof),
            'control': {k: c_out.get(k) for k in
                        WSEE_KEYS + FREQ_KEYS + LINE_KEYS + SIZE_KEYS},
            'v6': {k: v_out.get(k) for k in
                   WSEE_KEYS + FREQ_KEYS + LINE_KEYS + SIZE_KEYS},
            'source_weights': v_out.get('source_weights'),
            'layer_sources': v_out.get('layer_sources'),
            'coarse_top': v_out.get('coarse_top'),
            'coarse_probs': v_out.get('coarse_probs'),
            'est_n': (est or {}).get('n'),
            'est_conf': (est or {}).get('confidence'),
        })

    def wrapped(prof, opp_est):
        c_out = orig(prof, opp_est)
        def _ret(o):
            outs_digest.update(json.dumps(
                [round(float(o.get(k, 0.0) or 0.0), 9)
                 for k in WSEE_KEYS + FREQ_KEYS + LINE_KEYS + SIZE_KEYS],
                separators=(',', ':')).encode())
            return o

        if arm == 'control':
            _record(prof, opp_est, c_out, c_out)
            return _ret(c_out)
        v_out = RD.hierarchical_read_v6(prof, opp_est)
        _record(prof, opp_est, c_out, v_out)
        if arm == 'v6':
            return _ret(v_out)
        if arm in ('v6_coarse', 'v6_trait', 'v6_detail'):
            return _ret(_single_layer(v_out, arm.split('_', 1)[1]))
        if arm.startswith('v6_only_'):
            # control 을 바탕으로 그 채널만 V6 로 — 충분성 검정.
            out = dict(c_out)
            for k in GROUPS[arm[len('v6_only_'):]]:
                out[k] = v_out.get(k, out.get(k))
            return _ret(out)
        if arm.startswith('v6_freq_') or arm.startswith('v6_size_'):
            grp, layer = arm[3:].split('_', 1)
            if layer in ('coarse', 'trait', 'detail'):
                # 그 채널만 단일층으로 — 층 귀속.
                src = (v_out.get('layer_sources') or {}).get(layer) or {}
                out = dict(v_out)
                for k in GROUPS[grp]:
                    if k in src:
                        out[k] = float(src[k])
                return _ret(_v6_final_clip(out))
        keys = {'v6_freq_ctl': FREQ_KEYS, 'v6_line_ctl': LINE_KEYS,
                'v6_size_ctl': SIZE_KEYS, 'v6_wsee_ctl': WSEE_KEYS}[arm]
        out = dict(v_out)
        for k in keys:
            out[k] = c_out.get(k, out.get(k))
        return _ret(out)

    PS.read_opponent = wrapped

    outs_digest = hashlib.sha256()
    hands, pre, errors = [], [], []
    try:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=seed, hands_per_level=200)
        ctx['t'] = t
        for hi in range(HANDS):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            ctx['hand'] = hi
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

    return {'seed': seed, 'arm': arm, 'hands': hands, 'pre': pre,
            'reads_digest': outs_digest.hexdigest()[:16],
            'engine_errors': len(errors), 'errors': errors, 'probes': probes}


def _spawn(seed, arm, probe):
    cmd = [sys.executable, os.path.abspath(__file__), '--inner',
           '--seed', str(seed), '--arm', arm]
    if probe:
        cmd += ['--probe-hand', str(probe[0]), '--probe-entry', str(probe[1])]
    cp = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True,
                        timeout=900)
    if cp.returncode != 0:
        raise RuntimeError('%s rc=%s %s' % (arm, cp.returncode, cp.stderr[-1200:]))
    line = next((x for x in cp.stdout.splitlines()
                 if x.startswith('INNER_JSON=')), None)
    if not line:
        raise RuntimeError('%s missing INNER_JSON' % arm)
    return json.loads(line.split('=', 1)[1])


def _first_diff(a, b):
    n = max(len(a['hands']), len(b['hands']))
    for i in range(n):
        x = a['hands'][i] if i < len(a['hands']) else []
        y = b['hands'][i] if i < len(b['hands']) else []
        if x != y:
            m = max(len(x), len(y))
            for j in range(m):
                xa = x[j] if j < len(x) else None
                xb = y[j] if j < len(y) else None
                if xa != xb:
                    return {'hand': i, 'entry': j, 'a': xa, 'b': xb}
    return None


def _counts(a, b):
    n = max(len(a['hands']), len(b['hands']))
    dh = de = 0
    for i in range(n):
        x = a['hands'][i] if i < len(a['hands']) else []
        y = b['hands'][i] if i < len(b['hands']) else []
        if x != y:
            dh += 1
            for j in range(max(len(x), len(y))):
                if (x[j] if j < len(x) else None) != (y[j] if j < len(y) else None):
                    de += 1
    return dh, de


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--arm')
    ap.add_argument('--inner', action='store_true')
    ap.add_argument('--probe-hand', type=int)
    ap.add_argument('--probe-entry', type=int)
    ap.add_argument('--arms', default=','.join(ARMS))
    ap.add_argument('--out')
    a = ap.parse_args()
    probe = ((a.probe_hand, a.probe_entry)
             if a.probe_hand is not None and a.probe_entry is not None else None)

    if a.inner:
        print('INNER_JSON=' + json.dumps(_inner(a.seed, a.arm, probe),
                                         separators=(',', ':'), sort_keys=True))
        return 0

    want = [x for x in a.arms.split(',') if x]
    runs = {}
    for arm in want:
        runs[arm] = _spawn(a.seed, arm, probe)

    ctl = runs['control']
    rep = {'seed': a.seed, 'probe': probe, 'arms': {}}
    print('%-14s %-18s %-18s %6s %6s  first_divergence_vs_control' %
          ('arm', 'hands_hash', 'reads_digest', 'dHand', 'dEntry'))
    for arm in want:
        r = runs[arm]
        h = hashlib.sha256(json.dumps(r['hands'], sort_keys=True).encode()).hexdigest()[:16]
        dh, de = _counts(ctl, r)
        fd = _first_diff(ctl, r)
        rep['arms'][arm] = {'hash': h, 'reads_digest': r['reads_digest'],
                            'diff_hands': dh, 'diff_entries': de,
                            'first_diff': fd, 'engine_errors': r['engine_errors'],
                            'pre': r['pre']}
        print('%-14s %-18s %-18s %6d %6d  %s'
              % (arm, h, r['reads_digest'], dh, de, json.dumps(fd) if fd else '-'))

    # 연쇄 판정 — 읽기 전 사전 상태가 언제부터 갈라지는가
    v6 = runs.get('v6')
    if v6:
        pc, pv = ctl['pre'], v6['pre']
        first_pre = next((i for i in range(min(len(pc), len(pv))) if pc[i] != pv[i]), None)
        rep['pre_state_first_diff_hand'] = first_pre
        print('\npre-hand state first differs at hand: %s '
              '(control %d hands, v6 %d hands)'
              % (first_pre, len(pc), len(pv)))

    if probe:
        rep['probes'] = {arm: runs[arm]['probes'] for arm in want if runs[arm]['probes']}
        print('probe calls captured: %s'
              % {arm: len(runs[arm]['probes']) for arm in want})

    if a.out:
        json.dump(rep, open(a.out, 'w'), indent=1, sort_keys=True)
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
