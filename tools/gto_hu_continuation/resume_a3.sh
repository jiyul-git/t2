#!/bin/bash
# Resume A3 (outer_m28_6) with the exact pre-registered command; finished artifacts are reused via provenance checks.
cd "$(dirname "$0")/../.." || exit 1
if ps -C python3 -o args= | grep -q outer_loop_multi; then echo "A3 driver already running; not starting a second one"; exit 1; fi
K=data/gto_hu_continuation/panel72/outer_v2_damped_a05/k9; E=data/gto_terminal_expansion
L=${A3_LOG:-/tmp/claude-0/-home-user-t2/0f5a154b-8ae8-5a6f-a261-583af56cff70/scratchpad/logs/a3.log}
mkdir -p "$(dirname "$L")"; echo "=== resume $(date -u +%FT%TZ) ===" >> "$L"
nohup python3 tools/gto_hu_continuation/outer_loop_multi.py --out $E/outer_m28_6 --terminal 28=fold,raise,fold,call --terminal 6=fold,fold,raise,call \
  --init 28=$K/table.json --init 6=$E/node6_72/table72.json --init-measured 28=$K/table_measured.json --init-measured 6=$E/node6_72/table72.json \
  --init-terminal 28=$K/terminal.json --init-terminal 6=$E/terminals/p9_node6.json --k0 9 --steps 5 --preflop-only-final \
  --reuse-first $E/a25_routing_probe/P10_M9_28k9_6a1 --workers 4 --threads 1 >> "$L" 2>&1 &
echo "started pid $!"
