#!/bin/sh
# wait for a running flop driver (pid $1) to finish, then start the resumable chain once
cd "$(dirname "$0")/../.."
while kill -0 "$1" 2>/dev/null; do sleep 60; done
exec tools/gto_hu_continuation/run_a4b_a4r.sh
