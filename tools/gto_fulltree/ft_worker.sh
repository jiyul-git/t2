#!/bin/bash
# 보드 세션용 단일 명령(AI 판단 최소화). 언제 다시 불러도 이어서 한다.
#   bash tools/gto_fulltree/ft_worker.sh <보드번호> <묶음> [<묶음> ...]
# 하는 일: 브랜치 claude/ft<STACK>_board_<n> 준비 → setup(되어 있으면 건너뜀) → ft_board.py 실행
#          (이미 돌고 있으면 붙어서 기다림, 죽으면 남은 하위 프로세스 정리 후 다시 실행) → 최대 FT_WORKER_MIN(기본 110)분 기다림.
# 출력: 마지막 줄 하나만 의미 있음
#   WORKER_ALL_DONE            모든 묶음 done.json 푸시 끝 → 세션 종료
#   WORKER_RUNNING <진행>      아직 계산 중 → 같은 명령을 다시 실행
#   WORKER_FAIL <이유>         같은 자리에서 5번 연속 죽음 등 → 조정 세션이 확인
# 환경: FT_STACK(60), FT_BASE(묶음 목록이 있는 브랜치, 기본 claude/ft60_3way_s5), FT_SESSION.
set -u
N=$1; shift; B="$*"
ST=${FT_STACK:-60}; BASE=${FT_BASE:-claude/ft60_3way_s5}; BR=claude/ft${ST}_board_$N
MIN=${FT_WORKER_MIN:-110}
R=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "WORKER_FAIL not in repo"; exit 1; }
cd "$R"; G=/home/user/gto_ckpt; mkdir -p $G; L=$G/ft_worker.log; BL=$G/ft${ST}_board.log
log() { echo "$(date -u +%H:%M) $*" >> $L; }
# 1) 브랜치(이미 있으면 원격 것을 이어받음). git pull 은 모든 브랜치를 받으므로 쓰지 않는다.
if [ "$(git rev-parse --abbrev-ref HEAD)" != "$BR" ]; then
  if git fetch -q origin "$BR" 2>/dev/null; then git checkout -q -B "$BR" FETCH_HEAD
  else git fetch -q origin "$BASE" && git checkout -q -B "$BR" FETCH_HEAD; fi || { echo "WORKER_FAIL branch"; exit 1; }
  log "branch $BR"
fi
# 2) setup
sh tools/gto_fulltree/ft_board_setup.sh > $G/ft_setup.log 2>&1; tail -1 $G/ft_setup.log | grep -q FT_BOARD_SETUP_OK || { echo "WORKER_FAIL setup: $(tail -1 $G/ft_setup.log)"; exit 1; }
done_local() { for b in $B; do ls data/ft$ST/results/step*/$b/done.json > /dev/null 2>&1 || return 1; done; }
# 끝났으면 커밋·푸시가 원격에 반영됐는지까지 확인(ft_board 가 푸시하지만, 실패했을 때를 대비)
done_all() {
  done_local || return 1
  [ "${FT_NO_PUSH:-}" = 1 ] && return 0
  git add "data/ft$ST/results" && { git diff --cached --quiet || git commit -q -m "ft$ST board $N: worker final commit"; }
  for i in 1 2 3 4 5; do
    [ "$(git ls-remote origin "refs/heads/$BR" | cut -f1)" = "$(git rev-parse HEAD)" ] && return 0
    git push -q -u origin "$BR" 2>/dev/null || sleep $((i*5))
  done
  echo "WORKER_FAIL push"; exit 1
}
prog() { git log -1 --format=%s 2>/dev/null | cut -c1-60; }
launch() {
  pkill -f solve_panel.py 2>/dev/null; pkill -f t2_cont_panel 2>/dev/null; sleep 2
  FT_STACK=$ST FT_SESSION=${FT_SESSION:-worker} setsid nohup $G/py311bin/python3 tools/gto_fulltree/ft_board.py $B >> $BL 2>&1 < /dev/null &
  log "launch $B"
}
done_all && { echo "WORKER_ALL_DONE"; exit 0; }
# 공용 작업판(claude/ft_claims, 연구실 봇과 같은 규칙): 보드 번호를 잡고 30분마다 갱신. 남이 잡고 있으면 시작하지 않는다.
K=$(awk -F'\t' -v b="${B%% *}" '$1==b{print $2}' data/ft$ST/step*/bundles.tsv 2>/dev/null | head -1)
AP=$G/autopilot.py; git show origin/claude/lab_autopilot:tools/gto_fulltree/lab_autopilot/autopilot.py > $AP 2>/dev/null || { git fetch -q origin claude/lab_autopilot && git show FETCH_HEAD:tools/gto_fulltree/lab_autopilot/autopilot.py > $AP; }
OWNER=${FT_OWNER:-worker-${FT_SESSION:-$(hostname)}}
claim() { [ -z "$K" ] && return 0; [ "${FT_NO_PUSH:-}" = 1 ] && return 0; python3 $AP claim $ST $K board_$N --owner "$OWNER" > /dev/null 2>&1; }
claim; rc=$?; [ $rc -eq 3 ] && { echo "WORKER_FAIL claimed by other (ft$ST step$K board_$N)"; exit 1; }
END=$(( $(date +%s) + MIN*60 )); fails=0; last=$(git rev-parse HEAD)
pgrep -f ft_board.py > /dev/null || launch
hb=0
while [ $(date +%s) -lt $END ]; do
  sleep 60; hb=$((hb+1)); [ $((hb % 30)) -eq 0 ] && claim
  if ! pgrep -f ft_board.py > /dev/null; then
    done_all && { [ -n "$K" ] && [ "${FT_NO_PUSH:-}" != 1 ] && python3 $AP release $ST $K board_$N > /dev/null 2>&1; echo "WORKER_ALL_DONE"; exit 0; }
    now=$(git rev-parse HEAD); [ "$now" = "$last" ] && fails=$((fails+1)) || fails=0; last=$now
    [ $fails -ge 5 ] && { echo "WORKER_FAIL died 5x without progress: $(tail -2 $BL | tr '\n' ' ' | cut -c1-150)"; exit 1; }
    launch
  fi
done
echo "WORKER_RUNNING $(prog)"
