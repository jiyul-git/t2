#!/bin/sh
# ft_solve.sh 가 400회에서 멈춘 뒤 이어서 반복(사용자 결정 ft100): [FT_STACK=100] ft_solve_more.sh <k> [최대 반복=600]
# 50회마다 건너뛴 gap 기록. 정확 gap 은 건너뛴 gap <= 0.0101 일 때 재서 <= 0.010 이면 멈춤. 50회 동안 건너뛴 gap 감소폭 < 0.0005 이면 멈춤(그 값으로 진행).
# 어느 쪽이든 멈출 때 정확 gap 을 한 번 재서 exact_<N>.json 에 남기고 덤프를 만든다. 판정 기준은 숫자에 맞춰 바꾸지 않는다.
set -e
S=${FT_STACK:-60}; K=$1; MAX=${2:-600}; R=$(cd "$(dirname "$0")/../.." && pwd)
E=${FT_CALC:-/home/user/calc}/vendor/gtopen/target/release/examples
CFG=${FT_CALC:-/home/user/calc}/data/gto_spot/plan_a/cfg_p${S}_o25.json
W=${FT_WORK:-/home/user/gto_ckpt/ft$S}/solve_s$K; cd $W
M=$R/data/ft$S/step$K/tables/manifest.json
[ -f $M ] && export T2_CONT_FILE=$M
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200
[ -s final_n ] && mv final_n final_n_$(cat final_n)
[ -s dump.jsonl ] && mv dump.jsonl dump_$(ls solve_*.json | sed 's/solve_//;s/.json//' | sort -n | tail -1).jsonl
N=$(ls solve_*.json | sed 's/solve_//;s/.json//' | sort -n | tail -1)
PREV=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
exact() { [ -s exact_$1.json ] || { cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 $E/t2_pf_solve $CFG $1 ck_exact.gtop exact_$1.json > exact_$1.log 2>&1; rm -f ck_exact.gtop; }
  python3 -c "import json; print(json.load(open('exact_$1.json'))['gap_total'])"; }
REASON=
while [ -z "$REASON" ]; do
  N=$((N + 50)); echo "s$K solve to $N $(date -u +%FT%TZ)"
  [ -s solve_$N.json ] || PREFLOP_MW_SKIP_BELOW=1e-9 $E/t2_pf_solve $CFG $N ck.gtop solve_$N.json > solve_$N.log 2>&1
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  echo "s$K iterations $N gap(skip) $G (prev $PREV) $(date -u +%FT%TZ)"
  if python3 -c "import sys; sys.exit(0 if $G <= 0.0101 else 1)"; then
    X=$(exact $N); echo "s$K iterations $N exact gap $X"
    python3 -c "import sys; sys.exit(0 if $X <= 0.010 else 1)" && REASON="exact gap $X <= 0.010"
  fi
  [ -z "$REASON" ] && python3 -c "import sys; sys.exit(0 if $PREV - $G < 0.0005 else 1)" && REASON="gap_not_reached: 50-iteration decrease $(python3 -c "print($PREV - $G)") < 0.0005, skip gap $G"
  [ -z "$REASON" ] && [ $N -ge $MAX ] && REASON="gap_not_reached: max iterations $MAX, skip gap $G"
  PREV=$G
done
echo "$N" > final_n; echo "$REASON" > stop_reason
case "$REASON" in gap_not_reached*) X=$(exact $N); echo "s$K final exact gap $X";; esac
echo "s$K dump $(date -u +%FT%TZ)"; $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl
echo "s$K DONE final_n $N reason: $REASON $(date -u +%FT%TZ)"
