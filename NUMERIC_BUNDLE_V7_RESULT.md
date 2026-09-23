# NUMERIC_BUNDLE_V7 — 결과

사전등록: `NUMERIC_BUNDLE_V7_PREREG.md` (변경 없음).
기준 `claude/v7-tier` `653c2fc`. 브랜치 `claude/v7-num-validation`.
**production 무수정. LIVE 배선 없음. `c5`·tier 경계 무변경. 사후 weight fitting 없음.**

`Q` · tier 번호 · tier5 빈도를 종속변수로 쓰지 않았다. 종속변수는 `Q` 와 독립인
과제 배터리 점수 `QX_E` 다.

---

## 1. 사실

### 1-1 배터리 커버리지 — 첫 판은 무효였다

`PS.sk` 를 감시해 배터리가 실제로 읽는 concept 을 셌다. **첫 구현에서
`spr` · `blocker` · `fold_equity` 가 한 번도 읽히지 않았다.** 그 상태의 개입 효과
`0.0000` 은 "효과 없음"이 아니라 "코드에 도달 못 함"이었다.

원인 둘.

- `decide_aggression` 은 `plan` 에 따라 분기가 갈린다. `giveup`/`showdown` 은
  `cbet_freq` 이탈 경로라 `fold_equity` 를 **안 읽고**, `semibluff` 계열만
  블러프 경로(`p *= 1 + _fe·w·2.2·street_gap`)를 탄다. 첫 판은 `giveup` 만 썼다.
- `spr`·`blocker` 는 `make_plan` 에서만 읽힌다. 첫 판에는 `make_plan` 호출이 없었다.

두 경로를 다 부르고 `make_plan` 기반 F7 을 더해 **여섯 개 전부 읽히게** 고쳤다.
배터리 1회가 읽는 횟수: `range_read` 644 · `board_texture` 208 · `potodds` 216 ·
`fold_equity` 148 · `spr` 90 · `blocker` 24.

F7 은 파일럿에서 응답(`pc`)이 격자 위에서 **상수**였다(plan label 이 패 강도로만
정해지고 스택 깊이·상대 폴드성향에 안 움직인다). 그래서 **`QX_E` 점수에서 제외**하고
`spr`/`blocker` 가 읽히는 경로를 확보하는 용도로만 남겼다.
F2 의 첫 격자는 `ftb_flop = 1 − ftb_turn` 이라 판별 점수가 `2·r` 로 퇴화했다.
교차(직교) 격자로 고쳤다.

**이 수정들은 개입 결과를 본 뒤에 했다.** 감춤 없이 적는다. 다만 바꾼 것은
사전등록한 과제군을 실제로 도달시키는 구현이고, oracle·문턱·판정규칙·시드는
건드리지 않았다.

### 1-2 paired intervention (기저 200쌍, `910001..910004`, 400인 필드)

concept 하나만 `2.0 ↔ 8.0`, 나머지 고정, 같은 RNG. 부트스트랩 95% CI 2,000회.

| concept | ΔE | 95% CI | ΔG | 95% CI | Δlevel | 응답변화 |
|---|---:|---|---:|---|---:|---:|
| `range_read` | **+0.1859** | [+0.1730, +0.1990] | −0.0585 | [−0.0647, −0.0524] | −0.0018 | 66.6% |
| `potodds` | +0.0028 | [+0.0005, +0.0052] | −0.0049 | [−0.0090, −0.0010] | −0.0053 | 29.9% |
| `spr` | **+0.0000** | [0, 0] | +0.0000 | [0, 0] | +0.0000 | **0.0%** |
| `blocker` | **+0.0000** | [0, 0] | +0.0000 | [0, 0] | +0.0000 | **0.0%** |
| `fold_equity` | −0.0015 | [−0.0031, +0.0002] | +0.0000 | [0, 0] | +0.0016 | 38.9% |
| `board_texture` | −0.0007 | [−0.0025, +0.0004] | +0.0000 | [0, 0] | −0.0006 | 35.9% |

군별 `ΔE` 에서 `range_read` 의 효과는 거의 전부 **F2(스트리트 판별) +0.9293** 이다.
나머지 군은 +0.02~+0.08 이다.

**`spr` 과 `blocker` 는 격자점 85개 중 0개의 응답도 바꾸지 않는다.** 코드는 읽히는데
출력이 불변이다. `fold_equity`(38.9%)·`board_texture`(35.9%)는 응답을 바꾸지만
oracle 추종은 개선하지 않는다 — 수준(`Δlevel`)도 거의 안 움직이므로
"행동량만 늘린다"도 아니고 **정확도와 무관한 재배치**다.

### 1-3 자연 population (fit `920001..920010` 500봇 / holdout `930001..930010` 500봇)

`Q`·tier 미사용. 적합 없음.

| concept | r(QX_E) | r(QX_G) | partial (E 입력 4개 통제) |
|---|---:|---:|---:|
| `range_read` | +0.2859 | −0.4993 | **−0.0148** |
| `board_texture` | +0.1817 | −0.1837 | +0.0458 |
| `blocker` | +0.1799 | −0.2081 | **+0.1026** |
| `potodds` | +0.1642 | −0.0079 | +0.0262 |
| `spr` | +0.1395 | −0.2119 | +0.0557 |
| `fold_equity` | +0.0712 | −0.3123 | **−0.0772** |
| `sizing_tell` (NUMERIC 밖) | +0.1243 | −0.3161 | −0.0347 |
| `overall` = mean(CALC) | +0.2207 | −0.3424 | — |
| E:`use` (adaptability) | **+0.4300** | −0.0972 | — |
| E:`see_line` (range_read) | +0.2985 | −0.5037 | — |
| E:`see_size` | +0.1214 | −0.3033 | — |
| E:`see_freq` | −0.0009 | −0.0848 | — |

CALC 전체 + 일부 EXEC + 기질축까지 넓혀 본 결과, `QX_E` 를 가장 잘 설명하는 것은
**`adaptability` (r +0.4801, partial +0.3422)** 이고 **이미 `E` 안에 있다.**
NUMERIC 밖 CALC 중 partial 이 `blocker`(+0.103)를 넘는 것은 없다
(`spr` +0.056 · `icm` +0.042 · `pf_defend` +0.017).

### 1-4 holdout ablation (사전 지정 조합, 적합 없음)

| 조합 | r(QX_E) | 현재 대비 |
|---|---:|---:|
| **현재 equal-6** | **+0.1691** | — |
| single `range_read` | **+0.2081** | +0.0390 |
| LOO −`fold_equity` | +0.1912 | +0.0221 |
| current + `sizing_tell` | +0.1725 | +0.0035 |
| LOO −`blocker` | +0.1712 | +0.0021 |
| LOO −`board_texture` | +0.1701 | +0.0010 |
| LOO −`spr` | +0.1646 | −0.0044 |
| LOO −`potodds` | +0.1575 | −0.0116 |
| SUPPORT 묶음 | +0.1638 | −0.0053 |
| DIRECT 묶음 | +0.1414 | −0.0277 |
| LOO −`range_read` | +0.1420 | −0.0270 |
| single `board_texture` | +0.1144 | −0.0547 |
| single `blocker` | +0.1081 | −0.0610 |
| single `fold_equity` | +0.0225 | −0.1465 |

### 1-5 구조 점검 (holdout)

```
r(num, max concept)  +0.8724        r(num, min concept)  +0.8844
r(num, overall CALC) +0.9381   vs   r(num, QX_E)         +0.1691
r(QX_E, QX_G)        −0.0331
```

## 2. 사전등록 판정

규칙을 사전등록 4절의 순서대로 기계적으로 적용한 결과다.

| concept | ΔE | ΔG | partial | **판정** |
|---|---:|---:|---:|---|
| `range_read` | +0.1859 (CI 0 제외) | −0.0585 | −0.0148 | **REDUNDANT** (규칙 3) |
| `potodds` | +0.0028 | −0.0049 | +0.0262 | **UNSUPPORTED** (규칙 2) |
| `spr` | +0.0000 | +0.0000 | +0.0557 | **UNSUPPORTED** (규칙 2) |
| `blocker` | +0.0000 | +0.0000 | +0.1026 | **UNSUPPORTED** (규칙 2) |
| `fold_equity` | −0.0015 | +0.0000 | −0.0772 | **UNSUPPORTED** (규칙 2) |
| `board_texture` | −0.0007 | +0.0000 | +0.0458 | **UNSUPPORTED** (규칙 2) |

**KEEP_DIRECT 도 KEEP_SUPPORT 도 하나도 없다. GENERAL_SKILL_ONLY 도 없다.**

`GENERAL_SKILL_ONLY` 가 한 번도 안 뜬 이유는 3절에 적는다 — 규칙 자체의 한계다.

## 3. 해석

**3-1 `num` 은 정량 익스플로잇 축이 아니라 전반 실력 대리변수에 가깝다.**
`r(num, overall CALC) = +0.938` 이고 `r(num, QX_E) = +0.169` 다. 여섯 개 평균은
"이 사람이 포커 계산을 얼마나 아는가"를 거의 그대로 재고, "상대의 수치를 읽어
익스플로잇하는가"는 거의 안 잰다. 사용자가 의심한 구조가 실측으로 나왔다.

**3-2 `range_read` 의 효과는 실물이지만 `num` 이 아니라 `E` 를 타고 온다.**
개입 `ΔE = +0.186` 은 여섯 중 유일하게 큰 값이고 거의 전부 스트리트 판별(F2)에서
나온다. 그런데 `E` 의 입력 넷을 통제하면 partial 이 **−0.015** 로 사라진다.
`range_read` 가 곧 `see_line` 이기 때문이다. 즉 `Q = E · num` 에서 같은 능력을
**두 번 곱하고 있다.** 사전등록 1절에서 코드로 먼저 지적한 중복이 수치로 확인됐다.

**3-3 사전등록한 DIRECT/SUPPORT 가설은 뒤집혔다.**
코드 경로상 상대의 수치를 직접 곱하는 것은 `range_read`·`fold_equity` 둘뿐이었고
그래서 DIRECT 로 잡았다. 그런데 partial 기준으로 둘 다 음수(−0.015, −0.077)이고,
SUPPORT 로 분류한 `blocker` 가 가장 크다(+0.103). holdout 에서도 DIRECT 묶음
(+0.141)이 SUPPORT 묶음(+0.164)보다 낮다. **코드 경로의 직접성이 독립 과제
성능의 직접성을 뜻하지 않았다.**

**3-4 `spr`·`blocker` 는 이 세 판단 진입점에서 출력이 불변이다.**
`make_plan`·`decide_aggression`·`calldown_need` 를 다 불러도 2↔8 개입이 격자점
85개 중 0개를 못 바꾼다. `blocker` 의 자연 partial 이 +0.103 인 것과 모순처럼
보이지만 서로 다른 것을 재고 있다 — 개입은 **인과**, 자연 상관은 다른 개념과의
**공변**이다. 자연 population 에서 `blocker` 가 높은 사람은 다른 것도 높다
(`r(num, overall) = 0.938`). **인과적으로는 0 이다.**

**3-5 대조 배터리 `QX_G` 는 "일반 포커 실력"이 아니라 "날것 팟오즈 추종"을 쟀다.**
거의 모든 concept 에서 `r(QX_G) < 0` 이다 — 잘하는 사람일수록 raw pot odds 에서
**의도적으로 벗어난다**(리딩·블러프캐치 조정). 그래서 `GENERAL_SKILL_ONLY`
규칙(`ΔG ≥ 0.05`)은 구조적으로 발동할 수 없었다. **사전등록 판정표에서
GENERAL_SKILL_ONLY 가 0건인 것은 "그런 concept 이 없다"가 아니라
"이 규칙이 이 대조군으로는 그 구분을 못 한다"로 읽어야 한다.**
`potodds`·`spr`·`board_texture` 가 일반 실력 축인지 아닌지는 **아직 미판정**이다.

**3-6 동일가중 평균 자체가 틀렸다는 증거는 약하다.**
`r(num, max) = 0.872` ≈ `r(num, min) = 0.884` 로 한두 축이 과대평가를 만드는
구조는 **없다.** holdout 조합 비교에서도 모든 변형이 +0.02~+0.21 안에 있다.
다만 `single range_read`(+0.208)가 현재 6개 평균(+0.169)보다 낫고
`fold_equity` 를 빼면 올라간다(+0.191). **가중이 문제가 아니라 멤버십이 문제다.**

## 4. 아직 모르는 것

- **`QX_E` 가 "정량 상대 익스플로잇"의 타당한 대리변수인지 자체는 검증되지 않았다.**
  oracle 은 내가 공개 정보로 정의한 것이고, 실제 칩 EV 와 연결하지 않았다.
  `QX_E` 가 높은 봇이 실제로 더 버는지는 이번 측정 밖이다.
- **`QX_G` 대조군이 일반 실력을 못 쟀다** (3-5). `potodds`·`spr`·`board_texture` 의
  GENERAL_SKILL_ONLY 여부는 다른 대조군을 설계해야 판정된다.
- **`spr`·`blocker` 가 다른 출력 채널로는 작동할 수 있다.** 이번 배터리의 응답은
  `decide_aggression` 의 p, `calldown_need` 의 need, `make_plan` 의 pc 셋뿐이다.
  `plan` 라벨 자체나 사이즈 결정(`decide_size`)은 응답으로 쓰지 않았다.
  **"전역적으로 효과가 없다"가 아니라 "이 세 출력에 대해 불변"이다.**
- **F6(텍스처×빈도)은 전원 r ≈ 0** 이다(모집단 sd 0.081). production 에 그런
  상호작용이 없는 것인지 과제 설계가 잘못된 것인지 구분 못 했다.
- **F7 이 상수인 이유** — plan label 이 패 강도로만 정해진다. 이것이 설계인지
  결함인지는 이번 범위 밖이다.
- 기저 200쌍·holdout 500봇은 상관 추정에는 충분하지만 **작은 효과(|Δ| < 0.01)를
  가르기에는 부족**하다.

## 5. 결론만 기록 — 정의 변경은 하지 않는다

사전등록 6절대로 `NUMERIC` 정의를 바꾸지 않았고 `c5` 도 재적합하지 않았다.
기존 V7 은 그대로 보존한다. 기록하는 결론은 이것뿐이다.

> 현재 `NUMERIC` 6개 동일가중 평균은 독립 과제 기준으로 **정량적 상대 익스플로잇
> 능력의 근거가 없다.** 여섯 중 다섯이 UNSUPPORTED 이고, 유일하게 큰 효과를 내는
> `range_read` 는 이미 `E` 에 들어 있어 `Q = E · num` 에서 이중 계산된다.
> `num` 은 전반 포커 실력 대리변수에 가깝다 (`r = 0.938`).

**"tier5 가 3~4명 나왔으니 NUMERIC 이 맞다" 는 근거로 쓰지 않는다.**
tier5 분포는 `c5` 를 그 분포에 맞춰 적합한 결과이고 멤버십의 증거가 아니다.

다음 판에서 논의할 거리(이번에 실행하지 않는다).

- `Q` 에서 `range_read` 이중 계산을 어떻게 다룰 것인가 — `num` 에서 빼는가,
  `E` 에서 빼는가, 아니면 `Q` 의 형태를 바꾸는가.
- `adaptability` 가 독립 과제를 가장 잘 설명한다(partial +0.342). 5단계 게이트를
  `num` 이 아니라 적용 능력 쪽에서 더 좁히는 설계가 맞는가.
- `QX_G` 를 대체할 일반 실력 대조군 설계.
- 배터리의 응답 채널을 `plan` 라벨·`decide_size` 까지 넓힐 것인가.

## 6. 재현

```
python3 tools/v7_num_concept_trace.py --with-comparators
python3 tools/v7_num_intervention.py --concept range_read --out iv_range_read.json
python3 tools/v7_num_population.py --dump-seed 920001 --entries 400 --per-field 50 --out pop_920001.json
python3 tools/v7_num_population.py --fit-glob 'pop_92*.json' --holdout-glob 'pop_93*.json'
```

그림: `docs/NUMERIC_BUNDLE_V7.png` (`tools/draw_v7_num.py`)
