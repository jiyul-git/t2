#!/usr/bin/env python3
"""전체 프리플랍 트리 덤프 → 끝점(터미널)별 도달 확률 (계획용, 읽기 전용).

  python3 tools/gto_fulltree/terminal_mass.py <dump.jsonl.gz> <out.json>

덤프(t2_tree_dump, reach >= 1e-6 인 행동 노드)의 각 행동 노드에서 행동별 전체 확률
  p(a) = Σ_c actor_reach[c]·σ[a][c] / Σ_c actor_reach[c]
를 구하고, 자식이 덤프에 없으면 끝점(또는 도달 1e-6 미만 노드 — 무시할 크기)으로 본다.
끝점 = 폴드 승 / 올인 쇼다운(행동할 수 있는 사람이 1명 이하) / 플랍(칩이 남은 사람 2명 이상).
대칭 스택이라 올인 뒤 콜한 사람도 올인으로 본다. 도달 확률 = 덤프 reach_prob × p(a) (모든 패를 합친 '이 줄이 나올 확률').
"""
import gzip
import json
import sys
from collections import Counter

P = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def main():
    dump, out = sys.argv[1], sys.argv[2]
    nodes = {}
    for line in gzip.open(dump, 'rt'):
        d = json.loads(line)
        nodes[tuple(d['line'])] = d
    rows = []
    mass = Counter()
    for line, d in nodes.items():
        ar = d['actor_reach']
        s = sum(ar)
        if s <= 0:
            continue
        for ai, a in enumerate(d['actions']):
            ch = line + (d['actor'] + ':' + a,)
            if ch in nodes:
                continue
            w = d['reach_prob'] * sum(x * y for x, y in zip(ar, d['sigma'][ai])) / s
            if w <= 0:
                continue
            folded = {x.split(':')[0] for x in ch if x.endswith(':Fold')}
            live = [q for q in P if q not in folded]
            if len(live) == 1:
                mass['fold_win'] += w
                continue
            allin, seen = set(), False
            for x in ch:
                who = x.split(':')[0]
                if 'All-in' in x:
                    seen = True
                    allin.add(who)
                elif seen and ':Call' in x:
                    allin.add(who)
            flop = len(set(live) - allin) >= 2
            kind = 'flop' if flop else 'allin_showdown'
            mass['%s_%d' % (kind, len(live))] += w
            if flop:
                raises = sum(1 for x in ch if any(k in x for k in ('Raise', '3-bet', '4-bet', 'All-in')))
                rows.append({'reach': w, 'players': len(live), 'live': live, 'raises': raises,
                             'line': [x for x in ch if not x.endswith(':Fold')], 'full_line': list(ch)})
    rows.sort(key=lambda r: -r['reach'])
    hu = [r for r in rows if r['players'] == 2]
    flop_mass = sum(r['reach'] for r in rows)
    hu_mass = sum(r['reach'] for r in hu)
    summ = {
        'mass': {k: round(v, 6) for k, v in sorted(mass.items())},
        'flop_mass': round(flop_mass, 6), 'hu_flop_mass': round(hu_mass, 6),
        'hu_terminals_reached': len(hu),
        'hu_cover': {str(th): {'n': sum(1 for r in hu if r['reach'] >= th),
                               'share_of_hu_mass': round(sum(r['reach'] for r in hu if r['reach'] >= th) / hu_mass, 4)}
                     for th in (1e-3, 3e-4, 1e-4, 1e-5)},
        'multiway_terminals_reached': len(rows) - len(hu),
    }
    json.dump({'summary': summ, 'terminals': rows}, open(out, 'w'), indent=0)
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
