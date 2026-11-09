#!/bin/sh
# 60bb 전체 트리 k단계 풀이(이어서 가능): ft_solve.sh <k>
#   T2_CONT_FILE = data/ft60/step<k>/tables/manifest.json (없으면 정적). 50회 단위, 각 덩어리 뒤 gap(스킵 1e-9),
#   스킵 gap <= 0.012 이면 정확 gap(스킵 0) 측정. 정확 gap <= 0.010bb 또는 400회에서 멈춤 → 트리 덤프(reach >= 1e-6).
#   환경변수(기본값 = 위 ft60 규칙): FT_GAP_STOP(0.010) 정확 gap 정지선, FT_MAX_N(400) 최대 회수, FT_SKIP_TRIG(0.012) 정확 gap 측정 시작선,
#   FT_MIN_N(0) 이 회수 전에는 gap 이 낮아도 멈추지 않음, FT_START_N(50) 첫 측정 회수(앞 단계 체크포인트에서 이어 풀 때 그 회수 = 새 표로 본 gap 만 재고 시작), FT_MIN_DROP(없음) 50회당 최소 감소율 — 미달·상승이면 멈추고 stop.txt 에 이유(덤프 안 함).
#   2시간 작업 제한을 피하려면: setsid nohup sh tools/gto_fulltree/ft_solve.sh <k> > <log> 2>&1 &
set -e
S=${FT_STACK:-60}; K=$1; R=$(cd "$(dirname "$0")/../.." && pwd)
E=${FT_CALC:-/home/user/calc}/vendor/gtopen/target/release/examples
if [ -n "$FT_CFG" ]; then CFG=$FT_CFG; elif [ "$S" = 60 ]; then CFG=${FT_CALC:-/home/user/calc}/data/gto_spot/plan_a/cfg_p60_o25.json; else CFG=$R/data/ft$S/cfg.json; fi
W=${FT_WORK:-/home/user/gto_ckpt/ft$S}/solve_s$K; mkdir -p $W; cd $W
M=$R/data/ft$S/step$K/tables/manifest.json
[ -f $M ] && export T2_CONT_FILE=$M && echo "tables: $M"
export PREFLOP_EQ_SEED=202 PREFLOP_MULTIWAY_SEED=202 PREFLOP_EQ_SAMPLES=1200
N=$(cat next_n 2>/dev/null || echo ${FT_START_N:-50}); PREV=$(cat prev_g 2>/dev/null || echo)
while [ ! -s final_n ]; do
  [ -s solve_$N.json ] || { echo "s$K solve to $N $(date -u +%FT%TZ)"; PREFLOP_MW_SKIP_BELOW=1e-9 $E/t2_pf_solve $CFG $N ck.gtop solve_$N.json > solve_$N.log 2>&1; }
  G=$(python3 -c "import json; print(json.load(open('solve_$N.json'))['gap_total'])")
  echo "s$K iterations $N gap(skip) $G $(date -u +%FT%TZ)"
  X=9
  if python3 -c "import sys; sys.exit(0 if $G <= ${FT_SKIP_TRIG:-0.012} else 1)"; then
    [ -s exact_$N.json ] || { cp ck.gtop ck_exact.gtop; PREFLOP_MW_SKIP_BELOW=0 $E/t2_pf_solve $CFG $N ck_exact.gtop exact_$N.json > exact_$N.log 2>&1; rm -f ck_exact.gtop; }
    X=$(python3 -c "import json; print(json.load(open('exact_$N.json'))['gap_total'])")
    echo "s$K iterations $N exact gap $X $(date -u +%FT%TZ)"
  fi
  CUR=$X; [ "$X" = 9 ] && CUR=$G
  if { [ $N -ge ${FT_MIN_N:-0} ] && python3 -c "import sys; sys.exit(0 if $X <= ${FT_GAP_STOP:-0.010} else 1)"; } || [ $N -ge ${FT_MAX_N:-400} ]; then echo $N > final_n
  else
    if [ -n "$FT_MIN_DROP" ] && [ -n "$PREV" ] && ! python3 -c "import sys; sys.exit(0 if $CUR <= $PREV * (1 - $FT_MIN_DROP) else 1)"; then
      echo "gap $PREV -> $CUR over 50 iterations: drop < $FT_MIN_DROP or rising at N=$N" > stop.txt; echo "s$K STOP $(cat stop.txt)"; exit 3
    fi
    echo $CUR > prev_g; PREV=$CUR; N=$((N + 50)); echo $N > next_n
  fi
done
[ -s dump.jsonl ] || { echo "s$K dump $(date -u +%FT%TZ)"; $E/t2_tree_dump $CFG ck.gtop 1e-6 dump.tmp > dump.log 2>&1 && mv dump.tmp dump.jsonl; }
echo "s$K DONE final_n $(cat final_n) $(date -u +%FT%TZ)"
