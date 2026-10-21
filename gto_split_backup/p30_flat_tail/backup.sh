#!/bin/sh
# usage: sh backup.sh <spot_id> <label>   tar the spot dir (state + step dirs) and push to the tail branch
cd /home/user/t2
id=$1; lab=$2; d=gto_split_backup/p30_flat_tail/$id; mkdir -p $d
tar czf $d/$lab.tgz -C /home/user/gto_ckpt/spots $id --exclude='*/solve.log'
cp /home/user/gto_ckpt/plan_a/quick.log $d/quick.log 2>/dev/null
ls -la $d/$lab.tgz
git add $d && git commit -qm "p30_flat_tail $id: backup $lab" && git push -q origin claude/p30_flat_tail_20261021 2>&1 | tail -1
