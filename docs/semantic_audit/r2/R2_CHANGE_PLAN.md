# D. R2_CHANGE_PLAN — 변경 계획 (미적용, 승인 대기)

이 문서의 어떤 항목도 아직 코드에 반영하지 않았다. 계수, 표, 문턱, 액션 모두 그대로다.
R2 행동 변경은 `R2_BEFORE_BASELINE.md` 의 봉인 커밋(`46a2070`) 위에 **semantic cleanup 과 분리된 별도 커밋**으로 시작한다.

근거 문서:
- A `PCT_CONSUMER_AUDIT.md`
- B `9MAX_DEFEND_BASELINE_TABLE.md`
- C `9MAX_DEFEND_REFERENCE_COMPARISON.md`

## 0. 원인 분리 (서로 섞지 않는다)

| 원인 ID | 질문 | 범주 | 성격 |
|---|---|---|---|
| R2-A1 | 공격 집합(3벳, 4벳, 올인, 리쇼브)을 하나의 순서표의 상위 슬라이스로 정한다 | R2-A | 잘못된 양 (순서표 교체로는 고쳐지지 않음: A 1절) |
| R2-A2 | 가격·equity 질문(콜오프 잔여 경로, 오픈 형태, 리쇼브)을 백분위 문턱으로 답한다 | R2-A | 잘못된 양 |
| R2-A3 | 프리플랍 순서표가 둘이다(`PCT`, `bot._pf_score`) | R2-A | 중복 |
| R2-B1 | 9-max vs-open 디펜스 prior(legacy 선형식, DEF_SEAT, TB_SHARE, DEF_VS_SB) | R2-B | 근거 없는 prior. 9-max 자료 필요 |
| R2-B2 | 보정 prior 위에 짧은 스택 분할을 다시 적용한다(C 3.1) | R2-B 내부 | 이중 적용 (E: 코드 의미 버그) |
| R2-B3 | `_saturate` 가 좁은 폭을 1.45배까지 넓힌다(C 3.2) | R2-B 내부 | prior 변형 (E) |
| R2-B4 | prior 폭(tp) → 실제 3벳 빈도가 약 절반으로 줄어든다(C 3.3) | R2-B 내부 | prior→정책 변환 미교정 (E) |
| R2-B5 | 오픈 사이즈 MDF 보정을 cold 디펜더에도 곱한다(C 3.7) | R2-B | 검증 필요 |
| R2-K1 | vs-3bet prior 없음: 위치를 바꾼 vs-open prior × LEVEL_TIGHTEN | 별도 지식 | 지식 없음 |
| R2-K2 | 4벳·5벳·cold 4벳 prior 없음 | 별도 지식 | 지식 없음 |
| R2-K3 | 리쇼브 폭이 휴리스틱(`reshove_range`, `OPENER_MULT`)이다 | 별도 지식 | 지식 없음 + L-RA12 과적재 |

## 1. 순서(ordering)로 남길 것 — 변경 없음

- RFI 진입, iso 진입 순서, vs-open 계속 집합, 프리미엄 판정, open 레인지 구성, 블로커 최상단 정의, 머니점프 기록(A #1, #4, #5, #8, #14 open, #16, #19).
- `pf_rank.json` 은 **호환용 순서로 동결**한다. 값을 패치하거나 HU 순위로 통째로 바꾸지 않는다(사용자 규칙과 A 1절 측정이 같은 결론).
  - 리스트 레인지의 원소 순서와 tie-break 이 이 순서를 따른다(A #22). 표를 건드리면 의도하지 않은 행동 변화가 생긴다. 그것도 동결 이유다.

## 2. equity / EV / 가격으로 분리할 것

| 대상 | 지금 | 바꿀 질문 | 이미 있는 부품 | 선행 조건 |
|---|---|---|---|---|
| A #12 남은 percentile 콜오프 (`_hero_calloff`: 상대 비올인, 오픈 ≥ 스택×0.92) | `r <= cap` | 상대 레인지 대비 equity ≥ ICM 필요 equity | `calloff_layer_judgment`(순수 콜오프에서 이미 사용) | 상대 레인지 확보 경로 |
| A #2 오픈 형태(레이즈 vs 쇼브) | pf_rank 대역 | 쇼브 EV(폴드 에쿼티 + 콜당했을 때 equity) vs 레이즈 EV | 없음(새 계산). 또는 숏스택 RFI 차트의 raise/allin 분할 | 9-max 숏스택 RFI 자료 또는 EV 계산 설계 |
| A #9 리쇼브 | pf_rank × 휴리스틱 폭 | 오프너 레인지의 콜 확률·equity와 가격 | multiway 판단의 equity/가격 부품 | R2-K3 지식 |
| A #18 쇼다운 관찰 | 프리플랍 분위 | 쇼다운 시점 강도와 라인 | — | exploit 층 작업. baseline 고정 기간에는 보류(기록만) |

전역적으로 pf_rank 를 equity 로 바꾸지 않는다. 바꾸는 것은 **질문이 가격/EV 인 소비처만**이다.

## 3. 새 GTO prior 가 필요한 것 (R2-B1)

**필요한 자료:** 9-max, 1bb BBA, T2 실제 오픈 사이즈(≤40bb 2.15x, SB 2.75x, 깊으면 2.2~2.4x).
- 스택: 20/25/30/40bb 우선, 15/60/100bb 보조.
- spot: (opener, defender) 쌍별 call / 3bet(+allin 분할) / fold.

**자료 출처:** 사용자 결정이 필요하다.
- (a) 사용자 측 solver 또는 차트 서비스에서 9-max 수치를 내보내 저장소에 넣는다.
- (b) 공개 9-max 수치 자료를 찾는다. 이번 감사에서는 확보하지 못했다.
- (c) 프리플랍 solver 를 직접 돌린다. 비용이 크다.

8-max 자료를 위치 이름으로 옮겨 쓰는 것은 하지 않는다.

**구조 제안** (형태 근거는 C 3.4~3.6):
- 디펜스 총량은 (opener, defender, stack) 표 + 오픈 사이즈 보정으로 둔다. 선형식 `A + B·rfi` 는 BB 에서 기울기가 작아 표가 더 정직하다.
- 3벳 비중은 (defender, opener, stack) 별로 둔다. 전역 `TB_SHARE` 를 없앤다. BB 의 0.18 은 자료 범위 안에 있으므로 BB 표의 초기값 후보로만 남긴다.
- `DEF_SEAT` 의 곱셈 구조는 자료가 지지한다(오프너와 무관한 비율). 다만 값이 스택에 따라 변하므로 스택 축을 추가한다.
- 오픈 사이즈 보정(R2-B5)은 자료로 검증될 때까지 지금 식을 유지하고 범위만 기록한다.

**8-max 보정 경로**(`_MTT8_ANTE_*`)는 30bb 이상에서 총량이 자료와 ±0.08 안에 든다. 다만 R2-B2·B4 를 고친 뒤 다시 측정해야 한다.

## 4. 코드 내부 결함 — 자료 없이도 고칠 수 있으나 행동이 바뀐다 (R2-B2·B3·B4)

| ID | 제안 | 예상 영향 (측정은 B 표 L0/L1/L2) | 주의 |
|---|---|---|---|
| R2-B2 | 보정 prior 경로에서는 짧은 스택 분할(`tot×0.62, tp×1.6`)을 적용하지 않는다(그 prior 가 이미 스택별 값) | 8-max 15~25bb BB 디펜스 0.50~0.55 → L0(0.79~0.87) 근처 | 9-max legacy 경로는 이 분할에 의존하는 모양이라 R2-B1 전에는 그대로 둔다 |
| R2-B3 | `_saturate` 를 상한 보호(clip)로만 쓰고, 좁은 폭은 증폭하지 않는다 | 9-max cold 디펜스 폭 약간 감소(30bb BTN vs UTG 0.23 → 0.19) | R2-B1 과 함께 하는 편이 낫다. 단독으로 고치면 9-max 값이 근거 없는 L0 로 돌아갈 뿐이다 |
| R2-B4 | prior 를 "빈도"로 쓰는 경로(보정 경로, 향후 9-max 표)에서는 정책 혼합이 그 빈도를 실제로 재현하도록 변환을 교정한다(예: 실현 빈도가 tp 와 같아지게 w_raise 를 정규화) | 실제 3벳 빈도가 L0 3벳 쪽으로 상승(30bb BB vs BTN 8-max 0.09 → ~0.17) | 새 계수를 만들지 않는다. 기존 정의(prior = 빈도)에 맞춘다. 순서 집합 모양 문제(R2-A1)는 별개로 남는다 |

이 셋은 사용자 분류상 E(코드 의미 버그)에 해당한다. 행동이 바뀌므로 승인 후 각각 별도 커밋으로 진행한다. 커밋마다 23개 게이트, baseline sim(시드 11·12), 계수 ledger 확인을 거친다.

## 5. 3벳 / 4벳 / 리쇼브를 별도 지식으로 분리 (R2-K1~K3)

- **vs-3bet (R2-K1)**
  - 새 지식 항목 `opener_vs_3bet_prior(opener, three_bettor, stack, 3bet_size)` 를 만든다.
  - 출력: 오프너 자신의 오픈 레인지 조건부 call / 4bet / fold.
  - `defend_decision` 의 위치 swap 재사용을 멈추는 것은 이 지식이 생긴 뒤에 한다.
  - 8-max 자료에 30/100bb 노드가 있다(형태 확인용). 9-max 값은 R2-B1 과 같은 출처가 필요하다.
- **4벳·5벳·cold 4벳 (R2-K2)**
  - `LEVEL_TIGHTEN` 은 "3벳 폭을 줄여 쓰는 것"이다. 이것을 4벳 지식으로 간주하지 않는다.
  - cold 4벳은 이미 equity/가격 증거층이 있다(multiway_reraise). 그 위의 기본 확률만 독립 prior 로 바꾼다.
- **리쇼브 (R2-K3)**
  - 12~26bb 리쇼브 폭을 solver 리쇼브 차트나 EV 계산으로 대체한다.
  - `OPENER_MULT` 의 두 번째 용도(open_form 깊이, L-RA12)도 같은 지식으로 정리한다.
- **공격 집합 모양 (R2-A1)**
  - 3벳/4벳/올인 집합은 "상위 k%" 가 아니라 핸드 클래스별 액션 빈도로 표현해야 재현된다(A 1절: 상위 슬라이스 agreement 0.41~0.61).
  - R2-B1/K1~K3 의 자료가 핸드 클래스별 빈도를 주면 그대로 쓰고, 없으면 이 항목은 NEEDS_SOLVER_DATA 로 남긴다.
- **중복 순서 (R2-A3)**
  - `bot.range_combos` fallback 이 `PCT` 순서를 쓰도록 통합한다.
  - fallback 전용 경로라도 행동이 바뀌므로 별도 커밋으로 한다.

## 6. 제안 순서 (승인 후)

1. R2-B2: 이중 적용 제거. 8-max 보정 경로만 해당하고 9-max 는 영향 없음.
2. R2-B4: prior→빈도 변환 교정. 보정 경로만 해당.
3. 9-max 자료 확보 후 R2-B1 + R2-B3 를 함께 진행. 표 도입.
4. R2-K1 vs-3bet prior. 자료가 필요하다.
5. R2-A2 / R2-K3 가격·EV 분리(콜오프 잔여, 리쇼브, 오픈 형태).
6. R2-A3 중복 순서 정리.

9-max production(standard/main/lowbuyin)에서 바로 효과가 있는 것은 3·4·5 다. 1·2 는 8-max 포맷(deep/turbo/hyper/highroller 등)에 영향이 있다.

## 7. 계수 ledger 확인

- 이번 단계에서 바뀐 계수는 없다.
- 위 제안이 건드릴 대상:
  - `adjust_defend_widths_for_short_stack`(0.62/1.6)
  - `_saturate`(0.80/0.55)
  - `w_raise` 형상(0.35/0.65)
  - `TB_SHARE`, `DEF_*`
  - `LEVEL_TIGHTEN`
  - `reshove_range`, `OPENER_MULT`
- 과거 반대 방향 조정 기록:
  - `adjust_defend_widths_for_callers` 2026-09-04 조정은 이번 대상이 아니다.
  - `defend_action_likelihoods` 의 `w_cont` 폭(tot×0.15, audit9 HAND 17)은 계속 집합의 경계 폭이다. R2-B4 는 `w_raise` 쪽이라 같은 파라미터가 아니다.
- R2-B4 를 진행할 때 `w_cont` 를 다시 넓히는 방향으로 손대지 않는다(반대 방향 재조정 금지 규칙).
