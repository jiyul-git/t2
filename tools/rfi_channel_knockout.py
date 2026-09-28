#!/usr/bin/env python3
"""RFI attribution Phase 5 — 소비 채널별 녹아웃. 읽기 전용.

ca418d2 는 gto 데이터 표 네 개만 바꿨고, 그 표를 읽는 것은 gto.rfi 하나다.
gto.rfi 는 세 **채널**로 흘러간다 (tools/rfi_call_census.py 전수):

  OPEN    persona.py:398  open_pct 의 자기 오픈 폭
          persona.py:409  avg_rfi (포지션 평탄화 항)
  DEFEND  preflop.py:530  gto.defend_pct  = DEF_A + DEF_B * rfi(opener)
          preflop.py:531  gto.threebet_pct (같은 구조)
  OBS     session.py:1467 book.observe_preflop(rfi_exp) → reads rfi_rel → open_gap

gto.rfi 를 감싸 **호출 지점에 따라** 새 표/옛 표를 고른다. arm 마다 새 표를
쓰는 채널 집합이 다르다.

  ALL_OLD  아무 채널도 새 표를 안 씀 → e17be45 지문과 **같아야** 한다 (대조)
  ALL_NEW  전 채널 새 표            → ca418d2 지문과 **같아야** 한다 (대조)
  OPEN / DEFEND / OBS  그 채널만 새 표

두 대조가 성립해야 채널 arm 을 믿는다. 각 arm 은 **별도 프로세스**
(persona._TILT_VIEW_CACHE 대회 간 오염 때문).

production 무수정.
"""
import argparse
import collections
import hashlib
import json
import os
import sys

TABLES = ('RFI_BY_BEHIND', '_DEPTH_EARLY', '_DEPTH_LATE', 'ANTE_MULT')
CHANNELS = {
    'OPEN': ('persona.py:398', 'persona.py:409'),
    'DEFEND': ('preflop.py:530', 'preflop.py:531'),
    'OBS': ('session.py:1467',),
}
ARMS = {
    'ALL_OLD': (),
    'ALL_NEW': ('OPEN', 'DEFEND', 'OBS'),
    'OPEN': ('OPEN',),
    'DEFEND': ('DEFEND',),
    'OBS': ('OBS',),
}


def run(repo, arm, seeds, hands):
    if repo not in sys.path:
        sys.path.insert(0, repo)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rfi_decision_cf as M
    import gto as G
    import tourney as T
    old = M.old_tables(repo)
    cur = {t: getattr(G, t) for t in TABLES}
    use_new = set()
    for ch in ARMS[arm]:
        use_new.update(CHANNELS[ch])
    orig = G.rfi
    seen = collections.Counter()

    def site():
        f = sys._getframe(2)
        for _ in range(6):
            if f is None:
                break
            fn = os.path.basename(f.f_code.co_filename)
            if fn in ('persona.py', 'preflop.py', 'session.py'):
                return '%s:%d' % (fn, f.f_lineno)
            f = f.f_back
        return 'other'

    def wrap(pos, seats=8, bb=100.0, ante=True, band=None):
        s = site()
        seen[s] += 1
        if s in use_new:
            return orig(pos, seats, bb, ante, band)
        for t in TABLES:
            setattr(G, t, old[t])
        try:
            return orig(pos, seats, bb, ante, band)
        finally:
            for t in TABLES:
                setattr(G, t, cur[t])

    G.rfi = wrap
    per_seed, stats = {}, collections.Counter()
    for sd in seeds:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=sd, hands_per_level=200)
        rows = ['q=%.3f|a=%.2f' % (t.field_q, t.aggr_bias)]
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
            sn = set()
            for (stt, x, a, _amt) in log:
                if stt != 'preflop' or x == t.hero or x in sn:
                    continue
                sn.add(x)
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
        per_seed[str(sd)] = hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:16]
    G.rfi = orig
    unknown = {k: v for k, v in seen.items()
               if k not in sum(CHANNELS.values(), ())}
    return per_seed, dict(stats), dict(seen), unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--arm', required=True, choices=sorted(ARMS))
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    ps, st, seen, unknown = run(a.repo, a.arm, seeds, a.hands)
    n = max(1, st.get('n', 0)); h = max(1, st.get('hands', 0))
    print('@@RESULT@@' + json.dumps({
        'arm': a.arm, 'per_seed': ps, 'stats': st, 'seen': seen,
        'unknown_sites': unknown,
        'vpip': 100.0 * st.get('vpip', 0) / n,
        'pfr': 100.0 * st.get('pfr', 0) / n,
        'flop': 100.0 * st.get('flop', 0) / h}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
