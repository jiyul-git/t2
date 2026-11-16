#!/bin/bash
# 연구실 컴퓨터에서 세 명 플랍 전체(턴 49 × 리버 48)를 하나 푼다. 메모리 약 27GB.
#   bash tools/gto_3way_probe/lab_3way.sh            # 기본 Kc7d4h, 반복 최대 300(오차 0.1% pot 이면 먼저 멈춤)
#   BOARD=9h8h3c ITERS=300 bash tools/gto_3way_probe/lab_3way.sh
# WSL 1 이면 창을 닫으면 계산이 꺼지므로 창을 열어 둔다. 25회마다 로그 한 줄. 끝나면 결과를 claude/ft3way_lab_1 로 올린다.
set -u
B=${BOARD:-Kc7d4h}; IT=${ITERS:-300}
REPO=$(git rev-parse --show-toplevel) || exit 1; cd "$REPO"
for c in "${FT_CALC:-}" /home/user/calc $HOME/calc $HOME/t2lab/calc; do [ -n "$c" ] && [ -d "$c/vendor/gtopen" ] && { CALC=$c; break; }; done
[ -n "${CALC:-}" ] || { echo "계산 체크아웃이 없음 (lab_ft.sh 를 한 번 돌리면 생김)"; exit 1; }
[ -f $CALC/vendor/gtopen/crates/solver/examples/t2_3way.rs ] || { echo "t2_3way.rs 없음: $CALC"; exit 1; }
(cd $CALC/vendor/gtopen && cargo build --release --example t2_3way) || exit 1
avail=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo); echo "사용 가능 메모리 ${avail}GB (필요 약 27GB)"
[ "$avail" -ge 28 ] || { echo "메모리 부족 — 다른 계산(lab_ft.sh 등)을 멈추고 다시"; exit 1; }
git fetch -q origin claude/ft60_baltest && git checkout -q -B claude/ft3way_lab_1 origin/claude/ft60_baltest || exit 1
mkdir -p data/gto_3way_probe; O=data/gto_3way_probe/${B}_full
echo "$(date '+%m-%d %H:%M') 시작 $B 반복 최대 $IT, 스레드 $(nproc)"
RAYON_NUM_THREADS=$(nproc) $CALC/vendor/gtopen/target/release/examples/t2_3way solve tools/gto_3way_probe/term3_btn_sb_bb.json $B $IT $O.json --every 25 --target 0.1 2>&1 | tee $O.log
echo "$(date '+%m-%d %H:%M') 끝"
git add $O.* && git commit -q -m "3way lab full flop: $B" && for i in 1 2 3 4 5; do git push -q -u origin claude/ft3way_lab_1 && break; sleep $((i*5)); done && echo "올림 완료: claude/ft3way_lab_1"
