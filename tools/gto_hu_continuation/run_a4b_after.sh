#!/bin/sh
# A4b follow-up: after run_a4b.sh finishes, build V14_144 tables, run the preflop points + bootstrap, analyze (prereg a4b_panel144/prereg.json)
cd "$(dirname "$0")/../.."
while [ -n "$(ps -C run_a4b.sh -o pid=)$(ps -C python3 -o cmd= | grep solve_panel)" ]; do sleep 60; done
E=data/gto_terminal_expansion/a4b_panel144
for n in 6 28; do test "$(ls $E/node$n/flops/*.json | wc -l)" -eq 72 || { echo "node $n: flops missing"; exit 1; }; done
python3 tools/gto_hu_continuation/a4b_panel144.py tables && python3 tools/gto_hu_continuation/a4b_panel144.py run && python3 tools/gto_hu_continuation/a4b_panel144.py analyze && echo A4B_DONE
