#!/bin/sh
# OL chain (resumable): step k panels at state k -> D / U, stop decision, damped tables -> state k+1 preflop solve -> next step.
# usage: pilot9_ol_run.sh [k_start]   (state 0 = h1/H must exist)
set -e
R=/home/user/gto_ckpt
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 T2_CHECKPOINT_EVERY=10
SPECS="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call sb:fold,fold,fold,fold,fold,fold,fold,raise,call lj:fold,fold,fold,raise,fold,fold,fold,fold,call utg2:fold,fold,raise,fold,fold,fold,fold,fold,call utg1:fold,raise,fold,fold,fold,fold,fold,fold,call"
k=${1:-0}
while [ $k -lt 3 ]; do
  S=$R/ol/step$k
  python3 $T/pilot9_ol.py prep $k
  echo "OL step $k panels $(date -u +%FT%TZ)"
  for spec in $SPECS; do n=${spec%%:*}
    python3 /home/user/t2/tools/gto_hu_continuation/solve_panel.py $S/terminals/export_$n.json /home/user/t2/data/gto_hu_continuation/menu_m2_single_v1.json \
      /home/user/t2/data/gto_hu_continuation/panel_v1.json $S/$n/flops --workers 4 --threads 1 >> $S/solve.log 2>&1
  done
  [ -s $S/report.json ] || python3 $T/pilot9_ol.py step $k > $S/step.out
  grep -q '"decision": "continue' $S/report.json || { echo "OL stop at step $k"; echo OL_DONE; exit 0; }
  k1=$((k+1)); N=$R/ol/s$k1
  echo "OL state $k1 preflop $(date -u +%FT%TZ)"
  cd $N
  for spec in $SPECS; do n=${spec%%:*}; s=${spec#*:}
    [ -s export_$n.json ] || T2_CONT_FILE=$N/tables/manifest.json T2_CHECKPOINT=$N/ck.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s export_$n.json > /dev/null 2>&1
  done
  k=$k1
done
echo OL_DONE
