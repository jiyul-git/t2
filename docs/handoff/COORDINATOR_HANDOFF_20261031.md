# GTO 코디네이터 인계 (2026-10-31)

이 문서는 이전 코디네이터 세션(컨텍스트 소진)에서 새 코디네이터 세션으로 넘기는 인계 문서입니다.
기존 GTO 인계: `docs/handoff/GTO_HANDOFF_20261026.md`, 연결 기록: `docs/T2_HANDOFF.md`.

## 1. 사용자 고정 규칙
- 결과를 거꾸로 맞추지 않는다(역피팅 금지).
- master는 사용자 승인 시에만. test3 = 테스트 배포, fast-forward만(강제 푸시 금지).
- 커밋 메시지에 모델 이름 금지. PR은 요청 시에만.
- 게임 규칙 + 표준 사이즈만 사용.
- UI/게이트웨이 검사(`tools/t2_handoff/ui_checks.sh`)도 매번 돌린다.
- GTO → 런타임 연결은 승인 필요. 승인된 범위: quick 기록, 100bb 부모, 오픈 사이즈 수비, 10-30 재개 4개 스팟.
- **새 GTO 빈도를 연결할 때마다 상대 레인지 모델 동기화까지 포함한다** (`tools/verify_range_sync.py` 통과 후에만 test3).
- 사용자 보고는 짧은 한국어, 전문용어 최소화.
- 새 작업은 새 세션에 맡긴다. 코디네이터가 전달한 사용자 확인 = 사용자 승인.

## 2. 결정된 방향
- 최상위 실력 봇 = GTO 빈도 그대로(편차 0).
- 성향 레이어: 빈도표(gto_pf)를 불러와 기질·성향으로 편차를 주는 구조. 빈도표만 갈아끼우면 되게.
  - 상한: GTO가 95% 이상 플레이하는 핸드 클래스는 성향 때문에 폴드하지 않음.
  - 하한: 플레이 가능성 순서 × 편차 크기. 72o 같은 쓰레기는 일반 프로필 0%, 극단적 도박형만 아주 드물게.
  - EV 역실험으로 하한 정하기는 하지 않음.
- ICM-GTO는 기존(칩EV) GTO 정밀 검사가 끝난 뒤.
- 플랍 이후 GTO는 아직 구체화하지 않음.
- 베팅 사이즈 근사: 스택 버킷 안에서 가격 축(필요 승률)으로 근사, 스택 버킷은 따로 계산, ICM·인간 습관은 별도 레이어.

## 3. 진행 중 / 대기 세션
| 세션 | 내용 | 브랜치 | 상태 |
|---|---|---|---|
| session_01JQGBPJg4iTnLqnePrQAdtq | 프리플랍 GTO 빈도표 × 성향 레이어 | claude/pf_personality_layer_20261031 (money compose 기반) | 진행 중 |
| session_01JQGBPJ7rivY53N1sLWxt2N | 베팅 사이즈 근사 실험(40bb 3.0 오픈 수비 + 가격 축) | claude/size_approx_20261030 | 진행 중 → 결과 보고 정밀 검사 상위 5–8개 시작 |
| session_01JQGBPJXzHE761rR7r9WDtn | 머니 압박 × GTO 합성 | claude/gto_money_compose_20261031 | 완료, test3 미반영 |
| session_01JQGBPMpeEXQNhvPreedF4q | 멀티웨이 소극성 진단 | claude/multiway_diag_20261030 | 완료, 사용자 선택 대기 |
| session_01JQGBPLvpGtgo68NjNFiRkd | 정밀 검사 준비(우선순위) | — | 완료 (`docs/GTO_PRECISION_PRIORITY_20261030.md`) |
| session_01VBHtaL5cx8gRqQMzzkxX7Z | 라운지 동물 회전 v5 | claude/lounge_turns_20261025 (b8ff30c8) | 사용자 go 대기 |
| session_01DSYENpyxhkrRb37AKhX93Z | 펭귄 걷기/앉기 | claude/art_penguin_walk_20261025 (deaa0255) | 사용자 go 대기, 목도리 끝 6칸 재요청 이미지 대기 |
| session_014nAZQs4bgEqED6HxXiLut2 | ICM 푸시/폴드 | — | 보류(정밀 검사 뒤) |

## 4. 사용자 결정 대기
1. 멀티웨이 소극성 수정안: ① 공정 몫 승률 기준 ② 상대당 가산 제거 + 상대 강도 구간 재보정(추천: ②먼저, 그다음 ①) ③ 0% 프로브 해제. 스크립트 `tools/multiway_calibration.py`.
2. 머니 합성: 초반 숏스택 오픈이 +1.4pt 늘어남(급박함 때문). 그대로 둘지.
3. 체크다운(암묵적 공모) 규칙이 없음 — 나중에 구현 필요.
4. 아트 test3 반영 go(회전 v5 + 펭귄 브랜치 합쳐서).

## 5. 머니 합성 test3 반영 전 할 일
- 브랜치 claude/gto_money_compose_20261031을 최신 test3 위로 합치고 전체 검사(connect, regress, range sync, UI) 직접 재실행. 그 세션에서는 UI 검사가 opencv 문제로만 실패했으므로 코디네이터가 다시 확인.
- 요약: first-in = GTO × 레인지 계수, 위험 몫(danger_fraction)을 포지션 인식 버블 팩터 안으로, 콜/공격은 기존 BF 게이트 유지. GTO 사용률 0% → 100%.

## 6. 정밀 검사 메모
- 기록 66개 모두 quick. 39개 3단계 상한에서 멈춤(마지막 2단계 평균), 17개 24보드 패널 수렴.
- 상위 5: p100_flat_co_vs_bb_o25, p40_flat_co_vs_bb_o25, p40_flat_lj_vs_bb, p100_flat_hj_vs_bb_o25, p60_flat_hj_vs_bb_o25. 단계당 18–30h, 상위 5 ≈ 340 컨테이너-시간.
- v1 3벳 기록은 3벳 사이즈 창 때문에 거의 안 쓰임. bot_sanity는 0핸드(field_backend hybrid) — 별도 확인 필요.

## 7. 연결 절차 (요약)
1. 기록을 `tools/t2_handoff/refresh_records.sh` 워커 목록에 추가 → `rebuild_gto_pf.sh`.
2. `tools/verify_gto_pf.py`, `tools/verify_range_sync.py`.
3. `python3 tools/t2_handoff/verify_gto_connect.py $R 40 $R.json` (30분 넘음 → 백그라운드 + 긴 타임아웃).
4. `bash tools/t2_handoff/regress.sh` (SAME_AS_BASELINE), `bash tools/t2_handoff/ui_checks.sh` (28 0).
5. 모두 통과 + fast-forward 가능할 때만 `git push origin HEAD:test3`.

## 8. 최근 test3 반영
- 10-31: 100bb LJ 2.5bb 오픈 vs BB 수비 연결 (연결 검사 323 통과, range sync ok, regress SAME_AS_BASELINE, UI 28 0). 끊겼던 4개 스팟 모두 연결 완료.

## 9. 성향 레이어 범위 넓히기 방식 (사용자 확인 대기)
- 추천: 플레이 가능성 순서에서 GTO의 100%→섞음→0% 모양을 아래로 늘리기 + 성향별 "흐린 폭"(경계 아래로 갈수록 0을 향해 감소, 폭 밖 0%).
- 상위 100% 핸드는 이미 상한이라 변하지 않음. 하위에 얇게 고루 뿌리는 방식은 비추천.

## 10. 10-31 오후 변경
- 사이즈 근사 결론: 기준점 2개로는 안 됨 → 나중에 3.0 기준점 추가 + 사이값 1개로 보간 검증(0.1 단위 전부 계산은 안 함). 3.0 초과는 3.0 표로 고정.
- 사용자 결정: **정밀 검사보다 빈 자리(BB 외 수비 콜/폴드, 3벳 받은 오프너, 30bb+ SB 첫 진입, 4벳 이후) 채우기가 먼저.**
  - session_01JQGBPKuQRnsWkdDiV74y6n (claude/gto_gaps_20261031): 실제 대회 빈도로 빈 자리 순위 → 보고 후 대기 → quick 계산.
  - session_01JQGBPMv985bSc2TKc8UVq5 (claude/precision_runner_20261031): 정밀 도구만 만들고 멈춤(계산 안 함).
- 사이즈 불일치 발견(사용자 확인 대기): SB/BB 3벳을 봇은 오픈×3.7, GTO 계산은 ×4.0. 4벳은 일치(2.15/2.35). 4벳 받은 뒤 GTO 표 없음, 봇은 100bb에서 올인 아닌 5벳 가능.
