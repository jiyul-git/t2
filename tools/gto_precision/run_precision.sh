#!/bin/sh
# One launch of the precision check of one spot (docs/GTO_PRECISION_RUNNER.md). Run as a TRACKED background task (2 h limit) and relaunch the
# same command until it prints PREC_DONE / PREC_PAUSED: finished flops (per panel / terminal) are reused, the step continues where it stopped.
#   PREC_CALC_ROOT=/home/user/calc PREC_SESSION=session_<id> sh tools/gto_precision/run_precision.sh <spot_id>
# Progress (state.json + per step the small inputs and report) is committed and pushed to the CURRENT branch of this checkout at launch,
# after every finished terminal-panel, after every step and at the end. Flop artifacts stay container-local (recomputed after a loss).
# PREC_STAGE_LIMIT (default 1) = steps per approval (stage 1 = replication only); PREC_MAX_STEPS (default 3).
set -u
ID=$1
REPO=$(cd "$(dirname "$0")/../.." && pwd)
cd "$REPO"
: "${PREC_CALC_ROOT:=/home/user/calc}"; export PREC_CALC_ROOT
: "${PREC_SESSION:?set PREC_SESSION=session_<id> for the commit trailer}"
export SPOT_PANEL_WORKERS=${SPOT_PANEL_WORKERS:-4}
export T2_EXPORT_STRATEGY=${T2_EXPORT_STRATEGY:-1}   # flop strategy files (<board>.strategy.json; needs the patched solver, docs 8장)
PY=${PREC_PYTHON:-/home/user/gto_ckpt/py311bin/python3}      # Python 3.11 (float sums / hashes as the quick runs)
BR=$(git rev-parse --abbrev-ref HEAD)
case "$BR" in master|test3|HEAD) echo "refusing to commit on $BR"; exit 2;; esac
W=/home/user/gto_ckpt/precision/$ID
P=data/gto_precision/progress/$ID
LOG=/home/user/gto_ckpt/precision/$ID.log
mkdir -p $W
pkill -f "gto_precision/precision_loop.py $ID" 2>/dev/null; pkill -f t2_cont_panel 2>/dev/null; pkill -f solve_panel.py 2>/dev/null; sleep 2   # orphans of a killed launch

push() { for t in 2 4 8 16; do git push -q -u origin "$BR" && return 0; sleep $t; done; return 1; }
backup() {   # $1 = message
  mkdir -p $P
  [ -s $W/state.json ] && cp $W/state.json $P/
  for d in $W/s*/; do
    [ -d "$d" ] || continue
    s=$(basename $d); mkdir -p $P/$s
    for f in report.json tables_used.json matrices_used.json spot.json tables_A.json tables_B.json tables_AB.json matrices_A.json matrices_B.json matrices_AB.json; do
      [ -s $d/$f ] && gzip -9nc $d/$f > $P/$s/$f.gz
    done
    for f in $d/term*.json; do [ -s "$f" ] && cp "$f" $P/$s/; done
    for f in $d/term*_[AB]/run_ledger.jsonl; do [ -s "$f" ] && cp "$f" $P/$s/$(basename $(dirname $f)).ledger.jsonl; done
    ls -d $d/term*_[AB] 2>/dev/null | while read x; do [ -e $x/done ] && echo "$(basename $x)"; done > $P/$s/panels_done.txt
    for x in $d/term*_[AB]; do   # finished panel: its flop strategies as one tarball (values stay container-local, they are recomputable)
      [ -e $x/done ] || continue
      n=$(ls $x/*.strategy.json 2>/dev/null | wc -l); [ $n -gt 0 ] || continue
      T=data/gto_precision/strategy/$ID/$s/$(basename $x).tgz
      [ -s $T ] && [ "$(cat $T.count 2>/dev/null)" = "$n" ] && continue
      mkdir -p $(dirname $T); tar -C $x -czf $T $(cd $x && ls *.strategy.json) && echo $n > $T.count
      [ -s $x/strategy_backfill.json ] && cp $x/strategy_backfill.json data/gto_precision/strategy/$ID/$s/$(basename $x).backfill.json
    done
  done
  git add -A $P data/gto_precision/records data/gto_precision/strategy 2>/dev/null
  git commit -qm "$1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/$PREC_SESSION" && push
}
ndone() { ls $W/s*/term*_[AB]/done $W/s*/report.json 2>/dev/null | wc -l; }

# after a container loss: restore state.json and the step's terminal files from the branch (flops are recomputed)
if [ ! -s $W/state.json ] && [ -s $P/state.json ]; then
  cp $P/state.json $W/
  for s in $P/s*/; do [ -d "$s" ] || continue; mkdir -p $W/$(basename $s); cp $s/term*.json $W/$(basename $s)/ 2>/dev/null
    for f in $s/*.json.gz; do [ -s "$f" ] && gunzip -c $f > $W/$(basename $s)/$(basename $f .gz); done; done
  echo "restored $ID from $P"
fi
if [ -s $W/state.json ] && $PY -c "import json,sys; d=json.load(open('$W/state.json')); sys.exit(0 if d.get('final') else 1)"; then echo PREC_DONE; exit 0; fi

backup "precision $ID: launch $(date -u +%FT%TZ)"
$PY tools/gto_precision/precision_loop.py $ID >> $LOG 2>&1 &
RUN=$!
seen=$(ndone)
while kill -0 $RUN 2>/dev/null; do
  sleep 60
  n=$(ndone); [ "$n" != "$seen" ] && { seen=$n; backup "precision $ID: progress ($n panels/steps done)"; }
done
wait $RUN; rc=$?
backup "precision $ID: launch end rc=$rc"
tail -3 $LOG
if [ $rc -ne 0 ]; then echo PREC_FAILED_RUN; exit 1; fi
if $PY -c "import json,sys; d=json.load(open('$W/state.json')); sys.exit(0 if d.get('final') else 1)"; then echo PREC_DONE; else echo PREC_PAUSED; fi
