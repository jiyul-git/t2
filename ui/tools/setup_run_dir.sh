#!/bin/sh
# 엔진 실행 폴더를 만든다.
#
#   sh ui/tools/setup_run_dir.sh [대상폴더]        기본값 ~/t2_ui_run
#   T2_UI_REF=master sh ui/tools/setup_run_dir.sh ~/t2_play
#
# T2_UI_REF 를 주면 작업 트리가 아니라 그 브랜치(원격 우선) 내용으로 만든다.
# 플레이는 master, 개발은 test 라는 규칙을 로컬 체크아웃 상태와 무관하게
# 지키기 위한 것이다. 어느 커밋으로 만들었는지 대상폴더/UI_SOURCE 에 남긴다.
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
MODULES="action_events archetypes bot context depth dynamics field fieldsim formats gto icm
         live2 money_pressure persona plan play preflop ranges reads runner session storage_paths table
         telemetry_sync texture timing view tournament_store scheduled_runtime personal_data coarse_sim"

# 데이터 파일. pf_rank.json 이 없으면 preflop.py import 자체가 실패한다.
# style_*.json 은 없어도 죽지는 않지만 스타일 추정 경로가 통째로 꺼진다.
DATA="pf_rank.json style_sig.json style_prior.json"

mkdir -p "$DST"
if [ "$(cd "$DST" && pwd)" = "$SRC" ]; then
    echo "중단: 대상이 엔진 폴더 자신입니다 ($SRC)." >&2
    exit 1
fi

# 복사 원본: 기본은 작업 트리, T2_UI_REF 가 있으면 그 브랜치의 커밋.
FROM=$SRC
SOURCE_DESC="working tree $(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo '?') ($(git -C "$SRC" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?'))"
if [ -n "${T2_UI_REF:-}" ]; then
    git -C "$SRC" fetch -q origin "$T2_UI_REF" 2>/dev/null \
        || echo "경고: origin/$T2_UI_REF fetch 실패 — 로컬에 있는 ref 를 쓴다" >&2
    if git -C "$SRC" rev-parse -q --verify "origin/$T2_UI_REF^{commit}" >/dev/null; then
        REF="origin/$T2_UI_REF"
    else
        REF="$T2_UI_REF"
    fi
    COMMIT=$(git -C "$SRC" rev-parse --verify "$REF^{commit}")
    FROM=$(mktemp -d)
    trap 'rm -rf "$FROM"' EXIT
    PATHS="ui/server/ui_view.py ui/server/ui_server.py ui/web $DATA"
    for m in $MODULES; do
        case "$m" in
            tournament_store|scheduled_runtime|personal_data|coarse_sim)
                if git -C "$SRC" cat-file -e "$COMMIT:$m.py" 2>/dev/null; then
                    PATHS="$PATHS $m.py"
                fi ;;
            *) PATHS="$PATHS $m.py" ;;
        esac
    done
    # 통계 진행(hybrid) 보정 라이브러리. 없으면 hybrid 대회도 실제 진행으로 돈다.
    if git -C "$SRC" cat-file -e "$COMMIT:coarse_params" 2>/dev/null; then
        PATHS="$PATHS coarse_params"
    fi
    # shellcheck disable=SC2086
    git -C "$SRC" archive "$COMMIT" -- $PATHS | tar -x -C "$FROM"
    SOURCE_DESC="$REF $(git -C "$SRC" rev-parse --short "$COMMIT")"
fi

COPIED_MODULES=0
for m in $MODULES; do
    case "$m" in
        tournament_store|scheduled_runtime|personal_data|coarse_sim)
            [ -f "$FROM/$m.py" ] || continue ;;
    esac
    cp "$FROM/$m.py" "$DST/$m.py"
    COPIED_MODULES=$((COPIED_MODULES + 1))
done
for d in $DATA;    do cp "$FROM/$d"    "$DST/$d";    done
if [ -d "$FROM/coarse_params" ]; then
    mkdir -p "$DST/coarse_params"
    cp "$FROM/coarse_params/"*.json "$DST/coarse_params/" 2>/dev/null || true
fi
cp "$FROM/ui/server/ui_view.py"   "$DST/ui_view.py"
cp "$FROM/ui/server/ui_server.py" "$DST/ui_server.py"

# web/ 은 2단계 산출물. 아직 비어 있으면 건너뛴다.
if [ -n "$(ls -A "$FROM/ui/web" 2>/dev/null || true)" ]; then
    mkdir -p "$DST/web"
    cp -R "$FROM/ui/web/." "$DST/web/"
fi
echo "$SOURCE_DESC" > "$DST/UI_SOURCE"

# 이 표시 파일이 없으면 ui_server 가 시작을 거부한다.
: > "$DST/UI_SERVER_DIR"

# 이 프로젝트에서는 live hand telemetry를 GitHub의 별도 branch로 자동 공유한다.
# 토큰/비밀번호는 저장하지 않고, SRC git repository의 기존 remote/auth를 공유하는
# worktree를 telemetry_sync.py가 만든다.
if [ "${T2_TELEMETRY:-0}" != "0" ]; then
    TWD=${T2_TELEMETRY_WORKDIR:-$HOME/t2_telemetry_live}
    cat > "$DST/telemetry_config.json" <<EOF
{
  "enabled": true,
  "branch": "telemetry/live",
  "source_repo": "$SRC",
  "workdir": "$TWD"
}
EOF
else
    rm -f "$DST/telemetry_config.json"
fi

echo "실행 폴더: $DST"
echo "  원본: $SOURCE_DESC"
echo "  모듈 ${COPIED_MODULES}개, 데이터 $(echo $DATA | wc -w)개"
echo "  실행: cd $DST && python3 ui_server.py"
if [ -f "$DST/telemetry_config.json" ]; then
    echo "  텔레메트리: 켬 -> telemetry/live (비동기)"
else
    echo "  텔레메트리: 끔"
fi
echo "  주의: T2_LIVE_STATE 를 설정하지 마세요. 설정하면 접미사가 _alt 로 고정되어"
echo "        cli.py 세션과 아카이브를 공유하게 됩니다."
