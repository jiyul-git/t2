#!/usr/bin/env python3
"""RFI attribution Phase 4 — gto.rfi 호출 전수와 경로별 폭 변화. 읽기 전용.

gto.rfi 는 네 곳에서 불린다(엔진, tools 제외):
  persona.open_pct:398        → preflop._open → open_decision / iso_decision
  persona.open_pct:409        → avg_rfi (포지션 평탄화 항)
  preflop._open:35            → ref (기준 정규화용, 항상 100bb/ante=True)
  session.py:1467             → book.observe_preflop(rfi_exp)  ← 관찰 채널

호출마다 새 폭과 **같은 인자의 옛 폭**을 같이 기록한다. 게임은 안 건드린다
(gto.rfi 는 순수 함수라 두 번 계산해도 부작용이 없다).

production 무수정.
"""
import argparse
import collections
import json
import os
import sys

TABLES = ('RFI_BY_BEHIND', '_DEPTH_EARLY', '_DEPTH_LATE', 'ANTE_MULT')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.repo not in sys.path:
        sys.path.insert(0, a.repo)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rfi_decision_cf as M
    import gto as G
    import tourney as T
    old = M.old_tables(a.repo)
    cur = {t: getattr(G, t) for t in TABLES}
    orig = G.rfi
    acc = collections.Counter()
    sums = collections.defaultdict(float)

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
        n = orig(pos, seats, bb, ante, band)
        for t in TABLES:
            setattr(G, t, old[t])
        try:
            o = orig(pos, seats, bb, ante, band)
        finally:
            for t in TABLES:
                setattr(G, t, cur[t])
        s = site()
        acc['n_' + s] += 1
        sums['new_' + s] += n
        sums['old_' + s] += o
        if o > 0:
            sums['rel_' + s] += (n / o - 1.0)
            if n > o:
                acc['wider_' + s] += 1
            elif n < o:
                acc['narrower_' + s] += 1
            else:
                acc['same_' + s] += 1
        acc['ante_%s' % bool(ante)] += 1
        return n

    G.rfi = wrap
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    for sd in seeds:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=sd, hands_per_level=200)
        for _ in range(a.hands):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1
            t.finish_hand()
        print('  seed %d 누적 호출 %d' % (sd, sum(v for k, v in acc.items()
                                                if k.startswith('n_'))), flush=True)
    G.rfi = orig
    sites = sorted({k[2:] for k in acc if k.startswith('n_')})
    print('\n## gto.rfi 호출 전수 — 경로별 폭 변화 (새 vs 옛, 같은 인자)')
    print('%-18s %7s %9s %9s %9s   %s'
          % ('호출 지점', '호출수', '새 평균', '옛 평균', '평균변화', '넓어짐/같음/좁아짐'))
    for s in sites:
        n = acc['n_' + s]
        print('%-18s %7d %9.4f %9.4f %+8.2f%%   %d / %d / %d'
              % (s, n, sums['new_' + s] / n, sums['old_' + s] / n,
                 100.0 * sums['rel_' + s] / n,
                 acc['wider_' + s], acc['same_' + s], acc['narrower_' + s]))
    print('\n  ante=True %d   ante=False %d'
          % (acc['ante_True'], acc['ante_False']))
    json.dump({'acc': dict(acc), 'sums': dict(sums)},
              open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\nwrote %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
