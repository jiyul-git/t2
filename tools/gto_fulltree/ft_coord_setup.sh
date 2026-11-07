#!/bin/sh
# 모으는 세션 준비(스택 무관): 계산 체크아웃(/home/user/calc, census 79a9aca6) + 전략 저장 패치 + 예제 4개 빌드
# (t2_pf_solve, t2_tree_dump, t2_ft_export, t2_cont_panel). t2_pf_solve.rs / t2_ft_export.rs 는 이 폴더의 사본을 넣는다.
# 먼저 sh tools/gto_fulltree/ft_board_setup.sh 가 계산 체크아웃과 python 3.11 을 만든다.
set -e
R=$(cd "$(dirname "$0")/../.." && pwd); C=${FT_CALC:-/home/user/calc}
X=$C/vendor/gtopen/crates/solver
cp $R/tools/gto_fulltree/t2_pf_solve.rs $R/tools/gto_fulltree/t2_ft_export.rs $X/examples/
grep -q 't2_ft_export' $X/Cargo.toml || printf '\n[[example]]\nname = "t2_pf_solve"\n\n[[example]]\nname = "t2_ft_export"\n' >> $X/Cargo.toml
(cd $C/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_pf_solve --example t2_tree_dump --example t2_ft_export --example t2_cont_panel)
echo FT_COORD_SETUP_OK
