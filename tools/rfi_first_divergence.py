#!/usr/bin/env python3
"""RFI attribution Phase 3 — 최초 divergence 추적. 읽기 전용.

두 리비전에서 같은 시드를 돌려 핸드별 full_log 를 덤프하고,
**처음으로 갈라지는 지점**을 찾는다. 그 지점이 open_decision 인지,
그리고 그 뒤로 몇 핸드가 연쇄로 갈라지는지 센다.

`--dump` 는 한 리비전의 로그를 JSON 으로 떨군다 (프로세스 격리용 —
persona._TILT_VIEW_CACHE 가 대회 간 오염을 만들므로 리비전마다 새 프로세스).
`--diff` 는 두 덤프를 비교한다.

production 무수정.
"""
import argparse
import json
import os
import sys


def dump(repo, seeds, hands, out):
    if repo not in sys.path:
        sys.path.insert(0, repo)
    import tourney as T
    res = {}
    for sd in seeds:
        t = T.Tournament(entries=100, start_stack=30000, hero_seat=7,
                         seed=sd, hands_per_level=200)
        hs = []
        for _ in range(hands):
            if sum(1 for s in t.seats if t.stacks[s] > 0) < 3:
                break
            st = t.next_hand()
            guard = 0
            while st and not st.get('done') and guard < 200:
                st = t.submit('fold')
                guard += 1
            log = [list(x) for x in (getattr(t.run, 'full_log', []) or [])]
            hs.append({'log': log,
                       'alive': sum(1 for s in t.seats if t.stacks[s] > 0),
                       'stacks': {str(s): t.stacks[s] for s in t.seats}})
            t.finish_hand()
        res[str(sd)] = hs
        print('  seed %d  %d핸드' % (sd, len(hs)), flush=True)
    json.dump(res, open(out, 'w', encoding='utf-8'))


def diff(a_path, b_path):
    A = json.load(open(a_path, encoding='utf-8'))
    B = json.load(open(b_path, encoding='utf-8'))
    print('%-6s %8s %10s %12s   %s'
          % ('seed', '핸드수', '최초갈림', '갈린핸드수', '최초 갈림 지점'))
    tot = collections_first = 0
    summary = {}
    for sd in sorted(A, key=int):
        ha, hb = A[sd], B[sd]
        n = min(len(ha), len(hb))
        first = None
        ndiff = 0
        detail = ''
        for i in range(n):
            if ha[i]['log'] != hb[i]['log']:
                ndiff += 1
                if first is None:
                    first = i
                    la, lb = ha[i]['log'], hb[i]['log']
                    for j in range(max(len(la), len(lb))):
                        x = la[j] if j < len(la) else None
                        y = lb[j] if j < len(lb) else None
                        if x != y:
                            detail = 'entry %d  구:%s  신:%s' % (j, x, y)
                            break
        if len(ha) != len(hb):
            detail += '  (핸드수 %d vs %d)' % (len(ha), len(hb))
        summary[sd] = {'hands': n, 'first': first, 'ndiff': ndiff,
                       'detail': detail}
        print('%-6s %8d %10s %12d   %s'
              % (sd, n, ('-' if first is None else first), ndiff, detail))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', action='store_true')
    ap.add_argument('--repo')
    ap.add_argument('--out')
    ap.add_argument('--diff', nargs=2)
    ap.add_argument('--seeds', default='3000-3005')
    ap.add_argument('--hands', type=int, default=30)
    a = ap.parse_args()
    lo, hi = (a.seeds.split('-') + [None])[:2]
    seeds = list(range(int(lo), int(hi) + 1)) if hi else [int(lo)]
    if a.dump:
        dump(a.repo, seeds, a.hands, a.out)
    elif a.diff:
        diff(a.diff[0], a.diff[1])
    else:
        print('--dump --repo R --out F  또는  --diff A B')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
