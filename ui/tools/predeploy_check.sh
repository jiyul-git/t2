#!/bin/sh
# UI 배포 직전 회귀검사. 실제 라이브 상태는 건드리지 않는다.
set -eu

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"

# tools/*.py 직접 실행 시 repo root를 import 경로에 넣는다.
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "=== syntax ==="
python3 -m py_compile   live2.py session.py view.py   ui/server/ui_view.py ui/server/ui_server.py

if command -v node >/dev/null 2>&1; then
  node --check ui/web/app.js
else
  echo "node 없음: app.js 구문검사는 건너뜁니다"
fi

echo
echo "=== forced blind all-in ==="
python3 tools/verify_forced_blind_allin_view.py
python3 tools/verify_forced_blind_allin_showdown.py

echo
echo "=== UI server regression ==="
python3 ui/tools/verify_ui.py --hands 20 --entries 100 --seed 20260920

echo
echo "PREDEPLOY CHECK OK"
