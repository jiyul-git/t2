#!/bin/sh
# Resume of the interrupted 100 bb BB-vs-2.5-open quick spots (coordinator task 2026-10-30, same as run_flat_o25.sh). One launch runs the next unfinished spot to its quick record, then exits;
# relaunch the same command (tracked background task, 2 h limit): finished flops / steps are reused. Backup (progress/ + spot tarball < 100 MB)
# is committed and pushed at launch, after every finished step, and when the spot's record is written.
#   sh tools/gto_spot/run_resume_p100_flat.sh
cd /home/user/t2
IDS="p100_flat_co_vs_bb_o25 p100_flat_lj_vs_bb_o25"
BR=claude/resume_p100_flat_20261030
BK=gto_split_backup/resume_p100_flat
export PATH=/home/user/gto_ckpt/py311bin:$PATH SPOT_PANEL_WORKERS=4     # python3 = 3.11 (float sums / hashes)
NEXT=; for id in $IDS; do [ -s data/gto_spot/quick/$id.json ] || { NEXT=$id; break; }; done
[ -n "$NEXT" ] || { echo ALL_DONE; exit 0; }
pkill -f "tools/gto_spot/spot_loop.py" 2>/dev/null; pkill -f t2_cont_panel 2>/dev/null; pkill -f solve_panel.py 2>/dev/null; sleep 2   # orphans of a killed launch

push() {
  for t in 2 4 8 16; do git push -q -u origin $BR && return 0; sleep $t; done; return 1
}
backup() {   # $1 = message
  sh tools/gto_spot/plan_a_backup_progress.sh $NEXT
  S=/home/user/gto_ckpt/spots/$NEXT
  if [ -d $S ]; then
    tar -C /home/user/gto_ckpt/spots -czf /home/user/gto_ckpt/$NEXT.tgz --exclude='*.log' $NEXT
    [ $(stat -c %s /home/user/gto_ckpt/$NEXT.tgz) -lt 100000000 ] || tar -C /home/user/gto_ckpt/spots -czf /home/user/gto_ckpt/$NEXT.tgz --exclude='*.log' --exclude='first_attempt' $NEXT
    [ $(stat -c %s /home/user/gto_ckpt/$NEXT.tgz) -lt 100000000 ] && mkdir -p $BK && cp /home/user/gto_ckpt/$NEXT.tgz $BK/$NEXT.tgz
  fi
  git add -A data/gto_spot/plan_a/progress/$NEXT $BK data/gto_spot/quick 2>/dev/null
  git commit -qm "$1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JQGBPJuemihXD71P77VUva" && push
}
nrep() { ls /home/user/gto_ckpt/spots/$NEXT/step*/report.json 2>/dev/null | wc -l; }

backup "backup $NEXT (launch $(date -u +%FT%TZ))"
PLAN_A_IDS=$NEXT sh tools/gto_spot/run_quick.sh &
RUN=$!
seen=$(nrep)
while kill -0 $RUN 2>/dev/null; do
  sleep 60
  n=$(nrep); [ "$n" != "$seen" ] && { seen=$n; backup "backup $NEXT: step $((n - 1)) done"; }
done
wait $RUN
if [ -s data/gto_spot/quick/$NEXT.json ]; then
  backup "$NEXT quick record"
  echo "SPOT_DONE $NEXT"
else
  echo "SPOT_FAILED $NEXT"; tail -5 /home/user/gto_ckpt/plan_a/quick.log; exit 1
fi
