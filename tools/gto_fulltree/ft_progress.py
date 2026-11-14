#!/usr/bin/env python3
"""보드 진행 세기(읽기 전용): FT_STACK=100 python3 tools/gto_fulltree/ft_progress.py <단계 k>
claude/ft<스택>_board_* 브랜치마다 끝난 묶음(done.json)과 마지막 푸시 시각을 세고, assign.tsv 의 배분 수와 비교한다. 4시간 넘게 푸시 없는 세션 번호를 낸다."""
import os, subprocess, sys, json, time, csv
STACK = os.environ.get('FT_STACK', '100'); K = int(sys.argv[1]) if len(sys.argv) > 1 else 1
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
def git(*a): return subprocess.run(['git', '-C', REPO, *a], capture_output=True, text=True).stdout
asg = list(csv.DictReader(open(os.path.join(REPO, 'data/ft%s/step%d/assign.tsv' % (STACK, K))), delimiter='\t'))
want = {}
for r in asg: want.setdefault(int(r['session']), []).append(r['bundle'])
total = len(asg); done = set(); last = {}
git('fetch', '-q', 'origin', '+refs/heads/claude/ft%s_board_*:refs/remotes/origin/claude/ft%s_board_*' % (STACK, STACK))
for ref in git('for-each-ref', '--format=%(refname:short) %(committerdate:unix)', 'refs/remotes/origin/claude/ft%s_board_*' % STACK).splitlines():
    br, ts = ref.split(); n = int(br.rsplit('_', 1)[1]); last[n] = int(ts)
    for p in git('ls-tree', '-r', '--name-only', br, 'data/ft%s/results/step%d' % (STACK, K)).split():
        if p.endswith('/done.json'): done.add(p.split('/')[-2])
now = time.time(); stalled = []
for n, bs in sorted(want.items()):
    nd = sum(1 for b in bs if b in done)
    if nd < len(bs) and n in last and now - last[n] > 4 * 3600: stalled.append(n)
    if nd < len(bs) and n not in last: stalled.append(n)
print(json.dumps({'step': K, 'done': len(done & {r['bundle'] for r in asg}), 'total': total, 'stalled_over_4h_or_missing': sorted(set(stalled))}))
