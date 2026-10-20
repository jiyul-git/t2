#!/data/data/com.termux/files/usr/bin/sh
# 게이트웨이가 꺼지면(휴대폰이 signal 9 로 죽여도) 알아서 다시 켠다. Termux 에서:
#
#   termux-wake-lock
#   sh gateway/run_forever.sh                      # 기본 설정 gateway/gateway.dev.json
#   sh gateway/run_forever.sh gateway/other.json   # 다른 설정 파일
#
# 끝내려면 Ctrl+C 를 두 번(재시작 대기 중에 한 번 더). 남은 게임 서버는 게이트웨이가
# 다시 켜질 때 스스로 정리한다(run/<uid>/server.pid).
cd "$(dirname "$0")/.." || exit 1
CONF="${1:-gateway/gateway.dev.json}"
trap 'echo; echo "[run_forever] 종료"; exit 0' INT TERM
n=0
while :; do
    start=$(date +%s)
    python3 gateway/gateway.py --config "$CONF"
    rc=$?
    # 금방(30초 안) 다시 죽으면 설정 오류일 수 있으니 기다림을 늘린다(최대 60초).
    if [ $(( $(date +%s) - start )) -lt 30 ]; then n=$((n + 1)); else n=0; fi
    wait_s=$(( n * 5 )); [ "$wait_s" -gt 60 ] && wait_s=60; [ "$wait_s" -lt 2 ] && wait_s=2
    echo "[run_forever] $(date '+%m-%d %H:%M:%S') 게이트웨이 종료(코드 $rc) — ${wait_s}초 뒤 다시 켭니다"
    sleep "$wait_s"
done
