# ⑤ 반사실 개입 결과 — Level 1 (실행 층)

`CF_DESIGN.md` 명세. `RESULT_AXIS.md` 는 그대로 보존한다.

---

## 0. 범위 — 이것이 무엇을 재고 무엇을 안 재는가

**Level 1 은 `decide_aggression`(무저항 공격 확률)과 프리플랍 임계값
두 지점만 개입한다.** 계획(`plan`)은 고정한 채, 같은 계획·같은 상황에서
축만 바꿨을 때 최종 행동이 바뀌는지를 본다.

```
측정한다      계획이 동일하게 주어진 상태에서 축이 최종 행동을 바꾸는가
측정 안 한다   축을 바꿨을 때 계획 자체가 바뀌는가 (Level 2, 별도 실험)
              하류 전파 (한 결정의 효과만 격리)
```

### 소비처 커버리지 — **전 소비처를 덮지 못한다**

`tools/axis_sites.py` 기준.

| 축 | 총 소비처 | Level 1 이 덮는 것 | **덮지 못한 주요 경로** |
|---|---|---|---|
| `looseness` | 5 | `open_pct` · `defend_thresholds` | `reads:perceived_profile` |
| `discipline` | 3 | `decide_aggression` | **`decide_response`** |
| `bluff` | 17 | `decide_aggression`×2 | `decide_response`×2 · `make_plan`×4 · `line_bluff_prior` |
| `aggression` | 22 | `defend_thresholds`(tp) · `decide_aggression` | **`persona:open_pct`** · `make_plan`×2 · `calldown_need` · `decide_response` · `opp_bet_prob` |

**따라서 아래 수치는 축의 전체 인과 영향력이 아니라 `decide_aggression`
층에서의 영향력이다.** `aggression` 은 `open_pct` 경로가 `SITE` 표에서
빠져 프리플랍 효과도 `defend_tp` 만 잡혔다.

---

## 1. 실행 조건과 검증

```
entries=24 · hpl=12 · start_stack=30000 · 시드 5000–5054 (55개)
포스트플랍 결정 31,189건 (축마다)   프리플랍 호출 100,306 / 147,676건
엔진 오류 0건
```

### 불변량

Level 1 은 **구조적으로 보장된다.** `decide_aggression` 에 상황 입력
(board·rel·n_opp·oop·initiative·outs·plan_state)을 세 팔에 동일하게
넘기므로 위반이 발생할 수 없다. 검사가 필요한 것은 Level 2 다.

### RNG 정렬

```
decide_aggression 의 rng 소비 횟수 = 0   ← CountRandom 래퍼로 실측
세 축 전부 RNG 정렬 100%
```

**가정하지 않고 쟀다.** 0 이므로 같은 주사위 눈(CRN)을 세 팔에 쓰는 것이
구조적으로 보장된다. `rng_shifted` 케이스가 한 건도 없다.

### 위약 결정론

```
_rand_A   POST 1,197 결정에서 f 변화 0건 / action flip 0건
          PRE  12,011 호출에서 변화 0건
```

⑤의 위약은 결정론적이라 정확히 0 이어야 한다. 통과했다 — 개입 코드가
프로필 사본을 잘못 만들어 생기는 가짜 효과는 배제된다.

### plan flip

**측정하지 않았다.** Level 2 미구현.

---

## 2. 포스트플랍 결과 (주지표 = action flip)

```
축            결정      f(1)     f(9)   action flip   방향             |Δ|>0.01
aggression   31,189   0.215 →  0.439      9.2%     ↑16,181 / ↓0       50.9%
discipline   31,189   0.337 →  0.185      4.3%     ↑0 / ↓4,217        13.5%
bluff        31,189   0.246 →  0.297      3.5%     ↑6,098 / ↓0        19.4%
looseness         0      —        —         —      소비처 없음           —
```

**역방향이 정확히 0건이다.** 세 축 모두 완전 단조다.
④에서 관측한 방향과 전부 일치한다 (`aggression` +, `discipline` −,
`bluff` +).

`looseness` 의 POST 0 은 실패가 아니다 — `decide_aggression` 이 그 축을
읽지 않는다. **`SITE` 매핑이 맞았다는 검증이다.**

---

## 3. 프리플랍 결과

```
축          지표          호출      중앙(1)   중앙(9)   배율     |Δ|>0
looseness   defend_tot   100,306   0.1479   0.3476   2.35×    100%
looseness   open_pct     147,676   0.1665   0.3069   1.84×     86%
aggression  defend_tp    100,306   0.0356   0.0710   2.00×    100%
```

`looseness` 는 `defend_tot` 의 **모든 호출**에서 값이 변한다.
④의 관측(ρ +0.830, r .976)과 일관된다.

`open_pct` 에서 14% 가 안 변하는 것은 `gto.rfi` 기준값이 0 이거나
clamp 에 걸리는 포지션·스택 구간으로 보인다 — 확인하지 않았다.

---

## 4. 사전 예측과 실제 결과 — **예측이 틀렸다**

`CF_DESIGN.md` 4절에 측정 전 적어둔 것:

> `aggression` 은 통제 후 값이 절반 이하로 줄었으므로 **개입 효과가
> 관측 ρ 보다 작을 것으로 예상**한다.

실제는 반대다.

```
축            통제 후 ρ (④)    action flip (⑤)
aggression      +0.338            9.2%   ← ρ 최소, 개입 효과 최대
discipline      −0.811            4.3%
bluff           +0.512            3.5%
```

**세 축 중 통제 후 ρ 가 가장 작은 `aggression` 이 개입 효과는 가장 크다.**
순서가 완전히 뒤집혔다.

**예측은 수정하지 않는다.** 결과를 보고 설명을 바꾸면 반사실 검증이
아니게 된다.

### 왜 뒤집혔나 — ρ 와 개입효과는 다른 것을 잰다

```
ρ               플레이어 간 축 차이와 행동 차이가 얼마나 함께 움직이는가
개입효과         같은 상황에서 축만 바꿨을 때 행동이 얼마나 바뀌는가
```

그리고 여기에 **분기 도달률**이 들어간다.

```
aggression   밸류 분기 + pot_control 분기 (가장 흔한 경로)   |Δ|>0.01  50.9%
bluff        블러프 계획 분기만                              19.4%
discipline   giveup/showdown 이탈 분기만                     13.5%
```

`aggression` 은 개별 분기에서의 변화가 아주 크지 않아도 **도달하는
결정이 많아** 전체 action flip 이 커진다. `discipline`·`bluff` 는 관측
ρ 가 더 커도 좁은 분기에만 영향을 주므로 전체 flip 이 작다.

> **축의 "관측 가능성" 과 축의 "개입 영향력" 은 별개의 축이다.**

이것이 이번 실험의 가장 중요한 결론이다.

---

## 5. 주장의 범위

**말할 수 있는 것**

> 동일 상황과 동일 실행 조건에서 해당 축만 개입했을 때 행동이
> **결정론적으로** 변화했으며, 이는 해당 축의 **execution-layer causal
> influence** 에 대한 강한 반사실적 증거다.

**단, 0절의 커버리지 범위 안에서다.** Level 1 은 네 축 어느 것도 전
소비처를 덮지 못한다 — `discipline` 은 `decide_response` 가, `bluff` 는
`make_plan`·`decide_response` 가, `aggression` 은 `open_pct`·
`calldown_need`·`make_plan` 이 빠져 있다.

**말하지 않는 것**

- "인과효과가 증명됐다" 가 아니다. `decide_aggression` 층에서의
  반사실적 증거까지다
- 계획 층의 인과는 못 봤다 (Level 2)
- 하류 전파는 못 봤다 — 한 결정의 효과만 격리했다
- 축을 1↔9 로 흔드는 것은 필드 실재 범위를 넘을 수 있다.
  실제 필드 분포에서의 효과크기와 구분해야 한다
- `entries=24 / hpl=12 / stack=30000` 조건이다

---

## 6. Level 2 를 지금 붙이지 않는 이유

Level 2 는 질문이 하나 더 붙는다 — *"축을 바꾸면 계획 자체가 바뀌는가"*.
그러면 `make_plan` 의 RNG 단축 평가, 게이트, `refresh` 가 한꺼번에
들어와 **이번에 확인한 순수한 실행 층 효과와 실험 구조가 섞인다.**

`aggression` 의 결과(9.2% flip, 역방향 0건, |Δ|>0.01 50.9%)가 이미
명확하므로 먼저 고정한다. Level 2 는 **별도 설계 후 진행**한다.

우선 보강할 것은 Level 2 보다 **커버리지**일 수 있다 — `SITE` 표에
`aggression → open_pct` 를 넣고 `decide_response` 층을 추가하면 같은
Level 1 구조로 범위를 넓힐 수 있다.
