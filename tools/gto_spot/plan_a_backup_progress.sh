#!/bin/sh
# Back up the small resumable state of Plan A spots (state.json + every step report) into the repo, so another session can resume
# after a usage-limit stop or a container loss (flop artifacts are recomputed from the same terminals; step 0/1 are deterministic).
#   sh tools/gto_spot/plan_a_backup_progress.sh <spot_id>...
cd /home/user/t2
for id in "$@"; do
  src=/home/user/gto_ckpt/spots/$id; dst=data/gto_spot/plan_a/progress/$id
  [ -d $src ] || continue
  mkdir -p $dst
  cp $src/state.json $dst/ 2>/dev/null || true
  for r in $src/step*/report.json; do [ -s "$r" ] || continue; d=$(basename $(dirname $r)); mkdir -p $dst/$d; cp $r $dst/$d/; done
done
