#!/bin/sh
# 세 명 플랍 실측: 턴·리버 카드 수를 늘려 가며 값이 어디로 모이는지.
# 사용: FT_SESSION=<id> sh tools/gto_3way_probe/run_probe.sh "<board> <n> <balanced|random> <seed> <iters>" ...
# 결과: data/gto_3way_probe/<board>_<mode><seed>_<n>x<n>.json (+ .log), 일 하나 끝날 때마다 커밋·푸시.
set -u
REPO=$(git rev-parse --show-toplevel); cd "$REPO"
BIN=/home/user/calc/vendor/gtopen/target/release/examples/t2_3way
TERM=tools/gto_3way_probe/term3_btn_sb_bb.json
OUT=data/gto_3way_probe; mkdir -p $OUT
for job in "$@"; do
  set -- $job; b=$1; n=$2; mode=$3; seed=$4; it=$5
  name=${b}_${mode}${seed}_${n}x${n}
  [ -f $OUT/$name.json ] && { echo "skip $name"; continue; }
  sel=$(python3 tools/gto_3way_probe/runouts.py $b $n $n $mode $seed); T=${sel% *}; R=${sel#* }
  s=$(date +%s)
  RAYON_NUM_THREADS=4 $BIN solve $TERM $b $it $OUT/$name.json.tmp --turns $T --rivers $R --every 25 --target 0.1 > $OUT/$name.log 2>&1
  rc=$?; echo "rc=$rc sec=$(( $(date +%s) - s )) turns=$T rivers=$R" >> $OUT/$name.log
  [ $rc -eq 0 ] && mv $OUT/$name.json.tmp $OUT/$name.json
  git add $OUT/$name.* && git commit -q -m "3way probe: $name rc=$rc

Claude-Session: https://claude.ai/code/${FT_SESSION:-unknown}"
  for i in 1 2 3 4 5; do git push -q -u origin HEAD && break; sleep $((i*5)); done
  echo "done $name rc=$rc"
done
echo PROBE_ALL_DONE
