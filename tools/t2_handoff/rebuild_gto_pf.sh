#!/bin/sh
# GTO 기준 데이터(gto_pf_data.json)를 기록 폴더에서 다시 만든다.
#   sh tools/t2_handoff/fetch_records.sh /tmp/rec && sh tools/t2_handoff/rebuild_gto_pf.sh /tmp/rec
# 순서가 곧 버킷 순서다: 푸시/폴드·부모(10..100bb) 먼저, 그 뒤 플랫콜 루프 기록(spot_quick_v1, 아무 순서).
set -e
R="${1:?기록 폴더}"; cd "$(dirname "$0")/../.."
python3 tools/gto_pf_build.py $R/pf10.json $R/pf15.json $R/pf20.json $R/pf25.json $R/s30.json $R/s40.json $R/s60.json $R/s100.json \
  $(ls $R/p30_flat_*.json $R/p40_flat_*.json $R/p60_flat_*.json $R/p30v1_*.json $R/p40v1_*.json 2>/dev/null)
python3 tools/verify_gto_pf.py | tail -1
