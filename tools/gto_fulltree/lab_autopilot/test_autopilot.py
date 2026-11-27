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
    e = dict(dict(os.environ, GIT_AUTHOR_NAME='x', GIT_AUTHOR_EMAIL='x@x', GIT_COMMITTER_NAME='x', GIT_COMMITTER_EMAIL='x@x'), **(env or {}))
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

# 묶음 단위 판단(보드 번호 재배정): board_10 의 묶음이 다른 이름 브랜치에서 방금 푸시됨 / board_11 의 묶음 전부가 다른 브랜치에서 끝남
def board_branch_named(name, bundles, done, age_h):
    sh('git', 'checkout', '-q', '-B', 'tmp', 'claude/ft30_coord', cwd=seed)
    for b in bundles:
        d = os.path.join(seed, 'data/ft30/results/step1', b)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'done.json' if done else 'state.json'), 'w').write('{}')
    sh('git', 'add', '-A', cwd=seed)
    dt_ = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - age_h * 3600))
    sh('git', 'commit', '-q', '--allow-empty', '-m', name, cwd=seed, env={'GIT_COMMITTER_DATE': dt_, 'GIT_AUTHOR_DATE': dt_})
    sh('git', 'push', '-q', O, 'tmp:refs/heads/claude/ft30_board_%s' % name, cwd=seed)


board_branch_named('21', per[10][:1], False, 0.5)      # board_10 의 첫 묶음을 보드 21 이 진행 중
board_branch_named('11b', per[11], True, 30)           # board_11 의 묶음 전부를 11b 가 끝냄
# 봇 자신이 쓴 조정 커밋은 '조정 세션 작업 중' 판단에서 뺀다
sh('git', 'checkout', '-q', '-B', 'own', 'claude/ft30_coord', cwd=seed)
sh('git', 'commit', '-q', '--allow-empty', '-m', 'lab own push', cwd=seed, env={'GIT_AUTHOR_NAME': 't2-lab', 'GIT_COMMITTER_NAME': 't2-lab'})
sh('git', 'push', '-q', O, 'own:refs/heads/claude/ft30_coord', cwd=seed)

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
check('묶음이 다른 브랜치(21)에서 진행 중이면 보드 10 건너뜀', 'board_10' not in plan)
check('묶음 전부가 다른 브랜치(11b)에서 끝났으면 보드 11 은 끝난 것', 'board_11' not in plan and sv.boards[11]['all_done'])
check('봇 자신의 조정 푸시는 조정 대기 판단에서 제외(약 10시간 전 외부 푸시 기준)', sv.last_commit_age_h is not None and 9 < sv.last_commit_age_h < 12, str(sv.last_commit_age_h))

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

# ---- 4) 오류 경고·중복 푸시 줄이기·원격 명령·감시·도구 갱신·자체 점검
import types
ap.no_push = False
ap.hub.push = True
ap.refresh()
ap.derive_alerts()
d = ap.status_doc()
check('경고 없으면 status=ok', d['status'] == 'ok' and d['alerts'] == [], d['status'])
ap.alert('solver_rc', ('30', 1, 'board_7'), 'warn', '시험 오류', log=os.path.join(T, 'lab/logs/autopilot.log'), ttl_h=1)
ap.derive_alerts()
d = ap.status_doc()
check('경고 있으면 status!=ok, 로그 꼬리·시각 포함', d['status'] == 'warn' and d['alerts'][0]['code'] == 'solver_rc' and 'log_tail' in d['alerts'][0], d['status'])
ap.alert('solver_rc', ('30', 1, 'board_7'), 'error', '시험 오류 2')
check('같은 경고 반복 → 한 건(count 증가)', len(ap.alerts) == 1 and ap.status_doc()['alerts'][0]['count'] == 2 and ap.status_doc()['status'] == 'error')
ap.t_pushed = 0; ap.pushed_sig = None
ap.push_status()
head1 = ap.hub.remote_heads(['refs/heads/' + cfg['branches']['status']])[cfg['branches']['status']]
ap.t_pushed = time.time() - 400          # 5분 지남, 같은 경고 → 다시 안 올림
ap.push_status()
head2 = ap.hub.remote_heads(['refs/heads/' + cfg['branches']['status']])[cfg['branches']['status']]
check('같은 오류가 계속되면 중복 푸시 안 함', head1 == head2)
ap.alert('disk_low', 'disk', 'error', '새 경고')
ap.t_pushed = time.time() - 400
ap.push_status()
head3 = ap.hub.remote_heads(['refs/heads/' + cfg['branches']['status']])[cfg['branches']['status']]
check('경고가 바뀌면 바로 푸시', head3 != head2)
ap.clear('disk_low'); ap.clear('solver_rc')
ap.t_pushed = time.time() - 6 * 3600 - 10
ap.derive_alerts(); ap.push_status()
head4 = ap.hub.remote_heads(['refs/heads/' + cfg['branches']['status']])[cfg['branches']['status']]
check('오류 없음 + 6시간 지나면 heartbeat 한 번', head4 != head3 and ap.status_doc()['status'] == 'ok')
sd = json.loads(subprocess.run(['git', '-C', ap.hub.cr.path, 'show', 'origin/%s:status.json' % cfg['branches']['status']], capture_output=True, text=True).stdout or '{}') if False else None

# 원격 명령: 코디네이터가 lab_status 에 control.json 을 올린다
cdir = os.path.join(T, 'ctl')
sh('git', 'clone', '-q', '-b', cfg['branches']['status'], O, cdir)
json.dump({'seq': 1, 'commands': [{'id': 'a1', 'cmd': 'pause', 'stack': '30'}, {'id': 'a2', 'cmd': 'skip', 'stack': '30', 'unit': 'board_7'},
                                  {'id': 'a3', 'cmd': 'priority', 'order': ['30']}, {'id': 'a4', 'cmd': 'config', 'path': 'cpu.boards_parallel', 'value': 1},
                                  {'id': 'a5', 'cmd': 'config', 'path': 'cpu.total_cores', 'value': 99}, {'id': 'a6', 'cmd': 'rm -rf'}]}, open(os.path.join(cdir, 'control.json'), 'w'))
sh('git', 'add', '-A', cwd=cdir); sh('git', 'commit', '-qm', 'control', cwd=cdir); sh('git', 'push', '-q', 'origin', 'HEAD', cwd=cdir)
ap.t_control = 0
ap.poll_control()
res = ap.state['ctl']['applied']
check('원격 명령 처리: pause/skip/priority/config 성공', all(res[k]['ok'] for k in ('a1', 'a2', 'a3', 'a4')), str({k: v['ok'] for k, v in res.items()}))
check('허용 안 된 설정·모르는 명령은 실패로 기록', not res['a5']['ok'] and not res['a6']['ok'])
ap.derive_alerts()
check('pause 중이면 candidates 에서 스택 30 제외 + paused 경고', not [x for x in ap.candidates() if x[0] == '30'] and any(a['code'] == 'paused' for a in ap.alerts.values()))
ap.apply_command({'cmd': 'resume', 'stack': '30'})
check('resume 후 다시 계획에 나옴, skip 한 보드 7 은 제외', any(x[0] == '30' for x in ap.candidates()) and 'board_7' not in {x[3] for x in ap.candidates()})
ap.apply_command({'cmd': 'retry', 'stack': '30', 'unit': 'board_7'})
check('retry 로 skip 해제', 'board_7' in {x[3] for x in ap.candidates()})
ap.t_control = 0; ap.poll_control()
check('같은 명령 id 는 다시 처리 안 함', len(ap.state['ctl']['applied']) == 6)

# 감시: CPU 를 안 쓰는 프로세스를 계산 프로세스처럼 등록 → 진행 없음 경고 + 종료
sl = subprocess.Popen(['sleep', '1000'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
jb = A.Job(ap, 'board', '30', 1, 'board_99', lambda j: None, 3)
jb.pids.add(sl.pid); jb.no_progress_h = 0.0001; jb.t_cpu = jb.t_file = time.time() - 3600
jb.is_alive = lambda: True
ap.jobs[('30', 1, 'board_99')] = jb
ap.t_watch = 0; ap.watchdog()      # 첫 틱은 기준 CPU 시간을 잰다
ap.t_watch = 0; jb.t_cpu = time.time() - 3600; ap.watchdog()      # 둘째 틱: CPU 증가 없음 → 종료
time.sleep(0.5)
check('CPU 안 쓰는 계산 프로세스 → no_progress 경고 + 프로세스 종료', ('no_progress', '30|1|board_99') in ap.alerts and sl.poll() is not None, str(list(ap.alerts)))
del ap.jobs[('30', 1, 'board_99')]
t0 = A.proc_ticks(os.getpgid(0)); check('proc_ticks 가 CPU 시간을 읽음(>=0)', t0 >= 0)

# 도구 갱신(sync_tools): 구버전 coord 도구 → 최신 도구 기준 브랜치로 덮어쓰기 + 균형 패널 복사 + FT_MIN_REACH
sh('git', 'checkout', '-q', '-B', 'tools3', 'claude/ft30_coord', cwd=seed)
sh('bash', '-c', 'git -C %s archive origin/claude/ft60_3way_s5 tools/gto_fulltree data/ft60/panels | tar x -C %s' % (REPO, seed))
sh('git', 'add', '-A', cwd=seed); sh('git', 'commit', '-qm', 'tools ref', cwd=seed)
sh('git', 'push', '-q', O, 'tools3:refs/heads/claude/ft60_3way_s5', cwd=seed)
sh('git', 'checkout', '-q', 'claude/ft30_coord', cwd=seed)
sc = cfg['stacks']['30']
ap.refresh()
W, g = ap.coord_wt('30', sc)
before = open(os.path.join(W, 'tools/gto_fulltree/ft60.py')).read()
paths = []
ap.sync_tools('30', 2, sc, W, g, paths)
after = open(os.path.join(W, 'tools/gto_fulltree/ft60.py')).read()
check('구버전 도구가 최신 기준(행렬 끝점·균형 패널·FT_REPLACE)으로 갱신됨', 'FT_MATRIX_ALL' not in before and all(m in after for m in sc['tools_markers']))
check('FT_MIN_REACH 3줄 패치(도달 >= 값인 끝점 전부)', 'hu[:n] if MIN_REACH is None else [x for x in hu if x[0] >= MIN_REACH]' in after)
check('균형 패널 파일이 data/ft30/panels 에 복사됨', all(os.path.exists(os.path.join(W, 'data/ft30/panels/panel_bal_%s72.json' % x)) for x in 'AB') and 'data/ft30/panels' in paths)
paths2 = []
ap.sync_tools('30', 2, sc, W, g, paths2)
check('이미 최신이면 다시 안 덮어씀', paths2 == [])
env2 = ap.tool_env('30', W, sc, step=2); env1 = ap.tool_env('30', W, sc, step=1)
check('패널 세트: 2단계부터 bal, 1단계 재계산은 prec', env2.get('FT_PANEL_SET') == 'bal' and env1.get('FT_PANEL_SET') == 'prec')
compile(open(os.path.join(W, 'tools/gto_fulltree/ft60.py')).read(), 'ft60.py', 'exec')
check('덮어쓴 ft60.py 문법 정상', True)


# 특별 작업 대기열(enqueue/dequeue): 형식 검사, 중복 방지, 대기열이 있으면 새 스택 일을 시작하지 않음(돌고 있는 일이 있으면 기다림)
ok1, _ = ap.apply_command({'cmd': 'enqueue', 'kind': '3way_full', 'board': '9c8d2c'})
ok2, _ = ap.apply_command({'cmd': 'enqueue', 'kind': '3way_full', 'board': '9c8d2c'})
ok3, _ = ap.apply_command({'cmd': 'enqueue', 'kind': '3way_full', 'board': 'XYZ'})
ok4, _ = ap.apply_command({'cmd': 'enqueue', 'kind': 'other', 'board': 'AcKhJd'})
ap.apply_command({'cmd': 'enqueue', 'kind': '3way_full', 'board': 'AcKhJd'})
check('enqueue: 정상 추가·중복 무시·형식 오류 거부', ok1 and ok2 and not ok3 and not ok4 and [x['id'] for x in ap.special_pending()] == ['3way_9c8d2c', '3way_AcKhJd'])
_disk = ap.cfg['disk']['min_free_gb']; ap.cfg['disk']['min_free_gb'] = 0   # 시험 컨테이너 디스크와 무관하게
busy = type('J', (A.Job,), {'is_alive': lambda s: True})(ap, 'board', '30', 1, 'board_5', None, 3)
ap.jobs[('30', 1, 'board_5')] = busy
before = dict(ap.jobs)
r = ap.schedule()
check('대기열 있음 + 돌고 있는 일 있음 → 새 일 시작 안 함', r == 0 and set(ap.jobs) == set(before), str(list(ap.jobs)))
del ap.jobs[('30', 1, 'board_5')]
r = ap.schedule()
check('대기열 있음 + 빈 컴퓨터 → (시험 모드) 스택 일 대신 특별 작업 차례', r == 0 and not any(k[0] == '30' for k in ap.jobs))
ap.cfg['disk']['min_free_gb'] = _disk
okd, _ = ap.apply_command({'cmd': 'dequeue', 'board': '9c8d2c'})
check('dequeue', okd and [x['id'] for x in ap.special_pending()] == ['3way_AcKhJd'])
ap.state['special_done'].append('3way_AcKhJd')
check('끝난 특별 작업은 대기열에서 빠짐', ap.special_pending() == [])
d = ap.status_doc(); check('상태에 special 항목', 'special' in d and d['special']['done'][-1] == '3way_AcKhJd')

# 자체 점검 + 업데이트 실패 시 이전 버전 유지
r = subprocess.run([sys.executable, os.path.join(HERE, 'autopilot.py'), 'selfcheck'], capture_output=True, text=True, env=dict(os.environ, LAB_CONFIG=cfgp, FT_NO_PUSH='1'))
check('selfcheck 통과(문법·판정 재현·드라이런)', r.returncode == 0 and 'SELFCHECK_OK' in r.stdout, (r.stdout + r.stderr)[-200:])
bad = os.path.join(T, 'badrel/tools/gto_fulltree/lab_autopilot')
shutil.copytree(HERE, bad)
open(os.path.join(bad, 'judge.py'), 'a').write('\ndef broken(:\n')
r = subprocess.run([sys.executable, os.path.join(bad, 'autopilot.py'), 'selfcheck'], capture_output=True, text=True, env=dict(os.environ, LAB_CONFIG=cfgp, FT_NO_PUSH='1'))
check('깨진 새 버전은 selfcheck 실패(교체 안 됨)', r.returncode != 0 and 'SELFCHECK_FAIL' in r.stdout + r.stderr or r.returncode != 0, (r.stdout + r.stderr)[-150:])

print('\n전체:', '통과' if ok_all else '실패')
sys.exit(0 if ok_all else 1)
