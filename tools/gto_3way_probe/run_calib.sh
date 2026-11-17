#!/bin/bash
# 정답(전체 플랍) 보정용: 한 플랍을 일부 카드로 세 가지 방식으로 푼다(같은 끝점 term3_btn_sb_bb).
#   bash tools/gto_3way_probe/run_calib.sh <board>
#   disjoint_8x8 (지금 표 방식) / overlap_8 / overlap_12 (턴·리버 같은 카드 묶음)
# 결과: data/gto_3way_probe/calib/<board>_<방식>.json, 하나 끝날 때마다 현재 브랜치에 커밋·푸시. 이미 있는 것은 건너뜀.
set -u
B=$1; REPO=$(git rev-parse --show-toplevel); cd "$REPO"
BIN=/home/user/calc/vendor/gtopen/target/release/examples/t2_3way
TERM=tools/gto_3way_probe/term3_btn_sb_bb.json; O=data/gto_3way_probe/calib; mkdir -p $O
run() {  # name turns rivers
  [ -f $O/${B}_$1.json ] && { echo "skip $1"; return; }
  RAYON_NUM_THREADS=$(nproc) $BIN solve $TERM $B 400 $O/${B}_$1.json.tmp --turns $2 --rivers $3 --every 25 --target 0.1 > $O/${B}_$1.log 2>&1
  [ -f $O/${B}_$1.json.tmp ] || { echo "FAIL $1"; return; }
  mv $O/${B}_$1.json.tmp $O/${B}_$1.json; rm -f $O/${B}_$1.json.tmp.partial
  git add $O/${B}_$1.json $O/${B}_$1.log && git commit -q -m "3way calib $B $1" && for i in 1 2 3 4 5; do git push -q -u origin HEAD && break; sleep $((i*5)); done
  echo "done $1"
}
read T8 R8 <<< "$(python3 tools/gto_3way_probe/runouts.py $B 8 8 balanced)"
run disjoint_8x8 $T8 $R8
read U8 _ <<< "$(python3 tools/gto_3way_probe/runouts.py $B 8 8 balanced)"
run overlap_8 $U8 $U8
read U12 _ <<< "$(python3 tools/gto_3way_probe/runouts.py $B 12 12 balanced)"
run overlap_12 $U12 $U12
echo CALIB_ALL_DONE
