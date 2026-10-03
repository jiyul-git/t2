#!/bin/sh
# pilot9 S chain (resumable): C1b frozen-static control -> C2 panel_v1 flops at the 4 terminals -> C3 one outer step. Stops after C3.
set -e
R=/home/user/gto_ckpt
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 T2_CHECKPOINT_EVERY=10
SPECS="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call utg1_ctrl:fold,raise,fold,fold,fold,fold,fold,fold,call"
arm() {  # arm <dir> <manifest>: 100 iterations from scratch with T2_CONT_FILE, checkpointed, then the 5 path exports
  mkdir -p $1; cd $1
  for spec in $SPECS; do n=${spec%%:*}; s=${spec#*:}
    [ -s export_$n.json ] || T2_CONT_FILE=$2 T2_CHECKPOINT=$1/ck.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s export_$n.json > /dev/null 2>&1
  done
}
echo "C1b start $(date -u +%FT%TZ)"
arm $R/c1b $R/c1/static_tables/manifest.json
echo "C2 start $(date -u +%FT%TZ)"
mkdir -p $R/c2/terminals
for n in btn co hj utg; do cp -n $R/c1/legacy_$n.json $R/c2/terminals/ 2>/dev/null || true; done
for n in btn co hj utg; do
  python3 /home/user/t2/tools/gto_hu_continuation/solve_panel.py $R/c2/terminals/legacy_$n.json /home/user/t2/data/gto_hu_continuation/menu_m2_single_v1.json \
    /home/user/t2/data/gto_hu_continuation/panel_v1.json $R/c2/$n/flops --workers 4 --threads 1 >> $R/c2/solve.log 2>&1
done
python3 $T/pilot9_tables.py solved $R/c2 $R/c2/solved_tables > $R/c2/tables_report.json
echo "C3 start $(date -u +%FT%TZ)"
arm $R/c3 $R/c2/solved_tables/manifest.json
echo PILOT9_S_DONE
