#!/usr/bin/env python3
"""Build CANONICAL_VERIFIER_MANIFEST.{json,md} from verifier scripts + run results.

inputs:
  --head  results JSON of tools/run_verifier_manifest.py --tier all on a pristine HEAD checkout
  --work  results JSON of the same run on the working tree
  --older optional: results JSON at an older baseline (e.g. 70008d9) to date historical failures
"""
import argparse, ast, glob, json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(DOC))

GATE23 = ('core_p7_cold_reraise core_p7_observation core_multiway_reads core_joint_nut '
          'core_sizing_ownership preflop_closure human_model_v3 human_model_v3_runtime '
          'human_model_v3_integration read_recency_v3 p2_limped_pot p3_first_open p4_vs_3bet '
          'p5_backaction p6_calloff f3_checkraise_response f4_facing_bet f6_caller_backaction '
          'f7_street_closure weighted_boundaries weighted_range_adapter '
          'multiway_range_preservation f7b_defend_likelihood').split()
SUITE40 = [x['name'] for x in json.load(open(os.path.join(DOC, 'evidence', 'verifiers_after.json')))]
SUITE40_BEFORE = {x['name']: ('TIMEOUT' if x['exit'] == 'TIMEOUT' else
                              'PASS' if x['exit'] == 0 else 'FAIL')
                  for x in json.load(open(os.path.join(DOC, 'evidence', 'verifiers_before.json')))}


# Verified separately: each run ALONE in a clean worktree (only tracked files) at
# the source head -> PASS.  They assert repo-root sidecar/archive invariants, so a
# parallel run (--jobs > 1) or a developer checkout with untracked *.jsonl
# archives makes them FAIL (stage 11: jobs=3 run FAIL, solo rc=0 for all three).
CLEAN_TREE_PASS = {'audit_order', 'state_namespace', 'trace_schema'}
NOTES = {
    'audit_order': 'run alone in a clean worktree: D3/D4 read repo-root *.jsonl archives',
    'state_namespace': 'run alone in a clean worktree: repo sidecar invariants (parallel runs contaminate)',
    'trace_schema': 'run alone in a clean worktree: repo archive invariants (parallel runs contaminate)',
    'stepothers_timing': 'CLI driver: requires --mode (not a standalone pass/fail verifier)',
    'tilt_divergence': 'CLI driver: requires a command argument',
    'tilt_isolation': 'CLI driver: requires --mode',
    'human_model_v2': '~18 min; needs --timeout > 900',
    'oop_semantics': '~19 min; needs --timeout > 900. stage 11: B1c/C3 stale test model fixed (old arm vs_aggr=None is an input change)',
    'f1_free_action': 'stage 11: guard moved to plan.blockbet_probability by B3 split (20e206f7); verifier updated',
    'forced_blind_allin_showdown': 'stale test double: fake Book lacks observe_cold_reraise',
    'reaudit_semantic_extraction': 'new in re-audit; compares against HEAD (or given base)',
    'human_model_v3_integration': '~6-10 min: TIMEOUT under the 40-suite 180 s limit, PASS under 900 s',
}


def subsystem(n):
    for pre, sub in (('core_', 'core plan/range'), ('p2_', 'preflop P-series'), ('p3_', 'preflop P-series'),
                     ('p4_', 'preflop P-series'), ('p5_', 'preflop P-series'), ('p6_', 'preflop P-series'),
                     ('preflop_', 'preflop'), ('f1_', 'postflop F-series'), ('f2_', 'postflop F-series'),
                     ('f3_', 'postflop F-series'), ('f4_', 'postflop F-series'), ('f5_', 'postflop F-series'),
                     ('f6_', 'postflop F-series'), ('f7_', 'postflop F-series'), ('f7b_', 'F7-B range/defend'),
                     ('weighted_', 'weighted range'), ('human_model', 'human model v2/v3'),
                     ('read_', 'reads/range_read'), ('range_read', 'reads/range_read'),
                     ('remaining_read', 'reads/range_read'), ('semantic_cleanup', 'semantic audit parity'),
                     ('defend_semantic', 'semantic audit parity'), ('reaudit', 'semantic audit parity'),
                     ('money_', 'money jump / ICM'), ('icm', 'money jump / ICM'),
                     ('telemetry', 'telemetry'), ('tournament_telemetry', 'telemetry'), ('trace_', 'telemetry'),
                     ('tilt_', 'tilt/emotion'), ('decay_', 'tilt/emotion'), ('calc_noise', 'human model v2/v3'),
                     ('prelogic', 'judgment/execution boundary'), ('replan', 'plan lifecycle'),
                     ('allin_', 'betting rules/pot'), ('effective_allin', 'betting rules/pot'),
                     ('uncalled', 'betting rules/pot'), ('settle_', 'runtime/parallel'),
                     ('forced_blind', 'betting rules/pot'), ('postflop_events', 'public action events'),
                     ('oop_', 'position semantics'), ('multiway_range', 'weighted range'),
                     ('tda_', 'tournament runtime'), ('button_', 'tournament runtime'), ('9max', 'tournament runtime'),
                     ('parallel_', 'runtime/parallel'), ('prefetch', 'runtime/parallel'), ('defer', 'runtime/parallel'),
                     ('stepothers', 'runtime/parallel'), ('state_namespace', 'runtime/parallel'),
                     ('ui_', 'UI'), ('audit_order', 'audit tooling')):
        if n.startswith(pre):
            return sub
    return 'other'


def doc1(path):
    try:
        d = ast.get_docstring(ast.parse(open(path, encoding='utf-8').read())) or ''
    except SyntaxError:
        d = ''
    return d.strip().split('\n')[0][:140]


def blob_sha(path):
    try:
        return subprocess.run(['git', 'hash-object', path], capture_output=True, text=True,
                              cwd=ROOT).stdout.strip()[:12]
    except Exception:
        return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--head', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--source-head', default=None, help='commit SHA the run was made on')
    ap.add_argument('--timeout', default=None, help='per-verifier timeout used by the run')
    a = ap.parse_args()
    head = {r['name']: r for r in json.load(open(a.head))['results']}
    work = {r['name']: r for r in json.load(open(a.work))['results']}
    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, 'tools', 'verify_*.py'))):
        n = os.path.basename(p)[len('verify_'):-3]
        h = head.get(n, {}).get('status', 'NEW')
        w = work.get(n, {}).get('status')
        if n in CLEAN_TREE_PASS:
            h, w = 'PASS', 'PASS'
        if w == 'PASS':
            hist = 'pass'
        elif h in ('FAIL', 'TIMEOUT') and w == h:
            hist = 'historical (same status on pristine HEAD)'
        elif h == 'NEW':
            hist = 'new verifier'
        else:
            hist = 'REGRESSION (differs from pristine HEAD)'
        tiers = []
        if n in GATE23:
            tiers.append('gate23')
        if n in SUITE40:
            tiers.append('suite40')
        if w == 'PASS' and (work.get(n, {}).get('seconds') or 0) <= 60:
            tiers.append('fast')
        rows.append({
            'name': n, 'file': 'tools/verify_%s.py' % n, 'command': 'python3 tools/verify_%s.py' % n,
            'rc': work.get(n, {}).get('rc'), 'verifier_sha': blob_sha(p),
            'purpose': doc1(p), 'subsystem': subsystem(n),
            'in_gate23': n in GATE23, 'in_suite40': n in SUITE40,
            'suite40_status_at_4b9d33d': SUITE40_BEFORE.get(n),
            'status_pristine_head': h, 'status_working_tree': w,
            'expected': w, 'classification': hist,
            'seconds': work.get(n, {}).get('seconds'), 'tail': work.get(n, {}).get('tail'),
            'tiers': tiers, 'note': NOTES.get(n, ''),
        })
    meta = {'head_root': json.load(open(a.head))['root'], 'work_root': json.load(open(a.work))['root'],
            'source_head': a.source_head, 'timeout_s': a.timeout,
            'counts': {k: sum(1 for r in rows if r['expected'] == k) for k in ('PASS', 'FAIL', 'TIMEOUT')},
            'regressions': [r['name'] for r in rows if r['classification'].startswith('REGRESSION')]}
    json.dump({'meta': meta, 'verifiers': rows}, open(os.path.join(DOC, 'CANONICAL_VERIFIER_MANIFEST.json'), 'w',
                                                      encoding='utf-8'), ensure_ascii=False, indent=1)
    L = ['# CANONICAL_VERIFIER_MANIFEST', '',
         '검증 스크립트 기준을 하나로 정리한다. 스크립트를 합치지 않고 **무엇을 언제 돌리는지**만 통일한다.', '',
         '## 언제 무엇을 돌리나', '',
         '| 시점 | 실행 | 통과 기준 |', '| --- | --- | --- |',
         '| 모든 코드 변경 직후 | `python tools/run_verifier_manifest.py --tier fast` + `python tools/check_semantic_completeness.py` | fast 전부 PASS, completeness rc 0 |',
         '| 행동 불변 리팩터링 | 위 + 해당 parity verifier(`semantic_cleanup`, `defend_semantic_cleanup`, `range_read_semantics`, `remaining_read_semantics`, `reaudit_semantic_extraction`) + baseline sim action/intent 바이트 비교 | parity PASS, sim 동일 |',
         '| 행동 변경 batch / push 전 | `--tier gate23` (+ baseline sim before/after) | expected 와 동일한 PASS/FAIL 집합 |',
         '| 체크포인트 / 승격 검토 | `--tier all --timeout 2400`(human_model_v2·oop_semantics 는 약 18~19분). `audit_order`·`state_namespace`·`trace_schema` 는 clean worktree 에서 단독 실행 | 아래 expected 와 동일; REGRESSION 0 |', '',
         '`expected` 가 FAIL/TIMEOUT 인 스크립트는 pristine HEAD 에서도 같은 상태인 **역사적 실패**다. '
         '억지로 고쳐 PASS로 만들지 않았다. 상태가 바뀌면 원인을 조사하고 이 표를 갱신한다.', '',
         '요약: PASS %(PASS)d / FAIL %(FAIL)d / TIMEOUT %(TIMEOUT)d (총 %(n)d). REGRESSION: %(reg)s' % dict(
             meta['counts'], n=len(rows), reg=(', '.join(meta['regressions']) or '없음')), '',
         '실행 기준: source `%s`, 검증기별 timeout %s 초, 실행 명령은 저장소 루트에서 `python3 tools/verify_<name>.py`. '
         '`verifier_sha` 는 검증기 파일의 git blob SHA(앞 12자리)다.' % (meta['source_head'] or '?', meta['timeout_s'] or '?'), '',
         '| verifier | 목적(검증 계약) | subsystem | 23-gate | 40-suite | 40-suite@4b9d33d | pristine HEAD | 현재 | rc | 분류 | 초 | verifier_sha | 메모 |',
         '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        L.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            r['name'], r['purpose'].replace('|', '/'), r['subsystem'], 'Y' if r['in_gate23'] else '',
            'Y' if r['in_suite40'] else '', r['suite40_status_at_4b9d33d'] or '', r['status_pristine_head'],
            r['status_working_tree'], r['rc'], r['classification'], r['seconds'], r['verifier_sha'], r['note']))
    open(os.path.join(DOC, 'CANONICAL_VERIFIER_MANIFEST.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == '__main__':
    main()
