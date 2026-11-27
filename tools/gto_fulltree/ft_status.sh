#!/bin/bash
# 조정 세션용 한 줄 요약: bash tools/gto_fulltree/ft_status.sh <단계> <보드 첫번호> <끝번호> [기대 묶음 수]
# 출력: done N/기대, 그리고 3시간 넘게 커밋 없는 보드만 "번호:진행(분)".
ST=${FT_STACK:-60}; K=$1; A=$2; Z=$3; EXP=${4:-?}; now=$(date +%s); tot=0; stale=""
for n in $(seq $A $Z); do
  git fetch -q origin claude/ft${ST}_board_$n 2>/dev/null || { stale="$stale $n:없음"; continue; }
  c=$(git ls-tree -r --name-only FETCH_HEAD data/ft$ST/results/step$K 2>/dev/null | grep -c done.json); tot=$((tot+c))
  age=$(( (now - $(git log -1 --format=%ct FETCH_HEAD)) / 60 ))
  [ $age -gt 180 ] && ! git log -1 --format=%s FETCH_HEAD | grep -q 'done (' && stale="$stale $n:$(git log -1 --format=%s FETCH_HEAD | grep -o '[0-9]*/72')(${age}m)"
done
echo "done $tot/$EXP stale:${stale:- 없음}"
