# TIER5_AXIS_DESIGN — 사전등록

기준: `claude/v7-num-validation` `4b55d34`. 브랜치 `claude/tier5-axis-design`.
선행: `NUMERIC_BUNDLE_V7_RESULT.md` · `HIERARCHICAL_READ_V7_PREREG.md`

**질문: 정량적 상대 분석 능력을 현재 persona concept 조합으로 표현할 수 있는가,
아니면 별도 concept 이 필요한가.**

이번 범위는 **설계와 검증까지**다. V8 구현·LIVE wiring·긴 자연상태 CF·EV 실험을
하지 않는다. `c5` 변경 금지, tier 경계 변경 금지, production 무수정,
3~4명/400명 재적합 금지. 새 concept 을 **코드에 추가하지 않는다** — 후보 명세까지다.

## 1. 기능 6단계 → 코드 전수 매핑 (측정 전 완료)

`tools/tier5_concept_stage_map.py` 로 `persona.ALL_CONCEPTS + TEMPER` **48개 전부**의
사용처를 찾아 감싸는 함수로 단계를 판정했다. 이름이 아니라 소비 경로 기준이다.

```
RECORD     reads.Book.observe_*
ESTIMATE   reads.estimate / obs_from_profile / perceived_profile /
           estimate_concepts / _shrink
INTERPRET  persona.read_resolution / read_opponent / street_gap / exploit_weight,
           plan.line_bluff_prior, ranges.perceived_range / narrow_by_actions
APPLY      plan / preflop / depth / money_pressure / bot / session / ...
```

**상대분석 파이프라인(RECORD/ESTIMATE/INTERPRET)에 들어가는 관찰자측 concept 은
48개 중 5개뿐이다.**

```
attention · range_read · sizing_tell · adaptability · consistency
```

(`bluff` 도 걸리지만 전부 **상대의** 추정 축(`opp_profile['bluff']`)이지
관찰자의 능력이 아니다. 관찰자측이 아니므로 후보에서 제외한다.)

나머지 43개는 **APPLY 전용**이다. `potodds`·`spr`·`blocker`·`fold_equity`·
`board_texture` 를 포함해 CALC 16개 중 14개가 상대 추정 파이프라인을 한 번도
건드리지 않는다. NUMERIC 6개 평균이 독립 과제와 r=0.169 였던 이유가 여기 있다.

### 1-1 단계별 담당 축

| # | 단계 | 코드 | 이 단계를 조절하는 축 |
|---|---|---|---|
| 1 | 관찰한다 | `Book.observe_*` — 관찰자별 구분 없이 **동일하게 기록** | **없음** (전원 동일) |
| 2 | 기억한다 | `estimate:220` `n = min(hands, memory)`, `memory = 6·attention + 4·adaptability` | attention, adaptability |
| 3 | 표본이 충분한지 판단한다 | `_shrink:195` `eff_n = n·skill·overconf`, `w = eff_n/(eff_n+12)` · `estimate:284` `conf = min(1, n·skill/25)` | `skill = (0.5·attention + 0.3·range_read + 0.2·sizing_tell)/10`, `overconf = 1.8 − 0.09·consistency` |
| 4 | population/reference 와 비교한다 | `_rate(num, den, PRIOR[k])` · `read_opponent` `fg(v) = v − 0.52` | **없음** (`reads.PRIOR` 고정표, 상수 0.52) |
| 5 | 차이가 의미 있는지 해석한다 | `read_opponent` `fg(v) × see_freq` 등 | **전용 축 없음** — `see_*` 는 크기 감쇠(지각 게이트)이지 해석 능력이 아니다 |
| 6 | 얼마나 바꿀지 정한다 | `w = use·data`, `blend(baseline, exploit, w)` | adaptability |

### 1-2 사용자가 요청한 다섯 분류

| 분류 | 담당 축 |
|---|---|
| 일반 포커 계산 능력 | `potodds, spr, blocker, board_texture, outs, icm, …` — **전부 APPLY 전용** |
| 상대 관찰 능력 | `attention` (→ `see_freq`, `memory`, `noise`) |
| 상대 패턴을 정성적으로 읽는 능력 | `range_read` (→ `see_line`), `sizing_tell` (→ `see_size`) |
| **표본/빈도를 수치적으로 해석하는 능력** | **전용 축 없음.** `consistency` 가 `overconf` 로 3단계만 부분 조절 |
| 해석 결과를 전략에 적용하는 능력 | `adaptability` (→ `use`) |

**숨기지 않고 명시한다: 4번 분류에 대응하는 축이 현재 모델에 없다.**
"본다"(see_*)와 "바꾼다"(use) 사이에 "얼마나 정확히 해석하는가"가 비어 있다.
4단계의 기준표는 전원 동일하고 5단계는 고정 뺄셈 뒤 지각 게이트로 깎일 뿐이다.

### 1-3 Model A 의 후보 공간은 분석적으로 닫혀 있다

`E = app·(½·obs_mean + ½·obs_min)` 는 `attention · range_read · sizing_tell ·
adaptability` 넷의 함수다. 파이프라인 참여 축이 다섯뿐이므로 **Model A 가 `E` 에
더할 수 있는 새 정보는 `consistency` 하나로 닫힌다.** 다른 43개를 어떻게 조합해도
상대 추정 파이프라인에 들어가지 않는다.

## 2. 두 후보 모델 (결과 보기 전 정의)

### Model A — 기존 concept 만

```
Q_A = E · a_c        a_c = _see(consistency) = clamp((consistency − 2)/6, 0, 1)
```

- `_see` 는 `persona.read_resolution` 의 기존 앵커다. 새 상수를 만들지 않는다.
- **`range_read` 를 게이트에 다시 쓰지 않는다** — `E` 의 `see_line` 과 이중계산이다.
  같은 이유로 `attention`·`sizing_tell`·`adaptability` 도 게이트에 다시 넣지 않는다.
- 근거: `consistency` 만이 파이프라인에 있으면서 `E` 밖이다 (`overconf` → 3단계).

### Model B — 전용 정량 읽기 concept (후보 명세, 코드 추가 없음)

이름 **`stat_read`**. 기존 `range_read`(레인지를 읽는다) · `sizing_tell`(사이즈에서
읽는다) 와 같은 계열이고, **숫자를 읽는 축이 그 계열에 없다**는 것이 작명 근거다.

**할 수 있게 하는 것 (4·5단계 전용)**

- 기준 대비 편차 `|obs − PRIOR|` 를 표본 크기와 함께 해석해 **조정량의 크기**를 정한다.
- 즉 `read_opponent` 의 `fg(v) = v − 0.52` 뒤에 붙는 해석 이득으로만 들어간다.

**하지 못하게 하는 것 (역할 중복 금지)**

| 겹치면 안 되는 축 | 금지 사항 |
|---|---|
| `attention` | 관측량·기억(`memory`)·노이즈를 개선하지 않는다 |
| `range_read` | 스트리트 구분·레인지 축소를 개선하지 않는다 |
| `sizing_tell` | 사이즈 신호 지각을 개선하지 않는다 |
| `adaptability` | 바꿀 **의지**(`use`, `w`)를 올리지 않는다 |
| `consistency` | 과신 보정(`overconf`)을 대체하지 않는다 |

**중립 조건**: 편차가 0 이면 `stat_read` 는 출력에 아무 영향이 없어야 한다.
높은 `stat_read` 가 "더 많이 이탈한다"가 되면 안 되고 "편차 크기에 비례해
정확히 이탈한다"여야 한다.

**추가 비용 (설계 결정 전에 알아야 할 것)**: `persona.make_player` 는
`for k in LOADING.items(): rng.gauss(...)` 로 concept 마다 난수를 하나씩 뽑고
**기질 draw 가 그 루프 뒤에 온다.** `LOADING` 에 키를 더하면 이후 스트림이 전부
밀려 **모든 시드의 모든 플레이어가 바뀐다** — 지문 `d8e9271e…`, regression
baseline 3세대, reachability reference, V7 `c5` calibration 이 전부 무효가 된다.
`stat_read` 만 pid 에서 유도한 **별도 RNG** 로 뽑으면 기존 스트림을 한 draw 도
건드리지 않는다. Model B 를 채택한다면 이 방식이 전제다.

## 3. 독립 검증 설계

**기존 `Q`/tier 를 정답으로 쓰지 않는다.** `tools/v7_num_battery.py` 의
`QX_E`(F1~F6)를 그대로 재사용한다 — 이미 `Q` 와 독립이고 oracle 이 공개
`opp_est`·게임 상태에서만 나온다.

### 3-1 이번에 실제로 재는 것 (작은 synthetic validation)

1. **`consistency` paired intervention** — `2.0 ↔ 8.0`, 나머지 고정, 같은 RNG,
   기저 200쌍(`910001..910004`). `ΔE`·`ΔG`·응답변화율·부트스트랩 95% CI.
   V7 검증과 완전히 같은 절차다.
2. **`consistency` 자연 partial** — 이미 떠 놓은 population dump
   (`920001..920010` 500봇)에서 `E` 입력 넷을 통제한 부분상관.
3. **음성 대조 프로필 분리 검정** — 합성 프로필 두 종을 만든다.

```
CALC_ONLY   APPLY 전용 CALC 14개 = 9.0,  파이프라인 5축 = 2.0
            "포커 계산은 잘하지만 상대 통계는 못 읽는 사람"
PIPE_ONLY   파이프라인 5축 = 9.0,        APPLY 전용 CALC 14개 = 2.0
            "상대는 잘 읽지만 blocker/potodds 계산은 평범한 사람"
```

두 종의 `QX_E` 가 갈리는지 본다. **갈리지 않으면 배터리가 두 능력을 구분 못
하는 것이므로 이후 판정 전체가 무효다** (배터리의 타당성 검정을 겸한다).

### 3-2 이번에 하지 않는 것

긴 자연상태 CF, EV 실험, `stat_read` 구현, 새 population calibration.

## 4. 판정 규칙 (결과 보기 전 고정)

문턱은 `NUMERIC_BUNDLE_V7_PREREG.md` 4절과 동일하게 **`ΔE ≥ 0.05` (부트스트랩
95% CI 가 0 제외)**, **부분상관 ≥ 0.05** 를 쓴다. 같은 배터리·같은 표본 크기이므로
새 문턱을 만들 이유가 없다.

순서대로 적용한다.

```
0  전제 검정: 3-1-3 에서 CALC_ONLY 와 PIPE_ONLY 의 QX_E 차이가 0.05 미만이면
   → INSUFFICIENT_EVIDENCE (배터리가 두 능력을 구분 못 한다)

1  EXISTING_SUFFICIENT
   consistency 의 ΔE ≥ 0.05 (CI 0 제외) AND 부분상관 ≥ 0.05
   → Model A 로 Tier 5 축을 세울 수 있다

2  DEDICATED_CONCEPT_JUSTIFIED
   (a) 1-1 매핑에서 축이 없는 기능 단계가 확인되고          [이미 확인: 4·5단계]
   AND (b) consistency 가 기준 미달 (ΔE < 0.05 또는 부분상관 < 0.05)
   AND (c) 전제 검정을 통과했다
   → 기존 축으로 표현되지 않는 독립 기능이 실측으로 확인된 것이다

3  EXISTING_NEEDS_RESTRUCTURE
   consistency 는 기준 미달이지만, E 자체의 재구성(중복 제거·가중 변경)만으로
   PIPE_ONLY 와 CALC_ONLY 가 분리되고 희소 상위층이 나오는 경우

4  INSUFFICIENT_EVIDENCE
   위 어디에도 안 들어가는 경우
```

**"새 concept 쪽이 더 그럴듯하다"만으로 2번을 주지 않는다.** (b) 를 실측으로
확인해야 한다.

## 5. 산출물

```
TIER5_AXIS_DESIGN_PREREG.md        이 문서
tools/tier5_concept_stage_map.py   48개 concept → 단계 매핑
tools/tier5_axis_validate.py       consistency 개입 + 음성 대조 프로필 분리
TIER5_AXIS_DESIGN_RESULT.md        매핑표 · 중복/공백 분석 · 판정
```

결과 보고 뒤 사용자와 **기존 concept 재구성 vs 새 정량 concept 추가**를 정한다.
