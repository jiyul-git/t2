#!/bin/sh
# GTO 기록을 각 계산 브랜치에서 꺼내 한 폴더에 모은다(빌더·비교 도구 입력).
#   sh tools/t2_handoff/fetch_records.sh <출력폴더>
# 새 기록이 생기면 아래 목록에 한 줄 추가한다. 기록 형식은 docs/T2_HANDOFF.md 2장.
set -e
OUT="${1:?출력 폴더}"; mkdir -p "$OUT"
git fetch -q origin claude/pushfold-10-25-20261019 claude/p30-flat-20261019 chatgpt/terminal-census-v2-20260930
PF=origin/claude/pushfold-10-25-20261019        # 10~25bb 푸시/폴드 + 30/40bb 부모 트리
P30=origin/claude/p30-flat-20261019             # 30bb 플랫콜 루프 (011TJ 세션)
CEN=origin/chatgpt/terminal-census-v2-20260930  # 40bb 플랫콜 루프 + 60bb (Gto제작 세션)
for b in pf10 pf15 pf20 pf25 s30 s40; do git show $PF:data/gto_spot/records/$b.json > "$OUT/$b.json"; done
git show $CEN:data/gto_spot/records/s60.json > "$OUT/s60.json"
for f in $(git ls-tree --name-only $P30 data/gto_spot/quick/ | grep 'p30_flat_.*\.json$'); do git show $P30:$f > "$OUT/$(basename $f)"; done
for f in $(git ls-tree --name-only $CEN data/gto_spot/quick/ | grep 'p40_flat_.*\.json$'); do git show $CEN:$f > "$OUT/$(basename $f)"; done
ls "$OUT"
