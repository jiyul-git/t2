#!/bin/sh
# H1 chain (resumable): full HU SRP set. The 4 remaining HU SRP terminals (SB / LJ / UTG+2 / UTG+1 open -> BB call) get panel_v1
# tables at the S state's endpoint ranges; the 4 S-pilot tables stay unchanged; then one preflop solve (100 it) with all 8 -> state H.
# No frozen-static control arm (C1b bounded the freezing effect); no outer step 2 here.
set -e
R=/home/user/gto_ckpt
H=$R/h1
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 T2_CHECKPOINT_EVERY=10
NEW="sb:fold,fold,fold,fold,fold,fold,fold,raise,call lj:fold,fold,fold,raise,fold,fold,fold,fold,call utg2:fold,fold,raise,fold,fold,fold,fold,fold,call utg1:fold,raise,fold,fold,fold,fold,fold,fold,call"
OLD="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call"
mkdir -p $H/terminals
echo "H1a exports at S $(date -u +%FT%TZ)"
[ -s $H/ck_S.gtop ] || { cp $R/c3/ck.gtop $H/ck_S.tmp && mv $H/ck_S.tmp $H/ck_S.gtop; }
for spec in $NEW; do n=${spec%%:*}; s=${spec#*:}
  [ -s $H/terminals/s_$n.json ] || T2_CONT_FILE=$R/c2/solved_tables/manifest.json T2_CHECKPOINT=$H/ck_S.gtop \
    $B/t2_cont_terminal $R/cfg_pilot.json 100 $s $H/terminals/s_$n.json > /dev/null 2>&1
done
echo "H1b panels $(date -u +%FT%TZ)"
for spec in $NEW; do n=${spec%%:*}
  python3 /home/user/t2/tools/gto_hu_continuation/solve_panel.py $H/terminals/s_$n.json /home/user/t2/data/gto_hu_continuation/menu_m2_single_v1.json \
    /home/user/t2/data/gto_hu_continuation/panel_v1.json $H/$n/flops --workers 4 --threads 1 >> $H/solve.log 2>&1
done
python3 $T/pilot9_tables.py solved $H $H/new_tables sb,lj,utg2,utg1 s_ > $H/tables_report.json
mkdir -p $H/tables_all
cp $R/c2/solved_tables/node*.json $H/new_tables/node*.json $H/tables_all/
python3 -c "import json,glob,os; json.dump({'schema':'t2_hu_continuation_manifest_v1','tables':[{'file':os.path.basename(f)} for f in sorted(glob.glob('$H/tables_all/node*.json'))]},open('$H/tables_all/manifest.json','w'))"
echo "H1c preflop solve $(date -u +%FT%TZ)"
mkdir -p $H/H; cd $H/H
for spec in $OLD $NEW; do n=${spec%%:*}; s=${spec#*:}
  [ -s export_$n.json ] || T2_CONT_FILE=$H/tables_all/manifest.json T2_CHECKPOINT=$H/H/ck.gtop $B/t2_cont_terminal $R/cfg_pilot.json 100 $s export_$n.json > /dev/null 2>&1
done
echo H1_DONE
