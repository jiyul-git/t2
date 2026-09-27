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
