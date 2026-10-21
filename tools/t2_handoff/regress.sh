#!/bin/bash
# 봇 판단 회귀 검사 20개. 결과(종료코드)를 기준 파일과 비교한다. 오래 걸린다(약 10분).
#   bash tools/t2_handoff/regress.sh            → docs/handoff/regress_baseline.txt 와 다르면 diff 출력
# 기준에서 원래 실패하는 것: verify_preflop_closure(1) — 옛 master 4f6cf100 에서도 실패.
cd "$(dirname "$0")/../.."
export T2_DATA_DIR="${T2_DATA_DIR:-$(mktemp -d)}"     # 개인 지갑 폴더를 건드리지 않게
OUT=$(mktemp)
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
