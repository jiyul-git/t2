#!/bin/sh
# wait up to ~585 s; return early (exit 3) if the chain stopped; then print status
i=0
while [ $i -lt 58 ]; do
  ps -eo args | grep -v grep | grep -q "run_quick.sh" || { echo "CHAIN NOT RUNNING"; /home/user/gto_ckpt/watch/status30.sh | tail -3; exit 3; }
  sleep 10; i=$((i+1))
done
/home/user/gto_ckpt/watch/status30.sh | tail -3
