#!/usr/bin/env python3
"""정밀 검사 순위 = 실제 사용 빈도 × 불안정 — 세 결과 파일을 합친다(계산기 실행 없음).

  python3 tools/gto_precision/rank_precision.py <inst.json> <du.json> <out.json> <usage.json>...

inst.json  : record_instability.py 결과(기록별 불안정 지표)
du.json    : collect_step_du.py 결과(단계별 D/U, 없는 기록은 null)
usage.json : spot_usage_sim.py 결과(대회별), 여러 개

점수
  use_per_1k = 모든 대회 합계 가중 사용 수 / 합계 핸드 × 1000 (봇 결정에서 그 기록 값을 실제로 쓴 횟수)
  risk(루프 기록) = 0.05(바닥: 24보드 quick, 검증 안 됨)
                  + unstable_share(뿌리 노드에서 단계 사이 10%p 넘게 움직인 콤보 몫)
                  + 0.05 × min(4, max(0, last_D/U − 1))(마지막 단계에서도 끝점 값이 허용폭 밖으로 움직임; 자료 없으면 0)
  risk(부모 트리 pf·s) = 0.05(솔버 gap ≤ 0.01bb 로 작음). 대신 플랍 팟 간이 모델 편향은 기록에서 잴 수 없다 → 따로 표시.
  impact = use_per_1k × risk
EV 손실(ev_loss_max_bb)은 순위에 넣지 않고 같이 보인다(단계 사이 평균이 잃는 크기; 값이 크면 '흔들리는 게 큰 패'라는 뜻).
"""
import json
import sys
from collections import Counter


def main():
    inst = json.load(open(sys.argv[1]))
    du = json.load(open(sys.argv[2]))
    out = sys.argv[3]
    use, blocked, hands, runs = Counter(), Counter(), 0, []
    for p in sys.argv[4:]:
        u = json.load(open(p))
        hands += u['hands']
        runs.append({'fmt': u['fmt'], 'day': u['day'], 'hands': u['hands'], 'finished': u['finished'],
                     'tries': u['tries'], 'hits': u['hits'], 'first_in_blocked': u.get('first_in_blocked')})
        use.update(u['use'])
        blocked.update(u.get('first_in_blocked_use') or {})
    rows = []
    for rid, v in inst.items():
        upk = 1000.0 * use.get(rid, 0.0) / max(1, hands)
        d = du.get(rid) or {}
        last_r = d.get('last_max_r')
        if v['kind'] == 'loop':
            r = v['root']
            risk = 0.05 + r['unstable_share'] + 0.05 * min(4.0, max(0.0, (last_r or 1.0) - 1.0))
            row = {'id': rid, 'kind': 'loop', 'use_per_1k': round(upk, 3), 'risk': round(risk, 3),
                   'impact': round(upk * risk, 4), 'converged': v['converged'], 'method': v['method'],
                   'stopped_at_step_cap': v['stopped_at_step_cap'], 'unstable_share': r['unstable_share'],
                   'ev_loss_max_bb': r['ev_loss_max_bb'], 'near_mixed_share': r['near_mixed_share'],
                   'gap_w_bb': r['gap_w_bb'], 'du_by_step': d.get('max_r_by_step'), 'last_D_over_U': last_r,
                   'du_min_U': (d.get('steps') or [{}])[-1].get('min_U') if d else None,
                   'root_actor': r['actor'], 'root_mix': r['mix']}
        else:
            risk = 0.05
            row = {'id': rid, 'kind': 'parent', 'use_per_1k': round(upk, 3), 'risk': risk,
                   'impact': round(upk * risk, 4), 'converged': True, 'method': v['method'],
                   'gap_total_exact_bb': v['gap_total_exact_bb'],
                   'first_in_blocked_per_1k': round(1000.0 * blocked.get(rid, 0.0) / max(1, hands), 3),
                   'note': 'static flop model bias not measurable from the record; precision = loop-corrected subgames'}
        rows.append(row)
    rows.sort(key=lambda x: -x['impact'])
    for i, r in enumerate(rows, 1):
        r['rank'] = i
    loop = [r for r in rows if r['kind'] == 'loop']
    for i, r in enumerate(loop, 1):
        r['rank_loop'] = i
    json.dump({'hands': hands, 'runs': runs, 'records': rows}, open(out, 'w'), indent=1, ensure_ascii=False)
    print('hands', hands)
    for r in rows[:30]:
        print(r['rank'], r['id'], r['use_per_1k'], r['risk'], r['impact'])


if __name__ == '__main__':
    main()
