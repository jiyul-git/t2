#!/bin/sh
# Plan A spot chain (resumable; docs/GTO_PLAN_A_60BB_V1.md): per spec whose parent dump exists: spot loop (rule v3) -> grade ->
# P144 -> grade (PRECISION=144) -> sensitivity at the P144 state. Specs are regenerated first so they carry the parent's exact gap.
cd /home/user/t2
S=${1:-60}
L=/home/user/gto_ckpt/plan_a/spots.log
python3 tools/gto_spot/plan_a_specs.py $S > /dev/null || exit 1
# PLAN_A_IDS overrides the spot list (2026-10-13: utg_vs_btn and hj_vs_bb run in the T2-side session; B35 dropped)
IDS=${PLAN_A_IDS:-"p${S}_co_vs_sb_b40 p${S}_utg1_vs_sb_b40 p${S}_utg_vs_btn_b40 p${S}_btn_vs_bb_b40 p${S}_hj_vs_bb_b40"}
for id in $IDS; do
    SP=data/gto_spot/plan_a/specs/$id.json
    [ -s "$(python3 -c "import json; print(json.load(open('$SP'))['dump'])")" ] || continue
    [ -s data/gto_spot/plan_a/sensitivity/${id}_p144.json ] && continue
    echo "START $id $(date -u +%FT%TZ)" >> $L
    [ -s data/gto_spot/records/$id.json ] || {
      python3 tools/gto_spot/spot_loop.py $SP >> $L 2>&1 || { echo "loop failed $id" >> $L; exit 1; }
      python3 tools/gto_spot/grade_spot.py $SP >> $L 2>&1 || { echo "grade failed $id" >> $L; exit 1; }; }
    python3 -c "import json,sys; sys.exit(0 if json.load(open('/home/user/gto_ckpt/spots/$id/state.json')).get('converged') else 1)" || { echo "NOT CONVERGED $id" >> $L; continue; }
    [ -s data/gto_spot/records/${id}_p144.json ] || {
      python3 tools/gto_spot/precision_pass.py $SP >> $L 2>&1 || { echo "p144 failed $id" >> $L; exit 1; }
      PRECISION=144 python3 tools/gto_spot/grade_spot.py $SP >> $L 2>&1 || { echo "p144 grade failed $id" >> $L; exit 1; }; }
    PRECISION=144 python3 tools/gto_spot/sensitivity.py $SP >> $L 2>&1 || { echo "sensitivity failed $id" >> $L; exit 1; }
    echo "DONE $id $(date -u +%FT%TZ)" >> $L
done
echo "PLAN_A_PASS_END $(date -u +%FT%TZ)" >> $L
