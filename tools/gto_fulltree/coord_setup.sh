#!/bin/sh
# 모으는 세션 준비(컨테이너 하나): 계산 체크아웃(census 79a9aca6, sparse) + 전략 저장 패치 + 풀이·덤프·내보내기·패널 실행 파일 빌드.
# 저장소 루트에서: sh tools/gto_fulltree/coord_setup.sh   (ft_board_setup.sh 의 계산 체크아웃과 같은 것 + t2_pf_solve / t2_ft_export 추가)
# t2_pf_solve.rs 는 claude/pushfold-10-25-20261019 의 vendor 사본, t2_ft_export.rs 는 이 폴더의 소스(ft60 코디네이터가 로컬에서만 쓰던 도구를 저장소에 둔 것).
set -e
R=$(cd "$(dirname "$0")/../.." && pwd)
C=${FT_CALC:-/home/user/calc}
CEN=79a9aca658a2c1fcbec7e24d910429a2a8e79917
if [ ! -d $C ]; then
  for i in 1 2 3 4; do git -C $R fetch -q --depth=1 origin chatgpt/terminal-census-v2-20260930 && break || sleep $((2 ** i)); done
  [ "$(git -C $R rev-parse FETCH_HEAD)" = "$CEN" ] || { echo "census tip moved"; exit 1; }
  git -C $R worktree add --no-checkout $C $CEN
  git -C $C sparse-checkout set vendor/gtopen tools/gto_spot tools/gto_validation tools/gto_hu_continuation data/gto_hu_continuation data/gto_terminal_expansion/terminals
  git -C $C checkout -q $CEN
fi
git -C $C apply --check $R/tools/gto_fulltree/t2_cont_panel_strategy.patch 2>/dev/null && git -C $C apply $R/tools/gto_fulltree/t2_cont_panel_strategy.patch || true
cp $R/tools/gto_fulltree/t2_pf_solve.rs $R/tools/gto_fulltree/t2_ft_export.rs $C/vendor/gtopen/crates/solver/examples/
(cd $C/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_pf_solve --example t2_tree_dump --example t2_ft_export --example t2_cont_panel)
echo FT_COORD_SETUP_OK
