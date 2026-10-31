#!/bin/sh
# 봇 대회 8개(turbo day 1~6, standard day 1~2)를 4개씩 병렬로 돌린다. 끝난 것(finished=true)은 건너뛴다.
cd "$(dirname "$0")/../.."
O=data/gto_gaps/runs
mkdir -p $O
run() {
  f=$O/$1_d$2.json
  if [ -f "$f" ] && python3 -c "import json,sys;sys.exit(0 if json.load(open('$f'))['finished'] else 1)"; then return; fi
  python3 tools/gto_gaps/gap_usage_sim.py $1 $2 $f > $O/$1_d$2.log 2>&1
}
run standard 1 & run standard 2 & run turbo 1 & run turbo 2 & wait
run turbo 3 & run turbo 4 & run turbo 5 & run turbo 6 & wait
echo ALLDONE
