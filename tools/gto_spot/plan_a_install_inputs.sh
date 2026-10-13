#!/bin/sh
# Install the Plan A p60 B40 inputs that run_plan_a.sh reads from container-local paths (for a second session), and verify them.
#   sh tools/gto_spot/plan_a_install_inputs.sh
set -e
cd /home/user/t2
T=data/gto_spot/plan_a/transfer
mkdir -p /home/user/gto_ckpt/plan_a/p60_b40
gunzip -c $T/p60_b40_dump.jsonl.gz > /home/user/gto_ckpt/plan_a/p60_b40/dump.jsonl
gunzip -c $T/eq_table_202_1200.json.gz > /home/user/gto_ckpt/plan_a/eq_table_202_1200.json
mkdir -p /home/user/gto_ckpt/plan_a/p60_v2b
gunzip -c $T/p60_v2b_dump.jsonl.gz > /home/user/gto_ckpt/plan_a/p60_v2b/dump.jsonl
sha256sum -c $T/SHA256SUMS
echo PLAN_A_INPUTS_OK
