#!/bin/sh
# Plan A parent solve (resumable; docs/GTO_PLAN_A_60BB_V1.md section 3): usage plan_a_parent_run.sh <stack> <arm>
# Iterations with the 1e-9 multiway skip in chunks of 25; exact gap (skip off, separate process) when the chunk's skip gap <= 0.011
# or every 100 iterations; stop at exact gap <= 0.010 or 400 iterations; then the whole-tree dump (reach >= 1e-6, skip off).
set -e
S=$1; A=$2
CFG=/home/user/t2/data/gto_spot/plan_a/cfg_p${S}_${A}.json
W=/home/user/gto_ckpt/plan_a/p${S}_${A}
E=/home/user/gto_ckpt/target_exp/release/examples
CONV=/home/user/gto_ckpt/plan_a/p${S}_${A}/convergence.json   # copied into the repo at the end (no repo churn while running)
REPO_CONV=/home/user/t2/data/gto_spot/plan_a/parent_p${S}_${A}_convergence.json
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 PREFLOP_MAX_NODES=40000000
P=fold,fold,fold,fold,fold,fold,raise,fold,call
mkdir -p $W; cd $W
N=$(cat next_n 2>/dev/null || echo 25)
while [ ! -s final_n ]; do
  if [ ! -s solve_$N.json ]; then
    echo "p${S}_${A} solve to $N $(date -u +%FT%TZ)"
    PREFLOP_MW_SKIP_BELOW=1e-9 T2_CHECKPOINT=$W/ck.gtop T2_CHECKPOINT_EVERY=5 $E/t2_cont_terminal $CFG $N $P solve_$N.tmp > solve_$N.log 2>&1
    mv solve_$N.tmp solve_$N.json
  fi
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  if [ ! -s exact_$N.json ] && { python3 -c "import sys; sys.exit(0 if $G <= 0.011 else 1)" || [ $((N % 100)) -eq 0 ]; }; then
    echo "p${S}_${A} exact gap at $N $(date -u +%FT%TZ)"
    cp ck.gtop ck_exact.gtop
    PREFLOP_MW_SKIP_BELOW=0 T2_CHECKPOINT=$W/ck_exact.gtop $E/t2_cont_terminal $CFG $N $P exact_$N.tmp > exact_$N.log 2>&1
    mv exact_$N.tmp exact_$N.json
    rm -f ck_exact.gtop
  fi
  python3 - "$CONV" <<'PY'
import glob, json, os, sys
rows = []
for f in sorted(glob.glob('solve_*.json'), key=lambda x: int(x[6:-5])):
    n = int(f[6:-5]); e = f'exact_{n}.json'
    rows.append({'iterations': n, 'gap_skip_1e-9': json.load(open(f))['gap_total'],
                 'gap_exact': json.load(open(e))['gap_total'] if os.path.exists(e) else None})
json.dump({'schema': 'plan_a_parent_convergence_v1', 'target_gap_exact_bb': 0.010, 'max_iterations': 400, 'rows': rows},
          open(sys.argv[1], 'w'), indent=1)
PY
  if [ -s exact_$N.json ] && python3 -c "import json,sys; sys.exit(0 if json.load(open('exact_$N.json'))['gap_total'] <= 0.010 else 1)"; then
    echo $N > final_n
  elif [ $N -ge 400 ]; then
    [ -s exact_$N.json ] || { cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 T2_CHECKPOINT=$W/ck_exact.gtop $E/t2_cont_terminal $CFG $N $P exact_$N.tmp > exact_$N.log 2>&1; mv exact_$N.tmp exact_$N.json; rm -f ck_exact.gtop; }
    echo $N > final_n
  else
    N=$((N + 25)); echo $N > next_n
  fi
done
echo "p${S}_${A} dump $(date -u +%FT%TZ)"
[ -s dump.jsonl ] || { $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl; }
cp $CONV $REPO_CONV
echo "p${S}_${A} PARENT_DONE"
