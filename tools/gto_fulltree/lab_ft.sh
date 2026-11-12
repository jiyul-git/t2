#!/bin/bash
# 연구실 컴퓨터(우분투 22.04, 8코어, 메모리 약 35GB 사용 가능)에서 ft 보드 묶음을 끝까지 풀고 깃허브에 자동으로 올린다.
#   bash lab_ft.sh run      # 이 창에서 돌린다(WSL 1 은 창을 닫으면 계산도 꺼지므로 창을 열어 둔다)
#   bash lab_ft.sh start    # 백그라운드로 시작(WSL 2·일반 우분투용). 이미 돌고 있으면 아무것도 안 함
#   bash lab_ft.sh status   # 진행 상황(보드별 끝난 묶음, 최근 로그)
#   bash lab_ft.sh stop     # 멈춤(다시 start 하면 올라간 12보드 덩어리는 건너뛰고 이어서)
# 기본: 30bb 1단계, 보드 6~19, 동시에 2개(각 4 worker = 8코어, 메모리 약 17GB).
# 바꾸려면 앞에 붙인다: FT_STACK=30 FT_STEP=1 LAB_BOARDS="6 7 8" LAB_PAR=2 bash lab_ft.sh start
# 보드 브랜치(claude/ft<스택>_board_<n>)마다 자기 작업 폴더(git worktree)에서 돌린다. 같은 번호를 다른 곳(클라우드 세션)에서 동시에 돌리지 말 것.
set -u
S=${FT_STACK:-30}; K=${FT_STEP:-1}
BOARDS=${LAB_BOARDS:-"6 7 8 9 10 11 12 13 14 15 16 17 18 19"}
PAR=${LAB_PAR:-2}
ROOT=${LAB_ROOT:-$HOME/t2lab}
LOG=$ROOT/lab_ft$S.log
mkdir -p $ROOT/logs $ROOT/work $ROOT/lock

# 저장소: 이 스크립트가 들어 있는 체크아웃(또는 LAB_REPO)
if [ -n "${LAB_REPO:-}" ]; then REPO=$LAB_REPO
elif git -C "$(dirname "$0")" rev-parse --show-toplevel >/dev/null 2>&1; then REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
else REPO=$(git rev-parse --show-toplevel 2>/dev/null); fi
[ -n "${REPO:-}" ] && [ -d "$REPO/.git" -o -f "$REPO/.git" ] || { echo "t2 저장소 폴더 안에서 실행하거나 LAB_REPO=<저장소 경로> 를 붙여 주세요"; exit 1; }
# 계산 체크아웃과 파이썬 3.11: 예전에 만든 것이 있으면 그대로 쓴다
for c in "${FT_CALC:-}" /home/user/calc $HOME/calc $ROOT/calc; do [ -n "$c" ] && [ -x "$c/vendor/gtopen/target/release/examples/t2_cont_panel" ] && { CALC=$c; break; }; done
for p in "${LAB_PY:-}" /home/user/gto_ckpt/py311bin/python3 $HOME/gto_ckpt/py311bin/python3 $ROOT/py311/bin/python; do [ -n "$p" ] && [ -x "$p" ] && { PY=$p; break; }; done

say() { echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a $LOG; }

setup() {
  if [ -z "${CALC:-}" ]; then
    CALC=$ROOT/calc
    say "계산 체크아웃 만들기: $CALC (처음 한 번, 10~20분, cargo 필요)"
    CEN=79a9aca658a2c1fcbec7e24d910429a2a8e79917
    git -C $REPO fetch -q --depth=1 origin chatgpt/terminal-census-v2-20260930 || return 1
    [ "$(git -C $REPO rev-parse FETCH_HEAD)" = "$CEN" ] || { say "census 커밋이 다름"; return 1; }
    [ -d $CALC ] || git -C $REPO worktree add --no-checkout $CALC $CEN || return 1
    git -C $CALC sparse-checkout set vendor/gtopen tools/gto_spot tools/gto_validation tools/gto_hu_continuation data/gto_hu_continuation data/gto_terminal_expansion/terminals
    git -C $CALC checkout -q $CEN
    git -C $REPO show origin/claude/ft${S}_coord:tools/gto_fulltree/t2_cont_panel_strategy.patch > $ROOT/strategy.patch
    git -C $CALC apply --check $ROOT/strategy.patch 2>/dev/null && git -C $CALC apply $ROOT/strategy.patch
    (cd $CALC/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel) || return 1
  fi
  grep -q T2_EXPORT_STRATEGY $CALC/vendor/gtopen/crates/solver/examples/t2_cont_panel.rs || { say "전략 저장 패치 없음: $CALC"; return 1; }
  if [ -z "${PY:-}" ]; then
    command -v python3.11 >/dev/null || { say "python3.11 이 없음: sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt install -y python3.11 python3.11-venv"; return 1; }
    python3.11 -m venv $ROOT/py311 && $ROOT/py311/bin/pip install -q numpy==2.4.6 || return 1
    PY=$ROOT/py311/bin/python
  fi
  $PY -c "import numpy; assert numpy.__version__ == '2.4.6'" || { say "numpy 2.4.6 아님: $PY"; return 1; }
  say "준비 OK: 저장소 $REPO, 계산 $CALC, 파이썬 $PY"
}

# 보드 n 하나: 자기 worktree 에서 자기 묶음을 끝까지. 죽으면 같은 명령으로 이어서(최대 5번 연속 실패면 그 보드는 건너뜀)
run_board() {
  n=$1; W=$ROOT/b$n; BR=claude/ft${S}_board_$n; L=$ROOT/logs/board$n.log
  for i in 1 2 3 4; do git -C $REPO fetch -q origin "+refs/heads/claude/ft${S}_coord:refs/remotes/origin/claude/ft${S}_coord" && break || sleep $((2 ** i)); done
  # 이미 그 브랜치가 어딘가(예: 저장소 본 폴더)에 체크아웃돼 있으면 거기서 돌린다(올리지 못한 커밋을 지키기 위해)
  here=$(git -C $REPO worktree list --porcelain | awk -v b="refs/heads/$BR" '/^worktree /{w=substr($0,10)} $0=="branch "b{print w}')
  [ -n "$here" ] && W=$here
  if [ ! -d $W ]; then
    if git -C $REPO show-ref -q --verify refs/heads/$BR; then
      git -C $REPO worktree add -q $W $BR || { say "보드 $n: 작업 폴더를 못 만듦"; return 1; }
    elif git -C $REPO ls-remote --exit-code origin $BR >/dev/null 2>&1; then
      git -C $REPO fetch -q origin "+refs/heads/$BR:refs/remotes/origin/$BR"
      git -C $REPO worktree add -q -b $BR $W origin/$BR || { say "보드 $n: 작업 폴더를 못 만듦"; return 1; }
    else
      git -C $REPO worktree add -q -b $BR $W origin/claude/ft${S}_coord || { say "보드 $n: 작업 폴더를 못 만듦"; return 1; }
    fi
  fi
  [ "$(git -C $W rev-parse --abbrev-ref HEAD)" = "$BR" ] || { say "보드 $n: $W 가 $BR 이 아님"; return 1; }
  git -C $W pull -q --no-edit origin $BR 2>/dev/null
  git -C $W merge -q --no-edit origin/claude/ft${S}_coord || { say "보드 $n: coord 병합 충돌 — 손으로 확인 필요"; return 1; }
  B=$(awk -F'\t' -v n=$n 'NR>1 && $2==n {print $1}' $W/data/ft$S/step$K/assign.tsv | tr '\n' ' ')
  [ -n "$B" ] || { say "보드 $n: 배분된 묶음 없음"; return 0; }
  [ -n "${LAB_DRY:-}" ] && { say "보드 $n: (시험) 작업 폴더 $W, 묶음 $B"; return 0; }
  fails=0
  while :; do
    left=0; for b in $B; do [ -f $W/data/ft$S/results/step$K/$b/done.json ] || left=$((left+1)); done
    [ $left -eq 0 ] && { say "보드 $n: 끝 ($B)"; return 0; }
    say "보드 $n: 시작/재개 — 남은 묶음 $left ($B)"
    (cd $W && FT_STACK=$S FT_CALC=$CALC FT_WORK=$ROOT/work/ft${S}_b$n SPOT_PANEL_WORKERS=${LAB_WORKERS:-4} FT_SESSION=lab \
       $PY tools/gto_fulltree/ft_board.py $B >> $L 2>&1)
    if tail -1 $L | grep -q FT_BOARD_ALL_DONE; then continue; fi
    fails=$((fails+1)); say "보드 $n: 멈춤($fails번째). 마지막 줄: $(tail -1 $L)"
    if tail -5 $L | grep -q "input sha256 differs"; then say "보드 $n: 입력이 바뀜 — 이 보드는 멈춤(조정 쪽 확인 필요)"; return 1; fi
    [ $fails -ge 5 ] && { say "보드 $n: 5번 연속 실패 — 건너뜀. 로그 $L"; return 1; }
    sleep 60
    git -C $W pull -q --no-edit origin $BR 2>/dev/null; git -C $W merge -q --no-edit origin/claude/ft${S}_coord 2>/dev/null
  done
}

# 일꾼: 보드 목록에서 아직 아무도 안 잡은 번호를 하나씩 가져간다(mkdir 잠금)
worker() {
  for n in $BOARDS; do
    mkdir $ROOT/lock/ft${S}_b$n 2>/dev/null || continue
    run_board $n
  done
}

case "${1:-}" in
  start)
    if [ -f $ROOT/lab.pid ] && kill -0 $(cat $ROOT/lab.pid) 2>/dev/null; then echo "이미 돌고 있음 (pid $(cat $ROOT/lab.pid)). 상태: bash $0 status"; exit 0; fi
    setsid nohup bash "$0" run > $ROOT/logs/main.log 2>&1 < /dev/null &
    echo $! > $ROOT/lab.pid; sleep 2; echo "시작함 (pid $(cat $ROOT/lab.pid)). 상태 보기: bash $0 status"; tail -3 $LOG 2>/dev/null ;;
  run)
    echo $$ > $ROOT/lab.pid
    setup || { say "준비 실패 — 위 메시지 확인"; exit 1; }
    rm -rf $ROOT/lock/*
    for j in $(seq 1 $PAR); do worker & sleep 5; done
    wait; say "모든 보드 처리 끝: $BOARDS"; rm -f $ROOT/lab.pid ;;
  stop)
    [ -f $ROOT/lab.pid ] && kill -- -$(cat $ROOT/lab.pid) 2>/dev/null; pkill -f "ft_board.py" ; pkill -f solve_panel.py; rm -f $ROOT/lab.pid; echo "멈춤" ;;
  status)
    if [ -f $ROOT/lab.pid ] && kill -0 $(cat $ROOT/lab.pid) 2>/dev/null; then echo "실행 중 (pid $(cat $ROOT/lab.pid))"; else echo "실행 중 아님"; fi
    for n in $BOARDS; do W=$ROOT/b$n; h=$(git -C $REPO worktree list --porcelain | awk -v b="refs/heads/claude/ft${S}_board_$n" '/^worktree /{w=substr($0,10)} $0=="branch "b{print w}'); [ -n "$h" ] && W=$h; [ -d $W ] || { echo "보드 $n: 아직 안 시작"; continue; }
      B=$(awk -F'\t' -v n=$n 'NR>1 && $2==n {print $1}' $W/data/ft$S/step$K/assign.tsv | tr '\n' ' '); d=0; t=0
      for b in $B; do t=$((t+1)); [ -f $W/data/ft$S/results/step$K/$b/done.json ] && d=$((d+1)); done
      echo "보드 $n: $d/$t  마지막 커밋 $(git -C $W log -1 --format='%cd %s' --date=format:'%m-%d %H:%M' | cut -c1-70)"; done
    echo "--- 최근 로그"; tail -8 $LOG 2>/dev/null ;;
  *) sed -n 2,8p "$0" ;;
esac
