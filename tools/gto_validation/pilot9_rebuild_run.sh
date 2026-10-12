#!/bin/sh
# Rebuild chain (resumable) after the loss of /home/user/gto_ckpt (container reset, 2026-10-12): reproduce the J inputs with the
# original scripts, seeds and config, then the J2 solve to the G2 target. Stage outputs are checked against the committed
# evidence (pilot9_rebuild_check.py, data/gto_validation/pilot9/rebuild/). Exact mode (no multiway skip) for every mr2 stage.
#   S   : C3 preflop solve with the committed C2 tables (data/gto_validation/pilot9/c2/solved_tables)
#   H1  : pilot9_h1_run.sh                OL : pilot9_ol_run.sh with OL_KMAX=2 (states 1, 2; step-2 panels are not inputs of J)
#   T3  : pilot9_t3_run.sh, tables only   L  : line-keyed tables -> mr3_resolved (0-iteration censuses of both trees)
#   J2  : pilot9_j2_run.sh
set -e
R=/home/user/gto_ckpt
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
D=/home/user/t2/data/gto_validation/pilot9
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 T2_CHECKPOINT_EVERY=10
mkdir -p $R/c2/solved_tables $R/c3 $R/step3/j
[ -s $R/cfg_pilot.json ] || cp $D/cfg_pilot.json $R/cfg_pilot.json
[ -s $R/c2/solved_tables/manifest.json ] || cp $D/c2/solved_tables/*.json $R/c2/solved_tables/
echo "S $(date -u +%FT%TZ)"
cd $R/c3
for spec in btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call utg1_ctrl:fold,raise,fold,fold,fold,fold,fold,fold,call; do
  n=${spec%%:*}; s=${spec#*:}
  [ -s export_$n.json ] || { T2_CONT_FILE=$R/c2/solved_tables/manifest.json T2_CHECKPOINT=$R/c3/ck.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s export_$n.tmp > /dev/null 2>&1 && mv export_$n.tmp export_$n.json; }
done
python3 $T/pilot9_rebuild_check.py S
grep -q H1_DONE $R/h1/done 2>/dev/null || { sh $T/pilot9_h1_run.sh && echo H1_DONE > $R/h1/done; }
python3 $T/pilot9_rebuild_check.py H
grep -q OL_DONE $R/ol/done 2>/dev/null || { OL_KMAX=2 sh $T/pilot9_ol_run.sh 0 && echo OL_DONE > $R/ol/done; }
python3 $T/pilot9_rebuild_check.py OL
grep -q T3_DONE $R/step3/t3/done 2>/dev/null || { T3_SKIP_PREFLOP=1 sh $T/pilot9_t3_run.sh && echo T3_DONE > $R/step3/t3/done; }
python3 $T/pilot9_rebuild_check.py T3
J=$R/step3/j
echo "L $(date -u +%FT%TZ)"
[ -s $J/census_mr2_0it.json ] || { cd $J && $B/t2_cont_census $R/cfg_pilot.json 0 $J/census_mr2_0it.tmp > $J/census_mr2_0it.log 2>&1 && mv $J/census_mr2_0it.tmp $J/census_mr2_0it.json; }
[ -s $J/lines/line_manifest.json ] || python3 $T/pilot9_linekey.py tolines $R/step3/t3/tables_all/manifest.json $J/census_mr2_0it.json $J/lines > $J/tolines.log
[ -s $J/cfg_mr3_jam.json ] || cp $D/step3/cfg_mr3_jam.json $J/cfg_mr3_jam.json
[ -s $J/census_mr3_0it.json ] || { cd $J && PREFLOP_MAX_NODES=40000000 $B/t2_cont_census $J/cfg_mr3_jam.json 0 $J/census_mr3_0it.tmp > $J/census_mr3_0it.log 2>&1 && mv $J/census_mr3_0it.tmp $J/census_mr3_0it.json; }
[ -s $J/mr3_resolved/manifest.json ] || python3 $T/pilot9_linekey.py resolve $J/lines/line_manifest.json $J/census_mr3_0it.json $J/mr3_resolved > $J/resolve.log
python3 $T/pilot9_rebuild_check.py L
sh $T/pilot9_j2_run.sh
