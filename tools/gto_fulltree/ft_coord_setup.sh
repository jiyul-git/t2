#!/bin/sh
# 모으는 세션용 계산 도구 빌드(ft60 에는 없던 소스를 저장소에 둠): /home/user/calc = census 79a9aca6 + 예제 t2_pf_solve, t2_ft_export
# 사용: 저장소 루트에서 sh tools/gto_fulltree/ft_coord_setup.sh   (먼저 census 를 /home/user/calc 에 sparse 체크아웃: ft_board_setup.sh 의 앞부분과 같음)
set -e
R=$(cd "$(dirname "$0")/../.." && pwd); C=${FT_CALC:-/home/user/calc}; X=$C/vendor/gtopen/crates/solver
cp $R/tools/gto_fulltree/t2_pf_solve.rs $R/tools/gto_fulltree/t2_ft_export.rs $X/examples/
grep -q 'name = "t2_pf_solve"' $X/Cargo.toml || printf '\n[[example]]\nname = "t2_pf_solve"\n' >> $X/Cargo.toml
grep -q 'name = "t2_ft_export"' $X/Cargo.toml || printf '\n[[example]]\nname = "t2_ft_export"\nrequired-features = ["t2-cont"]\n' >> $X/Cargo.toml
(cd $C/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_pf_solve --example t2_ft_export --example t2_tree_dump --example t2_tree_estimate)
echo FT_COORD_SETUP_OK
