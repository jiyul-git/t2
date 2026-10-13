#!/bin/sh
# Snapshot immutable completed artifacts plus atomic state files. Inputs and
# interpreters are reconstructible and are intentionally excluded.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
R="$ROOT/.plan_a_runtime"
SNAP=$(mktemp -d "$R/snapshot.XXXXXX")
tar -cf - -C "$R" \
    --exclude='*.partial' --exclude='*.tmp' \
    --exclude='gto_ckpt/plan_a/p60_b40' \
    --exclude='gto_ckpt/plan_a/eq_table_202_1200.json' gto_ckpt \
    | tar -xf - -C "$SNAP"
for file in worker.log control_reproduction.log; do
    [ ! -f "$R/$file" ] || cp "$R/$file" "$SNAP/$file"
done
(
    cd "$SNAP"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
    sha256sum -c SHA256SUMS >/dev/null
)
tar -czf "$R/GTO_BTN_BB_checkpoint.tar.gz" -C "$SNAP" .
echo "$R/GTO_BTN_BB_checkpoint.tar.gz"
