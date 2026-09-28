#!/usr/bin/env python3
"""RFI attribution Phase 1 — 커밋별 VPIP/PFR/flop 사다리. 읽기 전용.

`test` HEAD 는 calibration 커밋 **셋**을 포함한다.

    e17be45  (직전)
    ca418d2  gto.py   RFI_BY_BEHIND / _DEPTH_* / ANTE_MULT   ← 사용자가 묻는 것
    ce5c118  gto.py   수비 계수 8max ante 게이팅
    1a23123  preflop.py  MTT 수비 폭

regression 수치가 RFI 단독인지 셋 합인지 먼저 갈라야 한다.
각 리비전을 **별도 worktree + 별도 프로세스**에서 돌린다 —
persona._TILT_VIEW_CACHE 가 (pid, tilt) 키라 한 프로세스에서 대회를 여럿
돌리면 대회 간 오염이 생긴다. 시드별 격리 옵션도 둔다.

레시피는 tools/regress.py fingerprint() 와 동일하다:
  entries=100, start_stack=30000, hero_seat=7, hands_per_level=200,
  seeds 3000-3005, 30핸드, 히어로는 계속 fold.

production 무수정.
"""
import argparse
import collections
import hashlib
import json
import os
import sys

SEEDS = list(range(3000, 3006))
HANDS = 30


def run_seed(repo, sd, hands):
    if repo not in sys.path:
        sys.path.insert(0, repo)
    import tourney as T
    t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                     seed=sd, hands_per_level=200)
    rows = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
    stats = collections.Counter()
    for _ in range(hands):
        if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
            break
        st = t.next_hand()
        guard = 0
        while st and not st.get('done') and guard < 200:
            st = t.submit('fold')
            guard += 1
        log = getattr(t.run, 'full_log', []) or []
        rows.append(';'.join('%s:%s:%s:%s' % x for x in log))
        seen = set()
        for (stt, x, a, _amt) in log:
            if stt != 'preflop' or x == t.hero or x in seen:
                continue
            seen.add(x)
            stats['n'] += 1
            if a in ('bet', 'raise', 'allin'):
                stats['vpip'] += 1
                stats['pfr'] += 1
            elif a == 'call':
                stats['vpip'] += 1
        stats['hands'] += 1
        if any(s == 'flop' for (s, _, _, _) in log):
            stats['flop'] += 1
        t.finish_hand()
    return (hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16],
            dict(stats))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--seed', type=int, default=None,
                    help='주면 그 시드 하나만 (프로세스 격리용)')
    ap.add_argument('--hands', type=int, default=HANDS)
    a = ap.parse_args()
    out = {'per_seed': {}, 'stats': collections.Counter()}
    for sd in ([a.seed] if a.seed is not None else SEEDS):
        fp, st = run_seed(a.repo, sd, a.hands)
        out['per_seed'][sd] = fp
        out['stats'].update(st)
    s = out['stats']
    n = max(1, s.get('n', 0))
    h = max(1, s.get('hands', 0))
    print('@@RESULT@@' + json.dumps({
        'per_seed': out['per_seed'], 'stats': dict(s),
        'vpip': 100.0 * s.get('vpip', 0) / n,
        'pfr': 100.0 * s.get('pfr', 0) / n,
        'flop': 100.0 * s.get('flop', 0) / h}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
