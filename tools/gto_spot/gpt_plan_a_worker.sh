#!/bin/sh
# Dedicated GPT BTN-vs-BB worker. All restart-critical files live under the
# workspace repository; /home/user contains compatibility links only.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd -P)
R="$ROOT/.plan_a_runtime"
mkdir -p "$R/gto_ckpt"
exec 9>"$R/worker.lock"
if ! flock -n 9; then
    echo 'WORKER_ALREADY_RUNNING'
    exit 0
fi
exec >>"$R/worker.log" 2>&1
echo "WORKER_START $(date -u +%FT%TZ)"
cd "$ROOT"
mkdir -p /home/user
for item in t2 gto_ckpt; do
    case "$item" in
        t2) target="$ROOT";;
        gto_ckpt) target="$R/gto_ckpt";;
    esac
    link="/home/user/$item"
    if [ -e "$link" ] || [ -L "$link" ]; then
        [ "$(readlink -f "$link")" = "$target" ] || {
            echo "BLOCKED: existing $link points elsewhere"; exit 1;
        }
    else
        ln -s "$target" "$link"
    fi
done
export UV_PYTHON_INSTALL_DIR="$R/python"
if [ ! -x "$R/venv/bin/python3" ]; then
    uv venv -p 3.11.17 "$R/venv"
    uv pip install -p "$R/venv/bin/python" numpy==2.4.6
fi
export PATH="$R/venv/bin:$PATH"
python3 -c 'import sys,numpy; assert sys.version_info[:3] == (3,11,17),sys.version; assert numpy.__version__ == "2.4.6",numpy.__version__; print("ENV_OK",sys.version,numpy.__version__)'
[ -x vendor/gtopen/target/release/examples/t2_cont_panel ] || {
    echo 'BLOCKED: solver binary missing; restore the approved build before proceeding'; exit 1;
}
sh tools/gto_spot/plan_a_install_inputs.sh
CONTROL="$R/gto_ckpt/plan_a/repro_co_control_py311"
python3 tools/gto_spot/plan_a_repro_step0.py \
    data/gto_spot/plan_a/specs/p60_co_vs_sb_b40.json 0 AcKc6c "$CONTROL" \
    >"$R/control_reproduction.log" 2>&1
term=$(sha256sum "$CONTROL/term0.json" | cut -d ' ' -f 1)
flop=$(python3 tools/gto_spot/flop_digest.py "$CONTROL/flops/AcKc6c.json" | cut -d ' ' -f 1)
[ "$term" = addd06e97e9bcfea36027fae7c21d71071cb5d77964ff15ca7aab9e3bf7a3e01 ] || {
    echo "BLOCKED: terminal hash mismatch $term"; exit 1;
}
[ "$flop" = a035dc0cc8ae5a15cdedbf31af63b06030021597b43485f087e9b0f0e9326466 ] || {
    echo "BLOCKED: flop digest mismatch $flop"; exit 1;
}
echo "REFERENCE_MATCHED $(date -u +%FT%TZ)"
PLAN_A_IDS=p60_btn_vs_bb_b40 SPOT_PANEL_WORKERS=3 \
    sh tools/gto_spot/run_plan_a.sh 60
echo "WORKER_CHAIN_EXIT_OK $(date -u +%FT%TZ)"
