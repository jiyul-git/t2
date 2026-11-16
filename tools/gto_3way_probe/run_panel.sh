#!/bin/sh
# 세 명 끝점 하나 × 균형 패널 A 플랍 일부를 턴·리버 고르게 8장씩으로 푼다(목표 0.3% pot, 2명 패널과 같은 기준).
# 사용: FT_SESSION=<id> sh tools/gto_3way_probe/run_panel.sh <끝점 번호 00~09> <시작> <끝(미포함)>
# 결과: data/gto_3way_panel/tNN/<보드>.json (trace 뺀 요약). 4장마다 커밋·푸시. 이미 있는 보드는 건너뜀.
set -u
T=$1; A=$2; Z=$3; N=${NRO:-8}
REPO=$(git rev-parse --show-toplevel); cd "$REPO"
BIN=/home/user/calc/vendor/gtopen/target/release/examples/t2_3way
PY=/home/user/gto_ckpt/py311bin/python3; [ -x $PY ] || PY=python3
OUT=data/gto_3way_panel/t$T; mkdir -p $OUT
BOARDS=$($PY -c "import json;p=json.load(open('data/ft60/panels/panel_bal_A72.json'))['panel'];print(' '.join(x['board'] for x in p[$A:$Z]))")
k=0
for b in $BOARDS; do
  [ -f $OUT/$b.json ] && continue
  sel=$($PY tools/gto_3way_probe/runouts.py $b $N $N balanced 0); TU=${sel% *}; RV=${sel#* }
  s=$(date +%s)
  RAYON_NUM_THREADS=4 $BIN solve data/gto_3way_panel/terms/t$T.json $b 400 $OUT/$b.tmp --turns $TU --rivers $RV --every 25 --target 0.3 > $OUT/$b.log 2>&1
  rc=$?; echo "rc=$rc sec=$(( $(date +%s) - s ))" >> $OUT/$b.log
  if [ $rc -eq 0 ]; then
    $PY -c "import json,sys;d=json.load(open(sys.argv[1]));d['trace']=d['trace'][-2:] if isinstance(d['trace'],list) else None;d['runouts']=sys.argv[3];json.dump(d,open(sys.argv[2],'w'))" $OUT/$b.tmp $OUT/$b.json "$sel"
  fi
  rm -f $OUT/$b.tmp $OUT/$b.tmp.partial
  k=$((k+1))
  if [ $((k % 4)) -eq 0 ]; then
    git add $OUT && git commit -q -m "3way panel t$T: $(ls $OUT/*.json | wc -l) boards" && for i in 1 2 3 4 5; do git push -q -u origin HEAD && break; sleep $((i*5)); done
  fi
done
git add $OUT && git commit -q -m "3way panel t$T [$A:$Z]: done" ; for i in 1 2 3 4 5; do git push -q -u origin HEAD && break; sleep $((i*5)); done
echo PANEL_ALL_DONE
