#!/bin/sh
# 전체 트리 k단계 풀이, 횟수 상한·"50회 감소 <10% 정지" 없음(사용자 결정 2026-11-10): 정확 gap < 0.02bb 가 되는 첫 50회 지점에서만 멈춘다.
#   FT_STACK=100 ft_solve_free.sh <k> <cont|fresh>
#   cont : solve_s<k> 의 체크포인트를 복사해 이어서 풀기.   fresh : 체크포인트 없이 이 단계 표로 처음부터.
# 50회마다 건너뛴 gap 을 기록하고, 건너뛴 gap <= 0.021 이면 정확 gap(건너뛰기 0)도 잰다.
# 200회(4덩어리) 동안 건너뛴 gap 감소가 10% 미만이면 로그에 "STALL200" 한 줄만 남긴다(멈추지 않음; 보고용).
# 다른 풀이가 먼저 0.02 에 닿으면 바깥에서 stop_now 파일을 만들어 이 풀이를 멈춘다(덤프는 안 만든다).
set -e
S=${FT_STACK:-60}; K=$1; M=$2; R=$(cd "$(dirname "$0")/../.." && pwd)
E=${FT_CALC:-/home/user/calc}/vendor/gtopen/target/release/examples
CFG=${FT_CALC:-/home/user/calc}/data/gto_spot/plan_a/cfg_p${S}_o25.json
B=${FT_WORK:-/home/user/gto_ckpt/ft$S}; W=$B/solve_s${K}_$M; mkdir -p $W; cd $W
if [ "$M" = cont ] && [ ! -f ck.gtop ]; then cp $B/solve_s$K/ck.gtop ck.gtop; fi
export T2_CONT_FILE=${FT_MANIFEST:-$R/data/ft$S/step$K/tables/manifest.json}
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200
if [ "$M" = cont ]; then N0=$(( $(ls $B/solve_s$K/solve_*.json | sed 's/.*solve_//;s/.json//' | sort -n | tail -1) + 50 )); else N0=50; fi
N=$(cat next_n 2>/dev/null || echo $N0)
exact() { [ -s exact_$1.json ] || { cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 $E/t2_pf_solve $CFG $1 ck_exact.gtop exact_$1.json > exact_$1.log 2>&1; rm -f ck_exact.gtop; }
  python3 -c "import json; print(json.load(open('exact_$1.json'))['gap_total'])"; }
REASON=$(cat stop_reason 2>/dev/null || true)
while [ -z "$REASON" ]; do
  [ -f stop_now ] && { REASON="stopped: other run reached first"; break; }
  echo "s$K/$M solve to $N $(date -u +%FT%TZ)"
  [ -s solve_$N.json ] || PREFLOP_MW_SKIP_BELOW=1e-9 $E/t2_pf_solve $CFG $N ck.gtop solve_$N.json > solve_$N.log 2>&1
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  echo "s$K/$M iterations $N gap(skip) $G $(date -u +%FT%TZ)"
  P4=$(python3 -c "import json,os; f='solve_%d.json'%($N-200); print(json.load(open(f))['gap_total'] if os.path.exists(f) else '')")
  [ -n "$P4" ] && python3 -c "import sys; sys.exit(0 if $G > 0.9 * $P4 else 1)" && echo "s$K/$M STALL200 at $N: $P4 -> $G"
  if python3 -c "import sys; sys.exit(0 if $G <= 0.021 else 1)"; then
    X=$(exact $N); echo "s$K/$M iterations $N exact gap $X"
    python3 -c "import sys; sys.exit(0 if $X < 0.02 else 1)" && REASON="reached: exact gap $X < 0.02 at $N"
  fi
  [ -z "$REASON" ] && N=$((N + 50)) && echo $N > next_n
done
echo "$REASON" > stop_reason
case "$REASON" in reached*) echo $N > final_n; echo "s$K/$M dump $(date -u +%FT%TZ)"; $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl;; esac
echo "s$K/$M DONE $REASON $(date -u +%FT%TZ)"
