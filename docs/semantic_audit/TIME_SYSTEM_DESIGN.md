# 온라인 토너먼트 시간 시스템 설계 (1차 — 감사 + 설계, 구현 없음)

기준: 2026-10-05 `test` (`26ce1287`). 이 문서는 production 코드를 바꾸지 않는다.
미확정 정책값(기본 액션 초, 타임뱅크 초기량·충전, 카운트다운 숫자 표시 시점, 포맷별 값)은 §G 에만 두고 임의로 정하지 않는다.

## 0. 감사 범위와 사실 확인

### 0.1 스케줄 토너먼트 / 지갑 / 바이인 / 레이트 레지 / 리바이 / 상금 지급

원격 전체 브랜치(`master`, `test`, `ccr-*`, `telemetry/live`, `chatgpt/*`)를 확인했다(2026-10-05).
**구현이 없다.** `wallet`, `late_reg`, `rebuy`, 스케줄 생성 코드가 어느 브랜치에도 없다. 지금 대회는 `/api/new` 로 하나를 만드는 구조다(`ui_server.py`, `live2.new_game`).
→ 이 설계는 그 기능을 다시 만들지 않는다. 시간 시스템이 붙을 **접점(인터페이스)** 만 정의한다(§C.4). 다른 작업에서 구현되면 그 구현의 대회 시작 시각·등록 마감 시각을 여기 TournamentClock 의 입력으로 쓴다.

### 0.2 현재 시간 구조 한 장 요약

```
TournamentClock(UI 서버)                         테이블 시계
───────────────────────────                      ───────────────────────────
st.ui_clock_started_at (wall 기준점)              HERO 테이블: wall-clock 그대로
st.ui_clock_paused_seconds / ui_break_*           봇 테이블: Table.virtual_seconds
_clock_values() → active(플레이 초), elapsed       live2._vclock_hand_seconds(res)
field.virtual_play_seconds = active               = (8 + 2·추가스트리트 + 액션별 고정비용
PLAY_WINDOW_SECONDS 3300 / BREAK_SECONDS 300        + 쇼다운 3) × VCLOCK_DURATION_SCALE 1.2125
level_minutes(포맷) → 레벨은 active 로 계산

선계산/확정                                       HERO 액션 시계
───────────────────────────                      ───────────────────────────
live2.compute_vclock_ahead(target)                 HERO_ACTION_SECONDS = 15 (env)
 └ 테이블별 _vclock_table_task (프로세스 풀)       _arm_action_clock(token): 같은 토큰 재무장 시
    첫 탈락·H4H 에서 barrier 를 세우고 멈춤         deadline 을 늘리지 않음(서버 권위 절대 시각)
VCLOCK 버퍼(서버 메모리): events, cursors,         st.ui_action_deadline / ui_action_token
 barrier_time, barrier_kind                        app.js actionDeadlineMs, #turnclock
apply_vclock_events(target): end<=target 인         _timeout_action(): fold 노출 시 fold,
 이벤트만 확정(미래 이벤트 commit 안 함)            아니면 check (fold 는 콜할 금액이 있을 때만 노출)
vclock_needs_sync: 브레이크/H4H/버블 경계
vclock_request_refill / find_refill / arrive:      봇 액션 스트림
 HERO 테이블 보충 예약(candidate)과                 session.HandRun._emit_bot_action
 핸드 경계 확정                                     → ui_server /api/step-stream (NDJSON bot_action)
_vclock_h4h: remaining == itm+1 또는 max_seat+1     → app.js 이벤트 큐 → 렌더
 → barrier_kind 'hand_for_hand', 가장 느린           (street, seat, action, amount, board)
   테이블 한 핸드 끝까지
```

### 0.3 시간 결정에 쓸 수 있는 기존 provenance (전략 계산을 복제하지 않기 위해)

| 결정 | 이미 계산되는 값 | 위치 |
|---|---|---|
| 포스트플랍 응답(콜/폴드/레이즈) | `eq`, `need`(필요 에쿼티), 응답 출처 `_last_response_source` | `plan.act_with_plan` 반환 `(act, amt), eq, need` |
| 포스트플랍 계획 | 계획 이름, `why` 근거, `rel`, `made`, `p2`(2스트리트 확률), 블락/팟컨트롤 확률 | `plan.make_plan` / `refresh` 상태, `h.intents` |
| 프리플랍 오픈/디펜스 | 손 순위 백분위 `r` 대 임계 `thr`(오픈), `tp/tot`(디펜스), gate 확률·roll | `preflop.open_decision`, `defend_thresholds`, `pf_defend_exact_calc_gate` audit |
| 다인원 재레이즈 | `eq_locked`, `need`, 증거 적용량 | `preflop.multiway_reraise_decision` audit dict |
| 사용된 개념 | 결정 경로의 `PS.sk(prof, concept)` 호출(현재 기록 안 함) | 여러 곳 — §F.3 |

## A. 시계 소유권

| 시계 | 소유자 | 값 | 비고 |
|---|---|---|---|
| TournamentClock | 대회(서버) | `t_abs` = 대회 시작 절대 시각 기준 플레이 초, 브레이크, 레벨 | 지금 `ui_clock_*` + `virtual_play_seconds`. 스케줄 대회가 생기면 `start_at` 이 기준점 |
| TableClock | 테이블 | `table_t` (그 테이블이 도달한 대회 시각) | REAL 테이블은 wall 로 전진, BOT 테이블은 `Table.virtual_seconds` |
| PlayerActionClock | (플레이어, 결정) | `started_at`, `base_deadline`, `bank_deadline` (모두 절대 시각) | 지금은 HERO 만(`ui_action_deadline`) |
| PlayerTimeBank | 플레이어(pid) | 남은 초(실수) | 신규. 테이블 이동해도 pid 를 따라감 |
| BotTimingModel | 플레이어(pid) 성향 + 결정 provenance | `reasoning_time`, `timing_hold`, `visible_action_time` | 신규. 전략 RNG 와 분리된 결정론적 시드 |

원칙: **같은 규칙, 다른 실행.** 시간 규칙(기계 시간, 액션 시계, 타임뱅크, 봇 시간 모델)은 하나의 순수 함수 묶음이고, REAL 테이블은 그 결과만큼 실제로 기다리고 BOT 테이블은 그만큼 `table_t` 만 전진한다.

## B. REAL / VIRTUAL 실행

```
decide(seat)                      ← 전략 엔진(변경 없음, sleep 없음)
  ↓ provenance(eq/need/계획/개념)
timing = bot_timing(pid, provenance, ctx, seed)      ← 순수 함수, 전략 RNG 미사용
clock  = action_clock(table_t, base, bank[pid])      ← 순수 함수
  visible = timing.visible_action_time
  used_bank = max(0, visible - base); bank[pid] -= used_bank
  timeout = visible > base + bank → 타임아웃 규칙(§G 결정값)
mech = mechanical_time(event)                        ← 딜/보드/칩/쇼다운/핸드 전환

REAL 테이블:  서버가 event 시각을 table_t + mech + visible 로 정하고,
              그 절대 시각까지 스트림 이벤트 송출을 미룬다(엔진은 이미 결과를 앎).
BOT  테이블:  table_t += mech + visible (대기 없음)
```

- 엔진 안에 `sleep` 을 넣지 않는다. REAL 테이블의 "기다림"은 **스트림 송출 시각**으로만 표현한다(이미 `/api/step-stream` 이 봇 액션을 하나씩 보내는 구조).
- HERO 결정은 모델링하지 않는다. 실제 경과 초 = `now - started_at` 이 그대로 `visible` 이다.

## C. 이벤트 타임스탬프 모델

### C.1 이벤트와 시각

| 이벤트 | 절대 시각 |
|---|---|
| 액션 | `t = action_clock.started_at + visible` (HERO: 실제 입력 시각) |
| 스트리트 전환·보드 공개 | 직전 액션 시각 + 기계 시간 |
| 핸드 종료 | 마지막 액션 + 쇼다운/칩 이동 기계 시간 |
| 탈락 | 그 핸드 종료 시각(지금 `vclock_bust_times` 와 같은 의미) |
| 이동(브레이크/밸런싱) | 출발 테이블 핸드 종료 시각 이후, 도착 테이블의 다음 핸드 경계 |
| 브레이크 시작 | 대회 시각이 세션 끝에 도달한 뒤 각 테이블의 진행 중 핸드 종료 |

### C.2 확정 규칙(지금 vclock 과 동일 개념)
- BOT 테이블은 미래까지 선계산해도 **`t ≤ 현재 대회 시각`** 인 이벤트만 확정(commit)한다(`apply_vclock_events` 의 cutoff 와 같음).
- 탈락·H4H 같은 전역 갈림 지점에서 barrier 를 세우고 그 뒤 결과를 확정하지 않는다(현재 그대로).

### C.3 지금 고정비용 모델과의 관계
`_vclock_hand_seconds` 는 핸드 하나의 총시간을 **결과 로그에서 사후 계산**한다. 새 모델은 결정마다 `visible` 을 만들기 때문에 핸드 시간이 `Σ(mech) + Σ(visible)` 이 된다. 교체 순서(§H):
1) 같은 기계 시간 + 봇 시간 모델로 핸드 시간을 계산하는 **새 함수**를 만들되, 결과 시간 총량이 지금 보정(시간당 약 70핸드)과 크게 어긋나지 않는지 측정.
2) 측정 후 `_vclock_hand_seconds` 를 대체. 그 전까지 지금 함수는 삭제하지 않는다.

### C.4 스케줄 대회 접점(구현은 다른 작업)
TournamentClock 은 `start_at`(절대 시각), `late_reg_until`, `break_schedule` 만 입력받으면 된다. 지갑·바이인·상금은 시간 시스템이 몰라도 된다. 레이트 레지 참가자는 "도착 이벤트"로 다루며 그 시각 이후 핸드부터 TableClock 에 들어간다.

## D. 지속성(서버 재시작·재접속)

| 저장(서버 권위, 절대 시각) | 이유 |
|---|---|
| `action_clock{pid, token, started_at, base_deadline, bank_at_start}` | 재접속·새로고침이 시간을 늘리지 못하게(지금 HERO `ui_action_token` 규칙을 모든 플레이어로 일반화) |
| `time_bank[pid]` | 이동·재접속 후에도 같은 잔량 |
| 봇 결정의 `visible` 과 그 결정 토큰 | 스트림 재연결 때 봇 생각 시간이 처음부터 다시 시작하지 않게 — 이미 정해진 액션 시각을 그대로 재송출 |
| TableClock `table_t`, 브레이크 상태 | 지금 `virtual_seconds`, `ui_break_*` |

저장하지 않는 것: 봇 timing 의 중간값(재계산 가능, 결정론적).
연결 끊김: 서버 시계는 멈추지 않는다. 재접속 시 `base_deadline - now` 와 남은 뱅크를 그대로 보여준다.

## E. 타이밍 성향(플레이어 프로필) vs 런타임 상태

| 프로필(pid, 대회 내내 고정) | 런타임 |
|---|---|
| `decision_pace` 평소 판단 속도 | 남은 타임뱅크 |
| `tank_sensitivity` 어려울수록 늘리는 정도 | 현재 액션 시계 |
| `timing_masking` 쉬운 결정도 일정 시간 기다리는 정도 | 이번 결정의 reasoning/hold/visible |
| `clock_usage` 주어진 시계를 평소 얼마나 쓰는가 | |

- 포커 숙련 개념(concepts)과 섞지 않는다. 새 성향 4개는 **새 prior 가 필요**하다 → 분포는 사용자 결정(§G). 생성 시 기존 RNG 흐름을 밀지 않도록 pid 기반 별도 시드로 만든다.
- 유형 표현(요구 §31): 일반형(sensitivity 중간), 마스커(masking 높음), 시계 사용형(clock_usage 높음), 충동형(pace 빠름·sensitivity 낮음), 느린형(pace 느림).

## F. 결정 난이도 모델

### F.1 구조
```
objective = f(closeness, structure, money, uncertainty)        ← 상황
perceived = objective × perception(관련 개념 숙련, 성향)        ← 사람
reasoning = pace_base × (1 + tank_sensitivity × perceived)     ← 내부 판단 시간
hold      = masking × clock_usage 기반 개인 기준 시간          ← 숨기기/습관
visible   = max(reasoning, hold) × jitter(결정론적)            ← 보이는 시간
```
손 강도·액션 종류·스트리트를 **직접** 시간에 넣지 않는다. 넣는 것은 판단 근거의 근접도뿐이다.

### F.2 지금 provenance 로 계산 가능한 것
| 요소 | 계산 근거 | 가능 여부 |
|---|---|---|
| closeness(콜/폴드) | `abs(eq - need)` (`act_with_plan`) | 가능 |
| closeness(벳/체크·계획) | 확률 분기의 확률값(예: 블락 p, 팟컨트롤 p, p2)의 0.5 근접도 | 가능(계획 상태에 있음) |
| closeness(프리플랍) | `abs(r - thr)` 정규화(오픈), `tp/tot` 경계 근접 | 가능 |
| structure | 레이즈 깊이, 다인원 수, SPR, 남은 스트리트, 뒤 액션자 수, 사이즈/팟 | 가능(이미 결정 입력) |
| money | `money_jump`, 버블 팩터 `bf`, 커버 여부 | 가능(`h.money_jump`, `h.bf`) |
| uncertainty | 상대 읽기 `confidence`, 표본 `n` | 가능(`perceived_profile` 결과) |

### F.3 "관련 개념"
지금은 결정에 실제로 쓰인 개념을 기록하지 않는다. 1단계는 결정 종류별 고정 매핑(예: 리버 블러프캐치 → `bluffcatch_river`, `line_interpretation`, `potodds`, `blocker`)으로 시작하고, 2단계에서 `sk()` 호출 추적(관측 전용)으로 대체한다. `overall_skill` 하나로 낮추지 않는다.

## G. 사용자 결정이 필요한 값 (임의 확정 금지)

| 값 | 참고(온라인 사례) | 제 추천(검토용) |
|---|---|---|
| 기본 액션 시간 | PokerStars 토너: Regular 18초, Turbo 14초, Hyper 12초 / GG: 프리플랍 10초, 이후 15초 | Regular 18초부터 시작해 체감으로 조정. 지금 15초는 짧다는 의견 반영 |
| 초기 타임뱅크 | PokerStars: 일반 MTT 90초 ~ 하이퍼 SNG 10초 | 일반 60~90초 |
| 충전 규칙 | 사이트마다 레벨/시간 경과 충전 | 레벨당 소량 충전 또는 브레이크 충전 중 택1 |
| 핸드당 사용 상한 | — | 처음엔 없음 |
| 레이트 레지 참가자 뱅크 | — | 시작 뱅크와 동일 |
| 포맷별 차이 | 위 사례처럼 터보·하이퍼는 짧게 | 포맷 표에 칸 추가 |
| 카운트다운 숫자 표시 시점 | — | 처음 몇 초는 생각 표시만 → 이후 숫자 → 기본 소진 시 TIME BANK 표시. 몇 초인지는 결정 필요 |
| 타임아웃 동작 | 요구: 체크 가능하면 체크, 아니면 폴드 | 확정(지금 HERO 구현과 같은 결과, §I-3). 봇·타임뱅크 소진에도 같은 함수를 쓴다 |
| 타이밍 성향 4개의 분포 | — | 새 prior. 별도 설계 |

## H. 단계별 구현 순서(승인 후)

1. 순수 함수 `mechanical_time`, `action_clock`, `bot_timing`(provenance 입력, 결정론적 시드) + 검증기(전략 불변성: timing ON/OFF 동일 액션·사이즈·승자·스택·RNG 지문).
2. 봇 액션 이벤트에 UI 안전 메타(`clock_started_at`, `base_deadline`, `bank_deadline`)만 실어 보내고, 화면은 **남은 액션 시계**를 그린다(봇 예정 시각 아님).
3. REAL 테이블 송출 시각 = 결정 시각. BOT 테이블 `virtual_seconds += mech + visible`.
4. `_vclock_hand_seconds` 대체(총량 보정 측정 후).
5. 타임뱅크·타임아웃·재접속 지속성.
6. H4H·이동이 새 시각을 그대로 쓰는지 검증(느린 테이블이 실제로 라운드를 늦춤, 미래 시점 플레이어를 과거 테이블로 옮기지 않음).

## I. 기존 vclock 과 충돌하는 지점

1. **REAL 테이블 봇 시간이 없다.** 지금 HERO 테이블 봇 액션은 UI 모션 템포(프런트 1.5초 등)로만 보이고, 대회 시각에는 HERO 실제 경과만 반영된다. 새 모델에서는 봇 `visible` 이 실제 테이블 시간을 소비해야 한다 → UI 모션 템포와 겹치지 않게 "모션은 visible 안에 포함"으로 정리 필요.
2. **두 시간 모델 공존.** BOT 테이블은 `_vclock_hand_seconds`(사후 고정비용), HERO 테이블은 wall. 같은 규칙 원칙에 어긋난다 → §H-4 에서 하나로.
3. **타임아웃 동작은 충돌 없음.** `_timeout_action` 은 "fold 가 노출되면 fold, 아니면 check" 인데 `ui_view` 가 fold 를 콜할 금액이 있을 때만(`tc > 0`) 노출하므로 결과는 요구("체크 가능하면 체크, 아니면 폴드")와 같다. 일반화할 때 이 의존(노출 규칙)을 함수 안에 명시하는 것만 필요.
4. **선계산 범위와 브레이크.** 선계산 청크(`VCLOCK_CHUNK_SECONDS` 120)는 고정비용 시간 기준이다. 봇 시간이 길어지면 같은 청크에서 더 적은 핸드가 계산되고 대기 체감이 달라진다 → 측정 필요.
5. **이동 예약.** `vclock_find_refill` 의 candidate 예약은 핸드 종료 시각 기준이라 새 시각 모델에서도 그대로 쓸 수 있다. 다만 같은 사람이 두 테이블 후보로 중복 예약되지 않는지(요구 §44)는 지금 HERO 보충 한 경로만 있어 문제없지만, 멀티플레이(인간 여러 명)에서는 예약을 전역으로 관리해야 한다.
6. **H4H 시각.** `compute_vclock_ahead` 의 H4H barrier 는 "가장 느린 테이블 한 핸드"로 이미 실시간 의미와 맞다. 긴 탱크가 라운드를 늦추는 효과는 봇 시간이 들어오면 자동으로 생긴다.

출처: PokerStars 타임뱅크·액션 시간(pokerstarsnj.com help, 2+2 포럼 요약), GGPoker 액션 시간·타임뱅크 카드(help.ggpoker.com, pokerlistings).
