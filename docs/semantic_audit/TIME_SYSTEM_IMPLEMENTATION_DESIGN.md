# 시간 시스템 구현 설계 — Action Clock · 누적 Time Bank · 봇 real/virtual timing

기준: `test` `4a7ef517`(2026-10-05). 입력은 확정값만 쓴다.
- 정책(사용자 결정, TIME_SYSTEM_DESIGN §J): 기본 액션 18 / 14 / 12초(일반 / 터보 / 하이퍼), 누적 타임뱅크 시작 60초
  (레이트 레지 동일), 핸드당 상한 없음, 충전 없음, 봇 UI 모션은 생각 시간 안에 포함, 카운트다운은 좌석 링 →
  마지막 10초 숫자, 타임아웃은 체크 가능하면 체크·아니면 폴드.
- 봇 생각 시간: Timing Model v1(§L) — B 4.0, 근접도 v3, 프리플랍 폭 ×2, 성향 분포 그대로.

이 문서는 설계다. production 코드는 아직 바꾸지 않았다. §9 의 결정이 나오면 §8 순서로 구현한다.

## 1. 원칙

1. **같은 규칙, 다른 실행.** 시간 규칙은 순수 함수 하나(`timing.py`). REAL 테이블(사람이 있는 테이블)은
   그 시간만큼 실제로 기다리고, BOT 테이블은 그 시간만큼 테이블 시계만 전진한다.
2. **전략 불변.** 시간 계산은 전략 RNG 를 한 번도 소비하지 않는다. 결정 결과를 바꾸지 않는다.
   검증: timing ON/OFF 에서 R2 기준 다이제스트·완주 trace 다이제스트가 같다.
3. **서버 권위 절대 시각.** 모든 deadline 은 절대 시각으로 저장한다. 재접속·새로고침·재시작으로 시간을 늘릴 수 없다
   (지금 HERO `ui_action_token` 규칙의 일반화).
4. **엔진 안에 sleep 없음.** 엔진은 지금처럼 즉시 계산한다. REAL 테이블의 기다림은 이벤트의 **예정 시각**으로만 표현한다.

## 2. 모듈 구성

### 2.1 새 모듈 `timing.py` (순수 함수, 상태 없음)

| 함수 | 입력 | 출력 |
|---|---|---|
| `action_seconds(fmt_key)` | 포맷 키 | 기본 액션 초. `FORMAT_SPEED`(formats.py) 로 regular 18 / turbo 14 / hyper 12. slow(deep)는 §9-F |
| `timing_traits(pid, tour_seed)` | pid, 대회 시드 | pace / tank / mask / clock (§L 분포). `random.Random(crc32(...))` 로컬 인스턴스 — 전역·전략 RNG 미사용 |
| `closeness(prov)` | 결정 provenance(§3) | c ∈ [0,1] — v3: 응답 `c_final`, 선택 0, 프리플랍 `c_rank`·`c_final` |
| `difficulty(prov, ctx, K)` | c, 구조 s, 돈 m(bf), commit | P, effect = commit × c |
| `bot_visible_seconds(traits, prov, ctx, K, jitter_seed)` | | reasoning·hold·visible (`tools/bot_timing_design_sim.visible_time` 과 같은 식) |
| `clock_plan(started_at, base, bank)` | 절대 시각 | `base_deadline`, `bank_deadline` |
| `settle_bank(started_at, acted_at, base, bank)` | | 사용한 뱅크, 남은 뱅크, timed_out |
| `mechanical_seconds(event)` | 딜 / 보드 공개 / 쇼다운 / 핸드 전환 | 기계 시간(§6.2 보정값) |

- 시뮬(`tools/bot_timing_design_sim.py`)은 이 모듈을 import 하도록 바꿔 공식이 한 곳에만 있게 한다.
- `jitter_seed = crc32(tour_seed, hand_hash, seat, action_index)` — 재계산해도 같은 값.

### 2.2 관련 개념 숙련 K (§9-B)

그 선수의 실제 concept 값. 결정 하나를 계산하는 동안 `persona.sk(prof, concept)` 가 실제로 조회한 concept 들을
기록(관측 전용, RNG 없음)하고, `K = 평균(PS.concept_knowledge(prof, c))` 로 묶는다. 조회가 하나도 없으면
fallback 으로 그 선수의 전체 concept 평균 knowledge. v1 검증(K ~ U(0.3, 0.95))과 분포가 다르므로 T4 에서
같은 지표로 재측정해 보고한다(파라미터는 재조정하지 않는다).

## 3. 결정 provenance 기록 (기록 전용, 행동 불변)

`tools/timing_trace.py` 가 외부 hook 으로 얻던 값을 엔진이 직접 남기게 한다. 전부 RNG 없는 값이다.

| 결정 | 기록 위치 | 값 |
|---|---|---|
| 프리플랍 open | `preflop_plan` 반환 seed `pf_timing` | `{'kind':'open','r','thr'}` — `apply_money_open_threshold` 이후 thr |
| iso | 같은 곳 | 림퍼 읽기 보정 후 thr — `iso_decision` 이 쓰는 값을 함수 안에서 그대로 내보낸다(재계산 아님) |
| defend / calloff | 같은 곳 | `defend_action_likelihoods` 의 `tot`(계속 폭) 또는 `calloff_cap` |
| calloff layer(gate 통과) | 같은 곳 | `layer_effective_equity`, `perceived_required_equity` |
| multiway(증거 완비) | 같은 곳 | `equity_vs_multiway_ranges`, `need_seen` |
| 포스트플랍 응답 | `plan_state['_last_response_boundary']` | `decide_response` 가 실제 비교한 eq/need(레이어 콜이면 call_eq/call_need) |
| 포스트플랍 벳/체크 | 없음 | c = 0 (경쟁 선택지 점수가 생기기 전까지) |

- `decide_response` 가 eq/need 를 반환값 밖으로 내보내는 방식: 지금 시그니처를 유지하고 `plan_state` 에 기록만 추가.
- iso 는 지금 thr 를 함수 밖으로 내보내지 않는다. 함수 안에서 같은 변수를 기록하도록 한 줄 추가한다
  (trace 도구의 재계산 사본을 production 으로 옮기지 않는다).
- 검증: provenance 추가 전후 R2 다이제스트(시드 11·12) 동일, `tools/timing_trace.py` 결과(K.5 의 boundary)와 엔진 기록이 결정마다 일치.

## 4. HandRun 통합 (`session.py`)

- `HandRun.__init__(…, timing_ctx=None)`. `timing_ctx` = 대회 시드, 포맷, 시계 모드('real'|'virtual'), 뱅크 조회/정산 콜백.
  `None` 이면 지금과 완전히 같다(기존 호출부 호환).
- 봇 액션을 적용한 직후(지금 `_emit_bot_action` 호출 지점, 1556·2406행) `timing.bot_visible_seconds` 를 계산해
  - `self.timing_log.append({...})` — 핸드 시간 합산용
  - REAL 모드면 `_emit_bot_action` 이벤트에 `clock_started_at`, `act_at`, `base_deadline`, `bank_deadline` 을 실어 보낸다.
- 봇 시각 진행: 핸드 안의 `cursor` = 핸드 시작 시각 + Σ(기계 시간 + 앞선 visible). 각 봇 결정의
  `clock_started_at = cursor`, `act_at = cursor + visible`.
- **봇 타임아웃(§9-A 결정)**: 사람과 같은 규칙이다. visible > base + bank 이면 그 결정은 타임아웃 —
  체크 가능하면 체크, 아니면 폴드. 사용한 뱅크 = min(bank, max(0, visible − base)).
  전략 불변 검증은 **시간 규칙 적용 전 엔진 결정** 기준으로 따로 유지한다(§8 T3).
  (이전 기본안 "봇은 타임아웃하지 않고 상한에서 결정한 행동을 그대로 한다"는 폐기 — 같은 시간 규칙 원칙에 어긋남.)
- REPLAY(재생 결정) 경로: 같은 시드로 같은 visible 이 다시 나온다(결정론). 기록을 따로 저장할 필요 없음.

## 5. 누적 Time Bank 저장

- 위치: 필드 덤프 `field['time_banks'] = {pid: seconds}` — 테이블 이동·재시작에 pid 를 따라간다.
  처음 보는 pid 는 60초로 시작(레이트 레지 포함). 재입장(re-entry)은 새 pid 라 60초.
- 봇·사람 모두 같은 저장소. 정산은 액션 시점에 한 번(`settle_bank`).
- BOT 테이블 선계산(worker)은 뱅크를 **예측 사본**으로 쓰고, `apply_vclock_events` 로 확정할 때 그 이벤트의 뱅크 변화만 반영한다
  (지금 스택·탈락 확정과 같은 규칙: `end ≤ target` 인 이벤트만 commit).

## 6. 실행 모드

### 6.1 REAL 테이블 (HERO 테이블)

```
HERO 액션 → /api/step-stream → _step() (엔진 즉시 계산)
  봇 이벤트마다: {seat, action, amount, clock_started_at, act_at, base_deadline, bank_deadline}
  서버: st['ui_bot_schedule'] = [이벤트...]  (절대 시각, 재접속 재생용)
  다음 HERO 결정: ui_decision_ready_at = 마지막 봇 act_at (+ 보드 공개 기계 시간)
  HERO 시계: started_at = ready_at, base_deadline = +18, bank_deadline = base_deadline + bank
```

- 프런트(`ui/web/app.js`): 고정 템포 `STEP_MS 1500 / FOLD_DIV` 대신 이벤트의 `act_at` 에 맞춰 재생한다.
  모션은 `act_at` 직전에 끝나도록 시작 — 별도 애니메이션 시간을 더하지 않는다(§J).
  지난 시각의 이벤트(재접속)는 즉시 반영하고, 아직 안 된 것만 예약.
- 행동 중인 좌석(봇·HERO 공통): 좌석 링 = `base_deadline − now` 비율. base 소진 뒤에는 TIME BANK 링(색 구분),
  `bank_deadline − now`. 숫자는 남은 시간 10초 이하에서만. **봇의 실제 행동 예정 시각은 화면에 쓰지 않는다**(§J).
- HERO 타임아웃: 지금 `_timeout_action` 그대로(체크 가능하면 체크, 아니면 폴드). 서버가 `bank_deadline` 을 넘긴
  요청을 받으면 타임아웃으로 바꾼다(지금 `ui_action_deadline` 비교 자리). 프런트 자동 전송도 `bank_deadline` 기준.
- `HERO_ACTION_SECONDS`(env, 15)는 포맷별 `action_seconds` 로 대체. env 는 개발용 override 로만 남긴다.
- HERO 가 시간을 얼마나 썼는지 = `acted_at − started_at` 실제 값. 모델하지 않는다.

### 6.2 VIRTUAL 테이블 (봇만 있는 테이블)

- 핸드 시간 = Σ 기계 시간 + Σ visible(봇 뱅크 상한 적용). 지금 `live2._vclock_hand_seconds`(결과 로그 사후
  고정비용: 8 + 2·추가 스트리트 + 액션별 1.5~5.5 + 쇼다운 3, ×1.2125)를 대체한다.
- 교체 방식: 새 함수 `_vclock_hand_seconds_v2(res, timing_log)` 를 먼저 만들고, `T2_TIMING_V1` 플래그로 고른다.
  기계 시간 상수는 지금 값에서 액션별 비용(생각 시간이 대신함)을 뺀 `8 + 2·추가 스트리트 + 쇼다운 3` 에서 출발해,
  시간당 핸드 수 보정(§9-C)으로 정한다.
- 선계산·barrier·H4H·보충 예약 규칙은 그대로다. 긴 탱크가 H4H 라운드를 늦추는 효과는 자동으로 생긴다.
- 확인할 것: 선계산 청크(`VCLOCK_CHUNK_SECONDS`)당 핸드 수가 줄어 대기 체감이 바뀌는지 측정.

### 6.3 오프스크린 / sit-out

지금 스케줄 대회의 오프스크린 HERO 는 `fieldsim` sitout 경로로 **즉시** 체크/폴드한다. 시계를 흘릴지는 §9-D 결정.

## 7. 지속성·재접속

| 저장(서버, 절대 시각) | 위치 | 이유 |
|---|---|---|
| HERO 액션 시계 `{token, started_at, base_deadline, bank_deadline}` | live state(지금 `ui_action_*` 확장) | 새로고침이 시간을 늘리지 못하게 |
| 남은 뱅크 | `field.time_banks` | 이동·재시작 후 같은 값 |
| 진행 중 봇 이벤트 예정표 | `st['ui_bot_schedule']` | 재연결 시 봇 생각 시간이 처음부터 다시 시작하지 않게 |
| 테이블 시계 | 지금 `virtual_seconds`, `ui_clock_*` | 변경 없음 |

저장하지 않는 것: 봇 timing 중간값(결정론적으로 재계산 가능).
서버 재시작: 예정표의 지난 이벤트는 이미 엔진 상태에 반영돼 있다(엔진은 즉시 계산했으므로). 프런트는 남은 것만 재생.

## 8. 구현 순서와 수락 기준

| 단계 | 내용 | 수락 기준 |
|---|---|---|
| T1 | `timing.py` 순수 함수 + 시뮬이 이 모듈 사용 | 시뮬 K.5/K.7 수치 재현(같은 trace 에서 동일) |
| T2 | §3 provenance 기록 | R2 다이제스트 불변, trace 도구 boundary 와 결정별 일치 |
| T3 | HandRun timing_log + 봇 뱅크 정산(virtual 모드) | timing ON/OFF 완주 다이제스트 동일(전략 불변), 뱅크 음수 없음 |
| T4 | `_vclock_hand_seconds_v2` + 플래그 | 시간당 핸드 수 보정 보고서(§9-C), H4H·barrier 검증기 통과 |
| T5 | HERO 시계: 포맷별 기본초 + 뱅크 + 타임아웃 | 새로고침·재접속·재시작에서 deadline 불변, 타임아웃 규칙 |
| T6 | REAL 테이블 이벤트 예정 시각 + 프런트 재생·좌석 링 | 봇 생각 중 링 표시, 마지막 10초 숫자, 재접속 시 예정표 이어 재생 |
| T7 | 플래그 기본 ON, 구 함수 제거 여부 결정 | 사용자 승인 |

각 단계는 test 에만 올리고, 행동이 바뀌는 단계(T4 의 시간당 핸드 수, T5·T6 의 체감)는 사용자 확인 후 다음으로 간다.

## 9. 사용자 결정 (2026-10-05)

| # | 질문 | 결정 |
|---|---|---|
| A | 봇이 base+bank 를 넘으면 | 사람과 동일하게 타임아웃(체크 가능하면 체크, 아니면 폴드). 봇 예외 없음. 전략 불변 검증은 시간 규칙 적용 전 엔진 결정 기준 |
| B | 관련 개념 숙련 K | 그 선수의 실제 Human Model concept 값. 그 결정에서 실제 참조한 concept provenance 로 묶고, 없을 때만 fallback. 새 RNG 금지 |
| C | 시간당 핸드 수 | 목표값을 정하지 않는다. T4 에서 실제 분포를 측정하고 지금 약 70 에서 얼마나 변하는지만 본다 |
| D | sit-out HERO | 지금처럼 즉시 체크/폴드, 타임뱅크 소비 없음 |
| E | 봇 뱅크 잔량 | 평소 표시 안 함. 실제로 Time Bank 에 들어간 순간만 TIME BANK 상태와 카운트다운 |
| F | deep(slow) 기본초 | 18초 |
| G | 작업 순서 | T1~T4 먼저. ui_server.py 가 겹치는 T5~T6 은 지갑/스케줄 최신 작업을 먼저 합친 뒤. 강제 푸시 금지 |

## 10. 범위 밖

- 블라인드 20레벨 상한(TS-1) — 고친 뒤 final-table 타이밍 재검산.
- 타임뱅크 충전 — 분포를 본 뒤.
- 사람 여러 명이 한 대회에 있는 경우의 전역 보충 예약 — 지금은 HERO 한 명 경로뿐(TIME_SYSTEM_DESIGN §I-5).

## 11. T1~T4 구현·검증 기록 (2026-10-05)

| 단계 | 커밋 | 내용 | 검증 |
|---|---|---|---|
| T1 | `5e60185c` | `timing.py` 순수 모듈. 시뮬이 이 모듈을 씀 | 같은 trace 에서 K.5·K.7 결과 완전 재현 |
| T2 | `e7ccb6c6` | 결정 경계 기록(`pf_timing`, `_last_response_boundary`), `persona.concept_tap` | R2 다이제스트 불변. `verify_timing_provenance`: 프리플랍 3,475·포스트플랍 응답 396 결정 불일치 0 |
| T3 | `d1270ba8`, `eefcf66c`, `a2d855f1` | HandRun 봇 시계(사람과 같은 타임아웃), pid 뱅크, `T2_TIMING_V1=off/record/enforce`(기본 off) | `verify_timing_strategy_invariance` 통과(아래) |
| T4 | `d1270ba8`, `15ffa046` | 뱅크 저장·병렬 작업·vclock 이벤트 전달, `_vclock_hand_seconds_v2`, 설치 모듈 목록에 timing 추가 | 기존 검증기 통과 + enforce 모드 vclock 검증 + 측정(아래) |

**T3 전략 불변 검증**(`tools/verify_timing_strategy_invariance.py`):
- off vs record: R2 시드 11·12 다이제스트 동일, realistic 짧은 완주 다이제스트 동일.
- `T2_TIMING_TEST_BASE`(테스트 전용 기본초 덮어쓰기)는 `fieldsim._timing_ctx` 한 곳에서만 읽고, 시간 규칙이 off 면
  그 전에 반환한다. env 를 켜고 off 로 돌린 R2 다이제스트가 off 와 같다.
- 기본 3초 강제(타임아웃 경로 실제 실행): 5,082결정 중 타임아웃 64건, 규칙 위반 0(체크 가능 → 체크, 아니면 폴드).
  첫 타임아웃 핸드(115번째) 전까지 record 와 핸드 기록 완전 동일, 그 핸드 안에서도 타임아웃 결정까지
  결정별 RNG 상태 지문·좌석·뱅크 동일. 뱅크 음수 0.

**기존 검증기**(시간 규칙 off): `verify_parallel_tables`, `verify_parallel_table_processes`, `verify_vclock_session`,
`verify_vclock_finish_ownership`, `verify_book_save_compact`, `verify_personal_installation` 통과.
`verify_vclock_finish_ownership` 은 처음에 `timing` 모듈이 설치 목록(`ui/tools/setup_run_dir.py/.sh`)에 없어
실패했다 — 설치본도 같은 이유로 실패했을 것이라 목록에 추가했다(`15ffa046`).
enforce 모드에서도 `verify_vclock_session` 통과. 탐침: vclock 이벤트 92개 모두 뱅크를 싣고, 다음 청크 필드와
`apply_vclock_events` 확정까지 52명 뱅크가 전달된다.

**T4 측정**(enforce, realistic 90명 × 3시드 완주, 3,536핸드 / 39,011 봇 결정, STRICT errors 0) —
`evidence/TIMING_T4_RUNTIME.json`, 그림 `docs/beta/timing_t4_runtime.png`. 파라미터는 바꾸지 않았다.

| 항목 | 값 |
|---|---|
| 핸드당 시간(가상 테이블, 같은 핸드) | 지금 고정비용 47.4초(중앙 41.8, 90% 77.6) → v2 37.8초(중앙 32.8, 90% 67.3) |
| 테이블당 시간당 핸드 | **75.9 → 95.2 (+25%)** — early_mid 71.0 → 88.7, bubble 93.2 → 120.4, itm 97.2 → 126.2, final 146.2 → 196.8 |
| 타임아웃 | 7건 / 39,011 결정(0.18‰). 느린형 5, 숨기는형 1, 시계사용형 1, 일반형·충동형 0. 7건 모두 뱅크가 남은 상태에서 한 결정이 base+bank 를 넘은 경우(그 결정으로 뱅크 0). 엔진 행동이 폴드 5(결과 동일), **콜 2(폴드로 바뀜)** |
| 타임뱅크 | 270명 중 마지막 결정 시점 뱅크 < 60초 71명, 0초 7명. 결정 시점 뱅크 0 인 결정 0.35% |
| K(실제 concept) | 결정당 조회 concept 평균 14.6개. K 평균 0.58(중앙 0.58, 90% 0.77) — v1 검증의 U(0.3,0.95)(평균 0.625)보다 좁고 약간 낮다 |
| 일반형 생각 시간 | 전체 평균 1.5초(90% 2.9), 어려운 올인 평균 **18.7초**(중앙 15.5, 90% 30.6, n 44), 명백한 올인 1.1초 |
| 느린형 | 어려운 올인 35.1초(n 17), 뱅크 사용 9.3초/시간 |

해석 재료(결정 아님):
- 시간당 핸드 증가는 쉬운 결정(대부분)이 지금 고정비용(액션당 1.5~5.5초 ×1.2125)보다 짧게 끝나기 때문이다
  (일반형 결정 평균 1.5초). 어려운 결정만 길어진다.
- 일반형 어려운 올인 평균이 v1 검증(21.4초)보다 낮은 18.7초다. K 가 실제 concept 값으로 바뀐 영향으로 보인다
  (근거: 다른 입력은 같고 K 분포만 바뀌었다). 표본 44건.
- 사람 있는 테이블(real) 핸드 시간은 T5·T6 이후 측정한다. 지금 측정은 전부 가상 테이블이다.

### 11.1 T1~T4 완료 (사용자 결정, 2026-10-05)

- 유지: B = 4.0, personality 분포, 실제 concept K, mechanical time(지금 값), `T2_TIMING_V1` 기본 off.
- 시간당 핸드 95.2 를 지금 고정비용 75.9 에 맞추지 않는다 — 75.9 는 액션 종류별 고정비용으로 만든 가상치라 기준이 아니다.
  final 197핸드/시간은 빠르므로 T5~T6 에서 사람 포함 테이블을 돌린 뒤 **mechanical time**(딜·보드 공개·칩 이동·
  쇼다운·핸드 전환)으로 맞춘다. 쉬운 결정을 일부러 느리게 만들지 않는다(Timing Model 을 망가뜨린다).
- 일반형 어려운 올인 18.7초(n 44)는 유지. 실제 concept 표본이 쌓이면 재검산.
- 재검산 항목(T5~T6 이후): 시간당 핸드 +25%, 일반형 어려운 올인 18.7초, final 197핸드/시간.
- 타임아웃으로 콜 2건이 폴드로 바뀐 것은 정상 — 시간 규칙이 실제 게임 규칙이므로 시간이 다 되면 결과가 바뀐다.
  전략 불변성은 record 모드까지, enforce 의 변화는 합법적 시간 초과로 따로 본다.

## 12. T5~T6 구현·검증 기록 (2026-10-05, `T2_TIMING_V1` 기본 off 유지)

원격 `test` 에 지갑/스케줄 쪽 새 커밋이 없음을 확인한 뒤 진행했다(최신 작업은 이미 합쳐져 있음).

**T5 — HERO 시계(서버)**: 시간 규칙이 켜지면 HERO 시계 = 포맷 기본 초(18/14/12, deep 18) + 누적 타임뱅크
(`field.time_banks[hero_pid]`, 시작 60초). `ui_action_started_at / ui_action_base_deadline / ui_action_deadline`
(절대 시각, 같은 토큰 재무장은 연장 안 됨). 행동 시 `timing.settle` 로 뱅크 정산(봇과 같은 규칙), base+bank 를 넘긴
요청·서버 tick 은 기존 `_timeout_action`(체크 가능 체크/아니면 폴드)로 바꾸고 뱅크 0. 시간 규칙이 꺼져 있으면
지금 동작(`T2_HERO_ACTION_SECONDS`, 기본 15초) 그대로.

**T6 — 사람 테이블 봇 시간**:
- `live2.step` 의 HandRun 에 시간 규칙 연결. 사람 테이블은 요청마다 핸드를 처음부터 재생하므로, 재생 결정(`_forced`)도
  시간을 다시 계산해 뱅크가 맞게 한다(재생 행동은 이미 실행 결과라 바꾸지 않음).
- 서버 `_BotSchedule`: 봇 이벤트마다 절대 시각(`clock_started_ms`, `act_at_ms`, `base_deadline_ms`, `bank_deadline_ms`),
  보드 공개는 `at_ms`(2초). 예정표를 `st['ui_bot_schedule']`·`ui_bot_ready_at` 에 저장. 다음 HERO 시계는 예정표 끝 이후에만
  시작하고, 그 전에 온 HERO 액션은 409.
- 프런트: 고정 템포(1.5초) 대신 예정 시각에 재생(봇 모션은 생각 시간 안). 행동 중인 봇 좌석에 남은 액션 시계 링,
  숫자는 남은 시간 10초 이하에서만, TIME BANK 는 실제 뱅크 구간에서만. 봇 행동 예정 시각은 표시하지 않음.
  재접속 시 `/api/ready` 의 남은 예정표로 링을 이어 보여 주고, 예정표가 끝나기 전 액션은 막는다.
- 스크린샷 `docs/beta/timing_t5_t6_ui.png`(왼쪽부터 HERO 기본 구간, HERO TIME BANK, 봇 생각 중 링;
  검증용 기본 4초·뱅크 4초).

**검증**: `ui/tools/verify_timing_clock.py`(새) — HERO 시계 = base+bank·재무장 불연장·재접속 동일 deadline,
기본 초를 0.5초 넘긴 행동이 뱅크 0.5초 사용(2 → 1.50), 봇 이벤트 예정 시각 단조 증가·HERO 시계가 예정표 뒤에 시작,
base+bank 초과 → 타임아웃·뱅크 0, 시간 규칙 off → 기존 시계·예정표 없음·테스트 덮어쓰기 무효. 전부 통과.
기존 UI 검증기(off): `verify_action_timeout`, `verify_clock_ui`(+JS), `verify_ui`, `verify_async_refill`,
`verify_personal_installation`, `verify_scheduled_ui`(DEFER=1) 통과.

알게 된 것:
- `verify_action_timeout`·`verify_clock_ui` 는 지갑 작업 이후 `/api/new` 가 `T2_ALLOW_PRACTICE_NEW=1` 일 때만 열려서,
  그 env 없이 돌리면 처음부터 실패한다(기존 상태, 이번 변경과 무관). 그 env 로 돌려 통과를 확인했다.
- `verify_clock_ui` 는 `_ui_timing` 함수만 떼어 실행하므로, 그 함수는 `TIMING_ON` 전역이 없으면 꺼진 것으로 본다.
- 연습 대회 첫 핸드(`/api/new`)의 HERO 앞 봇 액션은 스트림이 아니라 예정표가 없다(기존 템포로 재생). 이후 핸드는
  전부 스트림 경로라 예정표가 있다.
- 남은 재검산(§11.1): 사람 포함 테이블에서 시간당 핸드·final 197핸드/시간 → mechanical time 으로 조정할지,
  일반형 어려운 올인 18.7초.

### 12.1 새 핸드 예정표 누락 수정

원인은 첫 핸드만이 아니었다. `live2.step` 이 새로 딜한 핸드에서도 봇 콜백을 `run.start()` **뒤에** 달아서,
모든 새 핸드의 HERO 앞 봇 액션이 콜백(=예정표) 밖에 있었다. 화면은 그 액션을 뷰 로그로 고정 템포 재생했다.
- `live2.step`: 이번 호출에서 새로 딜한 핸드면 콜백을 처음부터 단다(진행 중 핸드 재생은 지금처럼 끔).
- `ui_server._step_sched`: 새 핸드를 만드는 모든 경로(`/api/new`, `/api/state`, 스트림의 다음 핸드, 서버 tick,
  `/api/step`)가 같은 예정표 규칙을 탄다. 새 핸드는 딜·블라인드 기계 시간 8초(봇 테이블 mechanical 핸드 기본값과
  같은 값, 화면 딜+블라인드 애니메이션 약 7.6초) 뒤에 첫 봇 시계가 시작한다. 응답 payload 에 `bot_schedule`.
- 프런트: 스트림·새 핸드 프리플랍(`playSequence`)·남은 액션 꼬리(`playDecisionTail`)·결과 꼬리 재생이 모두
  같은 `schedWait`/`schedPace` 를 쓴다. 예정표가 없을 때(시간 규칙 off)만 기존 템포.
- 검증: `verify_timing_clock` 에 첫 핸드(`/api/new`)와 다음 핸드(스트림 a=None)의 예정표·8초 시작 확인 추가, 통과.
  브라우저: 첫 핸드 블라인드 직후 UTG 좌석 링(`docs/beta/timing_first_hand_ring.png`).

## 13. 사람 포함 테이블 실측 (2026-10-05, 파라미터 변경 없음)

`tools/timing_live_measure.py` — 실제 UI 서버(시간 규칙 enforce)를 실시간으로 돌리고 HERO 를 자동으로 친다.
클라이언트는 브라우저와 같은 기다림만 재현한다(예정표 끝까지 기다린 뒤 행동, 핸드 종료 후 관전 꼬리 + 결과 2.0초 +
카드 수거 0.54초). 90명 대회, 연습 모드. 기록 `evidence/TIMING_LIVE_HUMAN_TABLE.json`, 그림 `docs/beta/timing_live_measure.png`.

| 케이스 | 런 | 핸드 | 시간당 핸드 | 핸드당 초(평균/중앙/90%) |
|---|---|---|---|---|
| **HERO 즉시 행동**(테이블 자체 속도) | 시드 21: 37핸드 84.6, 시드 22: 40핸드 107.6 | 77 | **95.2** | 37.8 / 31.4 / 63.4 |
| HERO 중앙 4초(가정 — 참고용, 조정 기준 아님) | 시드 23: 31핸드 70.7, 시드 24: 28핸드 64.6 | 59 | 67.7 | 53.2 / 51.1 / 84.6 |

HERO 정책(둘 다 같음, 가정): 프리플랍 체크 가능하면 체크, 아니면 22% 콜·나머지 폴드; 포스트플랍 체크, 팟 절반 이하
벳은 50% 콜. 시드 22 는 23.6분에 HERO 탈락으로 끝남. 시드 22 첫 실행은 임시 폴더 정리 오류로 결과가 저장되지 않아
같은 시드로 다시 돌렸다(도구 수정 `ignore_cleanup_errors`).

**기계 시간 분해(핸드당 평균, HERO 즉시)**: 딜+블라인드 8.0초(21%) · 봇 생각 합 25.0초(66%) · HERO 0.5초 ·
결과+카드 수거 2.54초 · 나머지 1.8초(보드 공개 스트리트당 2초 + 서버 계산·요청 지연).
**화면 정합(브라우저, `evidence/TIMING_UI_MECH_ALIGNMENT.json`)**: 다음 핸드 요청 → 첫 봇 시계 시작 8.0~8.1초(서버 값 그대로).
첫 좌석 링은 서버 시계 시작보다 **0.5~1.0초 먼저** 보인다 — 화면 딜+블라인드 애니메이션이 약 7.0~7.5초에 끝나므로
딜 기계 시간 8초가 화면보다 0.5~1.0초 길다(그동안 첫 링은 가득 찬 채 줄지 않는다). HERO 액션바는 서버 HERO 차례 시각보다
0.10~0.19초 뒤에 뜬다.

**봇 생각 시간(사람 테이블)**: 즉시 런 848결정 평균 2.27초(중앙 1.19, 90% 4.86, 99% 13.9, 최대 23.3) — 기본 18초 초과 3건,
타임아웃 0. 4초 런 743결정 평균 2.53초. 봇 뱅크 최소 54.7초.
**HERO 타임뱅크**: 즉시 런 60/60초 그대로, 4초 런 60.0·55.9초. HERO 타임아웃 0.

**어려운 올인 재검산(300명 × 3시드 enforce, 12,739핸드 / 139,180결정, `evidence/TIMING_T4_RUNTIME_300.json`)**:
일반형 평균 **22.6초**(중앙 19.9, 90% 39.5, n 215) — 90명 18.7초(n 44)는 표본이 작았던 값. 목표 20~24초 안.
느린형 40.5초(n 44), 숨기는형 23.8(n 18), 시계사용형 20.1(n 48), 충동형 7.3(n 5). 명백한 올인 일반형 1.08초.
K 평균 0.63(중앙 0.65, 90% 0.81). 시간당 핸드(가상 테이블) 지금 고정비용 78.1 → v2 92.9.

**같은 300명 실행의 타임뱅크·타임아웃(관찰)**: 타임아웃 58건 / 139,180결정(0.42‰). 그중 43건은 결정 시점 뱅크가 이미 0.
유형별 시계사용형 33, 느린형 17, 일반형 8. 구간별 final 35, early_mid 16, itm 7. 결정 시점 뱅크 0 인 결정 1.13%.
엔진 행동이 바뀐 것: 콜 15, 레이즈 14, 벳 6, 체크 4(→ 결과 같음), 폴드 18(결과 같음), 쇼브 1. 300명 대회는 길어서
충전 없는 60초 뱅크가 후반(final)에 바닥나는 사람이 생긴다 — 충전은 사용자 결정으로 보류 중인 항목.

## 14. 기계 시간·충전·T7·박스 시계 (2026-10-05, 사용자 결정)

- **딜 7.5초**(`timing.DEAL_SECONDS`, 화면 딜 애니메이션 7.0~7.5초에 맞춤). 보드 공개 2초, 결과+수거 2.54초 그대로.
  생각 시간 파라미터는 건드리지 않음.
- **타임뱅크 충전**: 시작 60초(레이트 레지 동일), 브레이크(55분 플레이 → 5분 브레이크)마다 +15초, 상한 60초.
  레벨·핸드별 충전 없음. 저장값 `[초, 반영한 브레이크 수]`, 읽을 때 반영 → worker/본 필드 이중 충전 없음.
  검증 `tools/verify_timing_bank_recharge.py`, `ui/tools/verify_timing_clock.py`(HERO 1.49 → 16.49).
- **T7 기본 ON**: 실제 게임 `T2_TIMING_V1` 기본 enforce. R2 기준선(`r2_baseline_sim.main`)은 off 강제
  (digest e04c7e88 / 6dc97c62 불변). 시간 검증기는 record/enforce 를 따로 설정. 즉시 행동하는 UI 검증기
  (`verify_action_timeout`, `verify_clock_ui`, `verify_scheduled_ui`, `verify_ui`)는 off 고정 — timing ON 은
  `verify_timing_clock` 이 맡는다. `verify_timing_strategy_invariance` 가 계속 "행동 차이는 정당한 타임아웃뿐"을 확인
  (T7 뒤 재실행 통과). 병렬 뱅크 병합 `float(list)` 버그 수정.
- **박스 테두리 시계(WPL 방식)**: HERO 외 모든 좌석은 자기 차례 시작 순간부터 `.pod .meta`(포지션·스택) 박스 테두리가
  실제 액션 시계 남은 비율만큼 줄어든다(봇은 서버 예정표의 모델 시간, 가짜 1.5초 없음). 행동하면 즉시 제거되고 다음
  좌석 시계가 시작된다. TIME BANK 구간은 주황·굵은 선 + `TIME BANK n`, 숫자는 마지막 10초에만.
  HERO(`#heroinfo`)도 같은 모양, HERO 는 실제 시간. 그림 `docs/beta/timing_box_clock.png`.
- **남은 공백**: timing ON 상태의 예약 대회 흐름 전용 검증기 없음(제안 항목).
