#!/bin/sh
# Isolated UI art preview for T2. Uses only PR branch content; no existing game data edits.
set -eu
REPO="$HOME/t2"
if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  REPO="$HOME/storage/downloads/t2-integrated"
fi
if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  echo "T2 Git 저장소를 찾을 수 없습니다." >&2; exit 1
fi
BRANCH=claude/t2-ui-changes-dobpqd
TARGET="$HOME/t2_airport_preview"
git -C "$REPO" fetch -q origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
REF=$(git -C "$REPO" rev-parse "refs/remotes/origin/$BRANCH")
if ! git -C "$REPO" merge-base --is-ancestor 80b973d4b9dc80f7685df5aa24532fdaec14229d "$REF"; then
  echo "승인된 공항 일러스트 커밋이 아닙니다. 중단합니다." >&2; exit 1
fi
if [ ! -f "$TARGET/ui_server.py" ]; then
  echo "격리 미리보기를 생성합니다 (기존 설치/지갑 수정 없음)."
  T2_UI_REF="$BRANCH" T2_TELEMETRY=0 sh "$REPO/ui/tools/setup_run_dir.sh" "$TARGET"
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
git -C "$REPO" archive "$REF" ui/web | tar -xf - -C "$TMP"
mkdir -p "$TARGET/web"
cp -R "$TMP/ui/web/." "$TARGET/web/"
if [ ! -s "$TARGET/range_posterior_v1.py" ]; then
  git -C "$REPO" show "$REF:range_posterior_v1.py" > "$TARGET/range_posterior_v1.py"
fi
# Only print success when the lobby images and the lounge scene files are present.
for file in lobby_hero_night.webp card_featured.webp \
            card_standard.webp card_turbo.webp card_deepstack.webp card_hyper.webp; do
  if [ ! -s "$TARGET/web/assets/t2-airport/$file" ]; then
    echo "이미지가 없습니다: $file" >&2; exit 1
  fi
done
printf '%s\n' "origin/$BRANCH $REF" > "$TARGET/UI_SOURCE"
if [ ! -s "$TARGET/web/lounge/assets/scene.json" ]; then
  echo "라운지 장면 파일이 없습니다: lounge/assets/scene.json" >&2; exit 1
fi
echo "GitHub UI 및 공항 라운지 장면 다운로드 완료"
echo "원본 커밋: $REF"
echo "로비 주소: http://127.0.0.1:8766/"
cd "$TARGET"
IP=127.0.0.1 PORT=8766 T2_DATA_DIR="$HOME/t2_airport_preview_personal" \
  T2_SCHEDULE_ENABLED=0 T2_UI_DEFER=0 T2_TELEMETRY=0 python3 ui_server.py
