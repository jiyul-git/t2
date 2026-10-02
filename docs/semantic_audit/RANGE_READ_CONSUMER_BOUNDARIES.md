# range_read의 소비 경계 — 3차 정리

기준 `33df2ee`. 기존 range_read 공급·분포·threshold·확률은 유지한다. 독립 skill 생성이나 학습 지식 추가는 없다. 함수 이름만 바꾼 것이 아니라 다음 계산 본문과 입출력을 분리했다.

| 역할 | 현재 계산 함수 | 입력 → 출력 | 실제 소비 경로 |
| --- | --- | --- | --- |
| 상대 range 복원 정확도 | `ranges.reconstruct_range_with_accuracy` | prior/full posterior, reconstruction_skill → 인식 가능한 combo range | perceived_range / perceived_continue_range / perceived_facing_bet_response → session 및 plan의 equity·value 판단 |
| 액션·value/bluff 성향 해석 | `persona.interpret_opponent_action_signals` | 관측 통계, frequency/line/size gate, 기존 w → bluff_gap·barrel_gap·street fold gap 등 | read_opponent → range 모델 및 계획·익스플로잇 판단 |
| bluff 위협의 주관적 해석 | `persona.interpret_bluff_threat_bias` | bluffcatch 숙련도·공격성·line_interpretation_skill → bluff_fear 편향 | bias('bluff_fear') → call_bias 및 decide_response |
| 해석을 판단에 사용할 능력/성향 | `persona.opponent_read_application_weight` | application_skill·adaptability·attention·표본 신뢰도/수 → 기존 legacy 적용 가중치 | exploit_weight → 기존 exploit consumer. V3 ON은 기존 _exploit_base_weight 우회 유지 |
| 해석된 편향의 실제 call/fold 적용 | `plan.apply_response_biases_to_call_threshold` | 필요승률·size·street·station/bluff_fear/hero_call → 주관적 콜 문턱 | decide_response → 실제 call/fold 선택 |

## 공급과 계산을 혼동하지 않음

- reconstruction_skill과 application_skill은 현재 각각 기존 range_read에서 공급받는다. 독립 값 샘플링은 없다.
- read_opponent는 기존 attention/range_read/sizing_tell 게이트와 adaptability/data 가중치를 계산한 후 interpretation 함수로 넘긴다. line gate를 별도로 주입할 수 있지만 새 gate 정책을 추가하지 않았다.
- interpretation 함수의 `w`는 결과 dict에 보존하는 기존 적용 정보이며 bluff_gap 계산에 곱하지 않는다. 해석 신호와 적용 가중치는 구분된다.
- bluff_fear 해석과 그 편향을 문턱에 반영하는 식은 서로 다른 함수다. 적용 함수는 profile/range를 직접 읽지 않는다.
- legacy `blend_action_range_by_grasp`는 호환 호출만 유지한다. 세 production perceived-range consumer는 새로운 reconstruction 함수로 직접 연결된다.
- 레인지 복원의 rr<1.5 early return과 full posterior 생성 순서는 각 caller에 그대로 둔다. 이를 강제로 한 곳에 옮겨 실행 시점을 바꾸지 않는다.
- flop/turn의 적용식은 동일한 계산을 공유하고 river만 기존 가중치가 다르다. 모든 street를 세 함수로 복제하지 않았다.

## 잔여 소비 경로와 경계

| 위치 | 추가 의미 | 이번 상태 |
| --- | --- | --- |
| reads.obs_from_profile | 관측 데이터 품질 | 유지; range 복원 정확도와 같다고 간주하지 않음 |
| persona.bias('overpair_love') | 자신의 원페어 과신 | 유지; bluff_fear 해석과 다른 편향 |
| persona.perceived_edge / overall_skill | 자기 실력 인식 및 종합 실력 | 유지; 상대 액션 해석으로 재분류하지 않음 |
| preflop.multiway_reraise_decision | potodds/multiway와 결합한 reasoning 능력 | 유지; 별도의 적용 consumer 추출 후보 |
| money_pressure.read_adjustment / actor_from_profile | 토너먼트 압력에 관한 인지·활용 | 유지; pressure 문맥 계약을 확인한 뒤 별도 정리 |
| plan.make_plan 및 여러 공격 consumer | 해석된 gap을 밸류/블러프/raise 동기에 적용 | 기존 read dict 소비 유지. 단일 독립 application skill로 전면 통일하지 않음 |

기존 코드에는 call/fold/raise 전부를 지배하는 하나의 '해석 적용 능력'이 없다. 이번에는 실제 존재하는 legacy 가중치와 call/fold 문턱 적용을 분리했으며, 새로운 skill을 모든 레이즈에 곱하지 않았다. 따라서 range_read 전체 과적재 제거 또는 독립 3-skill 모델 완성을 주장하지 않는다.

## 검증

`tools/verify_range_read_semantics.py`는 Git 기준의 실제 함수 본문과 현재 consumer를 비교한다. read/bias 300, application weight 180, range 540, response action+state+RNG 288건. 합계 1,308건이며 별도로 역할별 입력/출력 경계 4건을 검사한다. legacy/V3 exploit 분기, 낮은 skill 경계, 누락 관측치, weighted ranges, layer call 경로를 포함한다. 전체 핸드 검증 결과는 REFACTOR_AND_VERIFICATION에 기록한다.

## 4차: 추가 range_read 소비 경계

| 역할 | 현재 함수 | 입력 → 출력 | consumer / 계층 |
| --- | --- | --- | --- |
| 관측 정확도 | reads.observation_accuracy_from_capabilities | attention, observation_read_skill, sizing_tell → 기존 [0.03, 0.98] 정확도 | obs_from_profile → 관측 모델 / PERCEPTION |
| 토너먼트 압박 활용 | money_pressure.pressure_application_capacity | money_jump, fold_equity, pressure_read_skill, attention, adaptability, aggression → 기존 mean01 활용 능력 | exploit_realization → pressure_opportunity / EXPLOIT·ICM |
| 멀티웨이 근거 적용 능력 | preflop.multiway_evidence_application_capacity | read_application_skill, potodds_skill, multiway_skill → 기존 [0, 1] 적용 능력 | multiway_reraise_decision / REASONING |
| 멀티웨이 call/fold 적용 | preflop.apply_multiway_call_evidence | call/fold mass, equity, required_equity, application_capacity → 새 call/fold mass | multiway_reraise_decision / JUDGMENT |

네 함수 모두 기존 계산 본문을 이동한 ACTIVE 경계다. heuristic 지식 공급과 range_read 값은 유지한다. actor/profile adapter는 기존 API를 보존한다. 새로운 압박 prior, equity 공식, skill 분포 또는 threshold는 추가하지 않았다.

멀티웨이 application capacity는 call/fold의 evidence 혼합과 기존 attack 억제 경로에 함께 소비된다. 이번에는 call/fold 혼합 본문을 분리했고, attack 억제 본문은 기존 위치에 남겼다. 따라서 call/raise 정책 전체를 한 적용 함수로 통일했다고 주장하지 않는다.

3차 문서의 관측 품질·멀티웨이·pressure 경계 추출 후보를 여기서 처리했다. 여전히 range_read 값 공급은 공유하며, persona.overpair_love 편향과 perceived_edge 자기 실력 인식, read_opponent의 line visibility, 종합 실력/프로필 생성·진단 직렬화는 별도 역할로 남는다.
