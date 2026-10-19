#!/bin/sh
# quick chain (user decision 2026-10-19): per spec id: spot loop (rule v4, spec max_steps) -> quick record (no grade, no P144).
#   PLAN_A_IDS="id1 id2" sh tools/gto_spot/run_quick.sh        resumable: skips ids whose quick record exists
cd /home/user/t2
L=/home/user/gto_ckpt/plan_a/quick.log
for id in $PLAN_A_IDS; do
    SP=data/gto_spot/plan_a/specs/$id.json
    [ -s "$(python3 -c "import json; print(json.load(open('$SP'))['dump'])")" ] || { echo "no parent dump for $id" >> $L; continue; }
    [ -s data/gto_spot/quick/$id.json ] && continue
    echo "START $id $(date -u +%FT%TZ)" >> $L
    python3 tools/gto_spot/spot_loop.py $SP >> $L 2>&1 || { echo "loop failed $id" >> $L; exit 1; }
    python3 tools/gto_spot/quick_spot.py $id /home/user/gto_ckpt/spots/$id >> $L 2>&1 || { echo "quick failed $id" >> $L; exit 1; }
    echo "DONE $id $(date -u +%FT%TZ)" >> $L
done
echo "QUICK_PASS_END $(date -u +%FT%TZ)" >> $L
