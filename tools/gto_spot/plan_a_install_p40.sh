#!/bin/sh
# Install the 40 bb parent inputs for the flat-call spots (docs/GTO_RESUME_40BB.md) and verify them.
#   sh tools/gto_spot/plan_a_install_p40.sh     (also runs plan_a_install_inputs.sh for the equity table)
set -e
cd /home/user/t2
T=data/gto_spot/plan_a/transfer
mkdir -p /home/user/gto_ckpt/plan_a/p40_v1
gunzip -c $T/p40_v1_dump.jsonl.gz > /home/user/gto_ckpt/plan_a/p40_v1/dump.jsonl
gunzip -c $T/eq_table_202_1200.json.gz > /home/user/gto_ckpt/plan_a/eq_table_202_1200.json
sha256sum -c $T/SHA256SUMS 2>&1 | grep -E "p40_v1|eq_table" 
echo P40_INPUTS_OK
