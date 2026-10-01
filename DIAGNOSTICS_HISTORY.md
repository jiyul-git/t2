# DIAGNOSTICS HISTORY — closed investigations and legacy notes

이 문서는 현재 source of truth가 아니라, 과거 진단에서 얻은 재사용 가능한 결론을 보존한다.

## 1. Plan / response path

### Plan ladder
초기 조사에서 personality/skill이 모든 plan label에 균일하게 연결된 것이 아님을 확인.
일부는 gate/threshold, 일부는 aggression roll, 일부는 response path에만 영향.

### Refresh/replan
turn/river의 plan 상당수가 initial make_plan이 아니라 update/revise/refresh path에서 갱신됨.
과거에는 revise path가 initial path보다 적은 context를 넘기는 문제가 있었고 이후 context forwarding fix로 닫힘.

### Response
facing-bet은 기존 plan 실행의 “마음 바꿈”이 아니라 새 response-plan event.
pot odds / sizing read / read confidence / action class를 분리해야 함.

## 2. Pot odds / need path

과거 `need_true` 계산과 downstream overwrite를 분리해 조사.
핵심 교훈:
- 산수 오류 수정과 personality chain 복원은 같은 변경이 아님.
- 한쪽은 명백한 factual correction, 다른 쪽은 양방향 strategy behavior change일 수 있음.
- 따라서 같은 commit에서 “정확도 수정”으로 묶지 않는다.

## 3. Sizing-tell history

초기 `sizing_tell`은 실제 observed size를 연속적으로 보정하기보다 특정 overwrite의 on/off gate처럼 작동했던 시기가 있었음.
`_sz_seen` 대입이 기존 need chain을 통째로 교체하는 구조를 찾아 별도 분석.

교훈:
- perception skill은 measurement availability/trust와 observation error를 분리.
- assignment와 adjustment를 구분.
- river-only bypass/gate 누락은 street taxonomy와 함께 봄.

## 4. Preflop defend / MDF

BB defend audit에서:
- baseline range width
- pot-odds/MDF adjustment
- mixed execution layer
를 분리해야 한다는 결론.

단순 “pot odds보다 equity가 높았는데 fold”만으로 bug 판정하지 않는다.
hero의 전략 range 밖 fold와 execution mixing을 구분.

## 5. Bluff coherence

초기 bluff tag 중 여러 개가 control fixture에서 사라져 metric 자체를 수정.
river bluff 0건을 path blockage로 오진했다가 expected frequency가 매우 낮음을 재확인.

교훈:
- rare event 0 count를 reachability 0으로 단정하지 않음.
- hand-level 정상성 vs player-level 반복 pattern을 분리.

## 6. A5/A6 replan context

A5 blockbet control-flow와 A6 replan provenance audit를 분리해 실행.

결론:
- 일부 field mismatch는 production action에 영향 0.
- `bb_chips`, `opp_est`, `opp_stack_bb` 등은 상호작용으로 sizing difference를 만들 수 있음.
- position/initiative context는 단독 영향 0이더라도 완전 재생성 contract에서 default로 떨어지는 구조 문제였음.
- 이후 최소 context forwarding fix + regression으로 closure.

## 7. Blockbet / donk semantics

Known aggressor가 없는 pot에서 legacy positional fallback이 blockbet/donk 의미를 오염.

Audit 후 rule:
- blockbet에는 known aggressor 필요.
- donk suppression에도 known aggressor 필요.
- no-aggressor legacy fallback을 semantic consumer에서 제거.
- historical provenance는 유지.

Post-fix same-sample audit + frozen regression 후 CLOSED.

## 8. Near-all-in precursor

처음에는 “near stack bet이 왜 조금 남는가”를 sizing noise로만 봤지만,
실제로:
- strategic target
- legality/min-raise
- actor-effective vs opponent-effective
를 구분해야 함을 확인.

후속 accepted rule은 `POT_ALLIN_MODEL.md`의 effective-all-in v1.

## 9. Legacy project notes에서 보존할 것

과거 WORKLOG/CLAUDE/PLAN류에서 아직 유효한 핵심:
- `session.HandRun`이 실제 hand progression owner.
- driver/runtime copy와 source tree를 혼동하지 않음.
- `ranges._call_range` top-end handling 같은 range bug는 실제 play review에서 발견된 적 있음.
- draw-strength straight logic이 gap을 무시해 outs를 과대평가한 버그가 있었고, “필요 카드 수를 실제로 세기” 방식으로 수정.
- 실제 플레이 검증이 static review에서 안 보이는 문제를 잡을 수 있으므로 hand review를 유지.

그 외 오래된 line number, old branch, old baseline 설명은 현행 source로 사용하지 않는다.

## 10. Historical sources

- `TRACE_PLAN.md`
- `TRACE_REFRESH.md`
- `TRACE_RESPONSE.md`
- `TRACE_NEEDPATH.md`
- `TRACE_MDF.md`
- `TRACE_DEFEND.md`
- `TRACE_STELL.md`
- `TRACE_SZSEEN.md`
- `TRACE_BLUFF.md`
- `A5_*.md`
- `A6_REPLAN_PROVENANCE_RESULT.md`
- `BLOCKBET_DONK_*.md`
- `FIX_PLAN.md`
- `INSTRUMENTATION_BASELINE.md`
- `WORKLOG.md`
- `PLAN.md`
- `CLAUDE.md`
- `claude_README.md`
- `REVIEW_2.md`

원문은 pre-consolidation Git history에 보존된다.

## 11. audit9 실제 플레이 감사 (test 브랜치, HAND 15–86 + 2번째 토너먼트 1–8)

조건: max-skill 동일 프로필(`tools/manual_one_hand.py`), 9-max, 모든 테이블 감사.
판정 분류: A 직접 +EV / B solver 허용 / C 정상급 인간 deviation / D 의도된 인간 실수 / E 코드·의미론 버그 / F 근거 부족.
같은 증상이 다시 나오면 새 수정이 아니라 아래 root cause의 **재현 사례**로 추가한다.

### 11.1 Root cause 등록부

| ID | 내용 | 재현 핸드 | 상태 |
|---|---|---|---|
| R1 | 액션→레인지 의미: 혼합 정책을 hard slice로 모델링, 체크가 최상단 삭제, 비공격 액션 뒤 감쇠 누적, 가중 레인지 평탄화, 숏 올인 위 레이즈를 3벳으로 해석 | 15, 17, 67 | 수정 |
| R1b | 플랍 레이즈 레인지 구성: 인식 모델 원페어 69%(A-K-5 예) vs 실제 봇 레이즈 원페어 31%/투페어+ 39%/드로우·에어 30%(보드 비통제). 100bb 탑페어가 레이즈 위로 재레이즈 올인하는 연쇄의 출발점 | 시뮬 m_after 12/16(AQ), 12/36(AK) | **미수정** — 동일 보드 보정 테스트 필요(F) |
| R2 | `pf_rank`/PCT 다목적 사용(오픈·디펜스·3벳·4벳·레인지 재구성). AKo 7.1%(66·QTs·KTs보다 아래) | 17, 23, 41, 43, 56, 61, 2차 3(UTG+1 3벳 레인지에 AKo 거의 없음 → QQ eq 0.22로 턴 폴드), 86(KJs 4.8%) | **미수정** — 순위표 통교체 금지, 용도별 판단 분리 설계 필요 |
| R3 | 4bet/reraise 공격 근거: `bluff_support = max(bluff_skill, …)`라 max-skill(bluff 10)에서 keep=1 → 블로커 없는 88/TT 공격 질량 유지(코드로 확인) | 28, 41, 45, 51 | **설계 완료·미적용** — 체크포인트 3 이후 첫 batch. (1) 블러프 근거 = max(읽기, 블러프 실력×폴드 가능한 상대 최상단 밸류의 실제 블로커 비율) (2) 올인 상대가 있으면 기준은 fair share가 아니라 가격 need(올인 상대 레인지 eq). HAND 51 재구성: 88/TT/AKo 공격 0, KK 유지 |
| R4 | 올인 형태/스택 기하 의미 | 21(variance_seek에 accum_drive), 23(다인원 +0.2 고정가산), 49(체감 깊이로 쇼브 구조항), 81(포지션 무관 쇼브 구조항) | 수정(하위 원인 4개, 모두 같은 방향) |
| R5a | pot_control인데 어그레서가 뒤에 있는데 리드 | 38 | 수정 |
| R5a-ext | 같은 line-ownership 규칙의 누락 소비처: 턴/리버에만 있는 '상대 공격 콜 + OOP → 상대에게 액션 우선'이 플랍(프리플랍 레이저가 뒤에 있음)에 연결 안 됨 | 2차 13/15, 시뮬 플랍 동크 21% | **설계 완료·미적용** — 첫 batch. 빈도 목표 튜닝이 아니라 기존 규칙 연결, 새 계수 없음 |
| R5b | rel 불변인데 '강도 상승' 승격 | 46 | 수정 |
| R5c | 페어 보드 two-pair 등급을 드로우 완성으로 오판 | 63 | 수정 |
| R5d | 블락벳 사이즈가 텍스처·equity denial 보정에 덮여 0.76팟 | 2차 토너먼트 이전 83 | 수정 |
| R6 | 스택오프/오버벳을 전체 레인지가 아니라 그 사이즈에 계속할 레인지 대비로 | 16 | 수정 |
| R7 | 2-street bluff 리버 버짓 누락(계획 bet, 실행 check) | 20 | 수정 |
| R8 | 올인 + 다른 생존자 → multiway/calloff 경로 누락 | 36 | 수정 |
| T1 | 감사 도구: 히어로 테이블 replay에서 reasoning RNG 분기(20건 중 2건) | — | REPLAY-DIVERGED 표시, 근거로 단정 금지 |

정상 판정(수정 안 함): 19(A3s rel 0.06), 22(QQ 5bet), 29/32(J5o, read+혼합 꼬리), 75(J7o 20bb 리쇼브: 방어 경계 밖 콜 26%/공격 0.7%), 77(멀티웨이 JJ 345 체크), 82(AKo 8-6-2 투톤 폴드, 경계), 84(A7o 스퀴즈 쇼브 → KQo 콜오프: 레이어 eq 0.496 > 0.418).

### 11.2 계수 변경 장부 (base 70008d9 → 현재)

| 위치 | 이전 | 현재 | 방향/목적 | RC |
|---|---|---|---|---|
| `preflop.defend_action_likelihoods` 혼합 폭 | `max(0.02,(tot-tp)*0.35)` | `max(0.015, tot*0.15)` | 경계 혼합 축소(강한 핸드 폴드 감소). **주의: AKo 폴드는 R2 원인이므로 이 폭으로 더 보정하지 말 것** | R1/R2 |
| `ranges._LIK_MIN` | — | 0.01 | 가중 레인지 최소 가중 | R1 |
| `ranges._check_range` | 상위 `0.10·min(1,cbet/6)` 삭제 | 같은 상위를 `1−min(1,cbet/10)` 가중으로 유지 | 체크 레인지에 강한 핸드 잔존 | R1 |
| `preflop.raise_form` 다인원 쇼브 | `sh + 0.20(n−1)` | `sh·(1+0.20(n−1))` | 딥스택 쇼브 제거 | R4 |
| `persona.variance_seek` | `weak + 0.55·accum` | `weak` | 의미 분리 | R4 |
| `preflop.open_form` 구조항 | 체감 feel | aware는 유효스택 `eff_bb` | 쇼브 감소 | R4 |
| `preflop.open_form` 포지션 깊이 | — | `eff_bb·max(1, 2.6/OPENER_MULT[pos])^0.5` (UTG ×1.36, LJ ×1.2, HJ ×1.09, CO+ ×1) | 앞 포지션 쇼브 감소. 지수 0.5는 **신규 판단값** | R4 |
| `plan.make_plan` commit 재계산 | — | 탐침 사이즈 continue range rel, 조건 `commit>0.30 & made<5` | 스택오프 감소 | R6 |
| `plan.overbet_frac` value rel | 전체 rel | `min(rel, rel vs continue@1.15)` | 오버벳 감소 | R6 |
| `plan.SIZING['bluff_2street'].river` | 0.0 | 0.72 | 계획-실행 일치(증가 방향, 유일) | R7 |
| `plan.decide_aggression` pot_control | — | 어그레서 뒤 + 이니셔티브 없음 → 0.04 | 리드 감소 | R5a |
| `plan.revise_plan` 승격 | `rel≥0.70 or made 증가` | `rel≥0.88 or (rel≥0.70 and 상승)` — 0.88은 응답 경로 `rel_ps≥0.88` 단계 재사용 | 승격 감소 | R5b |
| `plan.revise_plan`/`river_fix` 완성 | `made≥2 or rel≥0.62` | `made≥4 or rel≥0.62` | 오판 제거 | R5c |
| `plan.decide_size` block | 상한 없음(0.15–1.0) | `[0.18, 0.40]` — **신규 대역** | 사이즈 감소 | R5d |

반대 방향 재조정 점검: 같은 계수를 서로 반대로 움직인 기록은 없다. 다만 R1·R4·R5·R6 수정이 **모두 공격성·투입을 줄이는 쪽**이라 누적 효과로 지나치게 수동적이 될 위험이 있다. 다음 체크포인트부터 max-skill 시뮬에서 벳/레이즈 빈도·VPIP·승격 수를 함께 감시하고, 공격성이 base보다 크게 줄면 개별 계수를 되돌리지 말고 어느 의미가 겹쳤는지부터 분리한다.

### 11.3 대표 재현 (HAND 15)
CO T♠A♣ 체크레이즈 7,100 → BTN T♣A♠. 수정 전 CO 콜 레인지 TT·99·22·ATo 0%, 체크레이즈 90콤보(셋/투페어 0%),
BTN rel 1.00, eq 0.845(need 0.324), value_3street → 30,900 올인. 수정 후 135콤보(질량 54, 셋 5.6%, 투페어 1.3%, 강한 드로우 36%),
rel 0.63, eq 0.437, showdown → 콜. 자연 재생에서는 CO가 체크레이즈 대신 콜(CO rel 0.98→0.89).

### 11.4 검증
- 회귀 게이트(체크포인트 3, 현재 코드): 23개 중 17개 통과(verify_core×5, preflop_closure, human_model_v3/runtime/integration, read_recency_v3, p2, p3, p5, p6, weighted_range_adapter, multiway_range_preservation, f7b_defend_likelihood). 실패 6개(p4_vs_3bet, f3, f4, f6, f7, weighted_boundaries)는 base에서도 동일 실패하는 레거시.
- **baseline 시뮬(체크포인트 3 기준, tilt 0·exploit 중립 고정, max-skill 동일 프로필, 시드 11/12, base 70008d9 → 현재)**:
  원페어 이하 스택 97%+ 투입 37→17(전체 71→44), 팟컨트롤 동크 24→6, 승격 213→159, 상위 3–6% 오픈 대면 폴드 10.9%→1.8%,
  6–10% 8.7%→6.4%, EP/MP 17–27bb 오픈 쇼브 7/12→2/13, 블락 사이즈 중앙값 0.56→0.39.
  공격성 감시: 무저항 벳 비율 0.363→0.331, 벳 대면 레이즈 0.090→0.076, 자기 벳 후 레이즈 대면 폴드 0.22→0.35, VPIP 0.234→0.228,
  플랍 동크 0.238→0.214. 감소 폭은 중간 — 다음 batch에서 계속 감시.
- (참고, exploit 활성 조건) max-skill 시뮬(시드 11/12, base → 체크포인트 2 코드): 상위 3–6% 오픈 대면 폴드 11.0%→1.0%, 6–10% 11.4%→4.7%,
  팟컨트롤 동크 31→5, 승격 155→113, 오버벳 17→10, 원페어 이하 스택 97%+ 투입 21→19.
- average persona: 강한 핸드 오픈 대면 폴드 15.7%→3.8%, 19.4%→8.3%. 단 레인지 grasp가 좁힌 레인지를 다시 넓혀 레이즈 대면 eq는 0.612 그대로.
- 판단 근거 중 직접 EV 비교가 있는 경로: 포스트플랍 call/fold(eq vs 가격·ICM), non-value raise EV gate, 프리플랍 calloff 레이어 EV(일부).
  프리플랍 디펜스/3벳/4벳과 포스트플랍 plan 선택은 아직 휴리스틱이다 — '정상'을 '+EV'로 부르지 않는다.

### 11.5 감사 조건과 workflow
- 현재 phase(baseline): tilt 0, exploit/상대 적응 중립 고정, 동일 max-skill 프로필·성향, 핸드마다 프로필·읽기 상태 불변.
  이 조건에서 이상 행동을 tilt나 exploit으로 설명하지 않는다. tilt·exploit은 baseline 계수 안정 후 별도 phase에서 독립 검증.
- 실제 실행 경로(트랜스크립트 명령 기준으로 검증):
  - HAND 1–15: `python tools/manual_one_hand.py` 1회(08:37:35–08:38:38). 한 프로세스의 `while True`가 HAND 5 이후를 연속 실행했다.
  - HAND 16–86: 스크래치 드라이버 `a9drv.py`(`act`/`show`/`auto N`/`init`). 드라이버 **호출마다** 새 python 프로세스다.
    다만 핸드마다 새 프로세스는 아니다: `auto N`은 한 프로세스에서 최대 N핸드(예: 28–33, 37–40, 55–66, 68–71)를,
    `init`은 기록된 히어로 액션으로 HAND 1부터 다시 재생한다(재생 시 봇 판단은 그 시점 코드로 다시 계산되어 핸드 내용이 바뀐다).
  - 코드 수정은 모두 드라이버 호출 **사이**에서만 일어났다. 포그라운드 호출은 순차 실행이고, 백그라운드 실행 4건
    (manual_one_hand 08:37–08:38, init 10:13–10:20, 10:30–10:38, 10:41–10:47)도 실행 중 저장소 코드 수정과 겹치지 않았다.
    따라서 각 핸드는 실행 내내 같은 코드로 진행됐고, 수정은 **다음 드라이버 호출부터** 반영됐다.
  - 장시간 시뮬·게이트도 시작 시점 코드로 돈다(수정 후 재실행).
  - 체크포인트 3 이후 대표 재현(HAND 15 레인지, 21, 23, 81, 83)은 HEAD 9b5b81b와 바이트 동일한 모듈을 불러온 새 프로세스에서 재확인했다.
  따라서 수정 후 같은 증상 재발은 '미반영'이 아니라 누락 소비처 / 다른 원인 / 정상 변동 중 하나로 판정하고, 미적용 설계(R3, R5a-ext)의 재발은 재현 사례로만 기록한다.
- 이후 workflow: ChatGPT = 실제 플레이, Claude = GitHub telemetry 감사 + root-cause 판정 + 코드 수정.

### 11.6 다음 순서
1. R3(4bet/reraise 공격 근거) — bluff_skill을 공격 근거가 아니라 블로커·폴드에쿼티·continue range 활용 능력으로.
2. R2 — pf_rank를 호환용 순서로 동결하고 용도별(디펜스/3벳/4벳) 판단을 레인지·가격·eq로 분리.
3. R1b — 동일 보드 보정 테스트.
4. 대형 팟(올인 콜, 4bet+, 딥 스택오프)부터 action별 EV 감사, solver/정상급 플레이어 사례는 조건 일치 클러스터 단위로만.
5. 열린 기타: 레이즈 ×1.45 후 작은 잔여 스택(HAND 51), average persona grasp 하한, max-skill UTG 숏스택 '이론적 림프' 12%(관찰).
