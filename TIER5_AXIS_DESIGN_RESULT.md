# TIER5_AXIS_DESIGN — 결과

사전등록: `TIER5_AXIS_DESIGN_PREREG.md` (변경 없음).
기준 `claude/v7-num-validation` `4b55d34`. 브랜치 `claude/tier5-axis-design`.

**production 무수정 · LIVE 배선 없음 · `c5` 변경 없음 · tier 경계 변경 없음 ·
새 concept 코드 추가 없음.** 이번 범위는 설계와 검증까지다.

**판정: `DEDICATED_CONCEPT_JUSTIFIED`** — 근거와 한계는 3·4절에 적는다.

---

## 1. 사실

### 1-1 concept 48개 → 파이프라인 단계 매핑

`tools/tier5_concept_stage_map.py`. `persona.ALL_CONCEPTS + TEMPER` 전부를
사용처마다 감싸는 함수로 판정했다. 이름이 아니라 소비 경로 기준이다.

**상대분석 파이프라인(RECORD/ESTIMATE/INTERPRET)에 들어가는 관찰자측 concept 은
48개 중 5개뿐이다.**

| concept | 그룹 | 단계 | 진입점 |
|---|---|---|---|
| `attention` | TEMPER | ESTIMATE · INTERPRET | `obs_from_profile:28` · `read_resolution:868` · `exploit_weight:825` |
| `range_read` | CALC | ESTIMATE · INTERPRET | `obs_from_profile:29` · `read_resolution:869` · `perceived_range:237` · `exploit_weight:826` |
| `sizing_tell` | CALC | ESTIMATE · INTERPRET | `obs_from_profile:29` · `read_resolution:870` |
| `adaptability` | TEMPER | ESTIMATE · INTERPRET | `obs_from_profile:28` · `read_resolution:871` · `exploit_weight:824` |
| `consistency` | TEMPER | ESTIMATE | `obs_from_profile:28` (→ `overconf`) |

`bluff` 도 걸리지만 전부 **상대의** 추정 축(`opp_profile['bluff']`, `e['bluff']`)
이지 관찰자 능력이 아니다.

**나머지 43개는 APPLY 전용이다.** `potodds` · `spr` · `blocker` · `fold_equity` ·
`board_texture` 를 포함해 CALC 16개 중 14개가 상대 추정 파이프라인을 한 번도
건드리지 않는다. EXEC 20개도 전부 APPLY 전용이다.

### 1-2 기능 6단계별 담당 축

| # | 단계 | 코드 | 조절 축 |
|---|---|---|---|
| 1 | 관찰한다 | `Book.observe_*` — 관찰자 구분 없이 **동일 기록** | **없음** |
| 2 | 기억한다 | `estimate:220` `n = min(hands, memory)`, `memory = 6·attention + 4·adaptability` | attention, adaptability |
| 3 | 표본 충분성 | `_shrink:195` `eff_n = n·skill·overconf`, `w = eff_n/(eff_n+12)` · `estimate:284` `conf = min(1, n·skill/25)` | skill(att·rr·st), overconf(consistency) |
| 4 | 기준과 비교 | `_rate(num, den, PRIOR[k])` · `read_opponent` `fg(v) = v − 0.52` | **없음** (고정표·상수) |
| 5 | 차이 해석 | `read_opponent` `fg(v) × see_freq` 등 | **전용 축 없음** (지각 감쇠일 뿐) |
| 6 | 얼마나 바꿀지 | `w = use·data`, `blend()` | adaptability |

### 1-3 중복과 공백

**중복** — `range_read` 가 세 곳에 들어간다.

```
read_resolution:869  see_line   → E
obs_from_profile:29  skill      → _shrink · conf (3단계)
TIER_V7_NUMERIC      num        → Q = E · num
```

`Q` 에서 `range_read` 가 **양변에** 있다. `NUMERIC_BUNDLE_V7_RESULT.md` 3-2 의
`partial = −0.015` 가 이 구조의 수치적 표현이다.

**공백** — 1·4·5단계에 축이 없다. 1단계(기록)는 설계상 동일한 것이 맞다.
**4·5단계가 문제다** — 기준표가 전원 동일하고, 편차는 고정 뺄셈 뒤 `see_*` 로
크기만 깎인다. **"본다"(see_*)와 "바꾼다"(use) 사이에 "얼마나 정확히 해석하는가"가
없다.** 사용자가 요청한 다섯 분류 중 **"표본/빈도를 수치적으로 해석하는 능력"**에
대응하는 전용 축이 없다.

### 1-4 배터리 타당성 전제 검정 — 통과

합성 프로필 두 종, 기저 200쌍.

```
CALC_ONLY   APPLY 전용 CALC 14개 = 9.0, 파이프라인 5축 = 2.0
PIPE_ONLY   그 반대
```

| | QX_E | QX_G |
|---|---:|---:|
| CALC_ONLY | 0.3016 | 0.9722 |
| PIPE_ONLY | **0.8010** | 0.8214 |
| 차이 (PIPE − CALC) | **+0.4993** [+0.4923, +0.5062] | −0.1508 |

**배터리가 "포커 계산 잘함"과 "상대 통계 잘 읽음"을 실제로 분리한다.**
`QX_E` 는 0.50 갈리는데 `QX_G`(일반 계산)는 오히려 CALC_ONLY 가 높다.
판정 0번 전제 통과.

### 1-5 두 번째 커버리지 결함 — QX_E 는 ESTIMATE 단계를 안 탄다

`consistency` 개입이 `ΔE = 0.0000`, 응답변화 0.0% 로 나왔다. 계측해보니
**배터리 1회가 `reads.estimate` · `_shrink` · `obs_from_profile` ·
`perceived_profile` · `estimate_concepts` 를 전부 0회 호출한다.**
`opp_est` 를 완성된 dict 로 넘기기 때문이다.

즉 `QX_E` 는 **기능 6단계 중 4~6단계만** 덮는다. 1~3단계(기록·기억·표본 충분성)가
통째로 빠져 있고, `consistency` 는 3단계에만 들어가므로 구조적으로 미도달이었다.

**이 결함은 `consistency` 결과를 본 뒤에 발견했다.** 숨기지 않고 적는다.
`NUMERIC_BUNDLE_V7` 에서 `spr`/`blocker`/`fold_equity` 에 났던 것과 같은 종류다.

### 1-6 ESTIMATE 단계 배터리 `QX_S` (추가 측정)

합성 `Book` 을 만들어 `perceived_profile` 을 거치게 한다. 관측 빈도(5수준)와
표본 크기(4수준)를 흔들고, 관찰자의 추정치가 **실제 생성 빈도**를 얼마나
따라가는지 잰다. oracle 은 내가 Book 을 만들 때 쓴 빈도이고 관찰자는 못 본다.
**사전등록한 `QX_E` 에 섞지 않고 따로 보고한다.**

`QX_S` 자연분포 (기저 200): **mean +0.8971, sd 0.0140, 범위 0.8667~0.9519**

| 축 | ΔS (2.0→8.0) | 95% CI | 응답변화 |
|---|---:|---|---:|
| `range_read` | +0.0169 | [+0.0164, +0.0174] | 100.0% |
| `sizing_tell` | +0.0110 | [+0.0107, +0.0114] | 100.0% |
| `attention` | +0.0080 | [+0.0064, +0.0096] | 100.0% |
| `adaptability` | −0.0127 | [−0.0146, −0.0109] | 26.2% |
| `consistency` | **−0.0198** | [−0.0202, −0.0193] | 100.0% |
| `potodds` | +0.0000 | [0, 0] | **0.0%** |
| `spr` | +0.0000 | [0, 0] | **0.0%** |
| `blocker` | +0.0000 | [0, 0] | **0.0%** |

파이프라인 5축은 전부 응답을 바꾸지만 **어느 것도 0.05 를 못 넘는다.**
APPLY 전용 셋은 ESTIMATE 단계에서도 응답을 0% 바꾼다 — 1-1 매핑과 일치한다.

`consistency` 는 **음의 방향**이다. 높을수록 `overconf` 가 낮아지고 수축이 커져
관측을 늦게 믿는다. "통계적 신중함 = 더 정확"이 아니라 **편향-분산 손잡이**다.

### 1-7 `consistency` 자연 population (기존 dump 재사용, 500봇)

```
r(QX_E) = +0.0532      partial (E 입력 4개 통제) = −0.0071
```

## 2. 사전등록 판정

규칙을 사전등록 4절 순서대로 적용한다.

```
0  전제 검정          통과 (+0.4993, CI 0 제외)                        → 계속
1  EXISTING_SUFFICIENT  consistency ΔE = 0.0000 < 0.05,
                        partial = −0.0071 < 0.05                        → 불충족
2  DEDICATED_CONCEPT_JUSTIFIED
   (a) 축이 없는 기능 단계 확인                    1-2 의 4·5단계      → 충족
   (b) consistency 기준 미달                       ΔE·partial 둘 다     → 충족
   (c) 전제 검정 통과                                                   → 충족
```

**판정: `DEDICATED_CONCEPT_JUSTIFIED`**

`QX_S` 로 다시 봐도 결론이 같다 — 파이프라인 5축 중 0.05 를 넘는 것이 없고
`consistency` 는 음수다. 두 배터리에서 같은 결론이 나온다.

## 3. 해석

**3-1 Model A 의 후보 공간은 분석적으로 닫혀 있고, 그 안이 비어 있다.**
`E` 가 `attention·range_read·sizing_tell·adaptability` 넷의 함수이고 파이프라인
참여 축이 다섯뿐이므로, `E` 에 더할 수 있는 새 정보는 `consistency` 하나다.
그 하나가 두 배터리 모두에서 기준 미달이고 `QX_S` 에서는 부호가 반대다.
**나머지 43개는 어떻게 조합해도 상대 추정 파이프라인에 들어가지 않는다** —
이건 통계가 아니라 코드 구조다.

**3-2 빠진 것은 "해석의 정밀도"다.** 현재 모델에는
`see_*`(볼 수 있는가) → `use`(바꿀 의지가 있는가) 는 있는데 그 사이가 없다.
4단계 기준표는 전원 동일하고 5단계는 고정 뺄셈이다. 관측된 편차가
`0.80 vs 0.52` 일 때 그 차이를 **얼마나 정확히 크기로 환산하는가**를 가르는 축이
없다. Model B 의 `stat_read` 가 놓이는 자리가 정확히 여기다.

**3-3 `consistency` 를 Tier 5 게이트로 쓰면 안 된다.** 방향이 음수다.
높을수록 관측을 덜 믿는다 — 과신 억제이지 분석력이 아니다. 이걸 게이트로 쓰면
"통계를 잘 읽는 사람"이 아니라 "관측을 잘 안 믿는 사람"을 뽑게 된다.

**3-4 그런데 ESTIMATE 단계는 헤드룸이 거의 없다.** `QX_S` 자연 sd 가 **0.0140**
이다. 전 인구가 r ≈ 0.90 으로 진실을 따라간다. 최대 개입(2→8)이 0.02 를
움직이는데 이건 인구 sd 의 1.4배다 — **문턱 0.05 는 `QX_E`(sd 0.15)에 맞춘
값이라 `QX_S` 에는 지나치게 엄하다.** 인구 sd 기준으로 보면 `consistency` 는
−1.4 sd 로 작지 않다. 다만 **방향이 반대**라 판정은 바뀌지 않는다.
**따라서 이번 `DEDICATED_CONCEPT_JUSTIFIED` 는 효과 크기보다 1-1·1-2 의
코드 매핑에 더 크게 기대고 있다.** 그 점을 분명히 해 둔다.

**3-5 `adaptability` 를 Tier 5 축으로 승격하지 않는 근거가 하나 늘었다.**
`QX_S` 에서 `adaptability` 는 −0.0127 이다. `memory` 를 통해 표본을 늘리지만
추정 정확도를 올리지는 않는다. 분석 능력이 아니라 적용 의지라는 해석과 맞는다.

## 4. 아직 모르는 것

- **`QX_E`·`QX_S` 가 실제 칩 EV 와 연결되지 않았다.** 둘 다 내가 공개 정보로
  정의한 oracle 이다. 점수가 높은 봇이 더 버는지는 안 쟀다. **새 concept 을
  실제로 만들기 전에 이 대리변수부터 검증하는 것이 맞다.**
- **`QX_S` 의 문턱이 적절한지 모른다** (3-4). 인구 sd 가 0.014 인 척도에
  0.05 를 적용했다. 사전등록한 값이라 그대로 썼고 결론이 부호 때문에 안 바뀌지만,
  다음 판에서는 척도별 문턱을 따로 등록해야 한다.
- **5단계에 축을 넣으면 실제로 개선되는지 모른다.** `stat_read` 가 있었다면
  `QX_E` 가 올랐을 것이라는 것은 **가설**이다. 구현 없이 검증한 것이 아니다.
  Model B 를 채택한다면 그 검증이 첫 단계여야 한다.
- **1단계(관찰 기록)가 전원 동일한 것이 옳은 설계인지** 이번에 판단하지 않았다.
  실제 사람은 "무엇을 세는지"부터 다르다.
- 합성 `Book` 은 스트리트별 빈도를 동일하게 넣었다. 스트리트가 갈리는 표본에서
  `range_read` 의 역할이 더 클 수 있다 — 안 쟀다.

## 5. Model A / Model B 명세 (사전등록 2절, 변경 없음)

**Model A** `Q_A = E · _see(consistency)` — 이번 결과로 **기각**된다.
유일한 후보인 `consistency` 가 기준 미달이고 부호가 반대다.

**Model B** `stat_read` — 4·5단계 전용. 기준 대비 편차 `|obs − PRIOR|` 를 표본
크기와 함께 해석해 **조정량의 크기**를 정한다. 편차가 0 이면 출력에 영향 없음
(중립 조건). `attention`(관측·기억), `range_read`(스트리트·레인지),
`sizing_tell`(사이즈 지각), `adaptability`(의지), `consistency`(과신 보정)와
역할을 겹치지 않는다.

**구현 전제**: `persona.make_player` 가 `for k in LOADING.items(): rng.gauss(...)`
로 concept 마다 난수를 뽑고 **기질 draw 가 그 뒤에 온다.** `LOADING` 에 키를
더하면 이후 스트림이 전부 밀려 **모든 시드의 모든 플레이어가 바뀐다** —
지문 `d8e9271e…`, regression baseline 3세대, reachability reference,
V7 `c5` calibration 이 전부 무효가 된다. `stat_read` 만 pid 에서 유도한 **별도
RNG** 로 뽑으면 기존 스트림을 한 draw 도 건드리지 않는다. 이 방식이 전제다.

## 6. 다음 단계에서 정할 것

이번 결과만으로 V8 을 만들지 않는다. 사용자와 정할 것은 둘이다.

1. **`QX_E`/`QX_S` 를 칩 EV 로 먼저 검증할 것인가.** 과녁이 틀렸을 가능성을
   남겨둔 채 새 축을 만드는 것은 위험하다.
2. **`stat_read` 를 별도 RNG 로 추가할 것인가.** 추가한다면 V8 사전등록에서
   population calibration 을 처음부터 다시 해야 하고, 기존 V7 은 보존한다.

## 7. 재현

```
python3 tools/tier5_concept_stage_map.py
python3 tools/tier5_axis_validate.py --n 200 --mode control
python3 tools/tier5_axis_validate.py --n 200 --mode interv
python3 tools/tier5_axis_validate.py --mode partial --pop-glob 'pop_92*.json'
python3 tools/tier5_estimate_battery.py --n 200
```
