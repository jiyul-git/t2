#!/bin/sh
# Verified-frequency chain for "opener facing a 3-bet, everyone else folded" on J30 (25 selected 3-bet lines; resumable).
cd /home/user/t2
for S in data/gto_spot/specs/j30_n*_opener_vs_3bet.json; do
  id=$(basename $S .json)
  [ -s data/gto_spot/records/$id.json ] && continue
  python3 tools/gto_spot/spot_loop.py $S >> /home/user/gto_ckpt/spots/chain3b.log 2>&1 || { echo "loop failed $id" >> /home/user/gto_ckpt/spots/chain3b.log; exit 1; }
  python3 tools/gto_spot/grade_spot.py $S >> /home/user/gto_ckpt/spots/chain3b.log 2>&1 || { echo "grade failed $id" >> /home/user/gto_ckpt/spots/chain3b.log; exit 1; }
  echo "DONE $id $(date -u +%FT%TZ)" >> /home/user/gto_ckpt/spots/chain3b.log
done
echo OPENER_VS_3BET_DONE >> /home/user/gto_ckpt/spots/chain3b.log
