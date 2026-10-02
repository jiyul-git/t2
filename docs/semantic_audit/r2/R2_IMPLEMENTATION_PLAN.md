# D. R2_IMPLEMENTATION_PLAN — 구조 분리 / DB 근거 수정 / 보류

기준 `test` `d284a9e`. 이 문서의 어떤 항목도 아직 코드에 반영하지 않았다. 승인을 기다린다.

행동 기준점은 `R2_BEFORE_BASELINE.md` 의 봉인이다.
- 46a2070 과 d284a9e 의 production 코드는 같다.
- sim 지문: 시드 11 `e6d8b5e5…`, 시드 12 `c13a5bf4…`

## 1. 행동 보존 구조 분리 (승인 후 바로 할 수 있음, 행동 변화 0)

검증:
- semantic 추출 probe 로 `d284a9e` 대비 같은 입력 → 같은 출력 + RNG 상태를 확인한다.
- baseline sim 지문이 봉인값과 같아야 한다.
- 23개 게이트 집합이 같아야 한다.
- completeness 검사기 미소유 0 을 유지한다.

| ID | 대상 | 할 일 | 행동 |
|---|---|---|---|
| S1 | 콜오프 legacy cap | `calloff_cap` 을 "디펜스 폭에서 파생한 legacy 콜 폭"으로 이름과 문서를 명시한다. 소비 경로(P4 near-all-in, P5 낮은 숙련 fallback, P7 콜러 레인지 복원)를 함수 경계로 드러낸다. 값과 호출 순서는 그대로 | 불변 |
| S2 | 3벳/4벳 네 층 | `defend_action_likelihoods` 안에서 (a) 후보 순서, (b) 동기·증거 배수(HU exploit 블록), (c) 3벳 prior 폭, (d) `tighten_defend_widths_for_raise_level` 를 이름 있는 함수로 나눈다. (d)에는 "독립 4벳 prior 없음 = MISSING_KNOWLEDGE" 를 코드 수준에서 명시한다 | 불변 |
| S3 | 리쇼브 | 후보(`r <= rs`), legacy 폭(`reshove_range`), legacy 확률(`p_hot`)을 각각 이름 붙여 분리한다. `p_hot` 이 빈도 지식이 아니라 legacy 근사임을 명시한다 | 불변 |
| S4 | 쇼브 라벨 provenance | 관찰자 레인지 메타에 "실제 액션은 첫 진입 올인이었다"를 기록한다(`_story` 메타 필드 추가). 레인지 자체는 그대로 `'open'` 경로 | 불변(기록만) |
| S5 | 두 순서표 | `bot._pf_score` / `range_combos` 를 "레인지를 모를 때의 fallback 순서"로 명명하고 소비처 셋을 명시한다. 통합은 하지 않는다 | 불변 |

## 2. DB 근거가 있어 실제 수정이 가능한 항목 (콜오프 관련만, 변경안 — 승인 전 미적용)

근거는 `CALLOFF_PATH_AUDIT.md`(완료된 9-max push/fold DB, near 조건)와 명확한 수학(올인 콜은 equity ≥ 가격)이다.
- 새 계수를 만들지 않는다. 기존 부품만 쓴다: `calloff_layer_judgment`, `icm.required_equity`, `PS.icm_bf`, `PS.calc_noise`, `players_behind_required_equity_premium`.

| ID | 경로 | 지금 | 변경안 | 근거 | 예상 영향 | 남는 MISSING |
|---|---|---|---|---|---|---|
| C5 | P7 쇼브에 콜한 사람의 레인지 복원 | 깊은 스택 콜러를 vs-open 플랫 구간으로 복원한다(AA 0.57/6, KK 0.63/6) | 올인에 대한 콜은 레이즈 선택지가 없는 콜오프 정책으로 복원한다(`opener_allin=True, can_raise=False` 의미). 관찰자가 아는 콜 정책(아래 C1~C4 결과)을 쓴다 | 수학적 사실(올인 콜에는 3벳이 없다). DB call-vs-shove 집합 | 다음 좌석 equity 와 사이드팟 층 equity 변화 | 20bb 초과 콜 집합 |
| C1 | P6 첫 진입 쇼브 레인지 복원 | `'open'` 라벨 → RFI 슬라이스(폭 0.21~0.25) | 유효 스택 ≤ 20bb 의 첫 진입 올인은 `'shove'` 로 라벨한다. 관찰자 지식 prior 로 DB first-in jam 차트(자리·스택)를 쓴다. 20bb 초과는 현재 경로 유지 | DB 쇼브 레인지를 쓰면 콜 판단 일치율 0.77 → 0.94 | 순수 콜오프(P1)의 콜이 넓어진다(10bb BB 0.24 → 약 0.60). 뒤 좌석 판단도 바뀜 | 20bb 초과 쇼브 레인지. T2 쇼버의 실제 레이즈/쇼브 혼합과의 차이 |
| C2 | P2 커버 스택의 쇼브 대응(뒤 좌석 있음) | vs-open 디펜스 폭(쇼브 크기와 무관) | 콜/폴드는 equity(C1 레인지) ≥ 가격 + 뒤 좌석 위험으로 판단한다. 기존 공격(아이솔레이션) 질량은 그대로 둔다 | DB 콜 0.28~0.52 vs 현재 0.13~0.29(가격 무관) | 가장 큰 경로(baseline 182건 중 102건) | 아이솔레이션 빈도 |
| C3 | P4 near-all-in (`_hero_calloff`) | legacy cap, 리쇼브 0 | 콜/폴드를 equity ≥ 가격으로 판단한다. 리쇼브 선택지는 지금처럼 0 을 유지한다(새 빈도를 만들지 않음) | 같은 수학 | baseline 10건 | 리쇼브 빈도 |
| C4 | P5 계산하지 않는 사람의 fallback | 디펜스 폭 파생 cap(평균 0.199) | ≤ 20bb 는 DB call-vs-shove 차트를 "기억 차트"로 쓰고, 기억 정확도 `gto_knowledge` 만큼 흐리게 한다. 20bb 초과는 현재 cap 유지 | DB 가 바로 그 차트 지식이다 | 필드 평균 순수 콜오프의 14~36% | 20bb 초과. **인간 모델 설계 결정**(무엇을 기억하는가)이라 사용자 확인 필요 |
| C6 | legacy cap 의 bf | 객관 bf 로 직접 나눔 | cap 이 남는 경로에서는 `PS.icm_bf` 인지 bf 를 쓴다(다른 경로와 일관) | 의미 일관성 | 버블 근처 낮은 숙련 | — |

제안 순서: C5 → C1 → C2·C3 → C6 → C4.
- 하나씩 별도 커밋으로 진행한다. 각 커밋마다 아래를 보고한다.
  - DB 일치율 before/after
  - baseline sim 지문 diff 와 행동 요약
  - 23개 게이트
  - 계수 ledger
- C1·C4 는 GTO DB 파일을 production 이 읽어야 한다. DB 는 `chatgpt/gto-reference-20260928` 에만 있다.
  - `data/gto_db/preflop_9max_pushfold_v1.jsonl` 과 라이선스 파일(CC BY 4.0, 저작자 표기)을 `test` 로 가져올지는 **사용자 결정**이다. 브랜치 병합이나 승격은 이번 범위가 아니다.

## 3. MISSING_KNOWLEDGE — 보류 (수치 변경 금지)

| 항목 | 현재 값 | 보류 이유 |
|---|---|---|
| 9-max 비올인 vs-open 디펜스 총량·좌석 배수·BvB | `DEF_A/B`, `DEF_SEAT`, `DEF_VS_SB`, `_MDF` | 완료된 9-max spot 없음. 출처 미상 |
| 3벳 빈도 | `TB_SHARE 0.18` (9-max), `_MTT8_ANTE_TB_SHARE` (8-max) | 정답으로 승격하지 않음 |
| vs-3bet | 위치를 바꾼 vs-open prior × `LEVEL_TIGHTEN[3]` | 독립 지식 없음 |
| 4벳 / 5벳 / cold 4벳 | `LEVEL_TIGHTEN`, `reads.PRIOR['pf_4bet']` 0.04 | 독립 지식 없음. S2 에서 코드에 명시만 한다 |
| 리쇼브 빈도 | `reshove_range`, `p_hot` | 비올인 오픈 대상 DB spot 없음. S3 에서 구조만 분리 |
| 짧은 스택 디펜스 분할 | `tot×0.62, tp×1.6` | 자료 없음 |
| iso 폭, 이론형 림프, polar 3벳 레인지 모델 | 현재 식 | 자료 없음 |
| 오픈 형태의 레이즈/쇼브 혼합 | `open_form` | DB 는 push/fold 전용(레이즈 선택지 없음) |
| 두 순서표 통합 | — | 행동 변화(fallback 레인지 약 6%) → 이번 단계 아님 |

코드 내부 결함 3개(짧은 스택 이중 적용, `_saturate` 증폭, 3벳 실현 손실)도 이번 단계에서는 수정하지 않는다. 9-max 디펜스 경로와 얽혀 있어서, 고치면 출처 미상 prior 의 영향이 커지거나 작아진다.

## 4. 이번 단계의 범위 밖

R1b(플랍 레이즈 레인지), OOP 체크레이즈 후속, tilt/exploit 실험, 브랜치 병합이나 승격.
