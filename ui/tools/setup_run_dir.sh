#!/bin/sh
# 엔진 실행 폴더를 만든다.
#
#   sh ui/tools/setup_run_dir.sh [대상폴더]        기본값 ~/t2_ui_run
#
# **허용 목록 방식이다.** 제외 목록으로 짜면 저장소에 파일이 하나 늘 때마다
# 샌다. 실제로 live2_state.json·hand_archive2*.jsonl·claude_state.json 은
# 전부 git 에 커밋되어 있어서, cp *.json 이나 clone 으로는 진행 중인 게임이
# 실행 폴더로 딸려 들어간다.
#
# 이미 있는 폴더에 다시 돌려도 된다. 코드만 덮어쓰고 상태·아카이브는
# 손대지 않으므로 진행 중인 게임이 유지된다.
set -eu

SRC=$(cd "$(dirname "$0")/../.." && pwd)
DST=${1:-$HOME/t2_ui_run}

# live2 가 전이적으로 import 하는 모듈 전부. view.py 는 ui_view 가
# view_text 라는 이름으로 직접 로드하므로 반드시 포함한다.
MODULES="archetypes bot context depth dynamics field fieldsim formats gto icm
         live2 money_pressure persona plan play preflop ranges reads runner session table
         texture view"

# 데이터 파일. pf_rank.json 이 없으면 preflop.py import 자체가 실패한다.
# style_*.json 은 없어도 죽지는 않지만 스타일 추정 경로가 통째로 꺼진다.
DATA="pf_rank.json style_sig.json style_prior.json"

mkdir -p "$DST"
if [ "$(cd "$DST" && pwd)" = "$SRC" ]; then
    echo "중단: 대상이 엔진 폴더 자신입니다 ($SRC)." >&2
    exit 1
fi

for m in $MODULES; do cp "$SRC/$m.py" "$DST/$m.py"; done
for d in $DATA;    do cp "$SRC/$d"    "$DST/$d";    done
cp "$SRC/ui/server/ui_view.py"   "$DST/ui_view.py"
cp "$SRC/ui/server/ui_server.py" "$DST/ui_server.py"

# web/ 은 2단계 산출물. 아직 비어 있으면 건너뛴다.
if [ -n "$(ls -A "$SRC/ui/web" 2>/dev/null || true)" ]; then
    mkdir -p "$DST/web"
    cp -R "$SRC/ui/web/." "$DST/web/"
fi

# 이 표시 파일이 없으면 ui_server 가 시작을 거부한다.
: > "$DST/UI_SERVER_DIR"

echo "실행 폴더: $DST"
echo "  모듈 $(echo $MODULES | wc -w)개, 데이터 $(echo $DATA | wc -w)개"
echo "  실행: cd $DST && python3 ui_server.py"
echo "  주의: T2_LIVE_STATE 를 설정하지 마세요. 설정하면 접미사가 _alt 로 고정되어"
echo "        cli.py 세션과 아카이브를 공유하게 됩니다."
