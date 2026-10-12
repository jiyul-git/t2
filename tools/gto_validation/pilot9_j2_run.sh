#!/bin/sh
# J2 solve (resumable): J tree (cfg_mr3_jam, 33 line-resolved tables) solved until the EXACT gap_total <= 0.010 bb (doc G2).
# Iterations run with PREFLOP_MW_SKIP_BELOW=1e-9 (bounded multiway terminal skip; ~19x faster, validated on mr2); the G2 gap
# is always measured in a separate process with the skip off (exact terminal values). Chunks of 25 iterations; the exact gap is
# measured when the skip-mode gap of the chunk is <= 0.011 (skip gap ran ~10% below exact on mr2) or every 100 iterations.
# Then: whole-tree dump (skip off) for the spot solver and the multi-path exports (8 SRP, 25 3-bet, 25 4-bet-jam).
set -e
R=/home/user/gto_ckpt
J=$R/step3/j
W=$J/J2
B=/home/user/t2/vendor/gtopen/target/release/examples
T=/home/user/t2/tools/gto_validation
OUT=/home/user/t2/data/gto_validation/pilot9/rebuild
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200 PREFLOP_MAX_NODES=40000000 T2_CONT_FILE=$J/mr3_resolved/manifest.json
UTG=raise,fold,fold,fold,fold,fold,fold,fold,call
mkdir -p $W $OUT
cd $W
N=100
while :; do
  if [ ! -s solve_$N.json ]; then
    echo "J2 solve to $N $(date -u +%FT%TZ)"
    PREFLOP_MW_SKIP_BELOW=1e-9 T2_CHECKPOINT=$W/ck.gtop T2_CHECKPOINT_EVERY=5 $B/t2_cont_terminal $J/cfg_mr3_jam.json $N $UTG solve_$N.tmp > solve_$N.log 2>&1
    mv solve_$N.tmp solve_$N.json
  fi
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  if [ ! -s exact_$N.json ] && { python3 -c "import sys; sys.exit(0 if $G <= 0.011 else 1)" || [ $((N % 100)) -eq 0 ]; }; then
    echo "J2 exact gap at $N $(date -u +%FT%TZ)"
    cp ck.gtop ck_exact.gtop
    PREFLOP_MW_SKIP_BELOW=0 T2_CHECKPOINT=$W/ck_exact.gtop $B/t2_cont_terminal $J/cfg_mr3_jam.json $N $UTG exact_$N.tmp > exact_$N.log 2>&1
    mv exact_$N.tmp exact_$N.json
    rm -f ck_exact.gtop
  fi
  python3 - "$N" <<'PY'
import glob, json, os, sys
rows = []
for f in sorted(glob.glob('solve_*.json'), key=lambda x: int(x[6:-5])):
    n = int(f[6:-5]); e = f'exact_{n}.json'
    rows.append({'iterations': n, 'gap_skip_1e-9': json.load(open(f))['gap_total'],
                 'gap_exact': json.load(open(e))['gap_total'] if os.path.exists(e) else None})
json.dump({'schema': 'pilot9_j2_convergence_v1', 'target_gap_exact_bb': 0.010, 'rows': rows},
          open('/home/user/t2/data/gto_validation/pilot9/rebuild/j2_convergence.json', 'w'), indent=1)
PY
  if [ -s exact_$N.json ] && python3 -c "import json,sys; sys.exit(0 if json.load(open('exact_$N.json'))['gap_total'] <= 0.010 else 1)"; then
    echo "J2 converged at $N" ; echo $N > final_n; break
  fi
  N=$((N + 25))
done
N=$(cat final_n)
echo "J2 dump $(date -u +%FT%TZ)"
[ -s $J/J2_dump.jsonl ] || { $B/t2_tree_dump $J/cfg_mr3_jam.json $W/ck.gtop 1e-9 $J/J2_dump.tmp > $J/J2_dump.log 2>&1 && mv $J/J2_dump.tmp $J/J2_dump.jsonl; }
echo "J2 exports $(date -u +%FT%TZ)"
SRP="btn:fold,fold,fold,fold,fold,fold,raise,fold,call co:fold,fold,fold,fold,fold,raise,fold,fold,call hj:fold,fold,fold,fold,raise,fold,fold,fold,call utg:raise,fold,fold,fold,fold,fold,fold,fold,call sb:fold,fold,fold,fold,fold,fold,fold,raise,call lj:fold,fold,fold,raise,fold,fold,fold,fold,call utg2:fold,fold,raise,fold,fold,fold,fold,fold,call utg1:fold,raise,fold,fold,fold,fold,fold,fold,call"
TB=$(python3 $T/pilot9_t3.py specs)
JAM=$(for x in $TB; do n=${x%%:*}; s=${x#*:}; echo "${n}_jam:${s%,call},jam,call"; done)
: > jobs.txt
for spec in $SRP $TB $JAM; do n=${spec%%:*}; s=${spec#*:}
  [ -s export_$n.json ] || echo "$s $W/export_$n.json" >> jobs.txt
done
[ -s jobs.txt ] && { cp ck.gtop ck_export.gtop; PREFLOP_MW_SKIP_BELOW=0 T2_CHECKPOINT=$W/ck_export.gtop $B/t2_cont_terminal $J/cfg_mr3_jam.json $N @multi jobs.txt > multi.log 2>&1; rm -f ck_export.gtop; }
echo J2_DONE
