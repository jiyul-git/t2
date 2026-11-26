#!/usr/bin/env python3
"""연구실 자동 판정 — 코디네이터가 쓰는 판정 기준 전체를 함수 하나(judge)로 옮긴 것. 계산·기록만, 런타임 연결 없음.

입력은 전부 깃허브 조정 브랜치에 있는 파일(collect report.json, history.json, prepare.json, bundles.tsv, solve/exact_*.json ...)이다.
순수 함수라서 파일을 읽지 않는다(읽는 쪽은 autopilot.py). 기준 표는 docs/LAB_AUTOPILOT.md 2장.
기준 출처 표시: [P3]=GTO_FULLTREE_PILOT_60BB 3장, [P7]=7장, [U]=사용자 결정(날짜), [M]=GTO_FT_MATRIX_TERMINAL.md, [C]=collect/next_tables 코드.
'확인 필요'(NC) 항목은 추측으로 정하지 않고 status 에 반영하지 않거나 사람 확인 대기로 둔다.

  python3 judge.py <report.json> [--history history.json] [--prev prev_report.json] [--step k]   # 단독 시험
"""
import json
import statistics

DEFAULTS = {
    'flop_accept_pct_pot': 0.6,        # [U 11-08] 재시도 뒤에도 안 풀린 플랍은 0.6% pot 이하면 받아들이고 기록
    'flop_fail_action': 'static',      # [M] 0.6% 초과 → 그 끝점은 정적 유지(static_nodes.json). 'stop' 이면 멈추고 보고 [P7]
    'tree_gap_stop': 0.02,             # [U 11-10] 정확 gap < 0.02 (미만) 이면 트리 풀이 통과. 0.010 이하가 아니면 기록
    'tree_gap_doc': 0.010,             # [P7] 문서 기준(기록용)
    'new_endpoint_share_max': 0.01,    # [P7] 끝점 고르기 안정: 새로 기준을 넘는 끝점의 헤즈업 몫 합 <= 1%
    'root_rep_min_fraction': 0.95,     # [P3-③] 뿌리 복제: 전략 차이 <= 5%p 인 콤보 >= 95%
    'root_replication': 'required',    # NC-1: 'required' = ③ 결과 파일 없으면 '값 통과(뿌리 복제 확인 대기)'에서 멈춤, 'skip' = ③ 생략
    'alpha': 0.5, 'alpha_cycle': 0.25,  # [C] 감쇠, 진동 끝점
    'rep_factor': 2.0,                 # [P3-②] |V_A-V_B| <= 2*sqrt(U_A^2+U_B^2) (collect 가 pass_rep_value 로 이미 계산)
    'stall_steps': 3, 'stall_min_improve': 0.05,   # NC-2: 정체 경고 문턱(경고만, 자동 중단 안 함) — 문서에 숫자 없음, 임시값
    'max_steps': None,                 # 단계 상한 없음(사용자 11-12, 코디네이터 확인). 숫자를 넣으면 그 단계를 넘을 때 사람 확인 대기
    'step0_never_passes': True,        # [C] 0단계는 통과로 치지 않는다(최소 1회 갱신)
}


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _seats(report):
    for j, t in sorted(report['terminals'].items(), key=lambda kv: int(kv[0])):
        for pos, s in t['seats'].items():
            yield j, t, pos, s


def cycling(hist):
    """ft60.next_tables 와 같은 식: 기록 h(이번 단계 값 포함) 에서 D/U>1 이고 방향이 뒤집히면 진동."""
    return len(hist) >= 3 and hist[-1] > 1 and (hist[-3] - hist[-2]) * (hist[-2] - hist[-1]) < 0


def summarize(report):
    """collect report → 자리 수준 지표(판정·추세 공용)."""
    seats = [(j, t, pos, s) for j, t, pos, s in _seats(report)]
    r = {'seats': len(seats), 'terminals': len(report['terminals'])}
    r['pass_D_le_U'] = sum(1 for *_, s in seats if s['pass_D_le_U'])                    # 면제 포함(판정에 쓰는 값)
    r['pass_D_le_U_strict'] = sum(1 for *_, s in seats if s.get('pass_D_le_U_strict'))   # 면제 없이
    r['exempt'] = sum(1 for *_, s in seats if s.get('exempt'))
    dou = [s['D_over_U'] for *_, s in seats]
    r['dou_median'] = _med(dou)
    r['dou_max'] = max([x for x in dou if x is not None], default=None)
    for kind, flag in (('matrix', True), ('simple', False)):
        xs = [s['D_over_U'] for _, t, _, s in seats if bool(t.get('matrix')) == flag]
        r['dou_median_' + kind] = _med(xs)
        r['dou_max_' + kind] = max([x for x in xs if x is not None], default=None)
    r['rep_pass'] = sum(1 for *_, s in seats if s['pass_rep_value'])
    r['rep_pass_strict'] = sum(1 for *_, s in seats if s.get('pass_rep_value_strict'))
    dm = [v for t in report['terminals'].values() for v in (t.get('dM_vs_prev_step') or {}).values()]
    r['dM_vs_prev_median'] = _med(dm)
    r['dM_vs_prev_max'] = max(dm, default=None)
    dmu = [s.get('Dm_over_U') for *_, s in seats]
    r['Dm_over_U_median'] = _med(dmu)
    r['Dm_over_U_max'] = max([x for x in dmu if x is not None], default=None)
    sc = [t['sum_check']['max_abs_pair_sum_minus_pot_measured'] for t in report['terminals'].values() if t.get('sum_check')]
    r['sum_check_max'] = max(sc, default=None)
    fm = [s.get('matrix_fill_mass') for *_, s in seats if s.get('matrix_fill_mass') is not None]
    r['fill_mass_max'] = max(fm, default=None)
    return r


def new_endpoint_share(cur_rows, prev_rows, hu_mass):
    """끝점 고르기 안정 [P7]: 이번 단계에서 새로 들어온 끝점(노드)의 도달 합 / 헤즈업 도달 질량. 이전 단계가 없으면 None."""
    if prev_rows is None or not hu_mass:
        return None
    prev = {r['node'] for r in prev_rows}
    seen, tot = set(), 0.0
    for r in cur_rows:
        if r['node'] in prev or r['node'] in seen:
            continue
        seen.add(r['node'])
        tot += float(r['reach'])
    return tot / hu_mass


def judge(report, step=None, history=None, prev_report=None, prev_reports=None, flop=None, solve=None, endpoint=None, root=None, cfg=None):
    """판정 하나. 반환 dict: status, checks(표), metrics, static_nodes_add, cycling, alpha_plan, needs_confirmation, reasons.

    report      step k 의 collect report.json (complete 여부 포함)
    history     history.json (노드 → 단계별 max D/U). next_tables(k) 를 이미 돌렸으면 이번 값이 들어 있다(중복 없이 처리).
    prev_reports  앞 단계들의 report (오래된 것부터) — 정체 경고용
    flop        {'accepted_pct':0.6?, 'failures':[{'bundle','board','retry_pct_pot'(None=모름),'node'}]}  (failures 는 report 의 flop_failures_after_retry 를 풀어 준 것)
    solve       {'exact_gap': float|None, 'final_n': int|None}  그 단계 트리 풀이의 마지막 정확 gap
    endpoint    {'new_share': float|None}  끝점 고르기 안정 값(new_endpoint_share)
    root        None 또는 {'fraction': 0.97}  뿌리 복제(③) 결과 파일(data/ft<S>/step<k>/root_replication.json)
    """
    c = dict(DEFAULTS, **(cfg or {}))
    k = report['step'] if step is None else step
    history = history or {}
    checks, reasons, needs, warns = [], [], [], []

    def add(cid, name, rule, value, ok, src, note=''):
        checks.append({'id': cid, 'name': name, 'rule': rule, 'value': value, 'ok': ok, 'source': src, 'note': note})

    m = summarize(report)
    out = {'step': k, 'stall': False, 'metrics': m, 'checks': checks, 'reasons': reasons, 'needs_confirmation': needs, 'warnings': warns,
           'static_nodes_add': [], 'cycling': [], 'alpha_plan': {}}

    # C1 모두 왔나
    complete = bool(report.get('complete')) and not report.get('bundles_missing')
    add('C1', '보드 묶음 전부 도착', 'bundles_missing == 0 and complete', {'done': report.get('bundles_done'), 'missing': len(report.get('bundles_missing') or [])},
        complete, '[C] collect')
    if not complete:
        out['status'] = 'wait_boards'
        reasons.append('묶음이 아직 다 안 옴 — 기다림')
        return out

    # C2 플랍 실패(재시도 뒤에도 안 풀린 보드)
    fl = (flop or {}).get('failures')
    if fl is None:
        fl = [{'bundle': b, 'board': x, 'retry_pct_pot': None, 'node': None} for b, boards in (report.get('flop_failures_after_retry') or []) for x in boards]
    bad = [f for f in fl if f.get('retry_pct_pot') is None or f['retry_pct_pot'] > c['flop_accept_pct_pot']]
    accepted = [f for f in fl if f not in bad]
    add('C2', '플랍 실패(재시도 후) 처리', '재시도 결과 <= %.1f%% pot 이면 받아들이고 기록; 초과면 그 끝점 정적 유지(static_nodes)' % c['flop_accept_pct_pot'],
        {'failures': len(fl), 'accepted': len(accepted), 'over_limit_or_unknown': len(bad)}, not bad, '[U 11-08][M]')
    if bad:
        nodes = sorted({f['node'] for f in bad if f.get('node') is not None})
        if any(f.get('node') is None for f in bad):
            # 끝점 번호를 못 찾으면 자동 처리 불가 → 사람 확인
            out['status'] = 'stop_report'
            reasons.append('플랍 실패 끝점 번호 불명 — 멈추고 보고')
            return out
        if c['flop_fail_action'] == 'stop':
            out['status'] = 'stop_report'
            reasons.append('플랍 실패 0.6%% pot 초과 %d장 — 규칙 [P7]: 멈추고 보고' % len(bad))
            return out
        out['static_nodes_add'] = nodes
        reasons.append('플랍 실패 0.6%% pot 초과 → 끝점 %s 정적 유지(static_nodes.json 에 기록)' % nodes)

    # C3 트리 풀이 정확 gap
    sg = (solve or {}).get('exact_gap')
    add('C3', '트리 풀이 정확 gap', '< %.3f (사용자 11-10). > %.3f 이면 기록만' % (c['tree_gap_stop'], c['tree_gap_doc']),
        sg, None if sg is None else sg < c['tree_gap_stop'], '[U 11-10][P7]',
        '' if sg is None or sg <= c['tree_gap_doc'] else '문서 기준 0.010 초과(사용자 기준 통과) — 기록')

    # C4 D<=U
    add('C4', 'D ≤ U (A∪B 144보드, 전 자리)', '모든 자리 pass_D_le_U (상대 1콤보 미만 자리는 개정 8 로 면제)',
        '%d/%d 자리 (면제 없이 %d)' % (m['pass_D_le_U'], m['seats'], m['pass_D_le_U_strict']), m['pass_D_le_U'] == m['seats'], '[P3-①][C]')
    # C5 A·B 복제
    add('C5', 'A·B 복제(값)', '모든 자리 |V_A−V_B| ≤ %g·√(U_A²+U_B²)' % c['rep_factor'], '%d/%d 자리' % (m['rep_pass'], m['seats']),
        m['rep_pass'] == m['seats'], '[P3-②][C]')
    # C6 끝점 고르기 안정
    ns = (endpoint or {}).get('new_share')
    add('C6', '끝점 고르기 안정', '새로 기준을 넘은 끝점의 헤즈업 몫 합 ≤ %.0f%%' % (100 * c['new_endpoint_share_max']), ns,
        None if ns is None else ns <= c['new_endpoint_share_max'], '[P7]', '이전 단계가 없으면 알 수 없음(None)' if ns is None else '')
    # C7 뿌리 복제
    if root is not None:
        rok = root.get('fraction', 0) >= c['root_rep_min_fraction']
        add('C7', '뿌리 복제(A만·B만 전체 트리)', '전략 차이 ≤ 5%%p 인 콤보 ≥ %.0f%%' % (100 * c['root_rep_min_fraction']), root.get('fraction'), rok, '[P3-③]')
    elif c['root_replication'] == 'skip':
        add('C7', '뿌리 복제(A만·B만 전체 트리)', '생략(설정 root_replication=skip)', None, True, '[P3-③] NC-1', '생략은 코디네이터 확인 필요')
        needs.append('NC-1')
    else:
        add('C7', '뿌리 복제(A만·B만 전체 트리)', '전략 차이 ≤ 5%p 인 콤보 ≥ 95% — 연구실에 계산 도구 없음 → root_replication.json 이 올라오면 읽음',
            None, None, '[P3-③] NC-1', '확인 필요: 도구가 없음')
        needs.append('NC-1')

    # 진동·감쇠 계획(next_tables 와 같은 식) — 정보
    for j, t in report['terminals'].items():
        node = str(t['node'])
        h = list(history.get(node, []))
        cur = t['max_D_over_U']
        if not h or abs(h[-1] - cur) > 1e-12:
            h.append(cur)
        cyc = cycling(h)
        out['alpha_plan'][node] = c['alpha_cycle'] if cyc else c['alpha']
        if cyc:
            out['cycling'].append(int(node))
    add('C8', '진동 끝점 감쇠', '끝점 최대 D/U 가 3단계 연속 방향 반전하고 D/U>1 이면 α=%.2f, 아니면 %.2f (next_tables 가 적용)' % (c['alpha_cycle'], c['alpha']),
        {'cycling_nodes': len(out['cycling']), 'of': len(report['terminals'])}, None, '[C] next_tables', '정보')

    # 추세(정보) + 정체 경고
    prevs = list(prev_reports or ([prev_report] if prev_report else []))
    trend = [summarize(r) for r in prevs] + [m]
    out['trend'] = [{'step': (prevs[i]['step'] if i < len(prevs) else k), 'pass_D_le_U': x['pass_D_le_U'], 'seats': x['seats'], 'dou_median': x['dou_median'],
                     'dM_vs_prev_median': x['dM_vs_prev_median']} for i, x in enumerate(trend)]
    add('C9', '수렴 추세(기록)', 'D/U 중앙값·D≤U 자리 수·dM_vs_prev_step 단계별 기록. 숫자 문턱은 문서에 없음(NC-2) → 판정에 쓰지 않음',
        {'dou_median': m['dou_median'], 'dM_vs_prev_median': m['dM_vs_prev_median'], 'dM_vs_prev_max': m['dM_vs_prev_max']}, None, '[U 11-12] NC-2', '정보')
    needs.append('NC-2')
    n = c['stall_steps']
    meds = [x['dou_median'] for x in trend if x['dou_median'] is not None]
    if len(meds) > n and (meds[-n - 1] - meds[-1]) / meds[-n - 1] < c['stall_min_improve']:
        warns.append('정체 경고: 최근 %d단계 동안 D/U 중앙값이 %.0f%% 도 안 줄었음(%.2f → %.2f). 임시 문턱(NC-2), 자동 중단 안 함.' % (n, 100 * c['stall_min_improve'], meds[-n - 1], meds[-1]))
        out['stall'] = True
    sc = m['sum_check_max']
    add('C10', '합=팟 점검(기록)', '보드 M 칸 단위 합−팟 최대. 문턱은 문서에 없음 → 기록만', sc, None, '[M]', '정보')

    # C11 단계 상한
    over = bool(c['max_steps']) and k + 1 > c['max_steps']
    add('C11', '단계 상한', '없음(사용자 11-12 "단계 제한 없음", 코디네이터 확인). 설정 max_steps 가 있을 때만 적용', k + 1, not over, '[U 11-12]', '기본 상한 없음')

    # 결정
    values_ok = m['pass_D_le_U'] == m['seats'] and m['rep_pass'] == m['seats'] and not bad
    stable = ns is None or ns <= c['new_endpoint_share_max']
    if c['step0_never_passes'] and k == 0:
        out['status'] = 'continue'
        reasons.append('0단계는 통과로 치지 않는다(최소 1회 갱신)')
    elif values_ok and stable:
        r = next(x for x in checks if x['id'] == 'C7')
        if r['ok'] is True:
            out['status'] = 'converged'
            reasons.append('값 통과(①②) + 끝점 안정 + 뿌리 복제 → 완료')
        else:
            out['status'] = 'values_pass_pending_root'
            reasons.append('값 통과(①②) + 끝점 안정. 뿌리 복제(③)는 확인 필요(NC-1) → 이 스택은 멈추고 코디네이터 확인 대기')
    elif over:
        out['status'] = 'stop_report'
        reasons.append('단계 상한 %d 도달 — 사람 확인 대기' % c['max_steps'])
    else:
        out['status'] = 'continue'
        if not values_ok:
            reasons.append('미통과: D≤U %d/%d 자리, A·B 복제 %d/%d → 다음 표(next_tables)로 다음 단계' % (m['pass_D_le_U'], m['seats'], m['rep_pass'], m['seats']))
        else:
            reasons.append('값은 통과, 끝점 고르기 불안정(새 끝점 몫 %.2f%% > 1%%) → 다음 단계' % (100 * (ns or 0)))
    if over and out['status'] == 'continue':
        out['status'] = 'stop_report'
        reasons.append('단계 상한 %d 도달 — 사람 확인 대기' % c['max_steps'])
    return out


def render_table(v):
    """사람이 읽는 판정표(markdown)."""
    lines = ['| 번호 | 기준 | 규칙 | 값 | 결과 |', '|---|---|---|---|---|']
    for x in v['checks']:
        ok = {True: '통과', False: '미통과', None: '기록/확인 필요'}[x['ok']]
        lines.append('| %s | %s | %s | %s | %s |' % (x['id'], x['name'], x['rule'].replace('|', '\\|'), json.dumps(x['value'], ensure_ascii=False).replace('|', '\\|'), ok))
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('report')
    ap.add_argument('--history')
    ap.add_argument('--prev')
    ap.add_argument('--step', type=int)
    a = ap.parse_args()
    rep = json.load(open(a.report))
    v = judge(rep, step=a.step, history=json.load(open(a.history)) if a.history else None, prev_report=json.load(open(a.prev)) if a.prev else None)
    print(render_table(v))
    print(json.dumps({k: v[k] for k in ('status', 'reasons', 'static_nodes_add', 'cycling', 'warnings', 'needs_confirmation')}, ensure_ascii=False, indent=1))
