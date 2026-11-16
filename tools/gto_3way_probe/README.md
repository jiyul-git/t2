# 세 명 플랍 실측 (2026-11-16)

- 끝점: 60bb 4단계 "BTN 2.5 오픈 → SB 콜 → BB 콜"(세 명 끝점 중 가장 큼, 플랍 도달의 6.2%). `mk_term3.py` 가 4단계 덤프에서 자리별 클래스 남는 몫(자기 행동 확률의 곱)을 만든다.
  같은 방식으로 2명 끝점 term01 을 다시 만들면 저장된 파일과 차이 1e-7 (검증).
- 전체 플랍 하나(턴 49 × 리버 48)는 메모리 26.9GB(`t2_3way build`) → 클라우드(15GB) 불가, 연구실 64GB 몫.
- 클라우드 실측: 턴·리버를 n장씩만 골라(`runouts.py`, balanced = 숫자·무늬 고르게 / random) 풀고,
  n 을 늘릴 때 클래스별 플랍 값이 어디로 모이는지, balanced 가 random 보다 빨리 모이는지 본다.
- 실행: `run_probe.sh`. 결과 `data/gto_3way_probe/`.

## 연구실 컴퓨터(64GB)에서 전체 플랍 하나 풀기
```sh
git fetch origin claude/ft60_baltest && git checkout -b claude/ft3way_lab_1 origin/claude/ft60_baltest
sh tools/gto_fulltree/ft_board_setup.sh
(cd /home/user/calc/vendor/gtopen && cargo build --release --example t2_3way)
mkdir -p data/gto_3way_probe
RAYON_NUM_THREADS=$(nproc) nohup /home/user/calc/vendor/gtopen/target/release/examples/t2_3way solve \
  tools/gto_3way_probe/term3_btn_sb_bb.json Kc7d4h 400 data/gto_3way_probe/Kc7d4h_full.json --every 25 --target 0.1 \
  > data/gto_3way_probe/Kc7d4h_full.log 2>&1 &
```
메모리 약 27GB. 시간은 첫 25회 로그(it 25 … s)로 판단한다. 클라우드 실측(턴·리버 n장)의 기준값이 된다.
