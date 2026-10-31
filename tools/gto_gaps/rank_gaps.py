#!/usr/bin/env python3
"""gap_usage_sim.py 결과들 → 빈 자리 순위표.

  python3 tools/gto_gaps/rank_gaps.py <out_json> <out_md_table> run1.json run2.json ...

빈 자리(gap) = 봇 결정 중 GTO 표가 행동 전체를 정하지 못한 몫:
  partial(공격 빈도만 GTO, 콜/폴드는 예전 판단) + none(GTO 값 없음).
ICM 관문(BF > 1.05)에 막힌 결정은 표가 있어도 안 쓰이므로 빈 자리에서 뺀다(따로 보인다).
첫 진입은 관문(머니점프 값 포함)과 상관없이 '표에 값이 있는가'(tbl_no)만 빈 자리로 센다
— 관문 문제(precision_prep 2.3절)는 표를 채우는 일이 아니다.
"""
import json
import sys
from collections import Counter, defaultdict

SIT_KO = {
    'first_in': '첫 진입',
    'limp_sb_vs_bb': 'SB 림프 받은 BB',
    'limp_single_behind': '림퍼 1명 뒤(아이소/림프)',
    'limp_multi': '림퍼 여럿 뒤',
    'vs_jam': '단독 올인 받음',
    'vs_jam_multi': '올인 + 콜러',
    'vs_3bjam': '오픈 후 3벳 올인 받음',
    'vs_3bjam_multi': '3벳 올인 + 콜러',
    'vs_open': '단독 오픈 받음',
    'vs_open_with_callers': '오픈 + 콜러 있음(스퀴즈/오버콜 자리)',
    'vs_iso_after_limp': '림프 뒤 레이즈 받음(아직 행동 안 함)',
    'limper_vs_raise': '내가 림프 → 레이즈 받음',
    'vs_3bet': '3벳 받은 오프너',
    'vs_3bet_multi': '3벳 받음 + 콜러',
    'cold_vs_3bet': '콜드 3벳 받음(오픈+3벳 앞에)',
    'vs_4bet': '4벳 받은 3벳터',
    'vs_4bet_multi': '4벳 받음 + 콜러',
    'cold_vs_4bet': '콜드 4벳 받음',
    'vs_5bet_plus': '5벳 이상',
}


def main():
    out_json, out_md = sys.argv[1], sys.argv[2]
    runs = [json.load(open(p)) for p in sys.argv[3:]]
    hands = sum(r['hands'] for r in runs)
    agg = defaultdict(Counter)
    sizes = defaultdict(Counter)
    for r in runs:
        for k, v in r['rows'].items():
            sit, bk, pk, sz = k.split('|')
            g = (sit, bk, pk)
            for a, b in v.items():
                agg[g][a] += b
            if sz != '-':
                sizes[g][sz] += v['n']
    rows = []
    tot = Counter()
    noante = Counter()
    for g, v in agg.items():
        sit = g[0]
        n = v['n']
        icm = v.get('icm', 0.0)
        # 노안테 테이블·5인 이하 테이블은 gto_pf 가 통째로 안 다룬다(covered/pos9) — 표 하나를 채우는 일이
        # 아니라 다른 트리(노안테, 짧은 테이블)라 따로 센다. 두 조건의 결정은 모두 none 이다.
        out_scope = min(n, v.get('no_ante', 0.0) + v.get('seats_le5', 0.0))
        tot['no_ante'] += v.get('no_ante', 0.0)
        tot['seats_le5'] += v.get('seats_le5', 0.0)
        noante[(sit, g[1])] += v.get('no_ante', 0.0)
        if sit == 'first_in':
            # tbl_no 에는 노안테·짧은 테이블 몫이 들어 있다 — 빼고 남은 것이 '표가 없는 자리'
            gap = max(0.0, v.get('tbl_no', 0.0) - out_scope)
            gate = v.get('tbl_yes', 0.0) - v.get('full', 0.0)
        else:
            gap = max(0.0, v.get('partial', 0.0) + v.get('none', 0.0) - icm - out_scope)
            gate = icm
        kind = ('partial' if v.get('partial', 0) > v.get('none', 0) - icm else 'none')
        tot['n'] += n
        tot['full'] += v.get('full', 0.0)
        tot['gap'] += gap
        tot['gate'] += gate
        rows.append({
            'situation': sit, 'situation_ko': SIT_KO.get(sit, sit), 'bucket': g[1], 'pair': g[2],
            'decisions': round(n, 2), 'gap': round(gap, 2), 'per_1000_hands': round(1000 * gap / hands, 2),
            'gto_full': round(v.get('full', 0.0), 2), 'gto_partial': round(v.get('partial', 0.0), 2),
            'pass_share_of_partial': (round(v.get('pass_w', 0) / v['partial'], 3) if v.get('partial') else None),
            'gated': round(gate, 2), 'old_fold_share': round(v.get('fold', 0.0) / n, 3) if n else None,
            'kind': kind,
            'sizes': {s: round(x, 1) for s, x in sizes[g].most_common(4)},
        })
    rows.sort(key=lambda r: -r['gap'])
    by_sit = Counter()
    for r in rows:
        by_sit[r['situation']] += r['gap']
    res = {'hands': hands, 'runs': [{k: r[k] for k in ('fmt', 'day', 'hands', 'finished')} for r in runs],
           'totals': {k: round(v, 1) for k, v in tot.items()},
           'gap_by_situation': {k: round(v, 1) for k, v in by_sit.most_common()},
           'no_ante_by_situation_bucket': {'%s|%s' % k: round(v, 1) for k, v in noante.most_common() if v > 0},
           'rows': rows}
    json.dump(res, open(out_json, 'w'), indent=1, ensure_ascii=False)
    with open(out_md, 'w') as f:
        f.write('| # | 상황 | 스택 | 자리(공격>나) | 1000핸드당 빈 결정 | 빈 결정 | 그중 공격만 GTO | 예전 판단 폴드 몫 | 크기(bb) |\n')
        f.write('|---|---|---|---|---|---|---|---|---|\n')
        for i, r in enumerate(rows[:60], 1):
            f.write('| %d | %s | %s | %s | %.1f | %.0f | %.0f | %s | %s |\n' % (
                i, r['situation_ko'], r['bucket'], r['pair'], r['per_1000_hands'], r['gap'], r['gto_partial'],
                '%.0f%%' % (100 * r['old_fold_share']) if r['old_fold_share'] is not None else '-',
                ', '.join('%s:%d' % (s, x) for s, x in r['sizes'].items()) or '-'))
    print(json.dumps({k: res[k] for k in ('hands', 'totals', 'gap_by_situation', 'no_ante_by_situation_bucket')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
