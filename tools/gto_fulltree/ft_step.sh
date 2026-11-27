#!/bin/bash
# 한 단계 넘기기(조정 세션 일 전부를 한 명령으로). 각 부분은 이미 끝났으면 건너뛴다 → 몇 번이고 다시 불러도 된다.
#   FT_STACK=60 bash tools/gto_fulltree/ft_step.sh <k>     (k 단계 보드 결과가 다 모였을 때)
# 순서(마지막에 GitHub Actions 보드 계산 자동 시작): collect k → 판정(연구실 봇 judge, continue 일 때만 진행) → next_tables k → 트리 풀이 k+1(ft_solve.sh) → 덤프 저장 → prepare k+1(균형 패널, 묶음당 작업 하나)
#       → used_gross 저장 → gha_jobs.txt(k+1) 작성 → 커밋·푸시. 마지막 줄 STEP_READY <k+1> <묶음수> / STEP_HOLD <판정> <이유>(종료코드 2) / STEP_FAIL <이유>.
# 환경: FT_STACK, FT_WORK(기본 /home/user/gto_ckpt/ft<STACK>c), FT_REPLACE(next_tables 섞지 않기, 기본 0),
#       FT_PREP_ENV(prepare 에 더 줄 환경, 예 "FT_MIN_REACH=0.001").
set -u
K=$1; K1=$((K+1)); ST=${FT_STACK:-60}; export FT_STACK=$ST
R=$(git rev-parse --show-toplevel); cd "$R"; BR=$(git rev-parse --abbrev-ref HEAD)
W=${FT_WORK:-/home/user/gto_ckpt/ft${ST}c}; export FT_WORK=$W; D=data/ft$ST
PY=python3; fail() { echo "STEP_FAIL $*"; exit 1; }
commit() { git add -A "$D" && { git diff --cached --quiet || git commit -q -m "ft$ST $1"; } && git push -q origin HEAD:"$BR" || fail "push $1"; }
# 1) collect k
if [ ! -f $D/step$K/collect/report.json ] || ! grep -q '"complete": true' $D/step$K/collect/report.json; then
  FT_PANEL_SET=bal $PY tools/gto_fulltree/ft60.py collect $K > $W/collect$K.log 2>&1 || fail "collect: $(tail -1 $W/collect$K.log)"
  grep -q '"complete": true' $D/step$K/collect/report.json || fail "collect incomplete: $(tail -1 $W/collect$K.log | cut -c1-120)"
  commit "step$K collect"
fi
# 1.5) 판정(연구실 봇과 같은 코드·기준). continue 일 때만 다음으로. 아니면 STEP_HOLD(사람·조정 세션이 판단)
AP=$W/lab_autopilot; mkdir -p $AP; git fetch -q origin claude/lab_autopilot && git archive FETCH_HEAD tools/gto_fulltree/lab_autopilot | tar -x -C $W --strip-components=2 || fail "lab_autopilot 받기"
if [ ! -f $D/step$K1/tables/manifest.json ]; then
  $PY tools/gto_fulltree/ft_judge.py $AP $ST $K $W/collect_s$K > $W/judge$K.log 2>&1 || fail "judge: $(tail -2 $W/judge$K.log | tr '\n' ' ' | cut -c1-200)"
  commit "step$K judge"
  JS=$(tail -1 $W/judge$K.log | awk '{print $2}')
  [ "$JS" = continue ] || { echo "STEP_HOLD $JS $(grep '^reasons' $W/judge$K.log | cut -c1-250)"; exit 2; }
fi
# 2) next_tables k
[ -f $D/step$K1/tables/manifest.json ] || { $PY tools/gto_fulltree/ft60.py next_tables $K > $W/next$K.log 2>&1 || fail "next_tables"; commit "step$K1 tables"; }
# 3) 트리 풀이 k+1
[ -s $W/solve_s$K1/final_n ] && [ -s $W/solve_s$K1/dump.jsonl ] || sh tools/gto_fulltree/ft_solve.sh $K1 > $W/solve$K1.log 2>&1 || fail "solve"
[ -s $W/solve_s$K1/dump.jsonl ] || fail "no dump"
mkdir -p $D/step$K1/solve; [ -f $D/step$K1/solve/dump.jsonl.gz ] || { gzip -c $W/solve_s$K1/dump.jsonl > $D/step$K1/solve/dump.jsonl.gz; cp $W/solve_s$K1/final_n $D/step$K1/solve/; cp $W/solve_s$K1/exact_$(cat $W/solve_s$K1/final_n).json $D/step$K1/solve/ 2>/dev/null; commit "step$K1 solve dump"; }
# 3.5) 실용 수렴(마감 기준): 도달확률 >= FT_FREQ_REACH(0.02) 결정 노드에서 이전 단계 덤프 대비 프리플랍 빈도 변화가 FT_FREQ_STOP(기본 0.02) 미만이면 멈추고 보고
PREV=$D/step$K/solve/dump.jsonl.gz
if [ -f $PREV ] && [ ! -f $D/step$K1/freq_change.txt ]; then
  $PY tools/gto_fulltree/ft_freq_change.py $PREV $W/solve_s$K1/dump.jsonl ${FT_FREQ_REACH:-0.02} > $D/step$K1/freq_change.txt 2>&1 && commit "step$K1 freq change"
fi
if [ -f $D/step$K1/freq_change.txt ] && [ "${FT_FREQ_HOLD:-0}" = 1 ]; then   # 기록만(멈춤 기준은 연구실 봇 judge 하나)
  FM=$(awk '/^FREQ_MAX/{print $2}' $D/step$K1/freq_change.txt)
  python3 -c "import sys; sys.exit(0 if float('$FM') < float('${FT_FREQ_STOP:-0.02}') else 1)" && { echo "STEP_HOLD freq_stable 프리플랍 최대 변화 $FM < ${FT_FREQ_STOP:-0.02} — 차트 단계로"; exit 2; }
fi
# 4) prepare k+1 (묶음마다 작업 하나)
if [ ! -f $D/step$K1/bundles.tsv ]; then
  env ${FT_PREP_ENV:-} FT_PANEL_SET=bal FT_SESSIONS=999 $PY tools/gto_fulltree/ft60.py prepare $K1 $W/solve_s$K1/ck.gtop $W/solve_s$K1/dump.jsonl > $W/prep$K1.log 2>&1 || fail "prepare: $(tail -1 $W/prep$K1.log | cut -c1-120)"
  gzip -c $W/step${K1}_export.jsonl > $D/step$K1/used_gross.jsonl.gz
  commit "step$K1 prepare"
fi
# 5) gha_jobs.txt
NB=$(awk 'NR>1' $D/step$K1/bundles.tsv | wc -l)
# 보드 번호 = assign.tsv 의 세션 번호(연구실 봇·클라우드 세션과 같은 번호 → claim 이 겹치지 않음). FT_SESSIONS=999 라 번호마다 묶음 하나.
awk -v st=$ST -v br=$BR 'NR>1{a[$2]=a[$2]" "$1} END{for(n in a) printf "%s %s %d%s\n", st, br, n, a[n]}' $D/step$K1/assign.tsv | sort -k3,3n > $D/step$K1/gha_jobs.txt
commit "step$K1 gha_jobs"
# 6) GitHub Actions 로 보드 계산 시작(트리거 브랜치 푸시). FT_LAUNCH=0 이면 건너뜀.
if [ "${FT_LAUNCH:-1}" = 1 ]; then
  TB=claude/gha_ft_${ST}_s$K1; T=$(mktemp -d); git worktree add -q --detach $T HEAD
  ( cd $T && cp $D/step$K1/gha_jobs.txt gha_jobs.txt && git add gha_jobs.txt && git commit -q -m "gha: ft$ST step$K1 보드 $NB 묶음" && git push -q origin HEAD:refs/heads/$TB ) || fail "launch"
  git worktree remove --force $T; echo "launched $TB"
fi
echo "STEP_READY $K1 $NB"
