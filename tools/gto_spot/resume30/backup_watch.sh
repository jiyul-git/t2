#!/bin/sh
# usage: backup_watch.sh <spot_id> <branch> <repo_dir>
# stepK (24-board loop step): stepK.tgz once its report.json exists; stepK_partial.tgz every ~30 min while running.
# stepK_p144 / p144sK (144-board work; P144 boards are written into stepK/term*_flops): incremental parts
#   <dir>_partN.tgz = files changed since the previous part (all of stepK_p144 or p144sK, plus new files in the
#   flops dirs they write to); a part every ~2 h and a final part when report.json appears. Restore: extract parts in order.
ID=$1; BR=$2; R=$3; SP=/home/user/gto_ckpt/spots/$ID; D=gto_split_backup/$ID; W=/home/user/gto_ckpt/watch/$ID
mkdir -p $W; cd $R || exit 1
push() { ( flock 9; git add -A $D && git commit -q -m "$1

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011TJwxsbnvbQgF3L3dSFKFd" || exit 0
  for t in 2 4 8 16 0; do timeout 900 git push -q origin HEAD:$BR && break; [ $t = 0 ] || sleep $t; done
  echo "$(date -u +%FT%TZ) $1" >> /home/user/gto_ckpt/watch/$ID.log ) 9>/home/user/gto_ckpt/watch/git.lock; }
states() { for f in state.json state_p144.json; do [ -f $SP/$f ] && cp $SP/$f $D/$f; done
  (cd $D && sha256sum $(ls *.tgz state*.json CLAIM.md STOPPED.md 2>/dev/null) > SHA256SUMS); }
part() { # $1 = dir name (stepK_p144 | p144sK); $2 = label
  stamp=$W/$1.stamp; n=$(ls $D/$1_part*.tgz 2>/dev/null | wc -l)
  case $1 in *_p144) b=${1%_p144}; srcs="$1 $b";; *) srcs="$1"; f=$(python3 -c "import json;print(json.load(open('$SP/state_p144.json')).get('from_step',''))" 2>/dev/null); [ -n "$f" ] && srcs="$1 step$f";; esac
  [ -f $stamp ] || { [ "$1" = step3_p144 ] && [ -f $D/step3_p144_term0_partial.tgz ] && touch -r $D/step3_p144_term0_partial.tgz $stamp; }
  (cd $SP && if [ -f $stamp ]; then find $srcs -type f -newer $stamp; else find $1 -type f; case $1 in *_p144) find ${1%_p144} -type f -newer $R/$D/${1%_p144}.tgz;; esac; fi | sort -u > $W/list)
  touch $W/now
  if [ -s $W/list ]; then tar czf $D/$1_part$n.tgz -C $SP -T $W/list; mv $W/now $stamp; states; push "$ID: $2 $1 part$n ($(wc -l < $W/list) files)"; fi; }
n=0; last=""
while :; do
  mkdir -p $D
  for s in $(ls -d $SP/step* $SP/p144s* 2>/dev/null); do k=$(basename $s)
    [ -s "$s/report.json" ] || continue
    [ -e $W/$k.done ] && continue
    case $k in
      *_p144|p144s*) part $k "final";;
      *) [ -s $D/$k.tgz ] || { tar czf $D/$k.tgz -C $SP $k; rm -f $D/${k}_partial.tgz; states
           push "$ID: back up $k (decision: $(python3 -c "import json;print(json.load(open('$s/report.json')).get('decision'))" 2>/dev/null))"; };;
    esac
    touch $W/$k.done
  done
  n=$((n+1))
  cur=$(for s in $(ls -dt $SP/step* $SP/p144s* 2>/dev/null); do [ -s $s/report.json ] || { echo $s; break; }; done); k=$(basename "$cur")
  case $k in step*_p144|p144s*) every=120;; *) every=30;; esac
  if [ -n "$cur" ] && [ $n -ge $every ]; then n=0
    case $k in
      step*_p144|p144s*) part $k "partial";;
      *) sig="$k $(ls $cur/term*_flops/*.json 2>/dev/null | wc -l)"
         if [ "$sig" != "$last" ]; then last=$sig; tar czf $D/${k}_partial.tgz -C $SP $k $( [ -f $SP/state.json ] && echo state.json ); states; push "$ID: partial backup $sig flops"; fi;;
    esac
  fi
  sleep 60
done
