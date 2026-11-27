#!/bin/bash
# 조정 세션용 한 줄 요약: bash tools/gto_fulltree/ft_status.sh <단계>
# 모든 claude/ft<STACK>_board_* 브랜치(다른 계정·다른 번호 포함)를 보고 bundles.tsv 대비 남은 묶음만 출력한다.
# 새 세션을 띄우기 전에 반드시 이걸로 "남은 묶음"과 "최근 3시간 안에 진행 중인 브랜치"를 확인한다.
ST=${FT_STACK:-60}; K=$1; R=$(git rev-parse --show-toplevel); now=$(date +%s)
git -C $R fetch -q origin "+refs/heads/claude/ft${ST}_board_*:refs/remotes/origin/claude/ft${ST}_board_*" 2>/dev/null
declare -A done live
for ref in $(git -C $R for-each-ref --format='%(refname:short)' "refs/remotes/origin/claude/ft${ST}_board_*"); do
  for b in $(git -C $R ls-tree -r --name-only $ref data/ft$ST/results/step$K 2>/dev/null | grep done.json | awk -F/ '{print $(NF-1)}'); do done[$b]=${ref##*/}; done
  age=$(( (now - $(git -C $R log -1 --format=%ct $ref)) / 60 ))
  s=$(git -C $R log -1 --format=%s $ref); b=$(echo "$s" | grep -o "s${K}_t[0-9]*_[AB]")
  [ -n "$b" ] && [ $age -lt 180 ] && ! echo "$s" | grep -q 'done (' && live[$b]="${ref##*/}(${age}m)"
done
all=$(awk 'NR>1{print $1}' $R/data/ft$ST/step$K/bundles.tsv); n=$(echo "$all" | wc -l); left=""
for b in $all; do [ -z "${done[$b]}" ] && left="$left $b${live[$b]:+@${live[$b]}}"; done
echo "step$K done ${#done[@]}/$n left:${left:- 없음}  (@=최근 3시간 안에 진행 중인 브랜치)"
