#!/bin/sh
# E1 step K postflop panel at R_K (resumable): verify -> solve all panel boards -> verify.   run_e1_flops.sh <K>
cd "$(dirname "$0")/../.."
K=$1
E=data/gto_terminal_expansion/e1/step$K
L=$E/flops_run.log
mkdir -p $E
python3 tools/gto_hu_continuation/e1_flops_verify.py $K >> $L 2>&1 || exit 1
for n in 6 28; do
  python3 tools/gto_hu_continuation/solve_panel.py $E/R/terminal_node$n.json data/gto_hu_continuation/menu_m2_single_v1.json \
    data/gto_hu_continuation/panel_v4_node$n.json $E/node$n/flops --workers 4 --threads 1 >> $L 2>&1 || exit 1
done
python3 tools/gto_hu_continuation/e1_flops_verify.py $K >> $L 2>&1
echo E1_FLOPS_DONE_STEP$K >> $L
tail -2 $L
