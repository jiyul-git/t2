# GTO 작업 이어받기 (2026-10-26, 코디네이터 세션 session_012qfUk9 → 다른 계정)

UI(라운지 그림)는 제외. GTO 계산과 T2 연결만. 이 문서 하나로 시작하고, 자세한 건 아래 "읽을 문서"로 간다.
다른 계정 세션은 이 계정 세션들에 메시지를 보낼 수 없다 → **브랜치와 문서가 유일한 연락 수단**.

## 0. 규칙 (사용자)
- 답은 한국어, 짧게, 전문용어 없이. 결과를 거꾸로 맞추지 않는다(봇 행동이 합격 기준이 아니다). 게임 규칙 + 표준 크기만.
- master 는 사용자 승인 때만. test3 = 시험 배포(빨리감기 push 만, force push 금지). PR 은 요청 때만.
- GTO 값을 T2 에 연결하는 건 사용자 승인 사항 — **지금까지 승인된 범위**: 퀵 기록 연결(10-24), 100bb 부모(첫 진입·오픈 받은 공격), 40bb UTG+2, 오픈 크기별 수비(2.0/2.5/3.0, 10-25 "그렇게 ㄱㄱ"). 새 종류의 연결은 물어본다.
- 연결 전 반드시: 연결 검사 + 회귀 20개 + 화면·게이트웨이 28개 (아래 3장). 커밋 메시지에 모델 이름 금지.
- 커밋 끝줄: `Co-Authored-By: <모델> <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_<id>`.

## 1. 지금 test3 에 연결된 것 (test3 3cf9cc5d 기준)
`docs/T2_HANDOFF.md` 2~3장이 원본. 요약:
- 첫 진입(SB 제외) 10~100bb, 올인 콜/3벳 올인 콜 10~60bb, 오픈 받은 공격 15~100bb, 3벳 받은 4벳 올인 30~60bb(60bb 초과는 기존 판단 — 100bb 트리는 작은 4벳이 있어 비움).
- BB 플랫콜 수비(보정) 30·40bb 전 자리(UTG~SB), 2.0bb 오픈 기준(`vs_open_full`).
- **오픈 2.5bb 받은 BB 수비**(`vs_open_full_o25`): 40bb BTN·CO 연결. 실제 오픈 2.0~2.5 는 두 표 직선 보간, 2.5~3.125 는 2.5 표, 2.5 표가 없는 스택(30bb 등)은 2.0 표만.
- 3벳 받은 오프너(폴드·콜·작은 4벳·올인) 30·40bb: CO·UTG+1 vs SB, UTG vs BTN. SB 림프 받은 BB(체크·레이즈) 30·40bb.
- 모든 기록은 quick(대칭 스택, chip EV) — 정밀 검사 대상. ICM 연결 없음.

## 2. 진행 중 / 남은 일 (우선순위 순)
| # | 일 | 상태 | 어디 |
|---|---|---|---|
| 1 | 30bb BTN·CO 2.5bb 오픈 수비 | **이 계정 세션(01MWq8rC)이 계산 중**: p30 BTN 2단계 끝(10-26 02:29), 다음 p30 CO | 브랜치 `claude/flat_open25_20261025`. 진행 상태는 `data/gto_spot/plan_a/progress/<spot>/`(단계별 json, 커밋됨). 이 계정이 멈췄으면 이어서 돌린다: `docs/GTO_RESUME_40BB.md`(같은 브랜치) 1장 설치 → `PLAN_A_IDS="p30_flat_btn_vs_bb_o25" SPOT_PANEL_WORKERS=4 sh tools/gto_spot/run_quick.sh` (끝난 칸은 다시 안 함). 먼저 그 브랜치에 CLAIM 을 올려 중복 계산을 막는다 |
| 2 | 30bb 2.5 기록 연결 | 기록이 나오면 | 3장 절차. `tools/verify_gto_pf.py` 의 "35bb without a 30bb 2.5 record" 검사는 30bb o25 가 생기면 "35bb 는 30·40 o25 보간"으로 바꾼다 |
| 3 | 2.0 vs 2.5 오프너 손익 재비교 | 4개 끝난 뒤 | 부모 트리는 2.5 를 99% 고른다(간이 플랍 모델). 플랫콜 루프 값(플랍 보정)으로 BTN·CO 오프너 EV 를 다시 비교해 쏠림이 진짜인지 확인 |
| 4 | 오픈 {2.0, 2.5, 3.0} 부모(SB {3.0, 3.5}) + 3.0 수비 BTN·CO | 3 다음 (승인됨) | 40bb 먼저, 그다음 30bb. 연결은 `vs_open_full_o30` 같은 표 + 이웃 크기 보간(`gto_pf.defend_vs_open` 이 지금 2.0/2.5 두 표를 다룸 — 표 목록으로 일반화). 2.0·2.5 차이가 크면 2.25 도 |
| 5 | 3벳 받은 오프너 남은 짝 | 미착수 | UTG+2·LJ·HJ vs SB, BTN vs SB 등 |
| 6 | 정밀 검사(quick → 더 나은 등급) | 미착수 | SB 림프 BB 뿌리 불안정 39~45% 가 1순위 |
| 7 | 30bb SB 오픈 vs BB 재계산 | 미착수 | 1단계 플랍 미수렴 — CFR+ 재시도(승인된 방식 `docs/GTO_AMENDMENT_CFRPLUS_RETRY.md`) |
| 8 | ICM | **사용자 결정 대기** | 표/실시간/버블 팩터, 올인·폴드만?, 상금 구조. `claude/icm_pushfold_20261024`. 연결 금지 |
| 9 | 100bb 플랫콜·서브게임 | 마지막 순위 | 100bb 부모 정확도 0.0169bb(목표 미달) |

## 3. 기록이 나오면 연결하는 절차 (복사해서 쓰기)
```sh
git fetch origin test3 && git checkout -B claude/connect_<이름> origin/test3
sh tools/t2_handoff/refresh_records.sh          # 새 기록 브랜치가 목록에 없으면 먼저 한 줄 추가(FO25 줄 참고)
R=$(mktemp -d) && sh tools/t2_handoff/fetch_records.sh $R
sh tools/t2_handoff/rebuild_gto_pf.sh $R          # 끝줄 "N gto_pf checks passed" 여야 함
python3 tools/t2_handoff/verify_gto_connect.py $R 40 $R/report.json   # 끝줄 "all connection checks passed"
bash tools/t2_handoff/regress.sh                  # "SAME_AS_BASELINE"
pip install opencv-python-headless; bash tools/t2_handoff/ui_checks.sh   # 28개 모두 0
git merge-base --is-ancestor origin/test3 HEAD && git push origin HEAD:test3   # 빨리감기만
```
- 연결 전 기록 점검: 이웃 자리/크기와 방향이 맞는지(예: 오픈이 클수록 BB 폴드↑, 앞자리일수록 폴드↑). 40bb: BTN 2.0 폴드 8.9% → 2.5 20.3%, CO 12.7% → 28.4%.
- 10~60bb 기존 값이 바뀌지 않았는지 데이터 diff 로 확인(새 항목만 늘어야 함).
- `docs/T2_HANDOFF.md` 3장 표와 8장 목록을 갱신.

## 4. 읽을 문서
- `docs/T2_HANDOFF.md` (test3) — 연결 구조·현황·함정. **먼저 읽기**.
- `docs/GTO_CONNECT_QUICK_REPORT_20261024.md`, `docs/GTO_CONNECT_S100_20261024.md` (test3) — 연결 검사 보고.
- `docs/GTO_RESUME_40BB.md`, `docs/GTO_SESSIONS_BOARD.md`, `data/gto_spot/quick/README.md` (계산 브랜치들) — 계산 재시작·표준·파일 지도.
- 끝난 계산 브랜치 17개는 `claude/archive-gto-runs-20261024` 에 묶여 있음(`ARCHIVE.md`).

## 5. 사용자가 확인할 것 (이어받은 세션에 이렇게 물어보면 됨)
1. "이 문서 읽었고, test3 끝 커밋이 3cf9cc5d 이후인지?"
2. "`claude/flat_open25_20261025` 에 p30_flat_btn_vs_bb_o25.json / p30_flat_co_vs_bb_o25.json 기록이 생겼는지, 없으면 누가 돌리고 있는지(CLAIM)?"
3. 연결했다고 하면: "연결 검사 끝줄, 회귀 SAME_AS_BASELINE, 화면 28/28 세 개를 그대로 보여줘."
4. "10~60bb 기존 값이 바뀌지 않았는지 데이터 diff 결과는?"
