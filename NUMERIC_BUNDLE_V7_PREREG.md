# NUMERIC_BUNDLE_V7 — 사전등록

기준: `claude/v7-tier` `653c2fc`. 브랜치 `claude/v7-num-validation`.
선행: `HIERARCHICAL_READ_V7_PREREG.md` · `HIERARCHICAL_READ_V7_RESULT.md`

작성 시점: **코드 전수 추적 직후, 측정 코드 실행 전.**

## 0. 목적과 금지

V7 의 `NUMERIC` 6개가 실제로 **정량적 상대 익스플로잇 능력**을 나타내는지 본다.

```
NUMERIC = (range_read, potodds, spr, blocker, fold_equity, board_texture)
num = mean(sk(c)/10 for c in NUMERIC)        Q = E · num
```

**금지**

- production / LIVE wiring 금지. `plan.py` · `persona.py` 판단 로직 무수정.
- `c5 = 0.7087277777777778` 변경 금지. `c1/c2/c3` 및 tier 경계 변경 금지.
- V7 결과를 좋게 만들기 위한 재튜닝 금지. **이번 결과로 6개 가중치를 사후
  fitting 하지 않는다.**
- **`Q` · tier 번호 · tier5 활성 빈도를 종속변수로 쓰지 않는다.** 6개가 이미
  `Q` 정의 안에 있으므로 순환논증이다.
- target 의 hidden profile / concepts 사용 금지. oracle 은 **공개 `opp_est` 와
  게임 상태에서만** 계산한다.
- 결과를 본 뒤 문턱을 바꾸지 않는다. 중간 결과가 나와도 이 문서를 고치지 않는다.

## 1. 코드 전수 추적 (측정 전, 완료)

`tools/v7_num_concept_trace.py` 로 선언을 뺀 사용처를 전수 수집했다.
"OPP" 는 그 사용처를 감싸는 함수가 상대 추정치(`opp_est` / `read_opponent` 결과)를
만진다는 뜻이다. 최종 판별은 식을 직접 읽어서 했다.

| concept | 사용처 | 대표 지점 | 식이 **상대의 수치**를 곱하는가 |
|---|---:|---|---|
| `range_read` | 9 | `plan.calldown_need:679` `trust *= (0.6·rr + 0.4·bc)/5` | **예** — `read` 기반 문턱 조정의 신뢰도 |
| `fold_equity` | 5 | `plan.decide_aggression:917` `p *= 1 + _fe·_rdf['w']·2.2·_fg` | **예** — `street_gap(read_opponent())` 을 직접 곱한다 |
| `potodds` | 4 | `plan.calldown_need:666` `need *= calc_noise(prof,'potodds')` | 아니오 — 자기 팟오즈 계산 오차 |
| `spr` | 13 | `plan.make_plan:301` · `target_commit:1957` · `preflop.open_form:234` | 아니오 — 자기 스택 깊이 역산 |
| `blocker` | 3 | `plan.make_plan:285` · `river_fix:1620` | 아니오 — 자기 카드가 막는 콤보 |
| `board_texture` | 8 | `plan.decide_aggression:928` `p *= 1 + 0.75·_tce·_bt` | 아니오 — 보드 자체의 성질 |

**중복 경로 — 측정 전에 기록한다.**

`range_read` 는 이미 `E` 안에 있다.

```
persona.read_resolution:869   see_line = _see(sk(prof, 'range_read'))   → E 의 obs_mean · obs_min
reads.obs_from_profile:29     skill = (0.5·att + 0.3·rr + 0.2·st)/10    → perceived_profile 노이즈
reads.TIER_V7_NUMERIC         num                                        → Q
```

즉 `Q = E · num` 에서 `range_read` 가 **양쪽에 들어간다.** `sizing_tell` 도
`see_size` 로 `E` 에 있고 `calldown_need:684` 에서 상대 사이즈를 해석하지만
`NUMERIC` 에는 없다 — 역할이 `range_read` 와 대칭인데 취급이 다르다.
`attention`(→`see_freq`)·`adaptability`(→`use`)는 `E` 전용이라 `NUMERIC` 후보와
역할이 겹치지 않는다.

**코드베이스에 이미 있는 '익스플로잇 능력' 식 두 개.** 가설의 근거로만 쓴다.

```
persona.exploit_weight:826           (0.50·adaptability + 0.30·range_read + 0.20·attention)/10
money_pressure.exploit_realization:166  mean(money_jump, fold_equity, range_read,
                                              attention, adaptability, aggression)
```

둘 다 `range_read` 를 넣고 `exploit_realization` 은 `fold_equity` 도 넣는다.
**둘 다 `potodds`·`spr`·`blocker`·`board_texture` 를 넣지 않는다.**

**코드 읽기만으로 결론 내지 않는다.** 위는 가설이고 아래 측정으로 판정한다.

### 1-1 사전 선언 가설 (ablation 의 묶음 정의로 쓴다)

```
DIRECT  = (range_read, fold_equity)        식이 상대의 수치를 곱한다
SUPPORT = (potodds, spr, blocker, board_texture)   자기 계산 정확도
```

이 분류는 **코드 경로에서 나온 것이고 측정 결과로 바꾸지 않는다.**

## 2. 독립 과제 배터리 — `Q` 와 무관한 종속변수

봇의 판단을 **production 진입점 두 개**로 직접 부른다. 핸드를 돌리지 않는다.

```
PL.decide_aggression(...)   무저항에서 칠 확률 p      — 공격 쪽 판단
PL.calldown_need(...)       콜 문턱 need              — 수비 쪽 판단
read = PS.read_opponent(profile, opp_est)             파이프라인 전체를 태운다
```

각 과제군은 **격자**다. 격자 위에서 공개 정보만으로 계산한 oracle 과 봇 응답의
**Pearson r** 을 점수로 쓴다.

```
score(family) = r( bot_response , oracle_response )     ∈ [−1, 1]
QX_E = mean(F1..F6)        상대 정보가 변하는 배터리
QX_G = score(G)            상대 정보가 고정된 대조 배터리
```

**왜 상관인가.** 봇이 상대를 아예 안 보면 r ≈ 0 이다. 그리고 oracle 이 격자 위에서
**부호가 바뀌도록** 설계했으므로, 단순히 더 치거나 더 접는 쪽으로 수준만 옮기는
봇도 r 이 오르지 않는다. 사용자가 지적한 "행동량만 늘리는지"를 이 지표가 가른다.
수준 변화는 `mean(bot_response)` 로 따로 기록해 같이 본다.

### 과제군

| 군 | 격자에서 변하는 것 | oracle (공개 정보만) | 봇 응답 |
|---|---|---|---|
| F1 frequency | `ftb` 0.20→0.80 | `ftb` 자체 (폴드 많이 하면 많이 쳐라) | `decide_aggression` p |
| F2 street/line | `ftb_turn` 을 흔들고 `ftb_flop` 은 반대로 | `ftb_turn` (해당 스트리트만) | 턴에서의 p. **판별 점수** `r(p, ftb_turn) − r(p, ftb_flop)` |
| F3 sizing | `sz_mean` · `sz_sd` · `sz_big`, 직면 사이즈 고정 | `z = (size_now − sz_mean)/max(sz_sd, 0.05)` (그 사람 기준 이례성) | `calldown_need` need |
| F4 sample | 같은 관측률에 `n` 2→64, `confidence` 연동 | 베이즈 수축 `post = (n·obs + 12·prior)/(n+12)` 의 prior 대비 편차 | p 의 기준선 대비 편차 |
| F5 price/SPR | `pot`·`tocall`·스택 | `need_oracle = tocall/(pot + tocall)` | `calldown_need` need |
| F6 texture×freq | 보드 건조/습윤 × `ftb` | `ftb ·(건조=+1 / 습윤=−1 가중)` | `decide_aggression` p |
| **G 대조** | `opp_est` 를 **모집단 prior 로 고정**, 자기 에퀴티·가격만 변화 | `equity − need_oracle` | `need` 대비 콜 여유 |

- `12` 는 production `data = conf·min(1, n/12)` 의 앵커다. 새 상수가 아니다.
- `0.05` 하한은 `sz_sd` 의 0 나눗셈 방어다.
- F4 의 prior 는 `reads.PRIOR` 를 쓴다. 새 값을 만들지 않는다.
- 배터리 RNG 시드는 `20260924` 로 고정한다. 모든 arm 이 같은 스트림을 본다.

## 3. 검증 방식 두 가지

### A. paired intervention

기저 프로필을 뽑아 **concept 하나만** `2.0 ↔ 8.0` 으로 바꾸고 나머지는 전부
고정한다. 같은 배터리·같은 RNG 시드로 `QX_E` 와 `QX_G` 를 각각 잰다.

```
ΔE(c) = QX_E(c=8) − QX_E(c=2)
ΔG(c) = QX_G(c=8) − QX_G(c=2)
Δlevel(c) = mean(bot_response)(c=8) − mean(bot_response)(c=2)     행동량만 늘었는지
군별 ΔE 도 같이 낸다 — 무관한 과제군까지 건드리는지 본다
```

기저 프로필: 시드 `910001..910004` 의 400인 필드에서 **200명** 추출
(hero 제외, 결정적 추출). 쌍 200개.

`2.0`/`8.0` 은 `read_resolution._see` 의 양 끝 앵커(2 에서 0, 8 에서 1)다.
새 값이 아니다.

### B. 자연 생성 population

`Q` 와 tier 를 쓰지 않는다. 각 봇의 자연 concept 값으로 `QX_E` 를 직접 잰다.

```
fit     시드 920001..920020 (400인 필드)     — 상관·부분상관 관찰용
holdout 시드 930001..930020                  — 확인용. 적합하지 않는다
```

**parameter fitting 을 하지 않는다.** fit 집합에서는 상관·부분상관만 보고,
holdout 에서는 **사전 지정된** 가중 조합만 비교한다.

부분상관: concept `c` 와 `QX_E` 의 상관에서 `E` 의 입력 네 개
(`see_freq`, `see_line`, `see_size`, `use`)를 통제한다. `E` 가 이미 담고 있는
것을 `num` 이 다시 담는지 본다.

## 4. 판정 규칙 — 결과 보기 전에 고정

통계: 쌍 200개의 부트스트랩 95% 신뢰구간, 2,000회 재표본, 시드 `20260924`.

**문턱 `0.05`** — `QX` 는 [−1, 1] 범위의 상관이다. 쌍 200개에서 상관차의
부트스트랩 SE 가 대략 0.01~0.02 이므로 0.05 는 약 3 SE 이고 전체 범위의 2.5% 다.
"노이즈보다 확실히 크되 실질적으로 작은" 지점으로 잡는다.

**비율 `2배`** — 상대 정보가 변하는 배터리에서의 개선이 상대 정보가 없는 대조
배터리에서의 개선보다 최소 2배는 되어야 "상대 익스플로잇 축"이라고 부른다.

판정은 **순서대로** 적용한다.

```
1  GENERAL_SKILL_ONLY : ΔG >= 0.05 (CI 0 제외)  AND  ΔE < 0.05
2  UNSUPPORTED        : ΔE < 0.05  AND  ΔG < 0.05
3  REDUNDANT          : ΔE >= 0.05 (CI 0 제외)  AND  부분상관 < 0.05
4  KEEP_DIRECT        : ΔE >= 0.05 (CI 0 제외)  AND  ΔE >= 2·max(ΔG, 0)  AND  부분상관 >= 0.05
5  KEEP_SUPPORT       : 그 외 (ΔE >= 0.05, CI 0 제외, 부분상관 >= 0.05)
```

## 5. equal-weight 검증 (최적 가중 찾기 아님)

holdout 에서 아래 조합의 `num` 과 `QX_E` 의 상관만 비교한다. **적합하지 않는다.**

```
현재          6개 동일가중 평균
leave-one-out 6가지
single-axis   6가지
DIRECT 묶음   (range_read, fold_equity) 평균
SUPPORT 묶음  (potodds, spr, blocker, board_texture) 평균
+sizing_tell  현재 6개 + sizing_tell (1절의 대칭성 가설 확인용)
```

목적은 **현재 평균이 명백히 잘못됐는지** 확인하는 것이다. 더 나은 가중을 찾아
채택하는 것이 아니다.

**과대평가 구조 점검** — 한두 축만 높아도 `num` 이 올라가는지:
`num` 과 `max(concept)` / `min(concept)` 의 상관을 같이 낸다.

**skill proxy 점검** — `num` 이 사실상 전반 포커 실력 대리변수인지:
`overall = mean(sk(c) for c in persona.CALC)` 를 만들어
`r(num, overall)` 과 `r(num, QX_E)` 를 비교한다. 전자가 후자보다 크게 높으면
`num` 은 exploit 축이 아니라 실력 대리변수다.

## 6. 이번 판에서 하지 않는 것

- `c5` 재적합 금지. tier 5 를 다시 3~4명/400명으로 맞추는 작업 금지.
- `NUMERIC` 정의 변경 금지. 바뀌어야 한다는 결론이 나오면 **결론만 기록**하고
  기존 V7 은 그대로 보존한다. 정의 변경은 새 V8 / V7-A2 사전등록에서 하고
  그때 population calibration 을 처음부터 다시 한다.
- `n↑ → data↑ → detail 비중↑` 를 "detail 이 prior 보다 정확하다"로 쓰지 않는다.
  그것은 **식이 의도대로 도는가**의 구조 검증이었다.

## 7. 산출물

```
NUMERIC_BUNDLE_V7_PREREG.md          이 문서
tools/v7_num_concept_trace.py        코드 경로표
tools/v7_num_battery.py              독립 과제 배터리 + oracle
tools/v7_num_intervention.py         paired intervention
tools/v7_num_population.py           자연 population fit/holdout + ablation
NUMERIC_BUNDLE_V7_RESULT.md          결과 — 사실 / 사전등록 판정 / 해석 / 아직 모르는 것 분리
```

**"tier5 가 3~4명 나왔으니 NUMERIC 이 맞다" 는 결론은 쓰지 않는다.**

## 8. 실행 안전

- 무한 polling loop 금지. 모든 장기 실행에 `timeout` 과 상한.
- detach 된 작업의 완료를 파일 하나에 무한 대기하지 않는다.
- 종료 시 **커널 스레드를 제외한 전체 사용자 프로세스**를 확인한다.
  현재 셸 grep 만으로 끝내지 않는다.
- 최종 보고 전에 작업트리 clean · local=remote · 남은 실험 프로세스 0 을 실제로 검증한다.
