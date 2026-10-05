#!/bin/sh
# Plan J gate A2: export all 33 paths at the T checkpoint with the line-resolved manifest (mr2 tree), then compare exactly
# with the original T exports (pilot9_j_gate.py). Resumable; atomic export files.
set -e
R=/home/user/gto_ckpt
G=$R/step3/j/gate
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200
SPECS="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call sb:fold,fold,fold,fold,fold,fold,fold,raise,call lj:fold,fold,fold,raise,fold,fold,fold,fold,call utg2:fold,fold,raise,fold,fold,fold,fold,fold,call utg1:fold,raise,fold,fold,fold,fold,fold,fold,call $(python3 $T/pilot9_t3.py specs)"
mkdir -p $G
[ -s $G/ck_T.gtop ] || { cp $R/step3/t3/T/ck.gtop $G/ck_T.tmp && mv $G/ck_T.tmp $G/ck_T.gtop; }
cd $G
for spec in $SPECS; do n=${spec%%:*}; s=${spec#*:}
  [ -s export_$n.json ] || { T2_CONT_FILE=$R/step3/j/mr2_resolved/manifest.json T2_CHECKPOINT=$G/ck_T.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s export_$n.tmp > /dev/null 2>&1 && mv export_$n.tmp export_$n.json; }
done
cmp -s $R/step3/t3/T/ck.gtop $G/ck_T.gtop && echo "checkpoint unchanged"
python3 $T/pilot9_j_gate.py
