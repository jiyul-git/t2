#!/bin/sh
# 봇 대회: turbo day 1~6 (끝까지), standard day 1~2 (끝까지 약 3시간+ — 2시간 작업 제한에 잘리면 중간 저장분을 쓴다).
# 4개 동시: standard 2개 + turbo 줄 2개(각 3대회).
cd "$(dirname "$0")/../.."
O=data/gto_gaps/runs
mkdir -p $O
run() { python3 tools/gto_gaps/gap_usage_sim.py $1 $2 $O/$1_d$2.json > $O/$1_d$2.log 2>&1; }
run standard 1 & run standard 2 &
(run turbo 1; run turbo 3; run turbo 5) & (run turbo 2; run turbo 4; run turbo 6) &
wait
echo ALLDONE
