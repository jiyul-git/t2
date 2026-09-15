# ④ 분석축 인벤토리 (확정)

`entries=24 / hpl=12 / start_stack=30000`, 시드 8개, 플레이어 192명.
기본 분석 기준 `≥3` (민감도 `≥2`/`≥4` 병기).

---

## PRIMARY

가장 강한 근거가 있는 축들.

| 축 | 층 | 지표 | ρ | split r | n |
|---|---|---|---|---|---|
| `looseness` | 프리플랍 | `defend_tot` | **+0.760** | .950 | 191 |
| `looseness` | 프리플랍 | `open_pct` | **+0.677** | .982 | 192 |
| `aggression` | 프리플랍 | `defend_tp` | **+0.732** | .949 | 191 |
| `discipline` | 포스트플랍 | 이탈 지속벳 `f` | **−0.681** | .854 | 67 |
| `bluff` | 포스트플랍 | 블러프 분기 `f` | **+0.801** | .629 | 33 |
| `thin_value_turn` | 포스트플랍 | 밸류 `f` (`rel<0.85`) | +0.476 | .640 | 43 |
| `potcontrol` | 계획 | **라우팅 비율** | +0.454 | .713 | 182 |
| `cbet_flop` | 포스트플랍 | 이탈 지속벳 `f` | +0.131 | .744 | 29 |

**`cbet_flop` 은 단순 primary 증거로 쓰지 않는다.** ρ 가 약한데 `r` 은
높다(.744). 같은 분기에서 `discipline` 이 1.8배 넓은 레버로 지배하므로
**편상관을 반드시 병행한다** — 잠재3 + 동일 분기 축(`discipline`·
`aggression`·`bluff`) 통제 후에도 남는지로 판정한다.

`aggression` 은 프리플랍 `tp`(+0.732)가 포스트플랍 밸류 분기(+0.328)보다
훨씬 강하다. 층을 분리해서 싣는다.

---

## CONDITIONAL / EXPLORATORY

### 응답층 6축

| 축 | flop | turn | river | 기대 |
|---|---|---|---|---|
| `range_read` | **−0.394** | — | — | −1 ✓ |
| `potodds` | −0.263 | −0.145 | −0.233 | −1 ✓ |
| `bluffcatch_river` | — | — | −0.237 | −1 ✓ |
| `sizing_tell` | −0.210 | — | — | −1 ✓ |
| `hero_call` | −0.189 | −0.282 | −0.165 | −1 ✓ |
| `bluffcatch_early` | −0.122 | −0.160 | — | −1 ✓ |

```
split r   flop .207   turn .111   river .342
```

> **응답층에서 방향성 있는 cross-player association 이 관찰됐으나,
> 낮은 split-half reliability 로 인해 개인 수준 효과의 신뢰성은
> 제한적이다.**

`range_read` ρ = −0.394 를 **"개인별로 안정적인 `range_read` 성향이
확인됐다"로 읽으면 안 된다.** `r` = .207 이면 관측 가능 ρ 상한이
√.207 ≈ .45 라 실측이 상한 근처이고, 그만큼 개인 수준 추정은 불안정하다.

**이 낮은 `r` 은 시드로 못 고친다.** 시드는 플레이어 수를 늘리지
인당 관측(플랍 4.9건)을 늘리지 않는다. 인당 관측은 `hpl` 만 올리는데
그것은 스택 깊이 교란 때문에 버린 선택지다.

### 그 외

| 축 | 상태 | 근거 |
|---|---|---|
| `barrel_turn` | 조건부 | `≥3` 에서 n=19 (경계선). `≥2` 에서 n=46 r=.691 |
| `pf_defend` | 조건부 | `defend_tp` +0.079 / `defend_tot` −0.101 — 거의 0 |

---

## SECONDARY — 파생축 중복성 분석 (독립 primary 아님)

`hero_call` / `bluff_fear` / `station` / `sticky`.

```
hero_call  ↔ bluff_fear          -0.830     거의 완전한 거울상
bluff_fear ↔ bluffcatch_river    -0.777
bluff_fear ↔ range_read          -0.772
station    ↔ potodds             -0.606
station    ↔ sticky              +0.600
```

넷을 독립 가설로 세면 **같은 신호를 네 번 센다.**

**그러나 임의로 합쳐 하나의 "응답 성향" 축을 만들지도 않는다.** 코드에서
이 넷은 같은 의미의 축이 아니다 — `hero_call`(특정 콜 성향),
`bluff_fear`(블러프 공포), `station`(계속 따라가는 성향),
`sticky`(콜 지속성). 평균이나 PCA 로 새 축을 만들면 **코드에 없는 latent
construct 를 발명**하는 것이고, 프로젝트 원칙 2(임계값을 새로 발명하지
마라)와 어긋난다.

별도 **중복성/상관 구조 분석용 묶음**으로 둔다. 필요하면 나중에 잠재요인
분석으로 하나의 공통 응답 성분으로 설명되는지 검증하되, 그 결과로
새 축을 만들어 primary 가설로 삼지 않는다.

### `station` — 제외가 아니라 단독 해석 금지

ρ 부호가 기대와 반대로 나온다 (flop +0.155, 기대 −1). **예상 가능한
결과다** — `station` 식이 `potodds` 를 −0.30 가중으로 직접 읽고 실측
상관이 −0.606 이다.

```
station = potodds 와 교락된 파생축 → 단독 association 해석 금지
```

"죽었다"가 아니다.

### `sticky` — ρ≈0 이지만 레버 자체가 가장 얇다

`persona.call_bias` 안에서 네 파생축이 만드는 실제 계수 변화폭:

```
축           계수   clamp후 0   p95(날것)   최대효과   게이트
station      0.22     54.1%      0.573      12.6%    항상
bluff_fear   0.30     35.2%      0.616      18.5%    street×size 가중
draw_love    0.18     52.7%      0.477       8.6%    outs>0
sticky       0.12     60.8%      0.415       5.0%    made>=1
```

`sticky` 는 **필드의 60.8% 가 clamp 로 0 이고, `made>=1` 게이트가 걸리며,
계수가 0.12 로 넷 중 가장 작다.** 최대 효과가 5.0% 다.
ρ ≈ 0 은 발견이 아니라 **레버 폭으로 예측되는 값**이다.

---

## EXCLUDED

| 축 | 이유 |
|---|---|
| `blockbet` | **구조적 도달 불가.** `plan.py:448` 이 죽은 코드 — 456/458/461 의 `if/elif/else` 가 빠짐없이 덮어쓴다 |
| `barrel_river` | `≥2` 에서도 n=24 `r`=.394 (같은 기준 `cbet_flop` .647 의 절반). `≥3` 은 n=5 |
| `open_size` · `consistency` | split `r` = **.079** (n=153). 표본 부족이 아니라 **개인별 오픈 사이즈가 반복되지 않는다**는 신뢰할 만한 발견 |
| `pf_range` · `positional` | `open_pct` 가 `pf_range`·`positional`·`adapt_mult` 셋을 섞는다. n=192 에서 ρ −0.051 / −0.083. **축 고정 반사실**이 아니면 측정 불가 |
| `adaptability` · `attention` | `opp_est` 미누적 (`fieldsim` 이 `book` 을 안 넘겨 핸드마다 초기화) |
| `tilt_swing` · `tilt_stack` | 위약 축. **판정 바닥값으로만 사용** |

### 정정 — `range_read` / `sizing_tell` 은 제외가 아니다

`opp_est` 미누적을 이유로 제외했었다. **틀렸다.** `calldown_need` 의
`trust` 경로는 `opp_est` 가 아니라 호출부가 넘긴 `read` 를 쓴다.

```
648   if read is not None:
652       trust *= min(1.4, (0.6*sk('range_read') + 0.4*bc)/5.0)
656       stell = sk('sizing_tell') ...
659       trust *= (1.0 + 0.10*(stell-5.0)/5.0 * min(2.0, dev/0.4))
```

`persona.read_opponent` 만 보고 판단한 것이 성급했다. 두 축은
conditional 로 살아 있다.

`sizing_tell` 은 **절반만 잡힌다** — `_sz_seen` 경로(624행)는 `need_true`
안에 있어 나눗셈으로 지워지고 `trust` 경로만 남는다.

---

## `need_ratio` 의 clamp 왜곡 — 후속 분석 규칙

```
중앙 1.107   5% 0.588   25% 0.851   75% 1.366   95% 1.665
최소 0.478   최대 9.034
```

코드 클램프는 `need_true*0.55 ~ need_true*1.75+0.05` 인데 **최대가 9.034**
다. 작은 `need_true` 가 절대 상한(0.95)에 걸리면 비율이 폭발한다.

**`need_ratio` 를 그대로 평균·상관에 넣지 않는다.** 새 cutoff 를 만들지
말고, **코드가 실제로 발생시킨 clamp 여부를 이진 플래그로 기록**해
상관이 clamp 로 만들어졌는지 가른다. `need_true` 크기도 같이 싣는다.
