#!/usr/bin/env python3
"""봇 자체 시험(계산기 없이, 가짜 origin). 실행: python3 test_autopilot.py [<임시폴더>]
 1) 판정 함수: 저장소의 실제 collect 보고서(ft30 0·1단계)로 문서 숫자와 일치 확인
 2) claim 원자성: 두 프로세스가 같은 단위를 동시에 잡으면 하나만 성공
 3) 계획: 가짜 보드 브랜치(끝남/남이 작업 중/오래 멈춤/내 것)에서 연구실이 잡을 보드만 고르는가
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../../..'))
sys.path.insert(0, HERE)
import autopilot as A  # noqa: E402
import judge as J  # noqa: E402

T = sys.argv[1] if len(sys.argv) > 1 else '/tmp/lab_ap_test'
shutil.rmtree(T, ignore_errors=True)
os.makedirs(T)
ok_all = True


def check(name, cond, extra=''):
    global ok_all
    ok_all &= bool(cond)
    print(('통과 ' if cond else '실패 ') + name + (' — %s' % extra if extra else ''))


def sh(*a, cwd=None, env=None):
    e = dict(os.environ, GIT_AUTHOR_NAME='x', GIT_AUTHOR_EMAIL='x@x', GIT_COMMITTER_NAME='x', GIT_COMMITTER_EMAIL='x@x', **(env or {}))
    return subprocess.run(a, cwd=cwd, env=e, capture_output=True, text=True, check=True).stdout.strip()


# ---- 1) 판정
for k, med, d_le_u, seats in ((0, 4.38, 0, 58), (1, 3.13, 5, 50)):
    rep = json.load(open(os.path.join(REPO, 'data/ft30/step%d/collect/report.json' % k)))
    dec = {'failures': [{'bundle': 's0_t00_B', 'board': 'Ac9h9d', 'retry_pct_pot': 0.4318, 'node': 10}]}   # step0/flop_failure_decision.json
    v = J.judge(rep, history=json.load(open(os.path.join(REPO, 'data/ft30/history.json'))), flop=dec if k == 0 else None)
    m = v['metrics']
    check('판정 ft30 단계%d: D≤U %d/%d, D/U 중앙값 %.2f' % (k, d_le_u, seats, med),
          m['pass_D_le_U'] == d_le_u and m['seats'] == seats and abs(m['dou_median'] - med) < 0.01, '%s %.2f → %s' % (m['pass_D_le_U'], m['dou_median'], v['status']))
    check('  단계%d 상태 continue (0단계는 통과 불가)' % k, v['status'] == 'continue')
fake_ok = json.load(open(os.path.join(REPO, 'data/ft30/step1/collect/report.json')))
for t in fake_ok['terminals'].values():
    for s in t['seats'].values():
        s['pass_D_le_U'] = True
        s['D_over_U'] = 0.5
v = J.judge(fake_ok, step=2, root=None)
check('가짜 전부 통과 → 값 통과(뿌리 복제 확인 대기, NC-1)', v['status'] == 'values_pass_pending_root', v['status'])
v = J.judge(fake_ok, step=2, root={'fraction': 0.97})
check('가짜 전부 통과 + 뿌리 복제 97% → converged', v['status'] == 'converged', v['status'])
v = J.judge(fake_ok, step=2, root={'fraction': 0.90})
check('뿌리 복제 90% → 완료 아님', v['status'] != 'converged', v['status'])
fl = json.loads(json.dumps(fake_ok))
fl['flop_failures_after_retry'] = [['s1_t10_A', ['Ac9h9d']]]
v = J.judge(fl, step=2, flop={'failures': [{'bundle': 's1_t10_A', 'board': 'Ac9h9d', 'retry_pct_pot': 0.43, 'node': 10}]})
check('플랍 실패 0.43% pot → 받아들임', not v['static_nodes_add'] and v['checks'][1]['ok'])
v = J.judge(fl, step=2, flop={'failures': [{'bundle': 's1_t10_A', 'board': 'Ac9h9d', 'retry_pct_pot': 0.9, 'node': 10}]})
check('플랍 실패 0.9% pot → 그 끝점 정적 유지', v['static_nodes_add'] == [10], str(v['static_nodes_add']))
check('진동 식 정확: [5,8,3] 진동 / [5,4,3] 아님 / [0.5,0.9,0.4] 아님(D/U≤1)', J.cycling([5, 8, 3]) and not J.cycling([5, 4, 3]) and not J.cycling([0.5, 0.9, 0.4]))

# ---- 2,3) 가짜 origin
O = os.path.join(T, 'origin.git')
sh('git', 'init', '-q', '--bare', O)
sh('git', '-C', O, 'config', 'uploadpack.allowFilter', 'true')
seed = os.path.join(T, 'seed')
os.makedirs(seed)
sh('git', 'init', '-q', cwd=seed)
tar = subprocess.run('git -C %s archive origin/claude/ft30_coord | tar x -C %s' % (REPO, seed), shell=True, check=True)
old = '2026-11-20T00:00:00'
sh('git', 'add', '-A', cwd=seed)
sh('git', 'commit', '-qm', 'coord30 collected', cwd=seed, env={'GIT_COMMITTER_DATE': old, 'GIT_AUTHOR_DATE': old})
sh('git', 'branch', '-M', 'claude/ft30_coord', cwd=seed)
sh('git', 'push', '-q', O, 'claude/ft30_coord', cwd=seed)
# 보드 단계 상태 흉내: 1단계 collect 보고서를 뺀 커밋(= 보드 진행 중)
os.remove(os.path.join(seed, 'data/ft30/step1/collect/report.json'))
sh('git', 'add', '-A', cwd=seed)
d2 = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - 10 * 3600))
sh('git', 'commit', '-qm', 'boards phase', cwd=seed, env={'GIT_COMMITTER_DATE': d2, 'GIT_AUTHOR_DATE': d2})
sh('git', 'push', '-q', O, 'claude/ft30_coord', cwd=seed)
assign = [l.split('\t') for l in open(os.path.join(seed, 'data/ft30/step1/assign.tsv')).read().splitlines()[1:]]
per = {}
for b, n in assign:
    per.setdefault(int(n), []).append(b)


def board_branch(n, done, partial, age_h):
    """coord 에서 갈라진 보드 브랜치 + 결과 파일. done=끝난 묶음 수, partial=부분 묶음 수"""
    sh('git', 'checkout', '-q', '-B', 'tmp', 'claude/ft30_coord', cwd=seed)
    bl = per[n]
    for i, b in enumerate(bl):
        d = os.path.join(seed, 'data/ft30/results/step1', b)
        if i < done:
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, 'done.json'), 'w').write('{}')
        elif i < done + partial:
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, 'state.json'), 'w').write('{}')
    sh('git', 'add', '-A', cwd=seed)
    dt_ = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - age_h * 3600))
    sh('git', 'commit', '-q', '--allow-empty', '-m', 'board %d' % n, cwd=seed, env={'GIT_COMMITTER_DATE': dt_, 'GIT_AUTHOR_DATE': dt_})
    sh('git', 'push', '-q', O, 'tmp:refs/heads/claude/ft30_board_%d' % n, cwd=seed)


board_branch(1, len(per[1]), 0, 30)     # 끝남
board_branch(2, 0, 1, 1)                # 남이 방금 부분 푸시 → 건너뜀
board_branch(3, 0, 1, 40)               # 남이 40시간 전에 멈춤 → 인계
board_branch(4, 1, 0, 5)                # 일부 끝, 5시간 전(활동 아님 <24h, 남이 시작함) → 건너뜀
board_branch(5, 0, 0, 100)              # 옛 단계(0단계) 흔적만 → 새로
board_branch(6, 0, 0, 0.5)              # 방금 푸시(막 시작) → 건너뜀

# 연구실 설정
R = os.path.join(T, 'repo')
sh('git', 'clone', '-q', O, R)
root = os.path.join(T, 'lab')
cfgp = os.path.join(T, 'cfg.json')
json.dump({'root': root, 'repo': R, 'work': os.path.join(T, 'gto'), 'calc': os.path.join(T, 'calc'), 'py311': sys.executable,
           'stacks': {'40': {'enabled': False}, '60': {'enabled': False}, '100': {'enabled': False}}}, open(cfgp, 'w'))
os.makedirs(os.path.join(T, 'gto'))
os.environ['FT_NO_PUSH'] = '1'
cfg = A.load_config(cfgp)
cfg['stacks']['30']['coord_actions'] = True
ap = A.Autopilot(cfg, dry=True)
ap.refresh()
sv = ap.view['30']
check('스택 30 단계 읽기: phase=boards, K=1', sv.phase == 'boards' and sv.K == 1, '%s %s' % (sv.phase, sv.K))
plan = {u: why for S, k, kind, u, why in ap.candidates()}
check('끝난 보드 1 은 건너뜀', 'board_1' not in plan)
check('남이 방금 푸시한 보드 2 는 건너뜀', 'board_2' not in plan)
check('40시간 멈춘 부분 푸시 보드 3 은 인계', 'board_3' in plan and '인계' in plan['board_3'], plan.get('board_3'))
check('일부 끝+5시간 전 보드 4 는 건너뜀', 'board_4' not in plan)
check('0단계 흔적만(100시간 전) 보드 5 는 새로', 'board_5' in plan and plan['board_5'] == '새로', plan.get('board_5'))
check('방금 푸시된 보드 6 은 건너뜀', 'board_6' not in plan)
check('아무 브랜치 없는 보드 7 은 새로', plan.get('board_7') == '새로')

# claim 원자성: 두 프로세스 동시
ap.hub.push = True          # 가짜 origin 이라 푸시 허용
env = dict(os.environ, FT_NO_PUSH='0')
cfgenv = dict(env, LAB_TEST_CFG=cfgp)
code = ('import sys,os; sys.path.insert(0,%r); import autopilot as A; cfg=A.load_config(%r); '
        'h=A.Hub(cfg,True); h.refresh_heads({}); ok=h.claim("30",1,"board_9",owner=sys.argv[1]); print("OK" if ok else "TAKEN")') % (HERE, cfgp)
ps = [subprocess.Popen([sys.executable, '-c', code, nm], stdout=subprocess.PIPE, text=True, env=env) for nm in ('A', 'B', 'C')]
res = [p.communicate()[0].strip() for p in ps]
check('claim 3개 동시 → 정확히 1개 성공', res.count('OK') == 1 and res.count('TAKEN') == 2, str(res))
ap.hub.refresh_heads({'30': cfg['stacks']['30']})
cl = ap.hub.read_claims()
check('claim 파일이 원격 claim 브랜치에 있음', ('30', 1, 'board_9') in cl, str(list(cl)))
ap.claims = cl
ok_ = ap.hub.claim('30', 1, 'board_9', owner='D')
check('이미 남이 claim(하트비트 최근) → 다른 사람은 실패', not ok_)
check('release 후 다시 claim 가능', ap.hub.release('30', 1, 'board_9', owner=cl[('30', 1, 'board_9')]['owner']) and ap.hub.claim('30', 1, 'board_9', owner='D'))
# claim 이 있으면 보드 선택에서 제외
ap.hub.claim('30', 1, 'board_8', owner='someone-else')
ap.refresh()
plan = {u for S, k, kind, u, why in ap.candidates()}
check('다른 쪽 claim 보드 8 은 계획에서 빠짐', 'board_8' not in plan and 'board_7' in plan)
# 상태 푸시
ap.hub.push = True
ap.no_push = False
ap.push_status(force=True)
ap.hub.heads = ap.hub.remote_heads(['refs/heads/' + cfg['branches']['status']])
check('상태(heartbeat) 브랜치에 푸시됨', cfg['branches']['status'] in ap.hub.heads)
print('\n전체:', '통과' if ok_all else '실패')
sys.exit(0 if ok_all else 1)
