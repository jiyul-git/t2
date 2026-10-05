#!/bin/sh
# Step 3a chain (resumable): 25 HU 3-bet terminals -> panel_v1 tables at OL state-2 ranges; 8 SRP tables stay at state 2;
# one preflop solve (100 it) with all 33 tables -> state T, exports of the 8 SRP paths and the 25 3-bet paths. No outer step here.
set -e
R=/home/user/gto_ckpt
D=$R/step3/t3
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 T2_CHECKPOINT_EVERY=10
SRP="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call sb:fold,fold,fold,fold,fold,fold,fold,raise,call lj:fold,fold,fold,raise,fold,fold,fold,fold,call utg2:fold,fold,raise,fold,fold,fold,fold,fold,call utg1:fold,raise,fold,fold,fold,fold,fold,fold,call"
TB=$(python3 $T/pilot9_t3.py specs)
mkdir -p $D/terminals
[ -s $D/ck_s2.gtop ] || { cp $R/ol/s2/ck.gtop $D/ck_s2.tmp && mv $D/ck_s2.tmp $D/ck_s2.gtop; }
echo "T3 exports at state 2 $(date -u +%FT%TZ)"
for spec in $TB; do n=${spec%%:*}; s=${spec#*:}
  [ -s $D/terminals/term_$n.json ] || T2_CONT_FILE=$R/ol/s2/tables/manifest.json T2_CHECKPOINT=$D/ck_s2.gtop \
    $B/t2_cont_terminal $R/cfg_pilot.json 100 $s $D/terminals/term_$n.json > /dev/null 2>&1
done
echo "T3 panels $(date -u +%FT%TZ)"
for spec in $TB; do n=${spec%%:*}
  python3 /home/user/t2/tools/gto_hu_continuation/solve_panel.py $D/terminals/term_$n.json /home/user/t2/data/gto_hu_continuation/menu_m2_single_v1.json \
    /home/user/t2/data/gto_hu_continuation/panel_v1.json $D/$n/flops --workers 4 --threads 1 >> $D/solve.log 2>&1
done
[ -s $D/tables_all/manifest.json ] || python3 $T/pilot9_t3.py tables $D > $D/tables_report.json
echo "T3 preflop $(date -u +%FT%TZ)"
mkdir -p $D/T; cd $D/T
for spec in $SRP $TB; do n=${spec%%:*}; s=${spec#*:}
  [ -s export_$n.json ] || T2_CONT_FILE=$D/tables_all/manifest.json T2_CHECKPOINT=$D/T/ck.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s export_$n.json > /dev/null 2>&1
done
echo T3_DONE
