#!/bin/sh
# 모으는 세션 준비(공용, 모든 스택): 계산 체크아웃 + 전략 저장 패치 + 행렬 끝점 엔진 패치 + 풀이·덤프·내보내기·패널 실행 파일 빌드.
# 저장소 루트에서: sh tools/gto_fulltree/ft_coord_setup.sh   (끝줄 FT_COORD_SETUP_OK)
# 엔진 패치(t2_matrix_terminal.patch): 표에 선택 필드 seats[].matrix(169x169, M[h*169+j])가 있으면 끝점 값 = Σ_j dist_opp[j]·M[h][j](상대 현재 레인지에 반응).
# matrix 가 없는 표·표 없는 끝점은 패치 전과 비트 동일. t2_ft_export 는 T2_EXPORT_STATIC_MATRIX=1 이면 정적 손패×손패 행렬(static_matrix)도 낸다.
set -e
R=$(cd "$(dirname "$0")/../.." && pwd)
C=${FT_CALC:-/home/user/calc}
CEN=79a9aca658a2c1fcbec7e24d910429a2a8e79917
if [ ! -d $C ]; then
  for i in 1 2 3 4; do git -C $R fetch -q --depth=1 origin chatgpt/terminal-census-v2-20260930 && break || sleep $((2 ** i)); done
  [ "$(git -C $R rev-parse FETCH_HEAD)" = "$CEN" ] || { echo "census tip moved"; exit 1; }
  git -C $R worktree add --no-checkout $C $CEN
  git -C $C sparse-checkout set vendor/gtopen tools/gto_spot tools/gto_validation tools/gto_hu_continuation data/gto_hu_continuation data/gto_terminal_expansion/terminals data/gto_spot/plan_a
  git -C $C checkout -q $CEN
fi
# 설정 파일이 sparse 목록에 없던 체크아웃을 위해 보충
mkdir -p $C/data/gto_spot/plan_a
for f in $C/data/gto_spot/plan_a/cfg_p*_o25.json; do [ -e "$f" ] && break; git -C $R show origin/chatgpt/terminal-census-v2-20260930:data/gto_spot/plan_a/cfg_p60_o25.json > $C/data/gto_spot/plan_a/cfg_p60_o25.json 2>/dev/null || true; done
git -C $C apply --check $R/tools/gto_fulltree/t2_cont_panel_strategy.patch 2>/dev/null && git -C $C apply $R/tools/gto_fulltree/t2_cont_panel_strategy.patch || true
git -C $C apply --check $R/tools/gto_fulltree/t2_matrix_terminal.patch 2>/dev/null && git -C $C apply $R/tools/gto_fulltree/t2_matrix_terminal.patch || true
grep -q "fn matrix_for" $C/vendor/gtopen/crates/solver/src/preflop/t2cont.rs || { echo "matrix patch missing"; exit 1; }
X=$C/vendor/gtopen/crates/solver
cp $R/tools/gto_fulltree/t2_pf_solve.rs $R/tools/gto_fulltree/t2_ft_export.rs $X/examples/
grep -q 'name = "t2_pf_solve"' $X/Cargo.toml || printf '\n[[example]]\nname = "t2_pf_solve"\n' >> $X/Cargo.toml
grep -q 'name = "t2_ft_export"' $X/Cargo.toml || printf '\n[[example]]\nname = "t2_ft_export"\nrequired-features = ["t2-cont"]\n' >> $X/Cargo.toml
(cd $C/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_pf_solve --example t2_ft_export --example t2_tree_dump --example t2_cont_panel)
echo FT_COORD_SETUP_OK
