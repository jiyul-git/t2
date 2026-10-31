#!/bin/bash
# 봇 판단 회귀 검사 20개. 결과(종료코드)를 기준 파일과 비교한다. 오래 걸린다(약 10분).
#   bash tools/t2_handoff/regress.sh            → docs/handoff/regress_baseline.txt 와 다르면 diff 출력
# 기준: 20개 모두 0(통과). verify_preflop_closure 는 2026-10-24 검사 갱신(0d9dfa5c 반영)으로 통과한다.
cd "$(dirname "$0")/../.."
export T2_DATA_DIR="${T2_DATA_DIR:-$(mktemp -d)}"     # 개인 지갑 폴더를 건드리지 않게
OUT=$(mktemp)
# 상대 레인지 ↔ GTO 기준 동기화(2026-10-30). 기준 파일 비교와 별개로, 실패하면 바로 멈춘다.
python3 tools/verify_range_sync.py > /dev/null 2>&1 || { echo "RANGE_SYNC_FAIL: python3 tools/verify_range_sync.py"; exit 1; }
echo "range sync ok"
# 첫 진입 GTO × 머니점프 합성·자리 기준 BF(2026-10-31). 실패하면 바로 멈춘다.
python3 tools/verify_money_compose.py > /dev/null 2>&1 || { echo "MONEY_COMPOSE_FAIL: python3 tools/verify_money_compose.py"; exit 1; }
echo "money compose ok"
for t in tools/verify_core_p7_cold_reraise.py tools/verify_core_p7_observation.py tools/verify_core_multiway_reads.py \
  tools/verify_core_joint_nut.py tools/verify_core_sizing_ownership.py tools/verify_preflop_closure.py \
  tools/verify_human_model_v3.py tools/verify_human_model_v3_runtime.py tools/verify_human_model_v3_integration.py \
  tools/verify_money_jump_context.py tools/verify_money_jump_observation.py tools/verify_money_pressure_signals.py \
  tools/verify_hand130_b37_replay.py tools/verify_calloff_price_routing.py tools/verify_hand130_exact_icm.py \
  tools/verify_hand130_partial_call_icm.py tools/verify_hand130_part2.py tools/verify_hand130_calloff_isolation.py \
  tools/verify_hand130_skill_semantics.py tools/verify_p6_calloff.py; do
  timeout 900 nice python3 $t > /dev/null 2>&1; echo "$? $t"
done > $OUT
diff docs/handoff/regress_baseline.txt $OUT && echo "SAME_AS_BASELINE"
