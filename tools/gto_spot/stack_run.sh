#!/bin/sh
# Stack bucket solve, Plan A parent rules (resumable; docs/GTO_STACK_30_40_V1.md section 2): usage stack_run.sh <cfg.json> <workdir>
# Chunks of 25 iterations with the 1e-9 multiway skip; exact gap (skip off) when the chunk's skip gap <= 0.011 or every 100
# iterations; stop at exact gap <= 0.010 bb or 400 iterations; then the whole-tree dump (reach >= 1e-6).
set -e
CFG=$1; W=$2
E=/home/user/gto_ckpt/target_exp/release/examples
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 PREFLOP_MAX_NODES=40000000
mkdir -p $W; cd $W
N=$(cat next_n 2>/dev/null || echo 25)
while [ ! -s final_n ]; do
  [ -s solve_$N.json ] || { echo "$W solve to $N $(date -u +%FT%TZ)"; PREFLOP_MW_SKIP_BELOW=1e-9 T2_CHECKPOINT_EVERY=5 $E/t2_pf_solve $CFG $N ck.gtop solve_$N.json > solve_$N.log 2>&1; }
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  echo "$W iterations $N skip gap $G $(date -u +%FT%TZ)"
  if [ ! -s exact_$N.json ] && { python3 -c "import sys; sys.exit(0 if $G <= 0.011 else 1)" || [ $((N % 100)) -eq 0 ] || [ $N -ge 400 ]; }; then
    cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 $E/t2_pf_solve $CFG $N ck_exact.gtop exact_$N.json > exact_$N.log 2>&1; rm -f ck_exact.gtop
    echo "$W iterations $N exact gap $(python3 -c "import json; print(json.load(open('exact_$N.json'))['gap_total'])") $(date -u +%FT%TZ)"
  fi
  if [ -s exact_$N.json ] && python3 -c "import json,sys; sys.exit(0 if json.load(open('exact_$N.json'))['gap_total'] <= 0.010 else 1)"; then echo $N > final_n
  elif [ $N -ge 400 ]; then echo $N > final_n
  else N=$((N + 25)); echo $N > next_n; fi
done
[ -s dump.jsonl ] || { echo "$W dump $(date -u +%FT%TZ)"; $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl; }
echo "$W DONE final_n $(cat final_n) $(date -u +%FT%TZ)"
