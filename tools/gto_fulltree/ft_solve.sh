#!/bin/sh
# 60bb 전체 트리 k단계 풀이(이어서 가능): ft_solve.sh <k>
#   T2_CONT_FILE = data/ft60/step<k>/tables/manifest.json (없으면 정적). 50회 단위, 각 덩어리 뒤 gap(스킵 1e-9),
#   스킵 gap <= 0.03 이면 정확 gap(스킵 0) 측정. 정확 gap < FT_STOP_GAP(기본 0.02, 횟수 상한 없음)에서 멈춤 → 트리 덤프(reach >= 1e-6).
#   2시간 작업 제한을 피하려면: setsid nohup sh tools/gto_fulltree/ft_solve.sh <k> > <log> 2>&1 &
set -e
K=$1; R=$(cd "$(dirname "$0")/../.." && pwd)
E=${FT_CALC:-/home/user/calc}/vendor/gtopen/target/release/examples
ST=${FT_STACK:-60}
CFG=${FT_CFG:-${FT_CALC:-/home/user/calc}/data/gto_spot/plan_a/cfg_p${ST}_o25.json}
STOP=${FT_STOP_GAP:-0.02}   # 사용자 11-10: 정확 gap < 0.02 에서만 멈춤(횟수 상한·50회 감소 규칙 없음)
W=${FT_WORK:-/home/user/gto_ckpt/ft$ST}/solve_s$K; mkdir -p $W; cd $W
M=$R/data/ft$ST/step$K/tables/manifest.json
[ -f $M ] && export T2_CONT_FILE=$M && echo "tables: $M"
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200
N=$(cat next_n 2>/dev/null || echo 50)
while [ ! -s final_n ]; do
  [ -s solve_$N.json ] || { echo "s$K solve to $N $(date -u +%FT%TZ)"; PREFLOP_MW_SKIP_BELOW=1e-9 $E/t2_pf_solve $CFG $N ck.gtop solve_$N.json > solve_$N.log 2>&1; }
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  echo "s$K iterations $N gap(skip) $G $(date -u +%FT%TZ)"
  X=9
  if python3 -c "import sys; sys.exit(0 if $G <= 0.03 else 1)"; then
    [ -s exact_$N.json ] || { cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 $E/t2_pf_solve $CFG $N ck_exact.gtop exact_$N.json > exact_$N.log 2>&1; rm -f ck_exact.gtop; }
    X=$(python3 -c "import json; print(json.load(open('exact_$N.json'))['gap_total'])")
    echo "s$K iterations $N exact gap $X $(date -u +%FT%TZ)"
  fi
  if python3 -c "import sys; sys.exit(0 if $X < $STOP else 1)"; then echo $N > final_n; else N=$((N + 50)); echo $N > next_n; fi
done
[ -s dump.jsonl ] || { echo "s$K dump $(date -u +%FT%TZ)"; $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl; }
echo "s$K DONE final_n $(cat final_n) $(date -u +%FT%TZ)"
