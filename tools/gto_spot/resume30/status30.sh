#!/bin/sh
tail -3 /home/user/gto_ckpt/plan_a/quick.log | cut -c1-160
for id in $(ls /home/user/gto_ckpt/spots | grep p30_flat); do
  SP=/home/user/gto_ckpt/spots/$id; [ -f /home/user/t2/data/gto_spot/quick/$id.json ] && { echo "$id: DONE (quick record)"; continue; }
  d=$(ls -d $SP/step*/term*_flops 2>/dev/null | sort -V | tail -1)
  echo "$id: $(ls -d $SP/step* | wc -l) step dir(s); $(echo $d | sed "s|$SP/||") $(ls $d/*.json 2>/dev/null | wc -l)/24"
done
free -g | awk '/Mem/{print "mem used",$3,"avail",$7}'
