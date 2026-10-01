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

## 9-A. 2026-10-01 균일 성향 실플레이 점검 + 계수 수정

조건: 봇 27명(3테이블) 전원 **동일 퍼소나**(latent 5/5/5, 노이즈 없음 → 개념 = LOADING base,
기질 = 생성식 평균)로 맞추고, HERO 로 36핸드를 직접 치며 매 핸드 **모든 테이블**의
프리플랍 판단(pf_seed)과 포스트플랍 intent(판단 → plan → 실행)를 읽었다.
발견 패턴은 `tools/measure_uniform_playtest.py`(90명, 시드 11/12/13 × 60핸드, 약 1,650핸드)로 정량화했다.

### 수정한 것 (논리 모순 → 수정)

| # | 위치 | 문제 (실플레이 근거) | 수정 | 수정 전 → 후 |
|---|---|---|---|---|
| 1 | `ranges.narrow_by_actions` | 감쇠 `_DECAY**step` 이 check/call 뒤에도 쌓여, 체크레이즈·콜 후 레이즈처럼 정보량이 가장 큰 공격이 오히려 덜 좁혀짐. 레이즈도 벳과 같은 value 비율(플랍 42%) | 감쇠는 이전 **공격** 뒤에만. 레이즈 value 비율 = 벳 × `_RAISE_VALUE_SHARE` 0.45 | (아래 3과 함께) |
| 2 | `session._acts_of` | 엔진 meta 의 `raised` 가 첫 벳에도 True → 레인지 축소에서 모든 벳이 'raise' | `_range_narrow_action`: 같은 스트리트 이전 올림이 없고 pre_current 0 이면 'bet' | 벳 대면 체감 eq 0.397 → 0.385 (대조군, 거의 불변) |
| 3 | `ranges.perceived_range` | 평균 range_read(4.0) grasp 0.42 → 레이즈로 걸러낸 콤보 58% 복원. 1 을 고쳐도 레이즈 대면 체감 eq 불변(0.634→0.646) | 경로에 레이즈가 있으면 grasp 하한 `_RAISE_GRASP_FLOOR` 0.75 (“레이즈=강함”은 상식) | 자기 벳이 레이즈된 뒤 체감 eq 0.634 → 0.587 |
| 4 | `plan.decide_response` 밸류 레이즈 | eq>need+0.15 만 봄 → 원페어 rel 0.38 이 턴 밸류 레이즈를 받고 다시 올인 리레이즈(핸드 15 테이블2) | rel ≥ 0.70 (재레이즈는 0.85) 일 때만 레이즈 후보, 미달이면 콜/폴드 | rel<0.70 밸류 레이즈 12건 → 0건 |
| 5 | 같은 곳 레이즈 크기 | `mult` 상한 1.6 이 깊은 스택에서 거의 항상 걸림(TT 가 800 벳에 6,900 레이즈) | `0.70+0.45*gap`, 상한 1.10 | 레이즈 크기 p90 1.68 → 1.15 (콜 후 팟 대비) |
| 6 | `plan.decide_aggression` pot_control | “대부분 체크” 라벨인데 0.18+0.035·aggr = 평균 35.5%, aggr10 53% | 0.10+0.025·aggr, 상한 0.40 | pot_control 무저항 벳률 15.3% → 9.7% |
| 7 | `plan.revise_plan` 승격 | 생성 시 rel 0.73 → pot_control, 다음 스트리트 rel 0.74 → “강도 상승” 밸류 전환(승격 문턱 < 생성 문턱 역전). made 항은 원래 죽은 항 | rel ≥ 0.85 또는 (rel ≥ 0.70 이고 이전 rel + 0.08 이상) | — |
| 8 | `preflop.defend_action_likelihoods` | 혼합 폭 (tot−tp)·0.35 ≈ tot 의 28% → AQs·88 이 UTG 오픈에 12~16% 폴드 | 폭 = tot·0.15 | 상위 3~6% 폴드 11.3% → 3.6%, 6~10% 21.9% → 11.2% |
| 9 | `preflop.limp_p` 습관 림프 | 하위 50% 전체에 ×1.45 → 53o·T6o UTG 림프율이 그 위 대역과 같음(5.6% vs 5.8%) | 하위 대역으로 갈수록 감소(하한 0.20배) | 하위 50% 림프 5.6% → 2.0% (25~50% 대역 5.8→6.0% 유지) |

그림: `docs/uniform_playtest_before_after.png`.

### 회귀

- 수정 전 코드: `tools/regress.py check --baseline current` 전 시드 지문 일치.
- 수정 후: 6시드 전부 지문 변경(의도된 전략 변경). VPIP 20.7→20.5%, PFR 12.1→11.9%, flop 47.2→47.8%.
- **baseline 은 덮어쓰지 않았다**(PROJECT.md 7절 규칙). 위 표가 attribution 이다.
- 구조 verifier P2–P6, F1–F4, F6, F7, preflop_closure, weighted_boundaries, multiway_range_preservation PASS.
- `verify_f5_backaction`(TypeError: call_eq kwarg), `verify_replan_contract`(C4) 는 **수정 전 코드에서도 같은 실패**다(기존 문제, 이번 변경과 무관).

### 발견했지만 고치지 않은 것 (구조/열린 항목)

- **P6 콜오프 폭**: `calloff_cap` = 일반 디펜스 tot × 2.6 × 0.55 ≈ 1.43배이고 `gto._MDF` 가 6bb 에서 포화되어
  올인 가격을 거의 반영하지 않는다. BB 가 140bb 에서 BTN 30.8bb 쇼브에 QJo(상위 43%까지 콜) 콜. docstring 이 이미
  “pot-odds/equity 직접 비교는 P6 남은 항목”이라고 적고 있어 계수만 바꾸지 않았다.
- **calldown_need 잡음**: 평균 potodds(4.4)에서 calc_noise σ≈0.37, 편향 1.17. need/실제 팟오즈 중앙 1.12, p10 0.63 —
  같은 사람이 결정마다 팟오즈를 ±40% 오독한다. 설계 의도(미숙도)일 수 있어 유지, 크기는 재검토 권장.
- **F7-D 실행 사이즈 변형**: `runner.shape_size` 의 `odd` 확률이 계획 사이즈를 팟×{0.33,0.5,1,1.5}로 갈아치움
  (핸드 1: 계획 600 → 실행 1,500). 3시드에서 ±40% 초과 변형 13~25건. F7-D 열린 항목.
- **made 등급의 보드 페어**: 페어 보드에서 모든 원페어가 made=2(투페어). known issue E 그대로.
- `pf_rank.json` 순위가 올인 에쿼티형이라 76s 38.8%, 77 3.9% 등 플레이어빌리티와 어긋남(데이터 문제, 미변경).

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
