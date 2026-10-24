#!/bin/sh
# 저장소 안의 GTO 기록 사본(data/gto_records/*.json.gz)을 한 폴더에 푼다(빌더·검사 도구 입력).
#   sh tools/t2_handoff/fetch_records.sh <출력폴더>
# 사본 갱신(새 기록이 왔을 때)은 tools/t2_handoff/refresh_records.sh. 출처는 data/gto_records/MANIFEST.tsv.
set -e
OUT="${1:?출력 폴더}"; mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
cd "$(dirname "$0")/../.."
for f in data/gto_records/*.json.gz; do gunzip -c "$f" > "$OUT/$(basename "$f" .gz)"; done
ls "$OUT"
