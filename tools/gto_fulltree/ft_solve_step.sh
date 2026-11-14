#!/bin/sh
# 전체 트리 k(>=1)단계 풀이: 앞 단계 체크포인트에서 이어서 새 표(data/ft<S>/step<k>/tables)로 반복.  [FT_STACK=100] ft_solve_step.sh <k> [최대 누적 반복=800]
# 사용자 규칙(2026-11-08, T2 세션 전달): 50회마다 건너뛴 gap 기록, 건너뛴 gap <= 0.021 이면 정확 gap(건너뛰기 0) 측정.
#  정확 gap < 0.02 인 첫 50회 지점에서 멈추고 진행(0.010 초과면 기록에 명시). 최대 800회(누적, 0단계의 500회 포함).
#  50회 감소가 10% 미만이거나 오르면(첫 덩어리는 비교 대상이 없다) 멈추고 보고. 어느 쪽이든 멈출 때 정확 gap 을 재고 트리를 덤프한다.
set -e
S=${FT_STACK:-60}; K=$1; MAX=${2:-800}; R=$(cd "$(dirname "$0")/../.." && pwd)
E=${FT_CALC:-/home/user/calc}/vendor/gtopen/target/release/examples
CFG=${FT_CALC:-/home/user/calc}/data/gto_spot/plan_a/cfg_p${S}_o25.json
B=${FT_WORK:-/home/user/gto_ckpt/ft$S}; W=$B/solve_s$K; mkdir -p $W; cd $W
[ -f ck.gtop ] || cp $B/solve_s$((K-1))/ck.gtop ck.gtop
export T2_CONT_FILE=$R/data/ft$S/step$K/tables/manifest.json
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200
N=$(cat next_n 2>/dev/null || echo $(( $(ls $B/solve_s$((K-1))/solve_*.json | sed 's/.*solve_//;s/.json//' | sort -n | tail -1) + 50 )))
PREV=; REASON=
[ -s stop_reason ] && REASON=$(cat stop_reason)
[ -s prev_gap ] && PREV=$(cat prev_gap)
exact() { [ -s exact_$1.json ] || { cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 $E/t2_pf_solve $CFG $1 ck_exact.gtop exact_$1.json > exact_$1.log 2>&1; rm -f ck_exact.gtop; }
  python3 -c "import json; print(json.load(open('exact_$1.json'))['gap_total'])"; }
while [ -z "$REASON" ]; do
  echo "s$K solve to $N $(date -u +%FT%TZ)"
  [ -s solve_$N.json ] || PREFLOP_MW_SKIP_BELOW=1e-9 $E/t2_pf_solve $CFG $N ck.gtop solve_$N.json > solve_$N.log 2>&1
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  echo "s$K iterations $N gap(skip) $G (prev ${PREV:-none}) $(date -u +%FT%TZ)"
  if python3 -c "import sys; sys.exit(0 if $G <= 0.021 else 1)"; then
    X=$(exact $N); echo "s$K iterations $N exact gap $X"
    python3 -c "import sys; sys.exit(0 if $X < 0.02 else 1)" && REASON="reached: exact gap $X < 0.02 at $N"
  fi
  if [ -z "$REASON" ] && [ -n "$PREV" ] && python3 -c "import sys; sys.exit(0 if $G > 0.9 * $PREV else 1)"; then REASON="stalled: skip gap $PREV -> $G (decrease < 10% or rise) at $N"; fi
  [ -z "$REASON" ] && [ $N -ge $MAX ] && REASON="max_iterations $MAX reached, skip gap $G"
  PREV=$G; echo $G > prev_gap; N=$((N + 50)); echo $N > next_n
done
N=$((N - 50)); echo "$N" > final_n; echo "$REASON" > stop_reason
case "$REASON" in reached*) ;; *) X=$(exact $N); echo "s$K final exact gap $X";; esac
echo "s$K dump $(date -u +%FT%TZ)"; $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl
echo "s$K DONE final_n $N reason: $REASON $(date -u +%FT%TZ)"
