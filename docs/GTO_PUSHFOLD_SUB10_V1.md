# 10bb 미만 푸시/폴드 버킷 4 / 6 / 8bb (사전 등록 2026-10-31, 계산 전)

작성: session_01JQGBPKuQRnsWkdDiV74y6n (코디네이터 session_012qfUk9 지시, 빈 자리 순위 4번: 10bb 미만 첫 진입 1000핸드당 109회).
**기록만** — 런타임(`gto_pf_data.json`) 연결은 보고 후 승인.

## 1. 게임 (pf10 과 같은 틀, `docs/GTO_PUSHFOLD_10_25_V1.md` 1장 S = 10 규약 그대로)
- 9인, 모든 자리 핸드 시작 스택 정확히 S bb(cfg.stack = S − 1/9), 안테 합계 1bb(자리당 1/9, 데드), 블라인드 0.5/1, 레이크 없음, chip EV.
- 메뉴: 첫 진입 올인/폴드(오픈 레이즈·림프 없음), 올인 받으면 콜/폴드(오버콜 허용, 엔진의 멀티웨이 에퀴티 모델). = cfg_pf10 에서 stack 만 바꿈.
- 버킷 4, 6, 8bb. 이유: gto_pf 버킷은 정수(키 = str(int)), 10bb 아래는 스택마다 범위가 빨리 바뀌어 2bb 간격. 4bb 아래(< 3.75bb)는 계속 범위 밖(기존 판단).
  봇 대회의 10bb 미만 결정이 실제로 어느 스택에 몰리는지는 이 측정에 없다(버킷 몫만 있음) — 다른 간격이 필요하면 같은 cfg 로 버킷만 추가.
- 대칭 스택 가정(짧은 스택일수록 실제와 차이가 큼 — 기록에 표시, 정밀 후보).

## 2. 풀이
- 엔진·드라이버·씨앗 pf10 과 같음: vendored gtopen preflop DCFR(`claude/pushfold-10-25-20261019` 30b7c1c9 의 vendor/gtopen, `t2_pf_solve`), PREFLOP_EQ_SEED=202,
  PREFLOP_MULTIWAY_SEED=202, PREFLOP_EQ_SAMPLES=1200. `tools/gto_spot/pushfold_run.sh` 그대로(25회 단위, 정확 gap ≤ 0.010bb 또는 400회).
- 재현 확인: 먼저 pf10 을 같은 빌드로 다시 풀어 기존 기록(25회, gap 0.00663bb)과 같은지 본다. 다르면 멈추고 보고.
- 기록: `tools/gto_spot/pushfold_record.py <S>` → `data/gto_spot/records/pf<S>.json`(pushfold_record_v1, status quick, G2 = gap ≤ 0.010bb).
- precision 표준(144보드)은 플랍이 없는 트리라 해당 없음(보드 패널이 없다). 솔버 정확도(gap)만이 기준.
