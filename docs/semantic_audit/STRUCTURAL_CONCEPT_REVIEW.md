# 기존 개념의 구조 일관성 재검토

확인 tree: `339c490f56694fbec80411b368d9ae6f9e5a3e35` (감사 checkpoint `968f10e`). 기존 ledger를 대체하지 않고, 플레이어가 묻는 질문을 기준으로 관련 구현을 비교한다. 아래 개선 이름은 제안이며 구현 완료를 뜻하지 않는다.

| 플레이어의 질문 | 실제 함수·경로 | 구조 판정 | 정리 방향 및 행동 보존 경계 |
| --- | --- | --- | --- |
| 재레이즈에 더 공격할까, 콜할까, 폴드할까? | `gto.defend_pct → threebet_pct`; `preflop.defend_thresholds → defend_action_likelihoods → defend_decision` | 3bet과 4bet 이상이 완전히 다른 엔진이라는 설명은 부정확하다. 공통 폭 계산 뒤 `raise_level >= 2`이면 `LEVEL_TIGHTEN`으로 축소한다. `3bet` 결과 라벨도 상위 레이즈에 재사용한다. | 행동 공간 attack/call/fold는 공통 유지. 상황별 prior 공급과 실제 raise level 명칭은 분리 후보. 독립 4bet 지식 추가는 전략 변경이므로 후속 작업. |
| 콜할 수 있을 만큼 수익성이 있는가? | `preflop.calloff_cap/calloff_decision/calloff_layer_judgment`; `plan.calldown_need/decide_response` | 같은 투자 질문에 PCT 순위 컷과 layer equity/EV 판단이 공존한다. layer 경로도 모든 상황에 연결된 것은 아니다. | 공통 입력은 비용·참가 자격·상대별 range. 계산 결과의 단위와 fallback provenance를 명시해야 한다. 순위 컷을 EV로 교체하면 행동이 바뀐다. |
| 상대의 베팅을 어떻게 해석하는가? | `ranges.perceived_range/blend_action_range_by_grasp`; `persona.bias/read_opponent`; `plan.decide_response` | range 복원 정확도, 상대 성향 해석, 콜 성향이 `range_read`와 연관돼 있다. 하나의 skill을 조정하면 서로 다른 질문까지 변한다. | 역할별 소비 경계를 구분하되 기존 skill 공급은 보존. 독립 skill 도입·중복 편향 제거는 후속 전략 변경. |
| 지금 보드가 얼마나 위험한가? | `plan.make_plan`의 `dang`; `plan.refresh`의 `state['danger']`; `bot.board_danger` | 최초 계획은 board_texture skill로 위험도를 축소하지만 refresh는 raw 값을 저장한다. 같은 상태 키가 lifecycle에 따라 객관값/인식값으로 달라진다. | raw_board_danger와 perceived_board_danger 계약을 분리할 필요. 현재 consumer를 새 값으로 연결하는 것은 행동 변경이므로 이번에는 보류. |
| 새 카드가 무엇을 바꿨는가? | `texture.turn_card_effect`; `plan.decide_response/refresh` | river에서도 `board[:3]`와 마지막 카드로 평가하는 경로가 있다. turn을 포함한 직전 보드와의 비교와 동일하지 않다. | flop→turn, turn→river 전이의 입력 계약 분리. river 입력 교정은 평가 결과가 달라지므로 semantic-fix로 분리. |
| 남은 기회에 목표 스택을 어떻게 넣을까? | `plan.stackoff_plan → spread_curve` | street 인자를 받지만 기하급수 배분은 세 번의 투자 및 flop/turn/river 출력에 고정돼 있다. turn/river 진입 시 남은 투자 횟수와 불일치할 수 있다. | 목표 투자액과 remaining streets를 분리한 계산이 필요. 지수·배분 변경은 sizing 변화이므로 후속 작업. |
| 체크 후 레이즈할 근거가 있는가? | `plan.checkraise_decision → checkraise_draw_street_probability/checkraise_river_probability` | flop/turn에는 semibluff 근거가 있지만 river에는 미래 draw가 없다. 확률 함수는 이번에 분리했다. turn/river capability 공급은 여전히 checkraise_late를 공유한다. | 동일한 value 하한 계산은 공통 유지. river draw 근거는 분리 유지. 독립 capability 생성과 river_bluff 라벨 교정은 후속 작업. |
| 상대가 계속할 range는 무엇인가? | `ranges._continue_range/_call_range/continuation_support_fraction` | continue는 raise까지 포함할 수 있고 call-only는 다르다. 이름이 비슷하다고 한 집합으로 합치면 베팅 EV 의미가 바뀐다. | 공통 폭 계산만 이번에 통합. raise 가능 여부와 call-only 분기는 유지. |
| 내 패가 강한가, 내 range가 유리한가? | `plan.relative_strength`; `bot.equity_vs_combos`; `ranges.range_advantage/joint_nut_advantage` | 현재 패의 not-behind, 미래 split share, range 대 range 우위, 강한 category 점유율은 서로 다른 질문이다. 특히 nut advantage 이름은 정확한 nuts 보유율로 오해하기 쉽다. | 공통 strength scalar로 통합하지 않는다. 계산량·tie 처리·대상 range를 계약에 명시. 정확한 nuts 지표로 교체하는 것은 후속 변경. |
| 상대를 관찰한 기억이 다음 판단에 이어지는가? | `live2.build_hand`; `play.Hand.__init__`; bot-table hand 생성 경로; `session.HandRun._finish → reads.Book.observe_showdown` | hero-table의 저장 Book과 기본 새 Book 경로의 지속성이 다르다. showdown 관측은 shown/muck 결정보다 먼저 이뤄진다. | 기억 lifecycle과 공개 정보 경계를 공통 계약으로 정리할 필요. 기억 유지/관측 대상 변경은 미래 행동이 바뀌므로 이번 리팩터링에 섞지 않는다. |

## 적용 판단

공통화해야 하는 것은 같은 입력·출력 의미의 계산이며, 같은 행동 이름 자체가 아니다. 반대로 3bet·4bet처럼 공통 의사결정 틀이 있는 곳은 틀을 복제하기보다 상황별 지식 공급의 빈칸을 드러내야 한다.

이번 추가 검토에서는 production 코드를 수정하지 않았다. 기존 행동 보존 검증의 범위도 확대했다고 주장하지 않는다. 개별 consumer 목록과 미해결 항목은 CONCEPT_FUNCTION_REGISTRY 및 DUPLICATION_AND_OVERLOAD_LEDGER를 따른다.
