# R2-B. 9-max defend prior — 현재 값의 출처와 검증 상태

이번 단계의 범위: 현재 값이 **어디서 왔고, 무엇으로 검증됐는가**만 감사한다.

규칙(사용자 지시, 2026-10-02):
- 수치는 바꾸지 않는다.
- 미완성인 자체 GTO solver(`chatgpt/mini-cfr-solver-20260928`, gto-reference 브랜치의 vendored GTOpen 경로)는 기준으로 쓰지 않는다.
- 이미 계산이 끝난 GTO DB spot이나 신뢰할 수 있는 공개 자료가 있는 경우에만 비교한다.
- 그런 자료가 없는 spot은 **MISSING_KNOWLEDGE** 로 남긴다.

## 0. 첫 보고 정정

- 첫 보고(커밋 `574dff8`)에서 "저장소에 9-max GTO DB 가 없다"고 썼다. **틀렸다.**
  - 그때는 `test` 의 추적 파일만 검색했다.
  - 원격 브랜치 `chatgpt/gto-reference-20260928`(커밋 `1d19561a`)에 `data/gto_db/` 9-max 지식층이 있다.
- 첫 보고의 `NEEDS_SOLVER_DATA` 판정과 "solver 를 직접 돌린다" 선택지는 이번 규칙에 따라 철회한다.
  - 자료가 없는 spot 은 `MISSING_KNOWLEDGE` 로 바꾼다.
- 8-max 차트로 9-max 값을 판정한 부분은 9-max 판정에서 뺀다(C 문서 0절 참고).
  - 8-max 차트는 8-max 보정값 자체를 검증할 때만 쓴다(그 보정값의 출처이기 때문).

## 1. 쓸 수 있는 9-max 자료 (계산 완료분만)

| 자료 | 위치 | 내용 | 조건 일치 | 신뢰도 | 이번 사용 |
|---|---|---|---|---|---|
| HoldemMath 9-max push/fold | `chatgpt/gto-reference-20260928:data/gto_db/preflop_9max_pushfold_v1.jsonl` (커밋 `0c9f4c34`, 원 저장소 `Julian-cloud-max/holdemmath-data@7c72b12`, CC BY 4.0) | 616 spot, 169 클래스. 첫 진입 쇼브 + **쇼브 대면 콜**, 4~20bb, 노안테 / 0.1bb×9 안테 | **near**: 총 데드머니 0.9bb vs T2 1bb BBA. ICM·림프 없음. 다인원은 single-caller 근사 | 중 (라이선스·모델·sha256 기록됨, DB 자체 판정 `near_t2_bba`) | 쇼브 대면 콜 폭 비교(3절) |
| PreflopRanges 9-max MTT RFI 집계 | 같은 브랜치 `data/gto_db/external_rfi_crosscheck_9max.json` (커밋 `8edb3d69`) | 20/25/30/40bb, 포지션별 RFI 합계와 대표 오픈 사이즈. 핸드별 값 없음 | 9-max MTT. 안테 모델은 차트별(BBA 여부 미기재) | 중하 (공개 뷰어 수동 집계, 방법론 비공개) | 디펜스 식의 입력인 `gto.rfi` 검증(4절) |
| GTO DB 의 20/25/30/40bb raise-tree 디펜스 | `SOLVE_PLAN_9MAX.md` | **계획만 있고 계산된 행이 없다** | — | — | 없음 → MISSING_KNOWLEDGE |
| 자체 solver 출력 | mini-cfr / GTOpen | 미완성 | — | 사용 금지 | 없음 |
| `poker-gto-trainer` 9-player JSON | (DB 에서 거부됨) | `solver: fallback, accuracy 0.0` | — | 거부 | 없음 |
| `gto-poker-trainer` `nine.ts` | 외부 | 6-max 를 손으로 좁힌 파생 | — | 낮음 | 없음 |

## 2. 현재 값별 출처와 검증 상태

| 값 (gto.py / preflop.py) | 현재 값 | 쓰이는 곳 | 출처 기록 | 검증 상태 | 판정 |
|---|---|---|---|---|---|
| `DEF_A, DEF_B` | 0.22, 0.68 | 9-max 모든 vs-open 디펜스 총량(legacy) | 주석: "공개 자료(9맥스, 3x 오픈 대면 BB)" 4점. **링크·자료명·안테 조건 없음**. 3x 오픈은 T2(2.15x, 공개 9-max 차트 2.0x)와 다름 | 완료된 9-max 디펜스 spot 없음 → 비교 불가 | **UNSUPPORTED_PRIOR** (출처 미상) / spot 값 **MISSING_KNOWLEDGE** |
| `DEF_VS_SB` | 0.60 | 9-max BB vs SB 오픈 | 주석 설명만("블라인드 대 블라인드라") | 비교 자료 없음 | **UNSUPPORTED_PRIOR** / **MISSING_KNOWLEDGE** |
| `DEF_SEAT` | BB 1.00, SB 0.62, BTN 0.46, CO 0.34, HJ 0.26, LJ 0.21, UTG+2 0.18, UTG+1 0.16, UTG 0.14 | 9-max 디펜더 배수 | 출처 기록 없음 | 비교 자료 없음 | **UNSUPPORTED_PRIOR** / **MISSING_KNOWLEDGE** |
| `TB_SHARE` | 0.18 | 9-max 3벳 폭 = 디펜스 × 0.18 | 주석: "기존 no-ante/비보정 경로의 기준". 출처 기록 없음 | 비교 자료 없음 | **UNSUPPORTED_PRIOR** / **MISSING_KNOWLEDGE** |
| `_MDF` 표, `mdf(open)/mdf(3)` | (2.0 .72)(2.5 .62)(3.0 .56)(4.0 .48)(6.0 .38) | 오픈 사이즈 보정(8·9-max 공통) | 주석: "MDF — 오픈 사이즈가 정하는 하한". 도출 근거·출처 미기재 | 오픈 사이즈별 9-max 디펜스 자료 없음 | **UNSUPPORTED_PRIOR** / **MISSING_KNOWLEDGE** |
| `_MTT8_ANTE_DEF_A/B/VS_SB/SEAT/TB_SHARE` | 0.5815 / 0.2949 / 0.7236 / {BB 1, BTN .298, CO .229, SB .350} / {BB .196, BTN .499, CO .549, SB .651} | **8-max + ante** 의 CO/BTN/SB/BB 디펜스만. 9-max 미사용 | `ce5c118f`. matthiola 8-max MTT vs-open 차트에 적합. 2.5bb 오픈 가정(자료에 사이즈 없음). gto-reference `defend_width_audit_20260928`: 60 차트, 디펜스 MAE 0.050, 3벳 MAE 0.033. 코드 주석: "calibration 실험 후보, 전역 일반화하지 않는다" | 출처 자료 대비 L0 는 ±0.08 안. 다만 실제 행동(L2)은 코드 내부 결함 3개 때문에 어긋남(C 3.1·3.3) | 8-max 한정 **PRIOR_SUPPORTED**(출처 신뢰도 중하) / 9-max 에는 적용되지 않음 |
| `gto.rfi` 9-max (`RFI_BY_BEHIND`, `_DEPTH_*`) | B 표 입력 | legacy 디펜스 식이 오프너 폭으로 씀 | 8-max matthiola 로 교정, 9-max UTG(뒤 8명) 0.15 는 "공개표 밖이라 유지" | 공개 9-max RFI 집계와 비교(4절): UTG~CO −0.024~+0.002, BTN −0.059~+0.001 | 비블라인드 **APPROXIMATION_ACCEPTABLE**(RFI 지식으로서. 디펜스 식이 정확하다는 뜻은 아님) |
| `CALLOFF_TIGHTEN` × 2.6, `calloff_cap` | {2: .55, 3: .22, 4: .11, 5: .07} | 디펜스 총량 `tot` 에서 쇼브 대면 콜 폭을 만든다 | 출처 기록 없음 | **9-max DB 쇼브 대면 콜 144 spot 과 비교 가능**(3절) | **WRONG_QUANTITY**(완료 spot 대비 체계적으로 좁음. 아래) |
| `adjust_defend_widths_for_short_stack` | `base_feel<0.20`: tp×1.6, tot×0.62 | 짧은 스택 분할 | 출처 기록 없음 | 비교 자료 없음(올인 아닌 20~26bb 디펜스) | 9-max **MISSING_KNOWLEDGE**. 8-max 보정 경로에서는 이중 적용(C 3.1, 코드 의미 결함) |
| `_saturate` | 상한 0.80, scale 0.55 | legacy 경로 포화 | "100% 초과 방지" | — | 코드 의미 결함(C 3.2. 좁은 폭을 최대 1.45배 넓힌다) |
| `LEVEL_TIGHTEN` | {2: 1, 3: .34, 4: .16, 5: .10} | vs-3bet / 4벳 이상 | 출처 기록 없음 | 9-max vs-3bet·4벳 spot 없음 | **MISSING_KNOWLEDGE** (독립 prior 아님) |

## 3. 쇼브 대면 콜 — 완료된 9-max spot 비교

생성: `python tools/r2_gto_db_compare.py origin/chatgpt/gto-reference-20260928 docs/semantic_audit/r2/gto_db_9max_comparison.json`

조건:
- HoldemMath 0.1bb×9 안테 변형, 10/12/15/20bb, 쇼버 × 콜러 36쌍씩, 총 144 spot.
- 코드는 `preflop.calloff_cap`(max-skill, bf 1.0, 콜러 0, 9-max, ante=True, 쇼브 크기 = 스택). 코드는 `pf_rank <= cap` 이면 콜한다. 즉 cap 이 그대로 콜 폭이다.

| 스택 | DB 평균 콜 폭 | 코드 평균 cap | 평균 \|차이\| | DB 콜 집합 중 코드 집합에 든 비율 |
|---|---|---|---|---|
| 10bb | 0.475 | 0.151 | 0.326 | 0.30 |
| 12bb | 0.425 | 0.149 | 0.281 | 0.33 |
| 15bb | 0.368 | 0.145 | 0.230 | 0.37 |
| 20bb | 0.302 | 0.148 | 0.165 | 0.44 |

대표 spot:

| 스택 | 쇼버 → 콜러 | DB 콜 | 코드 cap |
|---|---|---|---|
| 10bb | BTN → BB | 0.569 | 0.327 |
| 10bb | UTG → BB | 0.596 | 0.233 |
| 10bb | SB → BB | 0.330 | **0.371** (코드가 더 넓음) |
| 20bb | BTN → BB | 0.361 | 0.322 |
| 20bb | UTG → SB | 0.318 | 0.151 |
| 20bb | SB → BB | 0.161 | **0.363** (코드가 더 넓음) |

해석:
- 디펜스 prior 에서 파생된 콜오프 폭은 거의 모든 위치·스택에서 완료 spot 보다 **좁다**.
- 스택이 줄어도 거의 변하지 않는다(0.145~0.151). DB 는 짧을수록 넓어진다(0.30 → 0.48).
- SB 쇼브 대면 BB 는 반대로 넓다. legacy `DEF_VS_SB` 가 들어가기 때문이다.

조건 차이(near):
- 안테 0.9bb(전원) vs T2 1bb(BB만)
- ICM 없음(코드도 bf 1.0 으로 비교)
- 다인원 single-caller 근사

그래도 차이의 크기(평균 0.17~0.33)와 스택 경향의 방향이 이 조건 차이로 생기는 수준을 넘는다.

현재 행동에 미치는 범위:
- max-skill 의 순수 콜오프(상대 올인 + 레이즈 불가)는 `calloff_layer_judgment`(equity vs 가격)가 대신 판단한다. pf_defend 게이트 값이 1.80 이라 항상 통과한다.
- 그래서 이 cap 이 max-skill 행동을 직접 정하는 곳은 아래 둘이다.
  - (a) `_hero_calloff` 경로(상대 비올인, 오픈 ≥ 내 스택×0.92)
  - (b) 관찰자 레인지 모델 `_defend_likelihood_range` 에서 "쇼브에 콜한 사람"의 레인지
- 게이트가 1 미만인 낮은 숙련 프로필은 이 cap 을 일부 직접 쓴다.

## 4. 디펜스 식의 입력 — 9-max RFI 교차검증

공개 9-max MTT RFI 집계와 비교한 결과, 비블라인드 28칸(7포지션 × 4스택) 중 25칸이 ±0.024 안이다. 나머지 3칸은 모두 BTN 이다(20bb −0.059, 25bb −0.032, 40bb −0.032). 코드가 공개 집계보다 약간 좁다.

SB 는 비교하지 않는다:
- 공개값 0.86~0.90 은 림프를 포함한 진입률로 보인다.
- 코드 `RFI_SB` 는 "레이즈 폭"이라 질문이 다르다.

대표 오픈 사이즈도 다르다(조건 차이로 기록):
- 공개 9-max 차트: EP~BTN 2.0bb, SB 3~4bb
- T2: 2.15bb, SB 2.75bb

이것은 디펜스 식의 **입력**(오프너 폭)이 대체로 맞다는 뜻이다. 디펜스 식 자체(`DEF_A + DEF_B·rfi` × `DEF_SEAT` × `TB_SHARE`)는 비교할 9-max 자료가 없어 검증되지 않았다.

## 5. MISSING_KNOWLEDGE 목록 (9-max, 완료 spot 없음)

- 올인 아닌 오픈에 대한 디펜스(call / 3bet / fold): 모든 오프너·디펜더·스택(20/25/30/40bb 포함)
- BB vs SB(BvB) 레이즈 / 림프
- 오프너 vs 3벳(계속 / 4벳 / 폴드)
- 4벳 / 5벳 / cold 4벳 / 스퀴즈
- 올인 아닌 오픈에 대한 리쇼브(12~26bb)
- 오픈 사이즈별 디펜스 변화(MDF 보정 검증)
- 짧은 스택(20~26bb) 비올인 디펜스의 콜/3벳 분할

이 목록은 GTO DB 의 `PRIORITY_9MAX_MTT.md` Tier 1 계획과 같다. 채우는 방법(공개 자료 확보 또는 검증된 solver 출력)은 이번 단계에서 정하지 않는다. 자체 solver 는 완성·검증 전까지 기준으로 쓰지 않는다.
