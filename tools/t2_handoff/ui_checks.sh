#!/bin/bash
# 화면·게이트웨이 검사. 2026-10-24 기준 모두 통과해야 한다(원래 실패하던 4개는 0d9dfa5c 로 갱신).
# 라운지 자산 검사 2개는 opencv-python-headless 가 필요하다(없으면 환경 오류로 실패: pip install opencv-python-headless).
cd "$(dirname "$0")/../.."
export T2_DATA_DIR="${T2_DATA_DIR:-$(mktemp -d)}"
for t in "python3 tools/verify_gto_pf.py" "python3 gateway/verify_gateway.py" "python3 gateway/verify_stale_backend.py" \
  "python3 ui/tools/verify_profile_api.py" "python3 ui/tools/verify_lounge_assets.py" "python3 ui/tools/lounge_check_assets.py" \
  "python3 ui/tools/verify_action_timeout.py" "python3 ui/tools/verify_clock_ui.py" "python3 ui/tools/verify_vclock_finish_ownership.py" \
  "python3 ui/tools/verify_async_refill.py" "python3 ui/tools/verify_vclock_session.py" \
  "python3 tools/verify_ui_tournament_panel.py"; do
  timeout 900 $t > /dev/null 2>&1; echo "$? $t"
done
for f in ui/tools/verify_*.js; do timeout 300 node $f > /dev/null 2>&1; echo "$? node $f"; done
