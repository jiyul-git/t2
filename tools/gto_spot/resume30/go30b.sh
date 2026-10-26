#!/bin/sh
# detached (setsid nohup) start of the 30 bb flat-call chains: two chains x 2 workers, plus one backup watcher per spot.
export PATH=/home/user/py311/bin:$PATH
W=/home/user/gto_ckpt/watch; BR=claude/p30-flat-20261019
A="p30_flat_sb_limp_vs_bb p30_flat_hj_vs_bb p30_flat_utg2_vs_bb p30_flat_utg_vs_bb"
B="p30_flat_sb_vs_bb p30_flat_lj_vs_bb p30_flat_utg1_vs_bb"
cd /home/user/t2
ps -eo args | grep -v grep | grep -q run_quick.sh && { echo 'chains already running - not started'; exit 0; }
for id in $A $B; do
  ps -eo args | grep -v grep | grep -q "backup_watch.sh $id " || setsid nohup $W/backup_watch.sh $id $BR /home/user/t2 >> $W/w.out 2>&1 &
done
for L in "A:$A" "B:$B"; do
  n=${L%%:*}; ids=${L#*:}
  ps -eo args | grep -v grep | grep -q "PLAN_CHAIN=$n" && continue
  echo "LAUNCH $(date -u +%FT%TZ) chain $n: $ids" >> /home/user/gto_ckpt/plan_a/quick.log
  setsid nohup env PLAN_CHAIN=$n SPOT_PANEL_WORKERS=2 PLAN_A_IDS="$ids" sh tools/gto_spot/run_quick.sh >> /home/user/gto_ckpt/plan_a/chain_$n.out 2>&1 &
done
sleep 2; echo started
