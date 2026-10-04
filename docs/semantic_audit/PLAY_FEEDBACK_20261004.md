# 2026-10-04 플레이 피드백 반영 (test only)

보고한 실행본: UI_SOURCE origin/master 62abf3f. 이번 변경 출발점: 3de478c5.

| 피드백 | 처리 |
|---|---|
| 레벨 상승이 빠름 | 새 UI 게임에 분 단위 가상 시계, 포맷 속도 기본값과 독립 설정 추가 |
| 경과 시간 표시 | UI 상단 가상 경과, 기존 게임은 시간 역산 없이 구 방식 표시 |
| 브레이크 창·남은 시간 | 55분 플레이 / 5분 휴식, 서버 기한 기반 countdown, 정산 대기 후 닫힘 |
| 76핸드 뒤 10분 이상 멈춤 | 준비 조회에 네트워크 timeout/재시도와 워커 경과 표시. 최신 test 단일 테이블 KeyError 재현·수정. 원래 신고의 원인은 미확정 |
| 페어 보드 인식 | texture.classify의 paired/trips, plan.board_paired, paired_board_flush_raise_damp와 리버 기여 판정 경로 확인. 미구현 상태 아님. 실제 신고 핸드의 인지/소비 검토는 남음 |
| 리레이즈가 큼 | 체크레이즈 배수 2.7+0.09·aggr+0.06·overbet, danger 승수·±12% 잡음·2.2~5.0 clamp 확인. 프리플랍/밸류/체크레이즈를 합쳐 일괄 축소하지 않음. 실제 표본 감사 남음 |
| 큰 블러프에 잘 폴드 | 응답 판단은 상대 사이즈 인지→팟오즈→ICM/리딩/주관 문턱 경로. 단순 객관 콜 EV 하나만 쓰는 구조라는 해석은 부정확. 실제 베팅 라인/레인지/인지 가격 표본이 없어 행동 계수 변경하지 않음 |

가상 핸드 시간은 기존 설계의 raw duration 가정이다. 공식 근거는 레벨 길이에만 해당한다.
UI README에 적용 범위와 표본 보정 미적용을 명시했다.

기존 병렬 검증 `verify_parallel_table_processes`: 수정 전 3de478c5와 수정 후 모두
P1 bot_log_same=false / diff_keys=[]; P2 라운드 시작 문맥 통과. 기존 실패로 기록하며
통과라고 보고하지 않는다. 이번 변경은 parallel worker 구현을 바꾸지 않는다.

검증: 23-gate PASS 23 / FAIL 0 / TIMEOUT 0. UI 9명 4핸드와 18명 4핸드
모두 통과(칩 보존·좌석·홀카드 누출·legal·스트림). 시계·저장·HTTP 브레이크
수명주기·JS 남은 시간/대기/닫힘 검증 통과. 균등 안테 검증 통과.

completeness: sites 1,145 / owned 1,145 / unowned 0, span errors 0.
virtual_tournament_clock 개념과 코드 span을 registry에 추가했다.

## 2026-10-05 종료 후 추가 지연 수정

UI 75(5d1f50dc)에서 100명 seed=20261005, A♥ K♠ LJ 500 레이즈,
2♠ Q♥ 7♥ 플롭 350 베팅 후 상대 폴드 경로를 직접 선택해 재현했다.
마지막 폴드 이벤트→최종 응답은 원본 0.962초, 추적 재실행 0.919초였다.
추적 재실행 중 기존 `Field.step_others()`가 0.819832초를 사용했다.
원인: cc215661의 vclock 종료 경로는 pending을 설정했지만 아래의 별도
legacy if/elif 체인으로 내려갔다. UI는 defer_others 기본 False로 호출해
독립 선계산과 함께 기존 라운드 계산·탈락 수거·밸런싱도 실행했다.

수정은 vclock 모드에서 legacy 종료 체인을 건너뛰는 것으로 제한한다.
탈락·이동은 apply_vclock_events/finalize_vclock_settle이 계속 담당한다.
화면 모션, 고정 대기, 결과 전달 순서, CPU 워커 설정은 변경하지 않았다.
같은 핸드 수정 후 마지막 폴드→최종 응답 0.085초, 요청 전체 0.214초.
서버 한 사례 측정이며 휴대폰 지연이나 모든 구간 해결을 의미하지 않는다.

검증: 9/100명 × defer False/True에서 legacy 계산·정산 호출을 차단하고
HERO 종료가 성공함을 확인. 다른 테이블 상태 불변, 기존 pending 미생성,
새 정산기의 HERO 탈락 수거·순위·아카이브 완료를 확인. 독립 테이블 시계,
이동 barrier, 핸드포핸드, 시계/휴식, 액션 타임아웃, 18명 4핸드 UI 통과.
전체 gate: PASS 23 / FAIL 0 / TIMEOUT 0. 새 ownership 검사는 원본 UI75에서 실패함도 확인했다.

## 2026-10-05 — asynchronous HERO replenishment (test only)

Request: if a HERO-table vacancy becomes known at the river result at 120s,
start the next hand without waiting for a donor. Candidate discovery may finish
during that hand or the following hand. A donor finishing at 135s must not enter
an ongoing pot or continue playing published hands at the old table.

Implemented first stage:

- Normal HERO results close their archive and clear settlement-pending without
  waiting for bot coverage. Neither `/api/ready` nor the next `/api/step` waits
  for a refill candidate. A short HERO table continues playing with >=2 players.
- A persistent `vclock_refill` request is separate from hand/archive state.
  Readiness polling searches completed bot events while HERO plays. A reserved
  candidate pins the donor's completed hand/time; later speculative source
  hands cannot be published. Reservations are revalidated after worker reset.
- Current HERO hand snapshots remain unchanged. Ownership/seat changes commit
  only at a later HERO hand boundary, using the donor's next-BB player and the
  destination's worst eligible open seat. Normal global balancing excludes the
  HERO table. An 8-vs-9 split is already balanced and does not force a transfer.
- Existing full synchronization remains for break, money/seat or FT bubble,
  HERO elimination/final rank, and a HERO table unable to deal with >=2 players.
- Elimination timestamps preserve event-time ordering when older bot results
  arrive after a HERO-table bust. Existing saves retain their earlier bust prefix.
- Animation holds/collection/dealing durations and bot strategy coefficients are
  unchanged. UI engine changes live in `ui/server/ui_server.py`.

Validation:

- `verify_async_refill.py`: an unavailable worker is forbidden from blocking;
  TWO real HERO hands finish and archive; request survives serialization;
  135s donor cannot arrive at 134s or alter an active hand; a later 170s source
  hand is not applied after the 135s reservation; one transfer only; unique
  ownership and chip conservation; protected HERO balancing; sync exceptions.
- Existing vclock finish ownership, vclock session, clock HTTP lifecycle and
  action timeout checks passed.
- Actual HTTP UI smoke: 27 players / 8 completed hands / 38 decision chip and
  seat checks, zero failures; 6 showdowns. Gate suite: 23 PASS, 0 FAIL, 0 TIMEOUT.
- Python HTTP manual play: 100 players, seed 20261005; HERO A♥ K♠ opens to 500,
  bets 350 on 2♠ Q♥ 7♥, BB folds. Final stream payload follows the last fold
  in 0.108s on this server; `/api/ready` reports `working=false`, next hand deals.
  This is server evidence, not a phone animation measurement or speed guarantee.

Deliberate stage boundary:

- Tournament stats and arrivals still publish at HERO hand boundaries; this is
  not yet a live per-second global-state merger during an active HERO hand.
- Existing bot event buffers and conservative all-buffer invalidation on
  movement/bust remain. Per-table-only invalidation and fully independent bot
  balancing are future stages. Those calculations no longer gate ordinary
  HERO hand starts.
- An arrival is committed before the next eligible deal; no mid-hand arrival
  animation was added. Test branch only; master is unchanged.
