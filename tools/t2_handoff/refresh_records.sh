#!/bin/sh
# 계산 브랜치에서 GTO 기록을 꺼내 저장소 안의 사본(data/gto_records/*.json.gz + MANIFEST.tsv)을 갱신한다.
#   sh tools/t2_handoff/refresh_records.sh            (새 기록이 왔을 때만. 평소에는 fetch_records.sh)
# 새 기록이 생기면 아래 목록에 한 줄 추가한다. 기록 형식은 docs/T2_HANDOFF.md 2장.
# 같은 파일 이름은 뒤에 나온 브랜치가 덮어쓴다(새 기록이 옛 기록을 대신한다).
# 끝난 계산 브랜치는 지우고 태그 archive/<브랜치> 로 남긴다(2026-10-24 정리) — 브랜치가 없으면 태그에서 읽는다.
set -e
cd "$(dirname "$0")/../.."
OUT=$(mktemp -d)
PF=origin/claude/pushfold-10-25-20261019        # 10~25bb 푸시/폴드 + 30/40bb 부모 트리
P30=origin/claude/p30-flat-20261019             # 30bb 플랫콜 루프 (011TJ 세션)
CEN=origin/chatgpt/terminal-census-v2-20260930  # 40bb 플랫콜 루프 + 60bb (Gto제작 세션)
# 2026-10-21~24 코디네이터 세션(session_012qfUk9)이 나눠 맡긴 계산 브랜치
P30T=origin/claude/p30_flat_tail_20261021       # 30bb UTG
P30R=origin/claude/p30_flat_resume_20261023     # 30bb UTG+1, UTG+2
P40T=origin/claude/p40_flat_tail_20261021       # 40bb UTG, UTG+1 (SB 림프는 아래 CFR+ 기록이 대신)
P40U2=origin/claude/p40_flat_utg2_20261024      # 40bb UTG+2 (끝났을 때만 기록이 있다)
L30=origin/claude/p30_sblimp_cfrplus_20261023   # 30bb SB 림프 (CFR+ 재시도, 사용자 위임 승인 10-23)
L40=origin/claude/p40_sblimp_cfrplus_20261023   # 40bb SB 림프 (같음)
T30=origin/claude/p30_3bet_20261022             # 30bb 3벳 받은 오프너 3개
T40=origin/claude/p40_3bet_20261021             # 40bb CO·UTG+1 vs SB
T40R=origin/claude/p40_3bet_resume_20261023     # 40bb UTG vs BTN
for b in $PF $P30 $CEN $P30T $P30R $P40T $P40U2 $L30 $L40 $T30 $T40 $T40R; do
  n="${b#origin/}"
  git fetch -q origin "$n:refs/remotes/$b" 2>/dev/null \
    || git fetch -q origin "refs/tags/archive/$n:refs/remotes/$b" 2>/dev/null \
    || echo "fetch 실패(건너뜀): $b" >&2
done
show() {  # show <브랜치> <파일이름>  — 없으면 조용히 건너뛴다
  git show "$1:data/gto_spot/quick/$2" > "$OUT/$2" 2>/dev/null || rm -f "$OUT/$2"
}
for b in pf10 pf15 pf20 pf25 s30 s40; do git show $PF:data/gto_spot/records/$b.json > "$OUT/$b.json"; done
git show $CEN:data/gto_spot/records/s60.json > "$OUT/s60.json"
# 옛 플랫콜 기록 (SB 림프 0단계 정지 기록은 빼고 아래 새 기록을 쓴다)
for f in $(git ls-tree --name-only $P30 data/gto_spot/quick/ | grep 'p30_flat_.*\.json$' | grep -v sb_limp); do
  git show $P30:$f > "$OUT/$(basename $f)"; done
for f in $(git ls-tree --name-only $CEN data/gto_spot/quick/ | grep 'p40_flat_.*\.json$' | grep -v sb_limp); do
  git show $CEN:$f > "$OUT/$(basename $f)"; done
# 새 기록
show $P30T p30_flat_utg_vs_bb.json
show $P30R p30_flat_utg1_vs_bb.json
show $P30R p30_flat_utg2_vs_bb.json
show $P40T p40_flat_utg_vs_bb.json
show $P40T p40_flat_utg1_vs_bb.json
show $P40U2 p40_flat_utg2_vs_bb.json
show $L30 p30_flat_sb_limp_vs_bb.json
show $L40 p40_flat_sb_limp_vs_bb.json
for x in p30v1_co_vs_sb_3b40 p30v1_utg1_vs_sb_3b40 p30v1_utg_vs_btn; do show $T30 $x.json; done
for x in p40v1_co_vs_sb_3b40 p40v1_utg1_vs_sb_3b40; do show $T40 $x.json; done
show $T40R p40v1_utg_vs_btn.json
# 사본 갱신: 압축본 + 출처표(파일, 브랜치/태그, 커밋, sha256)
D=data/gto_records; mkdir -p $D; rm -f $D/*.json.gz
printf 'file\tsha256_json\n' > $D/MANIFEST.tsv
for f in $(ls "$OUT" | sort); do
  gzip -9n -c "$OUT/$f" > "$D/$f.gz"
  printf '%s\t%s\n' "$f" "$(sha256sum "$OUT/$f" | cut -c1-64)" >> $D/MANIFEST.tsv
done
for b in $PF $P30 $CEN $P30T $P30R $P40T $P40U2 $L30 $L40 $T30 $T40 $T40R; do
  printf '# %s %s\n' "${b#origin/}" "$(git rev-parse --short=8 "$b" 2>/dev/null || echo missing)" >> $D/MANIFEST.tsv
done
rm -rf "$OUT"; ls $D | wc -l
