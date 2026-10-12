#!/bin/sh
# Rebuild chain (resumable) after the loss of /home/user/gto_ckpt (container reset, 2026-10-12): reproduce the J inputs with the
# original scripts, seeds and config, then the J2 solve to the G2 target. Stage outputs are checked against the committed
# evidence (pilot9_rebuild_check.py, data/gto_validation/pilot9/rebuild/). Exact mode (no multiway skip) for every mr2 stage.
#   O   : 100-iteration static profile (ck_fixed) + legacy exports (pilot9_c1a.sh paths)
#   C2  : panel_v1 flops at the 4 S-pilot terminals (OL step 0 needs the per-board values), tables checked vs the committed ones
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
die() { echo "REBUILD FAIL: $*"; exit 1; }
SPECS5="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call utg1_ctrl:fold,raise,fold,fold,fold,fold,fold,fold,call"
mkdir -p $R/c1 $R/c2/solved_tables $R/c2/terminals $R/c3 $R/step3/j
[ -s $R/cfg_pilot.json ] || cp $D/cfg_pilot.json $R/cfg_pilot.json
[ -s $R/c2/solved_tables/manifest.json ] || cp $D/c2/solved_tables/*.json $R/c2/solved_tables/
echo "O $(date -u +%FT%TZ)"
cd $R/c1
for spec in $SPECS5; do n=${spec%%:*}; s=${spec#*:}
  if [ ! -s legacy_$n.json ]; then
    T2_CHECKPOINT=$R/c1/ck_fixed.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s legacy_$n.tmp > /dev/null 2>&1 || die "O export $n"
    mv legacy_$n.tmp legacy_$n.json
  fi
done
python3 $T/pilot9_rebuild_check.py O || die "check O"
echo "C2 $(date -u +%FT%TZ)"
for n in btn co hj utg; do
  [ -s $R/c2/terminals/legacy_$n.json ] || cp $R/c1/legacy_$n.json $R/c2/terminals/
  python3 /home/user/t2/tools/gto_hu_continuation/solve_panel.py $R/c2/terminals/legacy_$n.json /home/user/t2/data/gto_hu_continuation/menu_m2_single_v1.json \
    /home/user/t2/data/gto_hu_continuation/panel_v1.json $R/c2/$n/flops --workers 4 --threads 1 >> $R/c2/solve.log 2>&1 || die "C2 panel $n"
done
[ -s $R/c2/rebuilt_tables/manifest.json ] || python3 $T/pilot9_tables.py solved $R/c2 $R/c2/rebuilt_tables > $R/c2/tables_report.json || die "C2 tables"
python3 $T/pilot9_rebuild_check.py C2 || die "check C2"
echo "S $(date -u +%FT%TZ)"
cd $R/c3
for spec in $SPECS5; do n=${spec%%:*}; s=${spec#*:}
  if [ ! -s export_$n.json ]; then
    T2_CONT_FILE=$R/c2/solved_tables/manifest.json T2_CHECKPOINT=$R/c3/ck.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s export_$n.tmp > /dev/null 2>&1 || die "S export $n"
    mv export_$n.tmp export_$n.json
  fi
done
python3 $T/pilot9_rebuild_check.py S || die "check S"
if ! grep -q H1_DONE $R/h1/done 2>/dev/null; then sh $T/pilot9_h1_run.sh || die H1; echo H1_DONE > $R/h1/done; fi
python3 $T/pilot9_rebuild_check.py H || die "check H"
if ! grep -q OL_DONE $R/ol/done 2>/dev/null; then OL_KMAX=2 sh $T/pilot9_ol_run.sh 0 || die OL; [ -s $R/ol/s2/ck.gtop ] || die "OL: no state 2"; echo OL_DONE > $R/ol/done; fi
python3 $T/pilot9_rebuild_check.py OL || die "check OL"
if ! grep -q T3_DONE $R/step3/t3/done 2>/dev/null; then T3_SKIP_PREFLOP=1 sh $T/pilot9_t3_run.sh || die T3; [ -s $R/step3/t3/tables_all/manifest.json ] || die "T3: no tables"; echo T3_DONE > $R/step3/t3/done; fi
python3 $T/pilot9_rebuild_check.py T3 || die "check T3"
J=$R/step3/j
echo "L $(date -u +%FT%TZ)"
cd $J
if [ ! -s census_mr2_0it.json ]; then $B/t2_cont_census $R/cfg_pilot.json 0 census_mr2_0it.tmp > census_mr2_0it.log 2>&1 || die "census mr2"; mv census_mr2_0it.tmp census_mr2_0it.json; fi
[ -s lines/line_manifest.json ] || python3 $T/pilot9_linekey.py tolines $R/step3/t3/tables_all/manifest.json census_mr2_0it.json lines > tolines.log || die tolines
[ -s cfg_mr3_jam.json ] || cp $D/step3/cfg_mr3_jam.json cfg_mr3_jam.json
if [ ! -s census_mr3_0it.json ]; then PREFLOP_MAX_NODES=40000000 $B/t2_cont_census cfg_mr3_jam.json 0 census_mr3_0it.tmp > census_mr3_0it.log 2>&1 || die "census mr3"; mv census_mr3_0it.tmp census_mr3_0it.json; fi
[ -s mr3_resolved/manifest.json ] || python3 $T/pilot9_linekey.py resolve lines/line_manifest.json census_mr3_0it.json mr3_resolved > resolve.log || die resolve
python3 $T/pilot9_rebuild_check.py L || die "check L"
sh $T/pilot9_j2_run.sh || die J2
