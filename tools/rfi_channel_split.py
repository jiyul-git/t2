#!/usr/bin/env python3
"""RFI attribution Phase 6 — **호출 스택** 기준 채널 녹아웃. 읽기 전용.

rfi_channel_knockout.py 는 gto.rfi 를 '직접 부른 줄'로 채널을 갈랐다.
그런데 persona.py:398/409 는 두 곳에서 온다 (seed 3000 전수):

  preflop.open_decision:298 / iso_decision  → preflop._open → open_pct   (결정)
  ranges.preflop_range:236                   → preflop._open → open_pct   (레인지 모델)
      ranges.py:228 `_base_open = pf._open` 가 import 시점에 바인딩한다.

preflop.py:530/531 (defend_thresholds) 도 두 곳에서 온다:

  preflop.defend_decision → defend_action_likelihoods → defend_thresholds (결정)
  ranges.preflop_range:249 → _def_thresholds → defend_thresholds          (레인지 모델)

그래서 채널을 **스택 위의 함수 이름**으로 다시 나눈다.

  OPEN_DEC   open_decision / iso_decision 아래 (preflop_range 없음)
  DEF_DEC    defend_decision 아래 (preflop_range 없음)
  PF_RANGE   preflop_range ← session._preflop_perceived_range (프리플랍 중 상대 레인지)
  POST_RANGE preflop_range ← 그 밖 (session._run 포스트플랍 my_r/orange,
             session._locked_postflop_range)
  OBS        session.py:1467 book.observe_preflop 의 rfi_exp

arm:
  ALL_OLD / ALL_NEW          대조. e17be45 / ca418d2 지문과 같아야 한다
  ONLY_<C>                   그 채널만 새 표
  DROP_<C>                   그 채널만 옛 표 (나머지 새 표)

각 arm 은 별도 프로세스 (persona._TILT_VIEW_CACHE 대회 간 오염).
분류되지 않은 호출은 'other' 로 세고 결과에 싣는다 — 0 이어야 한다.

production 무수정.
"""
import argparse
import collections
import hashlib
import json
import os
import sys

TABLES = ('RFI_BY_BEHIND', '_DEPTH_EARLY', '_DEPTH_LATE', 'ANTE_MULT')
CHS = ('OPEN_DEC', 'DEF_DEC', 'PF_RANGE', 'POST_RANGE', 'OBS')


def arms():
    out = {'ALL_OLD': (), 'ALL_NEW': CHS}
    for c in CHS:
        out['ONLY_' + c] = (c,)
        out['DROP_' + c] = tuple(x for x in CHS if x != c)
    return out


def classify():
    f = sys._getframe(2)
    names = []
    first_session = None
    while f is not None:
        fn = os.path.basename(f.f_code.co_filename)
        names.append((fn, f.f_code.co_name))
        if first_session is None and fn == 'session.py':
            first_session = (f.f_code.co_name, f.f_lineno)
        f = f.f_back
    fnames = [n for (_, n) in names]
    if 'preflop_range' in fnames:
        i = fnames.index('preflop_range')
        caller = fnames[i + 1] if i + 1 < len(fnames) else ''
        return 'PF_RANGE' if caller == '_preflop_perceived_range' else 'POST_RANGE'
    if 'defend_decision' in fnames:
        return 'DEF_DEC'
    if 'open_decision' in fnames or 'iso_decision' in fnames:
        return 'OPEN_DEC'
    if first_session and first_session[0] == '_run' and names[0][0] == 'session.py':
        return 'OBS'
    return 'other'


def run(repo, arm, seeds, hands):
    if repo not in sys.path:
        sys.path.insert(0, repo)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rfi_decision_cf as M
    import gto as G
    import tourney as T
    old = M.old_tables(repo)
    cur = {t: getattr(G, t) for t in TABLES}
    use_new = set(arms()[arm])
    orig = G.rfi
    seen = collections.Counter()

    def wrap(pos, seats=8, bb=100.0, ante=True, band=None):
        ch = classify()
        seen[ch] += 1
        if ch in use_new:
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
    return per_seed, dict(stats), dict(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--arm', required=True, choices=sorted(arms()))
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    ps, st, seen = run(a.repo, a.arm, seeds, a.hands)
    n = max(1, st.get('n', 0)); h = max(1, st.get('hands', 0))
    print('@@RESULT@@' + json.dumps({
        'arm': a.arm, 'per_seed': ps, 'stats': st, 'seen': seen,
        'vpip': 100.0 * st.get('vpip', 0) / n,
        'pfr': 100.0 * st.get('pfr', 0) / n,
        'flop': 100.0 * st.get('flop', 0) / h}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
