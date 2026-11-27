#!/bin/bash
# 한 단계 넘기기(조정 세션 일 전부를 한 명령으로). 각 부분은 이미 끝났으면 건너뛴다 → 몇 번이고 다시 불러도 된다.
#   FT_STACK=60 bash tools/gto_fulltree/ft_step.sh <k>     (k 단계 보드 결과가 다 모였을 때)
# 순서(마지막에 GitHub Actions 보드 계산 자동 시작): collect k → next_tables k → 트리 풀이 k+1(ft_solve.sh) → 덤프 저장 → prepare k+1(균형 패널, 묶음당 작업 하나)
#       → used_gross 저장 → gha_jobs.txt(k+1) 작성 → 커밋·푸시. 마지막 줄 STEP_READY <k+1> <묶음수> 또는 STEP_FAIL <이유>.
# 환경: FT_STACK, FT_WORK(기본 /home/user/gto_ckpt/ft<STACK>c), FT_REPLACE(next_tables 섞지 않기, 기본 0),
#       FT_BOARD_BASE(보드 번호 시작, 기본 1000*(k+1)), FT_PREP_ENV(prepare 에 더 줄 환경, 예 "FT_MIN_REACH=0.001").
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
# 2) next_tables k
[ -f $D/step$K1/tables/manifest.json ] || { $PY tools/gto_fulltree/ft60.py next_tables $K > $W/next$K.log 2>&1 || fail "next_tables"; commit "step$K1 tables"; }
# 3) 트리 풀이 k+1
[ -s $W/solve_s$K1/final_n ] && [ -s $W/solve_s$K1/dump.jsonl ] || sh tools/gto_fulltree/ft_solve.sh $K1 > $W/solve$K1.log 2>&1 || fail "solve"
[ -s $W/solve_s$K1/dump.jsonl ] || fail "no dump"
mkdir -p $D/step$K1/solve; [ -f $D/step$K1/solve/dump.jsonl.gz ] || { gzip -c $W/solve_s$K1/dump.jsonl > $D/step$K1/solve/dump.jsonl.gz; cp $W/solve_s$K1/final_n $D/step$K1/solve/; cp $W/solve_s$K1/exact_$(cat $W/solve_s$K1/final_n).json $D/step$K1/solve/ 2>/dev/null; commit "step$K1 solve dump"; }
# 4) prepare k+1 (묶음마다 작업 하나)
if [ ! -f $D/step$K1/bundles.tsv ]; then
  env ${FT_PREP_ENV:-} FT_PANEL_SET=bal FT_SESSIONS=999 $PY tools/gto_fulltree/ft60.py prepare $K1 $W/solve_s$K1/ck.gtop $W/solve_s$K1/dump.jsonl > $W/prep$K1.log 2>&1 || fail "prepare: $(tail -1 $W/prep$K1.log | cut -c1-120)"
  gzip -c $W/step${K1}_export.jsonl > $D/step$K1/used_gross.jsonl.gz
  commit "step$K1 prepare"
fi
# 5) gha_jobs.txt
NB=$(awk 'NR>1' $D/step$K1/bundles.tsv | wc -l); B0=${FT_BOARD_BASE:-$((1000*K1))}
awk -v st=$ST -v br=$BR -v b0=$B0 'NR>1{printf "%s %s %d %s\n", st, br, b0+NR-1, $1}' $D/step$K1/bundles.tsv > $D/step$K1/gha_jobs.txt
commit "step$K1 gha_jobs"
# 6) GitHub Actions 로 보드 계산 시작(트리거 브랜치 푸시). FT_LAUNCH=0 이면 건너뜀.
if [ "${FT_LAUNCH:-1}" = 1 ]; then
  TB=claude/gha_ft_${ST}_s$K1; T=$(mktemp -d); git worktree add -q --detach $T HEAD
  ( cd $T && cp $D/step$K1/gha_jobs.txt gha_jobs.txt && git add gha_jobs.txt && git commit -q -m "gha: ft$ST step$K1 보드 $NB 묶음" && git push -q origin HEAD:refs/heads/$TB ) || fail "launch"
  git worktree remove --force $T; echo "launched $TB"
fi
echo "STEP_READY $K1 $NB"
