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

### 2.2 관련 개념 숙련 K

v1 검증은 K ~ U(0.3, 0.95)(pid 별 무작위)로 했다. 구현에서 K 를 어디서 얻을지는 §9-B 결정 사항이다.
결정 전까지는 v1 검증과 같은 방식(pid 시드로 고정 샘플)으로 둔다 — 검증된 분포를 그대로 쓴다.

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
- **봇 뱅크 상한(§9-A 결정 전 기본안)**: `visible = min(visible, base + bank − 0.5)`. 봇은 타임아웃하지 않고
  마지막 순간에 결정한 행동을 그대로 한다 — 전략 불변. 사용한 뱅크 = max(0, visible − base).
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

## 9. 결정이 필요한 것

| # | 질문 | 선택지 | 제 추천 |
|---|---|---|---|
| A | 봇이 base+bank 를 넘는 visible 을 뽑으면? | (1) 상한에서 결정한 행동 그대로 (2) 타임아웃 규칙 적용 | (1) — 전략 불변 원칙. 타임아웃은 사람만 |
| B | 관련 개념 숙련 K 의 출처 | (1) v1 검증대로 pid 시드 샘플 (2) 결정 종류별 개념 숙련 평균 | 우선 (1). (2)는 개념 매핑 설계 후 재검증 필요 |
| C | 시간당 핸드 수 기준 | 지금 보정(약 70핸드/시간)을 유지하도록 기계 시간 상수를 맞춘다 / 새 모델 결과를 그대로 받는다 | 측정 후 결정. 먼저 T4 에서 두 값을 보고 |
| D | 오프스크린 sit-out 중 HERO 결정 | (1) 지금처럼 즉시 체크/폴드 (2) 기본 액션 시간을 흘리고 타임아웃(뱅크는 쓰지 않음) | (1) — 실제 사이트도 sit-out 은 즉시 처리. 연결만 끊긴 경우는 (2) 가 맞으나 지금은 구분 신호가 없음 |
| E | 봇 뱅크 잔량 표시 | 좌석에 표시 / 표시 안 함(사람 것만) | 표시 안 함 — 링 단계 전환만으로 충분 |
| F | slow(deep) 포맷 기본 액션 초 | 18초(일반과 같음) / 20초 이상 | 18초 — §J 에 없던 포맷이라 확인 필요 |
| G | 다른 작업자 영역과의 순서 | `ui_server.py`·`scheduled_runtime` 은 지갑/스케줄 작업과 겹친다(T5·T6). `T2_UI_DEFER=0` 정산 버그도 같은 파일 | T1~T4 를 먼저(엔진·live2 쪽), T5·T6 는 그 작업자와 순서 합의 |

## 10. 범위 밖

- 블라인드 20레벨 상한(TS-1) — 고친 뒤 final-table 타이밍 재검산.
- 타임뱅크 충전 — 분포를 본 뒤.
- 사람 여러 명이 한 대회에 있는 경우의 전역 보충 예약 — 지금은 HERO 한 명 경로뿐(TIME_SYSTEM_DESIGN §I-5).
