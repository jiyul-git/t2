#!/bin/sh
# Back up the small resumable state of Plan A spots into the repo, so another session can resume after a usage-limit stop or a container loss:
# state.json, every step report, and (2026-10-21) per step the small inputs tables_used.json / matrices_used.json / spot.json / term*.json
# (needed by tools/gto_spot/quick_spot.py to average the last steps). Flop artifacts (term*_flops/) are never backed up: they are recomputed.
#   sh tools/gto_spot/plan_a_backup_progress.sh <spot_id>...
cd /home/user/t2
for id in "$@"; do
  src=/home/user/gto_ckpt/spots/$id; dst=data/gto_spot/plan_a/progress/$id
  [ -d $src ] || continue
  mkdir -p $dst
  cp $src/state.json $dst/ 2>/dev/null || true
  for d in $src/step*/; do
    s=$(basename $d); [ -d $d ] || continue
    mkdir -p $dst/$s
    for f in report.json tables_used.json matrices_used.json spot.json term0.json term1.json term2.json; do [ -s $d/$f ] && cp $d/$f $dst/$s/; done
  done
done
