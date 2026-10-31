#!/bin/sh
# resumable chain: three spot terminals, strategy export on. Relaunch after the 2 h task limit (finished boards are reused).
cd /home/user/calc
E=/home/user/gto_ckpt/export; S=/home/user/gto_ckpt/specs
run() { python3.11 tools/gto_postflop/run_export.py $S/$2.json $E/in/$1/tables_used.json $E/in/$1/matrices_used.json $E/in/$1/report.json 0 $E/out/$1 $3 >> $E/chain_$1.log 2>&1; echo "$1 rc $?" >> $E/chain.log; }
[ -f $E/out/btn/term0_repro_check.json ] || run btn p40_flat_btn_vs_bb
[ -f $E/out/o25/term0_repro_check.json ] || run o25 p60_flat_co_vs_bb_o25 $E/in/o25/term0.json
[ -f $E/out/3b/term0_repro_check.json ] || run 3b p40v1_btn_vs_sb_3b40 $E/in/3b/term0.json
echo chain_done >> $E/chain.log
