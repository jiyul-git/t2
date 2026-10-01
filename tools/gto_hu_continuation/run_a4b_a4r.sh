#!/bin/sh
# Resumable chain (every step skips finished work): A4b flops -> A4b tables/preflop/bootstrap/analysis (amendment 1)
# -> A4R cross-evaluation/analysis. Ends there: never starts 288 flops or any outer step.
cd "$(dirname "$0")/../.."
if [ -n "$(ps -C python3 -o cmd= | grep -E 'solve_panel|a4b_panel144|a4r_robust')" ]; then echo 'a driver is already running'; exit 1; fi
E=data/gto_terminal_expansion/a4b_panel144
echo "=== start $(date -u +%FT%T) uptime $(cut -d' ' -f1 /proc/uptime) s ==="
sh tools/gto_hu_continuation/run_a4b.sh || exit 1
for n in 6 28; do test "$(ls $E/node$n/flops/*.json | wc -l)" -eq 72 || { echo "node $n: flops missing"; exit 1; }; done
python3 tools/gto_hu_continuation/a4b_panel144.py tables || exit 1
python3 tools/gto_hu_continuation/a4b_panel144.py run || exit 1
python3 tools/gto_hu_continuation/a4b_panel144.py analyze || exit 1
echo A4B_DONE
python3 tools/gto_hu_continuation/a4r_robust.py run || exit 1
python3 tools/gto_hu_continuation/a4r_robust.py analyze || exit 1
echo A4R_DONE
