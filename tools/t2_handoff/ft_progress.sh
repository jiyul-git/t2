#!/bin/sh
# GTO 전체 트리 보드 진행 세기 (읽기만 함).
# 사용: sh tools/t2_handoff/ft_progress.sh 60 1   ← 스택 60bb, 단계 1
# 출력: 보드 세션 번호마다 "끝난 묶음/맡은 묶음", 마지막 커밋 시각(UTC)
# 브랜치는 하나씩 가져온다(없는 브랜치가 섞이면 한꺼번에 가져오기가 통째로 실패한다).
set -u
S=${1:?스택(30/40/60/100)}
K=${2:?단계(0~3)}
git fetch -q origin "claude/ft${S}_coord" || { echo "조정 브랜치 없음: claude/ft${S}_coord"; exit 1; }
A=$(git show "origin/claude/ft${S}_coord:data/ft${S}/step${K}/assign.tsv" 2>/dev/null) || { echo "배분표 없음: data/ft${S}/step${K}/assign.tsv"; exit 1; }
td=0; ta=0
for n in $(seq 1 20); do
  a=$(printf '%s\n' "$A" | awk -F'\t' -v n="$n" 'NR>1 && $2==n' | wc -l)
  [ "$a" -eq 0 ] && continue
  r="origin/claude/ft${S}_board_$n"
  if git fetch -q origin "claude/ft${S}_board_$n" 2>/dev/null; then
    d=$(git ls-tree -r --name-only "$r" -- "data/ft${S}/results/step${K}" | grep -c 'done.json$')
    t=$(git log -1 --format='%cd' --date=format-local:'%m-%d %H:%M' "$r" 2>/dev/null)
  else
    d=0; t="브랜치 없음"
  fi
  printf '보드 %2s: %s/%s  마지막 커밋 %s UTC\n' "$n" "$d" "$a" "$t"
  td=$((td+d)); ta=$((ta+a))
done
echo "ft${S} ${K}단계: 끝난 묶음 ${td}/${ta}"
