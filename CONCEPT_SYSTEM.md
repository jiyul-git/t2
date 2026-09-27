# CONCEPT SYSTEM — glossary, wiring, taxonomy, cleanup

이 문서는 기존 변수 사전, 배선 대장, 전수조사 장부, concept wiring/prior audit의 현재 결론을 통합한다.

## 1. 층 구분

### Latent
플레이어 생성 시 상관 구조를 만드는 잠재요인. runtime 판단에서 직접 읽지 않는다.

### Temperament / personality
장기 성향. 방향과 빈도 편향을 만든다.

### Strategic concepts
학습/능력/전략 지식의 축. 현재 production에는 37개 declared strategic concepts가 있다.

### Derived axes
기질/개념/상황을 조합한 runtime 값. 별도 “개념”으로 중복 생성하지 않는다.

### Observation / reads
상대의 공개 행동으로부터 추정하는 통계와 perceived profile.

### Range layer
preflop range -> perceived range -> action-history narrowing -> seat-keyed opponent pools.

## 2. Wiring rule

새 개념은 반드시 두 위치를 문서화한다:
1. producer — 어디서 생성/업데이트되는가
2. consumer — 실제 판단의 어느 지점에서 읽히는가

“변수는 있는데 아무도 안 읽음”을 허용하지 않는다.

Runtime 구분:
- perception/calculation concept: JUDGMENT
- motive/strategy concept: PLAN
- execution-form skill: 전략적 action form을 고르는 PLAN
- pure legality/rounding: ACTION

## 3. Current wiring status

Concept wiring audit 최종 요약:
- declared strategic concepts: 37
- core runtime dead concept: 0
- low reference count만으로 dead 판정하지 않음
- money_jump: partial/live+shadow architecture
- style-belief branch: 존재하지만 현재 production 의사결정에는 미배선
- archetype compatibility layer: legacy fallback로 유지
- concept prior/loading/spread: 전역 calibration 완료 상태가 아니라 provisional

## 4. Current taxonomy barrier

Prior sensitivity audit 이후 **street granularity**가 calibration blocker로 남아 있다.

확인된 대표 사례:
- `thin_value_turn`이 flop fallback에서도 쓰여 street 의미가 섞임.

진행 순서:
1. street/motive별 의미가 다른 concept을 식별.
2. missing motive -> execution wire 수정.
3. 필요하면 split/add하되 backward-compatible migration.
4. targeted counterfactual + frozen regression.
5. realized-prior audit 재생성.
6. 그 뒤에만 loading/spread calibration.

taxonomy가 안정되기 전에는 전역 prior 수치 튜닝을 확정하지 않는다.

## 5. Important semantic rules

- `nut_advantage`는 **range vs range strong-region occupancy**이지 Hero 현재 핸드 강도가 아니다.
- ICM/BF와 money_jump는 같은 개념이 아니다.
- blockbet과 donk는 known aggressor semantics가 필요한 별도 motive/execution 의미다.
- observation stat은 action class를 섞지 않는다: fold-to-bet, fold-to-raise, opener-4bet, caller-backraise 등은 분리.
- true persona는 opponent range/read reconstruction에 직접 누출되면 안 된다.

## 6. Prior/population audit

Realized concept distribution은 nominal base/spread와 같지 않다.
다음이 분포를 재형성한다:
- latent loading
- 0/10 clamp
- overall-skill rejection filter

따라서 “base를 x 올리면 median도 x 오른다”를 가정하지 않는다.

Local sensitivity audit는 mechanics map으로 받아들였지만, 새 target median/width 자체를 선택한 것은 아니다.
특히 clamp-sensitive concept은 spread 증가가 폭보다 saturation을 늘릴 수 있다.

## 7. Cleanup ledger — current summary

정리 후보이지만 production semantics와 분리해서 처리:
- duplicate/dead ICM `field_bf` definition
- `SIZING_SIG` / observation map의 불완전 dict API
- unused static PRE/POST order imports
- old `persona.skill/has`
- dead `live.py`, `legacy_dynamics.py`, `legacy/`
- dead `table.Table` helper methods
- 여러 미호출 helper

보존해야 하는 compatibility/public API:
- tool/UI가 호출하는 `tourney.next_hand/submit/finish_hand`
- format/review public entry
- archetype fallback layer

cleanup은 기능/전략 변경과 섞지 않고 별도 regression으로 닫는다.

## 8. Open concept-level work

- street concept granularity
- P7 cold defense concepts/observations
- F7-B2 opponent aggregation semantics
- F7-C emotion consumer boundary
- F7-D execution-form/sizing boundary
- W5 posterior update에서 read/persona attribution

## 9. Historical sources

- `CONCEPTS.md`
- `LEDGER.md`
- `AUDIT_LEDGER.md`
- `CONCEPT_WIRING_AUDIT_DESIGN.md`
- `CONCEPT_WIRING_AUDIT_RESULT.md`
- `CONCEPT_PRIOR_AUDIT_DESIGN.md`
- `CONCEPT_PRIOR_AUDIT_RESULT.md`
- `CONCEPT_PRIOR_SENSITIVITY_DESIGN.md`
- `CONCEPT_PRIOR_SENSITIVITY_RESULT.md`
- `STREET_CONCEPT_GRANULARITY_AUDIT_DESIGN.md`

원문은 pre-consolidation Git history에서 보존된다.
