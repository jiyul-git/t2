#!/bin/bash
# 조정 자동 진행(AI 토큰 0). 30분마다 상태를 보고 조건이 되면 다음 일을 시작한다. 한 일은 표시 파일로 한 번만.
#   setsid nohup bash pm_daemon.sh <coord60 폴더> <coord100 폴더> > ~/pm_daemon.log 2>&1 &
# 규칙: (1) ft60 6단계 묶음이 모두 끝나면 GHA 한 단계 실행(claude/gha_step_60_s7) 푸시
#       (2) ft100 2단계 트리 풀이가 끝나면 로컬 ft_step.sh 1 → prepare 2 → GHA 보드 시작, claim 풀고 RUNNING.md 갱신
C60=$1; C100=$2; M=/home/user/gto_ckpt/pm_marks; mkdir -p $M
AP=/home/user/gto_ckpt/autopilot.py
log() { echo "$(date -u +%m-%dT%H:%M) $*"; }
while :; do
  if [ ! -f $M/ft60_s7 ]; then
    out=$(cd $C60 && git fetch -q origin claude/ft60_3way_s5 && git merge -q --ff-only FETCH_HEAD 2>/dev/null; bash tools/gto_fulltree/ft_status.sh 6 2>/dev/null | tail -1); log "ft60 $out"
    if echo "$out" | grep -q 'left: 없음'; then
      T=$(mktemp -d); git -C $C60 worktree add -q --detach $T origin/claude/ft60_3way_s5 && ( cd $T && echo "60 6 claude/ft60_3way_s5" > gha_step.txt && git add gha_step.txt && git commit -q -m "gha step: ft60 6→7" && git push -q origin HEAD:refs/heads/claude/gha_step_60_s7 ) && touch $M/ft60_s7 && log "ft60 7단계 GHA 시작"
      git -C $C60 worktree remove --force $T 2>/dev/null
    fi
  fi
  if [ ! -f $M/ft100_s2 ] && [ -s /home/user/gto_ckpt/ft100c/solve_s2/final_n ] && [ -s /home/user/gto_ckpt/ft100c/solve_s2/dump.jsonl ] && ! pgrep -f "ft_solve.sh 2" > /dev/null; then
    log "ft100 2단계 풀이 끝 → ft_step 1"
    if (cd $C100 && FT_STACK=100 FT_PREP_ENV="FT_MIN_REACH=1e-3" bash tools/gto_fulltree/ft_step.sh 1 > /home/user/gto_ckpt/ft100_step1.log 2>&1); then
      touch $M/ft100_s2; log "ft100: $(tail -1 /home/user/gto_ckpt/ft100_step1.log)"
      [ -f $AP ] && python3 $AP release 100 2 coord_solve --owner cloud-coord-session_01XV9GKU > /dev/null 2>&1
      (cd $C100 && printf '# 지금 돌고 있는 계산\n\n| 무엇 | 어디서 | 시작(UTC) |\n|---|---|---|\n| ft100 2단계 보드 묶음 전부 | GitHub Actions(claude/gha_ft_100_s2) | %s |\n' "$(date -u +%FT%H:%M)" > data/ft100/RUNNING.md && git add data/ft100/RUNNING.md && git commit -q -m "RUNNING: ft100 2단계 보드는 GHA" && git push -q origin HEAD:claude/ft100_coord)
    else log "ft100 ft_step 실패: $(tail -2 /home/user/gto_ckpt/ft100_step1.log | tr '\n' ' ')"; touch $M/ft100_s2_failed; fi
  fi
  [ -f $M/ft60_s7 ] && { [ -f $M/ft100_s2 ] || [ -f $M/ft100_s2_failed ]; } && { log "할 일 끝 — 종료"; break; }
  sleep 1800
done
