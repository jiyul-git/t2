# CONCEPT SYSTEM — glossary, wiring, taxonomy, cleanup

## 2026-10-02 코드 재감사 동기화

37개 선언 capability는 전체 poker semantic inventory가 아니다. 227행 concept/function registry를 함께 사용한다. flop thin_value는 range_merge를 사용한다. trap은 latent.study를 runtime에서 소비하고 type label은 sizing_signature에 영향을 준다. 이 두 설계 불일치는 행동 보존 작업에서 교정하지 않았다.

현재 근거: [전체 구조](docs/semantic_audit/CURRENT_ARCHITECTURE_AUDIT.md), [개념→함수](docs/semantic_audit/CONCEPT_FUNCTION_REGISTRY.md), [문서 차이](docs/semantic_audit/DOCUMENT_DRIFT.md), [리팩터링·검증](docs/semantic_audit/REFACTOR_AND_VERIFICATION.md). 아래 과거 실험/commit별 증거는 그 시점 기록이며 현재 배포 인증이 아니다.

이 문서는 기존 변수 사전, 배선 대장, 전수조사 장부, concept wiring/prior audit의 현재 결론을 통합한다.

## 1. 층 구분

### Latent
설계상 플레이어 생성 시 상관 구조를 만드는 잠재요인이다. 실제 `plan.trap_judgment`의 study 직접 소비는 이 원칙의 미해결 위반이다.

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

## 3. GTO-study knowledge and reasoning must remain separate

GTO/solver 지식과 실제 테이블 reasoning은 같은 concept으로 뭉치지 않는다.

구분:
- **GTO-study knowledge / memory**: chart, solver 결과, 반복 학습으로 획득한 prior의 정확도·범위·회상 능력.
- **reasoning skill**: 현재 board/range/story/stack/pot/read를 이용해 처음 보는 상황을 계산·추론하는 능력.
- **adaptation/exploit skill**: 상대와 tournament context를 보고 prior에서 의도적으로 이탈하는 능력.

한 축이 높다고 다른 축도 자동으로 높다고 가정하지 않는다.
예:
- solver chart는 잘 외우지만 새로운 postflop spot 추론은 약한 player
- solver 공부는 적지만 live read와 exploit reasoning이 뛰어난 player
- 두 능력이 모두 높은 elite regular

향후 구현에서 필요한 first-class 상태:
1. 어떤 GTO spot/family를 학습했는가
2. 학습된 prior의 정확도와 confidence
3. exact-condition mismatch 시 memory confidence decay
4. reasoning이 prior를 얼마나 수정할 수 있는가
5. exploit/read가 baseline에서 얼마나 의도적으로 이탈시키는가
6. bounded memory/calculation 때문에 생기는 인간적 근사와 오류

GTO calibration은 이 knowledge/prior layer의 기준점을 교정하는 작업이며,
reasoning/persona를 solver 결과로 대체하는 작업이 아니다.

## 4. Current wiring status

Concept wiring audit 최종 요약:
- declared strategic concepts: 37
- core runtime dead concept: 0
- low reference count만으로 dead 판정하지 않음
- money_jump: partial/live+shadow architecture
- style-belief branch: 존재하지만 현재 production 의사결정에는 미배선
- archetype compatibility layer: legacy fallback로 유지
- concept prior/loading/spread: 전역 calibration 완료 상태가 아니라 provisional

## 5. Current taxonomy barrier

Prior sensitivity audit 이후 **street granularity**가 calibration blocker로 남아 있다.

확인된 대표 사례:
- flop thin-value fallback은 `range_merge`를 사용한다. 독립 flop thin-value ability는 없으며 공유 의미가 남는다.

진행 순서:
1. street/motive별 의미가 다른 concept을 식별.
2. missing motive -> execution wire 수정.
3. 필요하면 split/add하되 backward-compatible migration.
4. targeted counterfactual + frozen regression.
5. realized-prior audit 재생성.
6. 그 뒤에만 loading/spread calibration.

taxonomy가 안정되기 전에는 전역 prior 수치 튜닝을 확정하지 않는다.

## 6. Important semantic rules

- `nut_advantage`는 **range vs range strong-region occupancy**이지 Hero 현재 핸드 강도가 아니다.
- ICM/BF와 money_jump는 같은 개념이 아니다.
- blockbet과 donk는 known aggressor semantics가 필요한 별도 motive/execution 의미다.
- observation stat은 action class를 섞지 않는다: fold-to-bet, fold-to-raise, opener-4bet, caller-backraise 등은 분리.
- true persona는 opponent range/read reconstruction에 직접 누출되면 안 된다.

## 7. Prior/population audit

Realized concept distribution은 nominal base/spread와 같지 않다.
다음이 분포를 재형성한다:
- latent loading
- 0/10 clamp
- overall-skill rejection filter

따라서 “base를 x 올리면 median도 x 오른다”를 가정하지 않는다.

Local sensitivity audit는 mechanics map으로 받아들였지만, 새 target median/width 자체를 선택한 것은 아니다.
특히 clamp-sensitive concept은 spread 증가가 폭보다 saturation을 늘릴 수 있다.

## 8. Cleanup ledger — current summary

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

## 9. Open concept-level work

- street concept granularity
- P7 cold defense concepts/observations
- F7-B2 opponent aggregation semantics
- F7-C emotion consumer boundary
- F7-D execution-form/sizing boundary
- W5 posterior update에서 read/persona attribution

## 10. Historical sources

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

## 11. Human Model v2 — GTO learned prior ↔ human reasoning audit (2026-09-28)

Branch `tmp/claude-human-model-v2-20260928` (from test `a148d95`). Shadow/opt-in only.
Verifier: `tools/verify_human_model_v2.py`. Paired attribution: `tools/hm2_paired_cf.py`.
Results: `data/human_model_v2/*.json`.

### 11-1. Audit — what already exists

| 기능 | 현재 존재 | 파일/함수 | 판정 | 비고 |
|---|---|---|---|---|
| GTO knowledge | 암묵적 | `persona.open_pct` acc(`pf_range`), `preflop.defend_thresholds` acc(`pf_defend`), `preflop.limp_p` acc | 부분 | 같은 식 `0.10+0.80·min(1,sk/8)` 이 3곳에 복제. 한 숫자가 '차트 기억 정확도'와 '기질 이탈 상한 (1−acc)'을 겸한다 |
| GTO recall | 부분 | 위 acc | 부분 | coverage/recall 구분 없음. family 는 rfi·defend 둘 |
| interpolation / condition mismatch | 없음 | `gto.rfi`/`defend_pct` 가 조건을 외삽하지만 player 별 신뢰도는 조건과 무관 | 없음 → **11-3 추가** | 8max-ante-40bb 와 9max-noante-300bb 에서 같은 acc |
| reasoning noise | 있음 | `persona.calc_noise` (outs plan.py:561·2631, spr :588, potodds :1009, preflop.py:984), `size_read`, `icm_bf`, board_texture 스케일 plan.py:559, `perceived_rel` | 구조 충분 / 보정 의심 | perceived = true × N(bias, σ(skill)). **bias 가 모든 양에 같은 방향(+)** — outs 는 과대(낙관), pot-odds need 도 과대(=과폴드). 초보의 pot-odds 오차 방향은 관측으로 정해야 한다. `error_rate` 는 소비처 없음(dead) |
| uncertainty / confidence | 부분 | `reads.estimate` confidence=min(1,n·skill/25), `_shrink`, `est_uncertainty`, style prior spread | 부분 | 상대 모델 불확실성은 있다. 자기 spot/hand 판단의 불확실성 표현은 없다 |
| exploit restraint | 있음 | `reads._shrink` eff_n=n·skill·overconf (overconf=1.8−0.09·consistency), `read_opponent` data=conf·min(1,n/12)·adaptability, see_* 게이트 | 충분 | D/E PASS. **중복**: `exploit_weight`(trap_judgment plan.py:489 만) 와 `read_opponent['w']` 가 다른 공식 |
| persona uncertainty scaling | 부분 | 이탈 = 역치 이동 → logistic 이라 효과 ∝ p(1−p) (구조적으로 경계 집중) | 부분 | 크기가 폭 곱셈 (1−acc)·dir·0.95 → tot 0.95 포화. 중립 prior 자체가 pure-fold 순서 위반(A2) |
| line planning | 있음 | `make_plan` v3/v2/pcz, `target_commit`, `spread_curve`, `stackoff_plan` | 충분 | 강한 손은 플랍에서 commit·스트리트별 사이즈를 정한다. aware=sk('spr') 로 습관과 섞인다 |
| replan | 있음 | `update_plan` → `revise_plan`(board_changed) / `refresh` 강등·승격 사다리(read 보정) / `river_fix` / `decide_response` | 충분 | known issue E(made 기반 승격) 유지 |
| opponent memory | 부분 | `Book` 누적, memory cap=6·att+4·adp, `_shrink` | 부분 | recency/forgetting 없음. 필요성은 미입증 |
| cognitive load | 없음 | calc_noise σ 가 인원·SPR·사이즈와 무관. `multiway` 는 문턱 조정, `size_read` 는 2팟 초과 사이즈만 | 없음 | 보류 |
| equity realization | 부분 | implied odds plan.py:1347-1354, players-behind need 가산 plan.py:~1018 | 부분 | position/initiative 실현율 없음 |
| habit | 있음 | `aware×theory + (1−aware)×habit` 패턴: target_commit habit, spread_curve 균등, bluff_mode 'habit', limp_p habit, consistency→오픈 사이즈 | 충분(부분) | — |
| metagame / self-image | 없음 | Book 에 '남이 본 나' 통계는 있으나 자기 소비처 없음 | 없음 | 보류 |

Latent 측정 (q=0.78, 5,000명):
- corr(pf_range, reasoning 평균[potodds·spr·range_read·blocker]) = **0.536** (study 공유).
- 극단 비대각(knowledge 상위20 & reasoning 하위20) **0.60%**, 반대 0.62%.
- F·G 는 표현 가능(존재)하지만 드물다. 드문 것이 틀렸는지는 모집단 관측 없이는 판단할 수 없다.

### 11-2. Minimal v2 design — 추가한 것 / 추가하지 않은 것

**추가 (새 개념·새 latent 아님, 파생 함수):**

| name | semantic | producer | consumer | observable metric | 기존 개념과 관계 | 기존으로 안 되는 이유 |
|---|---|---|---|---|---|---|
| `gto_knowledge(prof, family)` | 차트 family 의 기억 정확도 | pf_range / pf_defend (기존) | open_pct, defend_thresholds, limp_p | matched spot 에서 recall Brier/MAE | 기존 acc 식 그대로 (값 동일) | 3곳 복제라 mismatch 를 붙일 이름이 없었다 |
| `gto_condition_match(family, spot)` | 지금 spot 에 기억한 차트가 맞는 비율 | reference layer(`gto.rfi`/`defend_pct`) + 공부한 조건 목록 `GTO_STUDIED` (데이터 커버리지 사실) | gto_memory_confidence | near/unfamiliar spot 에서 기억 차트를 적용했을 때의 오차 = 1 − match (정의상) | 없음 | 어떤 spot 을 공부했는지 표현이 없었다 |
| `gto_memory_confidence` | knowledge × match | 위 둘 | flag ON 일 때 위 3 소비처 중 spot 을 아는 2곳(open_pct, defend_thresholds) | 같음 | (1−acc) 이탈 항의 크기를 정한다 | — |

`match = 1 − |w_here − w_studied| / max(·)`. 새 계수 없음. 중첩 레인지에서 '넓은 쪽 레인지 중 행동이 같은 비율'이다.
**기본 OFF** (`T2_GTO_MEMORY_V2=1` 로 켬).

**추가하지 않음 (기존으로 충분 또는 근거 부족):**
- `gto_coverage / gto_recall / gto_interpolation` 3개 개념: family 가 2개뿐이고 recall 오차를 family·조건별로 가를 데이터가 아직 없다. knowledge×match 한 쌍으로 시작한다.
- `reasoning_accuracy` 상위 개념: calc_noise 가 개념별 인식오차를 이미 한다. 필요한 것은 개념이 아니라 **bias 방향 보정**(관측 필요).
- `exploit restraint` 개념: `_shrink`(overconf←consistency) + `read_opponent` data 항으로 이미 표현된다. 할 일은 중복 공식 통합(행동 변화 → 별도).
- `cognitive load`, `self-image`, `memory decay`, `equity realization` 개념: 지금은 소비처·관측 지표가 없다. equity realization 은 새 개념이 아니라 `positional`/`spr` 의 새 소비처로 넣는 것이 맞다.
- 새 latent: 11-1 측정대로 study 가 차트와 reasoning 을 0.54 로 묶는다. 분리 후보는 `study → chart_study + reasoning_study` 한 쌍이다. 하지만 make_player rng 스트림과 전 플레이어가 바뀌고, 목표 상관은 관측 없이 정할 수 없어 보류.

### 11-3. 구현

- `persona.py`: `GTO_MEMORY_V2`, `GTO_FAMILY_CONCEPT`, `GTO_STUDIED`, `gto_knowledge`, `_pos_equiv`, `gto_condition_match`, `gto_memory_confidence`. `open_pct` acc 가 `gto_memory_confidence(prof,'rfi',spot)` 을 쓴다.
- `preflop.py`: `defend_thresholds` acc 가 `gto_memory_confidence(prof,'defend',spot)` 을, `limp_p` acc 가 `gto_knowledge(prof,'rfi')` 를 쓴다. limp_p 호출부에는 spot 이 없어 match 를 걸지 않는다.
- plan.py / line-plan / replan / reads **무수정**.

### 11-4. Verifier 결과 (`tools/verify_human_model_v2.py`)

| 항목 | 결과 | 수치 |
|---|---|---|
| IDENT (flag OFF 지문) | **PASS** | regress9 6/6, turbo8 6/6 이 pristine a148d95 와 같음. `verify_preflop_closure` 4/4 (OFF·ON 모두) |
| MATCH | PASS | 공부한 조건 안 1.0. 9max-40bb 0.85, 8max-150bb 0.92, 8max-noante-40bb 0.76, 9max-noante-250bb UTG 0.49 |
| A1 open (중립·knowledge 10) | PASS | 페르소나/기억 항 0, 기존 positional 항만 남음 (기준 대비 1.5~4.5%) |
| A2 defense (중립·pf_defend 10 vs 공개 차트) | **FAIL — prior layer** | BB vs UTG+1 전 스택 pure-fold 22손 평균 continue 0.365. J4o 0.56, 82o 0.27. **페르소나 항 0 상태**라 defense prior 교정 workstream 소관 |
| B 경계 손 | PASS | BTN 오픈: 경계 손 Δ=1.0, 먼 손 Δ=0. defense: AA 0.00 / AKs 0.01 / KJo 0.04 / T7o 0.69 |
| C 명백한 우열 뒤집기 | 평균 순서 PASS / 최악 손 순서 FAIL | 중립 prior 에서 이미 최악 손 순서 위반. loose9: pure-fold 평균 0.365→0.604, ≥0.5 비율 13.6%→86.4%. tight1: pure-continue 평균 0.871→0.472. **페르소나가 양방향으로 명백한 영역을 크게 민다** |
| D evidence 0 | PASS | w=0, fold_gap=0, exploit_weight=0 |
| E evidence 증가 | PASS | 단조, 최대 스텝 0.053 ≤ 램프 0.067 |
| F / G | PASS (존재) | knowledge 중간대 1,104명 중 reasoning 상·하위 20% 176/201. reasoning 중간대 1,012명 중 knowledge 상·하위 164/185 |

### 11-5. Runtime attribution (flag ON vs OFF)

| fixture | VPIP | PFR | flop | 지문 | 같은 상태 paired flip |
|---|---|---|---|---|---|
| regress9 (9max, no ante, 대부분 >100bb) | 317→305 | 167→163 | 101→100 | 6/6 변화 | 24/1,427 (1.7%) |
| turbo8 (8max ante, 대부분 공부한 조건) | 368→369 | 190→191 | 107→107 | 1/6 | 1/1,304 |

- regress9 의 flip:
  - unopened raise→fold 7, fold→raise 1, fold→shove 1, fold→limp 1
  - vs_open call→fold 9, fold→call 2
  - vs_limp 3
  - 22건이 >100bb, 9건이 BB
- 방향은 기질을 따른다. tight(looseness ≤ 2.9) 17건은 fold 쪽, loose(≥ 7.3) 7건은 참여 쪽이다. mismatch 가 (1−acc) 이탈 항을 키운 결과다.
- **설계 한계 확인:** pf_range 10 인 tight player 가 9max-noante-150bb UTG 에서 AQo 를 접는다. mismatch 때 기억 대신 커지는 항이 '추론'이 아니라 '기질'이다. 프리플랍에는 기억과 별개인 reasoning 경로(깊이/좌석 보정을 스스로 하는 능력)가 없다.
- line-plan/replan 코드는 무수정이다. flag ON 의 포스트플랍 차이는 프리플랍 참여·레인지가 달라진 결과뿐이다.

### 11-6. 판정과 다음 단계

- **flag OFF 코드: test 승격 가능.** 행동 0 변화가 지문으로 증명됐다. 3곳 복제 식을 한 이름으로 모으고 shadow API 를 추가한 것이다.
- **flag ON: 승격 불가.** mismatch 에서 기억의 빈자리를 기질이 메우는 구조라 11-5 의 한계가 그대로 행동이 된다.

다음 (순서대로):
1. defense 중립 prior 교정 — A2/C 의 1차 원인이다 (GTO workstream).
2. preflop reasoning 경로 — mismatch 시 `gto_memory_confidence` 가 줄어든 만큼 reference 조건보정을 스스로 하는 능력. 개념 후보는 기존 `stack_decay`/`positional` 재사용을 먼저 검토.
3. 페르소나 이탈 크기 — 폭 곱셈 → logit 이동 + 상한. 모집단 관측(티어별 BB 디펜스율) 필요.
4. calc_noise bias 방향을 양마다 관측으로 정한다. `error_rate` 를 제거하거나 배선한다.
5. `exploit_weight` / `read_opponent['w']` 통합.
6. latent 분리 여부는 차트 퀴즈형 관측 지표를 만든 뒤 결정한다.


## 12. Human Model v3 — learned chart -> condition reasoning -> temperament (2026-09-29)

Branch: `chatgpt/human-model-v3-20260929`.  Opt-in only via
`T2_PREFLOP_REASONING_V3=1`; OFF preserves the v2/production path.

### 12-1. Problem

Human Model v2 separated GTO chart knowledge from condition match, but when a
spot was unfamiliar it reduced memory confidence and let the existing
looseness/aggression deviation fill the missing weight.  That means a player
who memorized an 8-max ante chart but faces 9-max/no-ante/deeper play becomes
"more loose/tight" instead of first trying to reason about the changed
conditions.

That conflates three different human mechanisms:

1. **recall** — what studied chart was remembered;
2. **reasoning** — how well the player adjusts that chart to a new stack/table/
   dead-money condition;
3. **temperament/habit** — stable loose/tight/aggressive deviation.

### 12-2. V3 split

No new strategic concept or latent factor is introduced.

- recall accuracy: existing `pf_range` / `pf_defend` through
  `gto_knowledge()`;
- depth adjustment: existing `stack_decay`;
- table-size/position adjustment: existing `positional`;
- ante/dead-money adjustment: existing `potodds`.

`gto_studied_anchor()` constructs the nearest chart that could actually have
been studied from `GTO_STUDIED`.

`preflop_reasoning_confidence()` activates only the skills relevant to the
conditions that differ and averages their existing 0..10 scores on a 0..1
scale.  There is no new mismatch coefficient: the size/direction of the
correction is the actual studied-anchor -> current-reference width delta.

`preflop_reasoned_width()` then applies:

1. remembered studied-condition width;
2. a reasoning fraction of the anchor -> current-condition delta;
3. the ordinary knowledge-dependent temperament deviation applied to that
   reasoned baseline.

Condition mismatch therefore does **not** enlarge temperament deviation.

### 12-3. Current consumers

Implemented behind the V3 flag:

- `persona.open_pct` (RFI width);
- `preflop.defend_thresholds` (total continue and 3bet widths).

`limp_p` is intentionally unchanged for now: its current call contract lacks
seats/ante/current chart context, so inventing a condition adjustment there
would mix semantics.  It continues to use chart knowledge only.

### 12-4. Structural verifier

`tools/verify_human_model_v3.py` checks:

- studied/matched spots are identical between V2 and V3;
- in unfamiliar RFI spots, stronger reasoning moves the remembered chart
  toward the current-condition reference;
- the same is true independently for defend total width and 3bet width;
- a weak reasoner stays nearer the studied anchor;
- V3 uses only already-declared concepts.

This verifier is about mechanism, not population calibration.  It does not
assert that the current GTO reference layer is correct and it does not choose
target human frequencies.

### 12-5. Next work

After the V3 structural verifier is runnable in CI/local:

1. paired counterfactual fixtures across matched vs mismatched conditions;
2. validate the unified exploit evidence weight (implemented behind
   `T2_EXPLOIT_WEIGHT_V3=1`);
3. measure concept-specific calculation-error directions before changing them;
4. test recency/forgetting in opponent memory;
5. only then revisit deviation shape (multiplicative width vs logit shift).


## 13. Human Model v3 — concept-specific calculation error (2026-09-29)

Opt-in: `T2_CALC_NOISE_V3=1`. OFF keeps the historical Gaussian formula
bit-for-bit.

Legacy `calc_noise()` gave **the same positive mean bias** to every calculation:
low skill meant `E[multiplier] ≈ 1.30` for outs, SPR, and pot odds.  The
behavioral meaning is not the same:

- outs × >1: counts too many/dirty outs (directional overestimate);
- required pot-odds equity × >1: systematic overfold;
- SPR × >1: says the pot is deeper than it is, while a separate perception
  model already pulls poor SPR readers toward neutral SPR=5.

V3 therefore keeps the positive outs bias, but makes `potodds` and `spr`
arithmetic error zero-mean with a symmetric ±0.80 error clamp around multiplier
1.0.  It consumes the same one Gaussian draw.

Verifier: `tools/verify_calc_noise_v3.py`.

Key checks:
- legacy OFF formula: exact, no mismatches;
- outs ON/OFF: identical;
- arithmetic means stay near 1.0 and SD falls monotonically with skill;
- at a symmetric pot-odds decision boundary, legacy low-skill error produced
  wrong overfold 0.631 vs wrong loose-call 0.305; V3 gives 0.464 vs 0.467;
- skill5, true SPR=8: existing neutral-pull model expects perceived SPR=7.0;
  V3 mean = 7.004 instead of the legacy upward cancellation.

Workflow run `36504408101`: structural, paired-runtime and baseline identity
all PASS.

## 14. Human Model v3 — real opponent-memory recency (2026-09-29)

Opt-in: `T2_READ_RECENCY_V3=1`.  No new decay coefficient was introduced.
The existing observer `memory` value (8..120 hands, derived from attention and
adaptability or family defaults) now means what its name says: **a recent-hand
window**.

Legacy behavior capped only effective sample size:

`n = min(lifetime_hands, memory)`

but computed VPIP/PFR/cbet/barrel/fold/sizing rates from lifetime numerators and
denominators.  Therefore an opponent who changed style never shed old evidence.

Implementation:
- at the first preflop observation of the next hand, store the previous hand's
  cumulative public-observation counters;
- retain at most 121 snapshots (max memory 120 + one baseline);
- `_recent_record()` subtracts the cumulative snapshot at the window boundary;
- every downstream rate uses that same recent view, including postflop,
  sizing, 3bet/4bet, showdown and fold counters;
- legacy saved books without snapshots remain lifetime-based until enough new
  V3-era history exists.  No synthetic history is invented.

Verifier: `tools/verify_read_recency_v3.py`.

Checks:
- OFF creates no history field;
- 80 tight + 20 loose hands → recent20 VPIP=1.0 while lifetime/memory100=0.20;
- same low-memory observer: lifetime estimate VPIP 0.234 → recent estimate 0.586;
- stationary 50% process remains 50%;
- postflop counters share the same window;
- history bounded at 121;
- save/load preserves history; old book fallback is safe.

Workflow run `36505153548`: structural, paired-runtime and baseline identity
all PASS.

## 15. Human Model v3 — preflop temperament direction audit (2026-09-29)

Current production/v2 direction normalizes a native 0..10 temperament score by
`(x-5)/4` and clips to [-1,1].  That makes score 0==1 and 9==10 before poker
logic is even applied.  The audit separated this **direction-axis clipping**
from final probability caps.

Audit: `tools/audit_preflop_deviation_shape_v3.py`, lightweight workflow
`Human V3 Deviation Audit`.

In 5,000 generated personas per field-quality band at 8-max/40bb/ante:
- RFI probability clamp is effectively absent (0 to 0.003%);
- total-defense probability clamp is real, concentrated in BB:
  - q=.4: overall 7.17%, BB-v-BTN 30.0%;
  - q=.8: overall 3.56%, BB-v-BTN 16.0%;
  - q=1.2: overall 1.20%, BB-v-BTN 5.86%.

Counterfactual using the natural 0..10 half-span `(x-5)/5`:
- removes all artificial adjacent endpoint ties in RFI;
- reduces defense clamp rate without changing the probability-cap rule:
  q=.4 7.17%→5.92%, q=.8 3.56%→2.73%, q=1.2 1.20%→0.83%;
- population p95 absolute width change is about 1.6–3.7pp depending on band/path.

Implementation is opt-in:
`T2_PREFLOP_TEMPER_DIRECTION_V3=1`.

It changes only the direction normalization to full-scale `/5`; endpoints
0/10 and midpoint 5 remain exactly unchanged.  RFI and 3bet retain all 11
integer temperament levels.  **The remaining BB total-defense collisions at
0.95 are a separate probability-cap issue and are not silently “fixed” by this
change.**  Current evidence does not justify a wholesale logit rewrite.

### 감사 2차: preflop defend 계산 경계

`preflop.defend_thresholds`의 정규화·콜러 보정·short-stack 보정·상위 재레이즈 축소를 명명된 순수 함수로 분리했다. 기준 prior, 상수, 계산 순서 및 actor/observer 공통 producer는 유지한다. [현재 함수 연결](docs/semantic_audit/CONCEPT_FUNCTION_REGISTRY.md)의 2차 정리를 참조한다. 독립 4bet prior 추가 또는 전략 교정은 아니다.

### 감사 3차: range_read 소비 경계

range 복원, 관측 액션 해석, legacy 적용 가중치, call/fold 문턱 적용의 계산을 분리했다. 기존 scalar 공급은 유지한다. [실제 함수 및 잔여 경로](docs/semantic_audit/RANGE_READ_CONSUMER_BOUNDARIES.md)를 참조한다. 독립 3-skill 체계가 완성된 것은 아니다.

### 감사 4차: 관측·압박·멀티웨이 적용 경계

기존 range_read 소비 중 observation accuracy, pressure application capacity, multiway evidence capacity와 call/fold evidence 혼합을 명시 입력의 함수로 분리했다. 기존 profile/actor 값 공급은 보존한다. [현재 함수와 잔여 의미](docs/semantic_audit/RANGE_READ_CONSUMER_BOUNDARIES.md)의 4차 항목 참조.
