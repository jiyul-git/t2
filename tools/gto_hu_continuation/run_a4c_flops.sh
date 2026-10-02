#!/bin/sh
# A4c: solve the new boards of panel_v4_node{6,28} at the frozen P14 ranges (prereg data/gto_terminal_expansion/a4c/prereg.json).
# Resumable: finished artifacts are verified by the solver's provenance check and never re-solved.
cd "$(dirname "$0")/../.."
E=data/gto_terminal_expansion
for n in 6 28; do
  B=$(python3 -c "import json;print(','.join(f['board'] for f in json.load(open('data/gto_hu_continuation/panel_v4_node$n.json'))['panel'] if not f['in_panel_v3_144']))")
  mkdir -p $E/a4c/node$n/flops
  python3 tools/gto_hu_continuation/solve_panel.py $E/outer_m28_6/k14/terminal_node$n.json data/gto_hu_continuation/menu_m2_single_v1.json \
    data/gto_hu_continuation/panel_v4_node$n.json $E/a4c/node$n/flops --workers 4 --threads 1 --boards $B || exit 1
done
echo A4C_FLOPS_DONE
