#!/bin/sh
# 60bb 전체 트리 보드 세션 준비(컨테이너 하나, 약 10~20분). 저장소 루트에서: sh tools/gto_fulltree/ft_board_setup.sh
# 1) 계산 체크아웃 /home/user/calc = census 79a9aca6 의 필요한 폴더만(sparse) + 전략 저장 패치 + t2_cont_panel 빌드
# 2) Python 3.11 + numpy 2.4.6 (3.12+ 는 float 합·해시가 달라 같은 결과가 안 나온다) → /home/user/gto_ckpt/py311bin/python3
set -e
R=$(cd "$(dirname "$0")/../.." && pwd)
C=${FT_CALC:-/home/user/calc}
CEN=79a9aca658a2c1fcbec7e24d910429a2a8e79917
if [ ! -x $C/vendor/gtopen/target/release/examples/t2_cont_panel ]; then
  for i in 1 2 3 4; do git -C $R fetch -q --depth=1 origin chatgpt/terminal-census-v2-20260930 && break || sleep $((2 ** i)); done
  [ "$(git -C $R rev-parse FETCH_HEAD)" = "$CEN" ] || { echo "census tip moved: $(git -C $R rev-parse FETCH_HEAD) != $CEN"; exit 1; }
  [ -d $C ] || git -C $R worktree add --no-checkout $C $CEN
  git -C $C sparse-checkout set vendor/gtopen tools/gto_spot tools/gto_validation tools/gto_hu_continuation data/gto_hu_continuation
  git -C $C checkout -q $CEN
  git -C $C apply --check $R/tools/gto_fulltree/t2_cont_panel_strategy.patch 2>/dev/null && git -C $C apply $R/tools/gto_fulltree/t2_cont_panel_strategy.patch
  (cd $C/vendor/gtopen && cargo build --release -p solver --features t2-cont --example t2_cont_panel)
fi
if [ ! -x /home/user/gto_ckpt/py311bin/python3 ]; then
  python3.11 -m venv /home/user/gto_ckpt/py311 && /home/user/gto_ckpt/py311/bin/pip install -q numpy==2.4.6
  mkdir -p /home/user/gto_ckpt/py311bin && printf '#!/bin/sh\nexec /home/user/gto_ckpt/py311/bin/python "$@"\n' > /home/user/gto_ckpt/py311bin/python3
  chmod +x /home/user/gto_ckpt/py311bin/python3
fi
/home/user/gto_ckpt/py311bin/python3 -c "import numpy; assert numpy.__version__ == '2.4.6'"
grep -q T2_EXPORT_STRATEGY $C/vendor/gtopen/crates/solver/examples/t2_cont_panel.rs || { echo "strategy patch missing"; exit 1; }
echo FT_BOARD_SETUP_OK
