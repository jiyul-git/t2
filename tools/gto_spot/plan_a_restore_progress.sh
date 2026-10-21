#!/bin/sh
# Restore a spot from data/gto_spot/plan_a/progress/<id>/ into /home/user/gto_ckpt/spots/<id>/ (after a container loss). The loop then continues
# at state.json's step k; flops of that step are recomputed. Usage: sh tools/gto_spot/plan_a_restore_progress.sh <spot_id>...
cd /home/user/t2
for id in "$@"; do
  src=data/gto_spot/plan_a/progress/$id; dst=/home/user/gto_ckpt/spots/$id
  [ -d $src ] || { echo "no backup for $id"; continue; }
  mkdir -p $dst; cp -r $src/. $dst/; echo "restored $id: $(python3 -c "import json;d=json.load(open('$dst/state.json'));print('k =',d.get('k'),'final_step =',d.get('final_step'))")"
done
