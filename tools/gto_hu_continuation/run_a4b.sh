#!/bin/sh
# A4b: solve the 72 new panel_v3_144 boards for nodes 6 and 28 at the k14 ranges (prereg a4b_panel144/prereg.json)
set -e
cd "$(dirname "$0")/../.."

E=data/gto_terminal_expansion
for n in 6 28; do
  mkdir -p $E/a4b_panel144/node$n/flops
  python3 tools/gto_hu_continuation/solve_panel.py $E/outer_m28_6/k14/terminal_node$n.json data/gto_hu_continuation/menu_m2_single_v1.json \
    data/gto_hu_continuation/panel_v3_144.json $E/a4b_panel144/node$n/flops --workers 4 --threads 1 --boards Ac6c5c,Ac6c4c,AcKc8c,Ac9c6c,AcQc4c,AcKc7c,Tc8c7c,Tc3c2c,8c7c2c,Tc7c6c,Jc8c7c,Jc9c4c,KcTc4c,Qc4c2c,KcJc7c,QcJc9c,Qc9c2c,QcJc3c,Ac4h4d,AdAc5c,Ac2d2c,Ac8d8c,Ac6d6c,AdAcJh,5d5c4c,5c2h2d,Tc8h8d,JdJc4c,6c3d3c,8d8c7c,QdQc2c,QdQc5h,Kc7d7c,QcJdJc,KdKc5h,QdQc8h,Ac7d6h,AcKd3h,Ac8d2h,AcQd9h,AcKdJh,Ac8d5h,9c5d4h,4c3d2h,8c6d5h,Jc9d3h,Jc4d3h,6c4d3h,Kc7d3h,Kc6d4h,KcQd7h,Qc9d4h,QcTd7h,Kc8d6h,Ac8d5c,Ac9d7d,AcQdJd,Ac7c6d,AcKd4d,AcTc2d,6c5d2c,Tc9c2d,7c3d2d,JcTd3c,JcTd6d,Tc6d4d,Qc6c2d,Qc9d4d,Kc6c4d,KcQdTd,KcTc8d,Kc5d3c
done
