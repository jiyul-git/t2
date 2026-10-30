#!/bin/sh
# 계산 브랜치에서 GTO 기록을 꺼내 저장소 안의 사본(data/gto_records/*.json.gz + MANIFEST.tsv)을 갱신한다.
#   sh tools/t2_handoff/refresh_records.sh            (새 기록이 왔을 때만. 평소에는 fetch_records.sh)
# 새 기록이 생기면 아래 목록에 한 줄 추가한다. 기록 형식은 docs/T2_HANDOFF.md 2장.
# 같은 파일 이름은 뒤에 나온 브랜치가 덮어쓴다(새 기록이 옛 기록을 대신한다).
# 끝난 계산 브랜치는 지우고 태그 archive/<브랜치> 로 남긴다(2026-10-24 정리) — 브랜치가 없으면 태그에서 읽는다.
set -e
cd "$(dirname "$0")/../.."
OUT=$(mktemp -d)
# 이미 있는 사본을 먼저 푼다. 계산 브랜치가 지워져 가져오지 못한 기록은 이 사본이 그대로 남는다
# (2026-10-27: 옛 브랜치 일부가 지워져 전체를 다시 만들면 기록이 빠졌다).
for g in data/gto_records/*.json.gz; do [ -e "$g" ] && gunzip -c "$g" > "$OUT/$(basename "$g" .gz)"; done
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
P100=origin/claude/p100_parent_20261024         # 100bb 부모 트리(s100, 4벳 2.25x 또는 올인)
FO25=origin/claude/flat_open25_20261025         # 오픈 2.5bb 받은 BB 플랫콜 수비(_o25, 사용자 승인 10-25)
# 2026-10-30 (코디네이터 session_012qfUk9): census 로 모이기 전에 일꾼 브랜치에서 끝난 기록(사용자 승인 10-30 "완료된 5개 연결")
WA=origin/claude/p3bet_a_20261026               # 60bb CO vs BTN 3벳(오픈 2.5)
WB=origin/claude/p3bet_b_20261026               # 100bb BTN vs SB 3벳(오픈 2.5)
WC=origin/claude/p3bet_c_20261026               # 60bb HJ 오픈 2.5 수비
WD=origin/claude/p3bet_d_20261026               # 100bb HJ 오픈 2.5 수비
W100=origin/claude/p100_flat_o25_20261027       # 100bb BTN 오픈 2.5 수비
for b in $PF $P30 $CEN $P30T $P30R $P40T $P40U2 $L30 $L40 $T30 $T40 $T40R $P100 $FO25 $WA $WB $WC $WD $W100; do
  n="${b#origin/}"
  git fetch -q origin "$n:refs/remotes/$b" 2>/dev/null \
    || git fetch -q origin "refs/tags/archive/$n:refs/remotes/$b" 2>/dev/null \
    || echo "fetch 실패(건너뜀): $b" >&2
done
show() {  # show <브랜치> <파일이름>  — 없으면 기존 사본을 그대로 둔다
  git show "$1:data/gto_spot/quick/$2" > "$OUT/$2.new" 2>/dev/null && mv "$OUT/$2.new" "$OUT/$2" || rm -f "$OUT/$2.new"
}
for b in pf10 pf15 pf20 pf25 s30 s40; do git show $PF:data/gto_spot/records/$b.json > "$OUT/$b.json.new" 2>/dev/null && mv "$OUT/$b.json.new" "$OUT/$b.json" || rm -f "$OUT/$b.json.new"; done
# 60·100bb 부모: 오픈 2.5bb(SB 3.0) 로 푼 판(2026-10-27). 봇이 60bb 이상에서 2.5bb 로 오픈하므로 이 판을 쓴다.
#   옛 2.0 판: $CEN records/s60.json, $P100 records/s100.json
git show $CEN:data/gto_spot/records/s60_open25.json > "$OUT/s60.json"
git show $CEN:data/gto_spot/records/s100_open25.json > "$OUT/s100.json"
# 옛 플랫콜 기록 (SB 림프 0단계 정지 기록은 빼고 아래 새 기록을 쓴다)
for f in $(git ls-tree --name-only $P30 data/gto_spot/quick/ 2>/dev/null | grep 'p30_flat_.*\.json$' | grep -v sb_limp | grep -v p30_flat_sb_vs_bb); do
  git show $P30:$f > "$OUT/$(basename $f)"; done
for f in $(git ls-tree --name-only $CEN data/gto_spot/quick/ | grep 'p40_flat_.*\.json$' | grep -v sb_limp | grep -v _stopped_); do
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
for x in p40_flat_btn_vs_bb_o25 p40_flat_co_vs_bb_o25 p30_flat_btn_vs_bb_o25 p30_flat_co_vs_bb_o25; do show $FO25 $x.json; done
# 2026-10-27 Gto제작1(CEN): 3벳 받은 오프너 짝 추가, 오픈 2.5 수비(30 CO, 60 BTN·CO), 30bb SB 오픈 재계산 최종본
#   (_stopped_step1 은 옛 정지 기록이라 쓰지 않는다)
for x in p30v1_btn_vs_sb_3b40 p30v1_hj_vs_sb_3b40 p30v1_lj_vs_sb_3b40 p30v1_utg2_vs_sb_3b40 p30v1_utg_vs_sb_3b40 \
         p30v1_co_vs_btn p30v1_hj_vs_btn p30v1_lj_vs_btn p30v1_utg2_vs_btn p30v1_utg1_vs_btn \
         p40v1_btn_vs_sb_3b40 p40v1_hj_vs_sb_3b40 p40v1_lj_vs_sb_3b40 p40v1_utg2_vs_sb_3b40 p40v1_utg_vs_sb_3b40 \
         p40v1_co_vs_btn p40v1_hj_vs_btn p40v1_lj_vs_btn \
         p30_flat_co_vs_bb_o25 p60_flat_btn_vs_bb_o25 p60_flat_co_vs_bb_o25 p30_flat_sb_vs_bb; do show $CEN $x.json; done
# 2026-10-28 Gto제작1(CEN) 2차: 40bb vs BTN 나머지 짝(UTG+2·UTG+1 → 40bb vs BTN 완성), 60bb BTN vs SB(오픈 2.5, _o25)
for x in p40v1_utg2_vs_btn p40v1_utg1_vs_btn p60v1_btn_vs_sb_3b40_o25; do show $CEN $x.json; done
# 2026-10-30: 일꾼 브랜치에서 바로(census 에 같은 이름이 있으면 일꾼 쪽이 덮어쓴다 — 같은 내용인지 MANIFEST sha 로 확인)
show $WA p60v1_co_vs_btn_o25.json
show $WB p100v1_btn_vs_sb_3b40_o25.json
show $WC p60_flat_hj_vs_bb_o25.json
show $WD p100_flat_hj_vs_bb_o25.json
show $W100 p100_flat_btn_vs_bb_o25.json
# 사본 갱신: 압축본 + 출처표(파일, 브랜치/태그, 커밋, sha256)
D=data/gto_records; mkdir -p $D; rm -f $D/*.json.gz
printf 'file\tsha256_json\n' > $D/MANIFEST.tsv
for f in $(ls "$OUT" | sort); do
  gzip -9n -c "$OUT/$f" > "$D/$f.gz"
  printf '%s\t%s\n' "$f" "$(sha256sum "$OUT/$f" | cut -c1-64)" >> $D/MANIFEST.tsv
done
for b in $PF $P30 $CEN $P30T $P30R $P40T $P40U2 $L30 $L40 $T30 $T40 $T40R $P100 $FO25 $WA $WB $WC $WD $W100; do
  printf '# %s %s\n' "${b#origin/}" "$(git rev-parse --short=8 "$b" 2>/dev/null || echo missing)" >> $D/MANIFEST.tsv
done
rm -rf "$OUT"; ls $D | wc -l
