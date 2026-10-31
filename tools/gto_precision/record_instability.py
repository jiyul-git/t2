#!/usr/bin/env python3
"""GTO 기록별 불안정·불확실 지표 — 기록 파일만 읽는다(계산기 실행 없음).

  python3 tools/gto_precision/record_instability.py <기록폴더> <out_json>

spot_quick_v1(루프 기록): 연결에 쓰는 뿌리 노드(첫 '3-bet response', off_path 아님)와,
  도착 콤보로 가중한 모든 on-path 노드에서
  - unstable_share   : 단계 사이 클래스 빈도가 10%p 넘게 움직인 콤보 몫(unstable_combos / reach_combos)
  - ev_loss_max_bb   : 평균 전략이 각 단계 전략 대비 잃는 EV 의 최댓값(ev_loss_of_mean_vs_each_step_bb)
  - gap_w_bb         : 클래스별 gap_bb(최선 행동과 섞은 행동의 EV 차)의 콤보 가중 평균 — 무차별에 가까운 정도
  - near_mixed_share : 빈도 0.2~0.8 로 섞인 콤보 몫(작은 변화에 크게 흔들릴 수 있는 몫)
  - converged / stopped_at_step_cap / method / steps
pf·s 부모 트리: 솔버 정확도(gap_total_exact_bb, G2_gap_max_bb) — 루프가 없으므로 단계 불안정은 없음.
  대신 플랍 팟을 간이 모델로 매긴 '모델 편향'이 불확실성의 주원인(점수에 따로 표시).
단계별 원자료(걸음마다의 전략)는 기록에 없어 '걸음 사이 최대 클래스 변화'는 >10%p 표시만 쓸 수 있다.
"""
import glob
import json
import os
import sys


def root_node(rec):
    for n in rec['nodes']:
        if n.get('scope') == '3-bet response' and not n.get('off_path'):
            return n
    return rec['nodes'][0]


def node_stats(n):
    hs = n.get('hands') or {}
    tot = sum(h['combos'] for h in hs.values()) or 1e-9
    gap = sum(h['combos'] * (h.get('gap_bb') or 0.0) for h in hs.values()) / tot
    mixed = sum(h['combos'] for h in hs.values() if 0.2 <= max(h['freq'].values()) <= 0.8) / tot
    unst_cls = sum(h['combos'] for h in hs.values() if h.get('unstable_across_steps')) / tot
    reach = float(n.get('reach_combos') or tot)
    return {'reach_combos': round(reach, 1),
            'unstable_share': round(float(n.get('unstable_combos') or 0.0) / max(1e-9, reach), 4),
            'unstable_share_cls': round(unst_cls, 4),
            'ev_loss_max_bb': round(max(n.get('ev_loss_of_mean_vs_each_step_bb') or [0.0]), 4),
            'gap_w_bb': round(gap, 4), 'near_mixed_share': round(mixed, 4)}


def quick(rec):
    r = root_node(rec)
    rs = node_stats(r)
    on = [n for n in rec['nodes'] if n.get('scope') and not n.get('off_path') and n.get('hands')]
    w = sum(float(n.get('reach_combos') or 0) for n in on) or 1e-9
    allu = sum(float(n.get('unstable_combos') or 0) for n in on) / w
    return {'kind': 'loop', 'method': rec.get('method'), 'converged': bool(rec.get('loop_converged')),
            'stopped_at_step_cap': bool(rec.get('stopped_at_step_cap')), 'steps': rec.get('steps'),
            'final_step': rec.get('final_step'), 'solve_s': rec.get('solve_s'),
            'flops_accepted_above_target': rec.get('flops_accepted_above_target'),
            'root': dict(rs, actor=r.get('actor'), actions=r.get('actions'), mix=r.get('mix')),
            'all_on_path_unstable_share': round(allu, 4), 'n_on_path_nodes': len(on),
            'max_node_ev_loss_bb': round(max([max(n.get('ev_loss_of_mean_vs_each_step_bb') or [0]) for n in on] or [0]), 4)}


def parent(rec):
    return {'kind': 'parent', 'method': 'full_tree_solve', 'converged': True, 'stopped_at_step_cap': False,
            'gap_total_exact_bb': rec.get('gap_total_exact_bb'), 'G2_gap_max_bb': rec.get('G2_gap_max_bb'),
            'iterations': rec.get('iterations'), 'stack_bb': rec.get('stack_bb'),
            'model_bias_note': 'flop pots valued by the simple static model (no loop correction)'}


def main():
    src, out = sys.argv[1], sys.argv[2]
    res = {}
    for f in sorted(glob.glob(os.path.join(src, '*.json'))):
        rec = json.load(open(f))
        if rec.get('id', '').endswith('_dcfr_stop'):
            continue
        res[rec['id']] = quick(rec) if rec.get('schema') == 'spot_quick_v1' else parent(rec)
    json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
    print(len(res), 'records')


if __name__ == '__main__':
    main()
