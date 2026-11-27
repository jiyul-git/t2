#!/bin/sh
# 로컬에서 도는 긴 계산의 로그를 브랜치에 주기적으로 올려 다른 계정도 진행을 볼 수 있게 한다.
#   ft_progress_push.sh <로그파일> <저장소 안 경로> <브랜치> [<지켜볼 pgrep 패턴>]  (패턴 프로세스가 끝나면 마지막으로 한 번 올리고 끝)
L=$1; P=$2; BR=$3; PAT=${4:-}
cd "$(dirname "$0")/../.."
while :; do
  cp "$L" "$P" 2>/dev/null && git add "$P" && ! git diff --cached --quiet && git commit -q -m "진행 기록: $(tail -1 "$L" | cut -c1-70)" && git push -q origin HEAD:"$BR"
  [ -n "$PAT" ] && ! pgrep -f "$PAT" > /dev/null && break
  sleep 1200
done
