#!/usr/bin/env python3
"""collect 뒤 판정 — 연구실 봇(lab autopilot)의 do_collect 후처리·evaluate 와 같은 코드·같은 기준을 그대로 쓴다.
  python3 ft_judge.py <봇 폴더(lab_autopilot)> <STACK> <k> <collect 작업 폴더(FT_WORK/collect_s<k>)>
저장소 루트에서 실행. 하는 일: flop_failure_decision.json, step<k>_board_hours.json, static_nodes.json(플랍 실패 끝점 정적 유지),
judge.json/md 작성. 마지막 줄: JUDGE <status> (continue 일 때만 다음 표로 넘어간다)."""
import csv, gzip, json, os, statistics, sys
AP, S, k, wk = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
sys.path.insert(0, AP)
os.environ.setdefault('LAB_ROOT', '/tmp/ft_judge_root')
import autopilot as A  # noqa: E402
import judge as J  # noqa: E402
cfg = A.load_config()
sc = cfg['stacks'][S]
W = os.getcwd()
sd = os.path.join(W, 'data/ft%s/step%d' % (S, k))
rep = json.load(open(os.path.join(sd, 'collect/report.json')))
rows = list(csv.DictReader(open(os.path.join(sd, 'bundles.tsv')), delimiter='\t'))
node_of = {r['bundle']: int(r['node']) for r in rows}
dec, hours = {}, {}
for b, boards in rep.get('flop_failures_after_retry') or []:
    vals = json.load(gzip.open(os.path.join(wk, b, 'values.json.gz'), 'rt'))
    for x in boards:
        rt = (vals.get(x) or {}).get('retry') or {}
        dec['%s/%s' % (b, x)] = {'first_pct_pot': rt.get('first_pct_pot'), 'retry_pct_pot': rt.get('retry_pct_pot'),
                                 'accepted': rt.get('retry_pct_pot') is not None and rt['retry_pct_pot'] <= sc['judge']['flop_accept_pct_pot']}
for b in node_of:
    dj = os.path.join(wk, b, 'done.json')
    if os.path.exists(dj):
        hours.setdefault(str(node_of[b]), []).append(json.load(open(dj)).get('wall_min_this_run', 0) / 60)
if hours:
    json.dump({n: round(statistics.median(v), 2) for n, v in hours.items()}, open(os.path.join(W, 'data/ft%s/step%d_board_hours.json' % (S, k)), 'w'), indent=1)
if dec:
    json.dump({'rule': 'retry exploitability <=%.1f%% pot accepted (accepted_above_target), else terminal stays static (ft_judge = lab autopilot rule)' % sc['judge']['flop_accept_pct_pot'],
               'boards': dec}, open(os.path.join(sd, 'flop_failure_decision.json'), 'w'), indent=1)
v = A.evaluate(A.local_evidence(S, W), k, sc['judge'])
if v['static_nodes_add']:
    sn = os.path.join(sd, 'static_nodes.json')
    cur = set(json.load(open(sn))) if os.path.exists(sn) else set()
    json.dump(sorted(cur | set(v['static_nodes_add'])), open(sn, 'w'))
json.dump(v, open(os.path.join(sd, 'judge.json'), 'w'), indent=1, ensure_ascii=False)
open(os.path.join(sd, 'judge.md'), 'w').write('# ft%s 단계 %d 자동 판정 (ft_judge = lab autopilot 기준)\n\n상태: **%s**\n\n%s\n\n%s\n' % (
    S, k, v['status'], '\n'.join('- ' + r for r in v['reasons'] + v['warnings']), J.render_table(v)))
print('reasons:', '; '.join(v['reasons'])[:300])
print('JUDGE %s' % v['status'])
