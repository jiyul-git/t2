#!/bin/sh
# Main resumable chain: P144 for converged spots without a P144 record (UTG first), then the BB-defence loop for the rest.
cd /home/user/t2
for id in utg btn sb co hj lj utg2 utg1; do
  S=data/gto_spot/specs/j30_${id}_open_bb_v3.json
  R=data/gto_spot/records/j30_${id}_open_bb_v3.json
  [ -s $R ] || continue
  [ -s data/gto_spot/records/j30_${id}_open_bb_v3_p144.json ] && continue
  python3 -c "import json,sys; sys.exit(0 if json.load(open('/home/user/gto_ckpt/spots/j30_${id}_open_bb_v3/state.json')).get('converged') else 1)" || continue
  python3 tools/gto_spot/precision_pass.py $S >> /home/user/gto_ckpt/spots/p144.log 2>&1 || { echo "p144 failed $id" >> /home/user/gto_ckpt/spots/p144.log; exit 1; }
  PRECISION=144 python3 tools/gto_spot/grade_spot.py $S >> /home/user/gto_ckpt/spots/p144.log 2>&1 || { echo "p144 grade failed $id" >> /home/user/gto_ckpt/spots/p144.log; exit 1; }
  echo "P144 DONE $id $(date -u +%FT%TZ)" >> /home/user/gto_ckpt/spots/p144.log
done
sh tools/gto_spot/run_bb_defence.sh
