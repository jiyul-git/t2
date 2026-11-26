#!/bin/bash
# 연구실 자동 계산·판단 봇 시작 스크립트 (WSL 우분투). 문서: docs/LAB_AUTOPILOT.md
#   bash lab_autopilot.sh install   # 처음 한 번: 봇 코드 폴더 만들기 + 준비 점검(깃허브 claude/lab_autopilot 에서). 설치 뒤 start
#   bash lab_autopilot.sh run       # 이 창에서 계속 돈다(이미 돌고 있으면 조용히 끝남). 작업 스케줄러가 쓰는 명령
#   bash lab_autopilot.sh start     # 백그라운드로 시작(WSL 1 은 창이 닫히면 꺼질 수 있음 → 스케줄러의 run 권장)
#   bash lab_autopilot.sh stop      # 봇과 계산 전부 멈춤(올라간 12보드 덩어리는 건너뛰고 다음에 이어서)
#   bash lab_autopilot.sh status    # 지금 상태(한눈에)
#   bash lab_autopilot.sh logs      # 로그 끝부분
#   bash lab_autopilot.sh once      # 계산 안 하고 '지금 할 일'만 보기(시험)
# 시험 모드: LAB_DRY=1(풀지 않음, 푸시 안 함), FT_NO_PUSH=1(푸시 안 함), FT_TEST_BOARDS=2(보드 앞 2장만)
set -u
ROOT=${LAB_ROOT:-$HOME/t2lab}
REPO=${LAB_REPO:-$HOME/t2}
BR=claude/lab_autopilot
AP=$ROOT/releases/bootstrap
mkdir -p $ROOT/logs $ROOT/state
PYBIN=$(command -v python3)
CMD=${1:-help}

code_dir() { echo $ROOT/current/tools/gto_fulltree/lab_autopilot; }

case "$CMD" in
  install)
    command -v git >/dev/null || { echo "git 이 없음"; exit 1; }
    [ -d $REPO/.git -o -f $REPO/.git ] || { echo "$REPO 가 t2 저장소가 아님 (LAB_REPO=<경로> 로 지정)"; exit 1; }
    git -C $REPO fetch -q origin +refs/heads/$BR:refs/remotes/origin/$BR || { echo "깃허브에서 $BR 를 못 가져옴(네트워크·로그인 확인)"; exit 1; }
    SHA=$(git -C $REPO rev-parse origin/$BR | cut -c1-10)
    AP=$ROOT/releases/$SHA
    mkdir -p $ROOT/releases
    if [ ! -e $AP/.git ]; then git -C $REPO worktree prune; git -C $REPO worktree add -q --detach $AP origin/$BR || exit 1; fi
    ln -sfn $AP $ROOT/current.tmp && mv -T $ROOT/current.tmp $ROOT/current
    echo "봇 코드: $ROOT/current -> $AP ($SHA). 이후 새 버전은 봇이 스스로 받아 점검하고 교체한다"
    # 예전 lab_ft.sh 가 돌고 있으면 멈춘다(CPU 를 두 곳에서 쓰지 않도록; 올라간 덩어리는 건너뛰고 이어서 함)
    if [ -f $ROOT/lab.pid ] && kill -0 $(cat $ROOT/lab.pid) 2>/dev/null; then echo "예전 lab_ft.sh 를 멈춤"; bash $AP/tools/gto_fulltree/lab_ft.sh stop; fi
    # 준비 점검
    C=/home/user/calc; [ -x $C/vendor/gtopen/target/release/examples/t2_cont_panel ] || C=$HOME/calc
    if [ ! -x $C/vendor/gtopen/target/release/examples/t2_cont_panel ]; then
      echo "계산 체크아웃이 없음 → 준비(10~20분). 먼저 python3.11 필요: sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt install -y python3.11 python3.11-venv"
      (cd $AP && nice -n 19 sh tools/gto_fulltree/ft_board_setup.sh) || { echo "준비 실패"; exit 1; }
    fi
    [ -x /home/user/gto_ckpt/py311bin/python3 ] || echo "경고: /home/user/gto_ckpt/py311bin/python3 없음 (ft_board_setup.sh 가 만든다)"
    [ -f $ROOT/config.local.json ] || echo '{}' > $ROOT/config.local.json
    $PYBIN -c "import sys; assert sys.version_info >= (3,8)" || { echo "python3 3.8 이상 필요"; exit 1; }
    echo "설치 OK. 시험: bash $(code_dir)/lab_autopilot.sh once   /  시작: bash $(code_dir)/lab_autopilot.sh start" ;;
  run)
    [ -d $(code_dir) ] || { echo "먼저 install"; exit 1; }
    exec 9>$ROOT/state/lab.lock
    flock -n 9 || { echo "이미 돌고 있음"; exit 0; }
    echo $$ > $ROOT/state/lab.pid
    while :; do
      # 매번 current 링크를 다시 읽는다 → 봇이 새 코드로 교체하면(종료코드 75) 바로 새 버전으로 시작
      $PYBIN $ROOT/current/tools/gto_fulltree/lab_autopilot/autopilot.py run >> $ROOT/logs/main.log 2>&1
      rc=$?
      [ -f $ROOT/state/STOP ] && { rm -f $ROOT/state/STOP; break; }
      [ $rc -eq 75 ] && { echo "$(date '+%m-%d %H:%M:%S') 새 코드로 교체 — 바로 다시 시작" >> $ROOT/logs/main.log; continue; }
      echo "$(date '+%m-%d %H:%M:%S') 봇이 끝남(rc=$rc) — 30초 뒤 다시 시작" >> $ROOT/logs/main.log
      sleep 30
    done ;;
  start)
    if [ -f $ROOT/state/lab.pid ] && kill -0 $(cat $ROOT/state/lab.pid) 2>/dev/null; then echo "이미 돌고 있음 (pid $(cat $ROOT/state/lab.pid))"; exit 0; fi
    setsid nohup bash "$ROOT/current/tools/gto_fulltree/lab_autopilot/lab_autopilot.sh" run > /dev/null 2>&1 < /dev/null &
    sleep 3; echo "시작함. 상태: bash $(code_dir)/lab_autopilot.sh status" ;;
  stop)
    touch $ROOT/state/STOP
    [ -f $ROOT/state/lab.pid ] && kill $(cat $ROOT/state/lab.pid) 2>/dev/null
    pkill -TERM -f "lab_autopilot/autopilot.py run" 2>/dev/null
    sleep 2
    pkill -f "lab_autopilot/board_run.py" 2>/dev/null; pkill -f "ft_solve.sh" 2>/dev/null
    for f in $ROOT/state/pgids/*; do [ -f "$f" ] && kill -- -$(basename $f) 2>/dev/null; done
    rm -f $ROOT/state/lab.pid; echo "멈춤" ;;
  status)
    if [ -f $ROOT/state/lab.pid ] && kill -0 $(cat $ROOT/state/lab.pid) 2>/dev/null; then echo "봇: 실행 중 (pid $(cat $ROOT/state/lab.pid))"; else echo "봇: 실행 중 아님"; fi
    if [ -f $ROOT/state/status.json ]; then $PYBIN - <<EOF
import json
d = json.load(open("$ROOT/state/status.json"))
print("상태: %s | 마지막 갱신 %s, 모드 %s, CPU %s/%s 코어, 디스크 여유 %s GB, 코드 %s" % (d["status"].upper(), d["time"], d["mode"], d["cpu"]["in_use"], d["cpu"]["budget"], d["disk_free_gb"], d["code_release"]))
for a in d["alerts"]: print("  경고[%s] %s %s: %s" % (a["severity"], a["code"], a["key"], a["msg"][:140]))
for j in d["jobs"]: print("  하는 중: %sbb 단계%s %s %s" % (j["stack"], j["step"], j["unit"], j["progress"]))
if not d["jobs"]: print("  하는 중: 없음(대기)")
for s, e in d["stacks"].items():
    print("  %sbb 단계 %s: %s — %s" % (s, e["step"], e["phase"], e["why"]))
    v = e.get("verdict")
    if v: print("     판정(단계 %s): %s, D≤U %s, D/U 중앙값 %s" % (v["step"], v["status"], v["pass_D_le_U"], v["dou_median"]))
for e in d["errors"][-3:]: print("  오류:", e["t"], e["key"], e["err"][-90:])
EOF
    fi
    echo "--- 최근 로그"; tail -6 $ROOT/logs/autopilot.log 2>/dev/null
    echo "--- 원격(코디네이터가 보는 곳): git fetch origin claude/lab_status && git show origin/claude/lab_status:status.json" ;;
  logs) tail -${2:-60} $ROOT/logs/autopilot.log ;;
  once) $PYBIN $(code_dir)/autopilot.py once --dry ;;
  *) sed -n 2,12p "$0" ;;
esac
