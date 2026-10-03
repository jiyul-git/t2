#!/bin/sh
# C1a: exact injection-plumbing check at the fixed 100-iteration profile (no iterations): legacy export -> tables -> injected export.
set -e
D=/home/user/gto_ckpt/c1
B=/home/user/t2/vendor/gtopen/target/release/examples
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 T2_CHECKPOINT=$D/ck_fixed.gtop
cd $D
for spec in "btn:fold,fold,fold,fold,fold,fold,raise,fold,call" "co:fold,fold,fold,fold,fold,raise,fold,fold,call" "hj:fold,fold,fold,fold,raise,fold,fold,fold,call" "utg:raise,fold,fold,fold,fold,fold,fold,fold,call" "utg1_ctrl:fold,raise,fold,fold,fold,fold,fold,fold,call"; do
  n=${spec%%:*}; s=${spec#*:}
  [ -s legacy_$n.json ] || $B/t2_cont_terminal /home/user/gto_ckpt/cfg_pilot.json 100 $s legacy_$n.json > /dev/null 2>&1
done
python3 /home/user/t2/tools/gto_validation/pilot9_tables.py legacy $D $D/static_tables
export T2_CONT_FILE=$D/static_tables/manifest.json
for spec in "btn:fold,fold,fold,fold,fold,fold,raise,fold,call" "co:fold,fold,fold,fold,fold,raise,fold,fold,call" "hj:fold,fold,fold,fold,raise,fold,fold,fold,call" "utg:raise,fold,fold,fold,fold,fold,fold,fold,call" "utg1_ctrl:fold,raise,fold,fold,fold,fold,fold,fold,call"; do
  n=${spec%%:*}; s=${spec#*:}
  [ -s injected_$n.json ] || $B/t2_cont_terminal /home/user/gto_ckpt/cfg_pilot.json 100 $s injected_$n.json > /dev/null 2>&1
done
echo C1A_RUNS_DONE
