#!/bin/sh
# Plan J solve (resumable): max_raises 3, 4-bet = jam only, 33 line-resolved tables, 100 iterations with checkpoints,
# exports of the 8 SRP paths, the 25 3-bet paths and the 25 4-bet-jam paths, then a census at J. Requires the gate to pass.
set -e
R=/home/user/gto_ckpt
J=$R/step3/j
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 T2_CHECKPOINT_EVERY=10 PREFLOP_MAX_NODES=40000000
python3 -c "import json,sys; sys.exit(0 if json.load(open('/home/user/t2/data/gto_validation/pilot9/step3/j_gate.json'))['pass'] else 1)" || { echo "gate not passed"; exit 1; }
SRP="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call sb:fold,fold,fold,fold,fold,fold,fold,raise,call lj:fold,fold,fold,raise,fold,fold,fold,fold,call utg2:fold,fold,raise,fold,fold,fold,fold,fold,call utg1:fold,raise,fold,fold,fold,fold,fold,fold,call"
TB=$(python3 $T/pilot9_t3.py specs)
JAM=$(for x in $TB; do n=${x%%:*}; s=${x#*:}; echo "${n}_jam:${s%,call},jam,call"; done)
mkdir -p $J/J; cd $J/J
echo "J solve/exports $(date -u +%FT%TZ)"
for spec in $SRP $TB $JAM; do n=${spec%%:*}; s=${spec#*:}
  [ -s export_$n.json ] || { T2_CONT_FILE=$J/mr3_resolved/manifest.json T2_CHECKPOINT=$J/J/ck.gtop $B/t2_cont_terminal $J/cfg_mr3_jam.json 100 $s export_$n.tmp > export_$n.log 2>&1 && mv export_$n.tmp export_$n.json; }
done
echo "J census $(date -u +%FT%TZ)"
[ -s $J/ck_J_census.gtop ] || { cp $J/J/ck.gtop $J/ck_J_census.tmp && mv $J/ck_J_census.tmp $J/ck_J_census.gtop; }
[ -s $J/census_J.json ] || T2_CONT_FILE=$J/mr3_resolved/manifest.json T2_CHECKPOINT=$J/ck_J_census.gtop $B/t2_cont_census $J/cfg_mr3_jam.json 100 $J/census_J.json > $J/census_J.log 2>&1
echo J_DONE
