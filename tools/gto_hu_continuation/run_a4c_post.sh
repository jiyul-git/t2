#!/bin/sh
# A4c post-flop chain (prereg order): waits for the flop driver, requires 162/162 (161 target-converged + approved exception),
# then tables -> margdiag -> points -> lobo -> boot (60, resumable) -> analyze. Each step is resumable; stops on the first failure.
cd "$(dirname "$0")/../.."
L=data/gto_terminal_expansion/a4c/post_run.log
while ps -eo args | grep -v grep | grep -q "run_a4c_flops\|solve_panel.py"; do sleep 60; done
python3 - <<'PY' >> $L 2>&1 || exit 1
import json, subprocess, sys
v = json.loads(subprocess.run(['python3', 'tools/gto_hu_continuation/a4c_flops_verify.py'], capture_output=True, text=True, check=True).stdout)['verify']
ok = v['6']['ok'] + len(v['6']['accepted_exception_nonconverged']) == 88 and v['28']['ok'] + len(v['28']['accepted_exception_nonconverged']) == 74 \
     and not any(v[n]['quarantined'] or v[n]['nonconverged_at_cap_pending_user'] for n in v)
print('POST_GATE', json.dumps(v), 'ok' if ok else 'BLOCKED')
sys.exit(0 if ok else 1)
PY
for step in tables margdiag points lobo boot analyze; do
  echo "STEP $step $(date -u +%FT%TZ)" >> $L
  python3 tools/gto_hu_continuation/a4c_run.py $step >> $L 2>&1 || { echo "FAILED $step" >> $L; exit 1; }
done
echo A4C_POST_DONE >> $L
