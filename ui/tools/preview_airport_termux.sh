#!/bin/sh
# T2 airport lobby preview. Sandbox installation only; no production data.
set -eu
REPO="$HOME/t2"
if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  REPO="$HOME/storage/downloads/t2-integrated"
fi
if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  echo "T2 원본 Git 저장소를 찾을 수 없습니다." >&2
  exit 1
fi
TARGET="$HOME/t2_airport_preview"
ZIP=""
for CANDIDATE in "$HOME/storage/downloads/t2_airport_final_assets.zip" \
                 "$HOME/storage/shared/Download/t2_airport_final_assets.zip" \
                 "/storage/emulated/0/Download/t2_airport_final_assets.zip"; do
  if [ -f "$CANDIDATE" ]; then ZIP="$CANDIDATE"; break; fi
done
if [ -z "$ZIP" ]; then
  echo "이미지 ZIP을 휴대폰의 Download 폴더에 저장하세요: t2_airport_final_assets.zip" >&2
  echo "파일이 있다면 Termux 저장소 접근 권한도 확인하세요: termux-setup-storage" >&2
  exit 1
fi
BRANCH=chatgpt/airport-lobby-day-night-20261016
git -C "$REPO" fetch -q origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
REF=$(git -C "$REPO" rev-parse "refs/remotes/origin/$BRANCH")
if ! git -C "$REPO" merge-base --is-ancestor c1de399aa7f970121c2aea4939b5073816413b8d "$REF"; then
  echo "검증되지 않은 브랜치: 실행을 중단합니다." >&2
  exit 1
fi
# Existing isolated preview is updated; never touch the installed game/system.
mkdir -p "$TARGET/web"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
git -C "$REPO" archive "$REF" ui/web | tar -xf - -C "$TMP"
cp -R "$TMP/ui/web/." "$TARGET/web/"
if [ ! -f "$TARGET/ui_server.py" ]; then
  echo "먼저 기존의 격리 미리보기 실행 폴더(t2_airport_preview)를 만드세요." >&2
  exit 1
fi
if [ ! -f "$TARGET/range_posterior_v1.py" ]; then
  git -C "$REPO" show "$REF:range_posterior_v1.py" > "$TARGET/range_posterior_v1.py"
fi
# Built-in Python ZIP extractor; avoid needing extra Termux packages.
python3 -m zipfile -e "$ZIP" "$TARGET/web/assets"
for file in lobby_hero_night.webp lobby_hero_day.webp card_featured.webp \
            card_standard.webp card_turbo.webp card_deepstack.webp card_hyper.webp; do
  if [ ! -s "$TARGET/web/assets/t2-airport/$file" ]; then
    echo "누락된 이미지: $file" >&2
    exit 1
  fi
done
echo "완료: $REF"
echo "로비 이미지 7종 검사 통과"
echo "주소: http://127.0.0.1:8766/"
cd "$TARGET"
IP=127.0.0.1 PORT=8766 T2_DATA_DIR="$HOME/t2_airport_preview_personal" \
  T2_SCHEDULE_ENABLED=0 T2_UI_DEFER=0 T2_TELEMETRY=0 python3 ui_server.py
