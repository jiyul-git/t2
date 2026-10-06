#!/bin/sh
# Verified-frequency chain for the "single open folded to the BB" family on the J30 tree (resumable): spot loop + grade per spot.
cd /home/user/t2
for id in utg btn sb co hj lj utg2 utg1; do
  S=data/gto_spot/specs/j30_${id}_open_bb_v3.json
  [ -s data/gto_spot/records/j30_${id}_open_bb_v3.json ] && continue
  python3 tools/gto_spot/spot_loop.py $S >> /home/user/gto_ckpt/spots/chain.log 2>&1 || { echo "loop failed $id" >> /home/user/gto_ckpt/spots/chain.log; exit 1; }
  python3 tools/gto_spot/grade_spot.py $S >> /home/user/gto_ckpt/spots/chain.log 2>&1 || { echo "grade failed $id" >> /home/user/gto_ckpt/spots/chain.log; exit 1; }
  echo "DONE $id $(date -u +%FT%TZ)" >> /home/user/gto_ckpt/spots/chain.log
done
echo BB_DEFENCE_DONE >> /home/user/gto_ckpt/spots/chain.log
