#!/bin/sh
# A4c flop relaunch wrapper: verify finished artifacts (quarantine bad/truncated ones), solve the rest, verify again.
cd "$(dirname "$0")/../.."
L=data/gto_terminal_expansion/a4c/flops_run.log
python3 tools/gto_hu_continuation/a4c_flops_verify.py >> $L 2>&1 || exit 1
tools/gto_hu_continuation/run_a4c_flops.sh >> $L 2>&1
rc=$?
python3 tools/gto_hu_continuation/a4c_flops_verify.py >> $L 2>&1
tail -1 $L
exit $rc
