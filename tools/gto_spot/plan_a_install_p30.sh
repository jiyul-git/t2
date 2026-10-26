#!/bin/sh
# Install the 30 bb parent inputs (cfg_p30_v1 dump + equity table) and verify them. Usage: sh tools/gto_spot/plan_a_install_p30.sh
set -e
cd /home/user/t2
T=data/gto_spot/plan_a/transfer
mkdir -p /home/user/gto_ckpt/plan_a/p30_v1
gunzip -c $T/p30_v1_dump.jsonl.gz > /home/user/gto_ckpt/plan_a/p30_v1/dump.jsonl
gunzip -c $T/eq_table_202_1200.json.gz > /home/user/gto_ckpt/plan_a/eq_table_202_1200.json
sha256sum -c $T/SHA256SUMS 2>&1 | grep -E "p30_v1|eq_table"
echo P30_INPUTS_OK
