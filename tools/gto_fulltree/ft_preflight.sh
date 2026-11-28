#!/bin/bash
# 시작 전 강제 점검(사람·AI 기억에 기대지 않는다). 하나라도 걸리면 종료코드 1 + 이유 한 줄, 시작하지 않는다.
#   bash ft_preflight.sh <STACK> <단계> <단위: coord_solve|coord_step|board_<n>> [--long]
# 1) 공용 작업판(claude/ft_claims): 남이 3시간 안에 갱신한 claim 이 있으면 거부
# 2) 연구실 봇 상태(claude/lab_status status.json): 같은 스택·단계·단위를 지금 돌리고 있으면 거부
# 3) --long(1시간 넘는 계산)인데 여기가 클라우드 세션 컨테이너면 거부 — 쉬면 재시작돼 계산이 죽는다(11-27 실제 두 번). GitHub Actions 나 연구실 봇으로.
ST=$1; K=$2; U=$3; LONG=$4; R=$(git rev-parse --show-toplevel); cd "$R"
fail() { echo "PREFLIGHT_FAIL $*"; exit 1; }
if [ "$LONG" = --long ] && { [ -d /root/.ccr ] || [ -n "${CLAUDE_CODE_REMOTE:-}" ]; }; then
  fail "클라우드 세션 컨테이너에서 긴 계산 금지 — GitHub Actions(ft-step.yml/ft-board.yml) 또는 연구실 봇으로"
fi
git fetch -q origin claude/ft_claims 2>/dev/null && c=$(git show FETCH_HEAD:claims/ft$ST/step$K/$U.json 2>/dev/null) && [ -n "$c" ] && \
  echo "$c" | python3 -c "
import json,sys,datetime as d,os
c=json.load(sys.stdin); me=os.environ.get('FT_OWNER','')
t=d.datetime.fromisoformat(c.get('t_heartbeat',c.get('t_claim')).replace('Z','+00:00'))
age=(d.datetime.now(d.timezone.utc)-t).total_seconds()/3600
sys.exit(1 if age<3 and c.get('owner')!=me else 0)" || fail "claim: ft$ST step$K $U 를 다른 쪽이 잡고 있음"
git fetch -q origin claude/lab_status 2>/dev/null && git show FETCH_HEAD:status.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(1 if any(str(j['stack'])=='$ST' and int(j['step'])==$K and j['unit']=='$U' for j in d.get('jobs',[])) else 0)" || fail "연구실 봇이 ft$ST step$K $U 를 돌리는 중"
echo PREFLIGHT_OK
