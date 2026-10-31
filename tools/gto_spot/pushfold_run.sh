#!/bin/sh
# Push/fold bucket solve (resumable; docs/GTO_PUSHFOLD_10_25_V1.md section 2): usage pushfold_run.sh <S> [<S> ...]
# Chunks of 25 iterations with the 1e-9 multiway skip; exact gap (skip off, separate call on the checkpoint) after every chunk;
# stop at exact gap <= 0.010 bb or 400 iterations; then the whole-tree dump (reach >= 1e-6).
set -e
E=/home/user/gto_ckpt/target_exp/release/examples
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200
for S in "$@"; do
  CFG=${PF_CFG_DIR:-/home/user/t2/data/gto_spot/pushfold}/cfg_pf$S.json
  W=/home/user/gto_ckpt/pushfold/pf$S; mkdir -p $W; cd $W
  N=$(cat next_n 2>/dev/null || echo 25)
  while [ ! -s final_n ]; do
    [ -s solve_$N.json ] || { echo "pf$S solve to $N $(date -u +%FT%TZ)"; PREFLOP_MW_SKIP_BELOW=1e-9 $E/t2_pf_solve $CFG $N ck.gtop solve_$N.json > solve_$N.log 2>&1; }
    [ -s exact_$N.json ] || { cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 $E/t2_pf_solve $CFG $N ck_exact.gtop exact_$N.json > exact_$N.log 2>&1; rm -f ck_exact.gtop; }
    G=$(python3 -c "import json; print(json.load(open('exact_$N.json'))['gap_total'])")
    echo "pf$S iterations $N exact gap $G $(date -u +%FT%TZ)"
    if python3 -c "import sys; sys.exit(0 if $G <= 0.010 else 1)" || [ $N -ge 400 ]; then echo $N > final_n; else N=$((N + 25)); echo $N > next_n; fi
  done
  [ -s dump.jsonl ] || { echo "pf$S dump $(date -u +%FT%TZ)"; $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl; }
  echo "pf$S DONE final_n $(cat final_n) $(date -u +%FT%TZ)"
done
