# ④ 관측 지표 정의서 — personality → 장기 기본 행동 성향

**측정 전에 확정한다.** 지금까지 두 번, 지표를 먼저 정의하지 않아서
임계값 artifact 가 나왔다 (블러프 일관성 6개 태그 중 4개, `my_pctile` 퇴화).

---

## 0. 질문

> **같은 성격축을 가진 플레이어가 실제 관측 행동에서도 예측 가능한
> 방향성을 보이는가?**

"플레이어별 행동 분산이 큰가"가 **아니다.** 제각각이기만 한 것은
좋은 결과가 아니다. 축 값을 알면 그 사람의 관측 행동을 얼마나
좁힐 수 있는가가 질문이다.

---

## 1. 이번 라운드가 측정하지 않는 것

**고정된 personality → 장기 기본 행동 성향**으로 한정한다.

`fieldsim` 은 `play.Hand(...)` 에 `book` 을 넘기지 않는다
(`fieldsim.py:225`). `play.py:35` 가 `book is None` 이면 새 `reads.Book()`
을 만들므로 **리딩 장부가 핸드마다 초기화된다.** `tourney` 는 대회 단위로
넘긴다(`tourney.py:120`) — 두 드라이버의 차이다.

그래서 "이 사람은 나를 어떻게 읽고 대응하는가"(기억·적응)는
이번 범위 밖이며 ⑤급 별건으로 분리한다. 구체적으로 `opp_est` 누적에
의존하는 경로가 여기 해당한다:

```
persona.read_opponent → see_freq / see_size / street_gap / exploit_weight
plan.cbet_freq 의 opp_est 블렌드
plan.calldown_need 의 trust 블록
```

`range_read`·`sizing_tell`·`adaptability`·`attention` 은 이 경로에
얹혀 있다. **파일럿에서 `opp_est` 가 실제로 얼마나 채워지는지 먼저 재고,
비어 있으면 이번 라운드에서 제외한다** (측정 불가를 "축이 죽었다"로
읽지 않기 위해서다 — `probe`/`delayed_cbet` 에서 한 번 겪었다).

---

## 2. 공통 규칙

1. **분모는 핸드가 아니라 기회다.** "c-bet 빈도"는 c-bet 할 자리에
   섰던 횟수로 나눈다. 핸드 수로 나누면 참가율이 섞인다.
2. **공동 구동축을 축마다 명시한다.** 단변량 ρ 는 공동 구동축의
   분산에 희석된다. 희석을 오독하지 않으려면 목록이 먼저 있어야 한다.
3. **`concepts` 는 독립 축이 아니다 — 3인자 모형이다.** `persona.py:195`
   의 `LOADING` 이 36개 개념을 `study`·`aggro`·`exp` 의 선형결합 + 개별
   노이즈로 만든다. 단변량 ρ 만으로 축에 효과를 귀속시키면 안 된다.
   **4절 (0) 의 3단 분해를 쓴다.**
4. **중간값을 같이 기록한다.** `max(0.0, bias(...))` 로 축의 절반이
   잘리는 자리가 있다 (`looseness` 하위 절반, `discipline` 상위 절반).
   최종 빈도만 보면 '무반응'으로 오독한다.
5. **스트리트 도메인을 지킨다.** `bluffcatch_early` 는 플랍·턴,
   `bluffcatch_river` 는 리버. `overbet` 은 플랍에서 `return None`.
6. **단조 ↑ 를 기본 가정으로 두지 않는다.** `potcontrol` 은 이미
   스위치임이 확인됐다 (PS.sk 3.33 게이트 위에서 기울기 0). 축마다
   기대 형태(단조/계단/반응성)를 적는다.
7. **기회 수가 적은 플레이어를 평균에 같은 무게로 넣지 않는다.**
   기회 수로 가중하거나 하한을 두되, 하한은 파일럿이 정한다.

---

## 3. 축별 정의

기대 형태: ↑ 단조증가 · ↓ 단조감소 · ⌐ 계단(게이트) · ⇄ 반응성(기울기 차)

### 3.1 프리플랍

| 축 | 관측 지표 | 분모(기회) | 기대 | 공동 구동축 |
|---|---|---|---|---|
| `looseness` | VPIP | 프리플랍 자발 액션 기회 (BB 무저항 워크 제외) | ↑ | `pf_range`·`positional`·`adapt_mult` (`open_pct`), `pf_defend` (`defend_thresholds` **tot**) |
| `looseness` | BB defend | BB 에서 오픈 직면 | ↑ | 같음 |
| `aggression` | PFR | 프리플랍 자발 액션 기회 | ↑ | `open_pct` 3축 |
| `aggression` | 3bet | 프리플랍에서 레이즈 직면 | ↑ | `pf_defend` (`defend_thresholds` **tp**) |
| `pf_range` | VPIP | 위와 같음 | ↑ | `positional`·`adapt_mult` **9 고정 필요** |
| `open_size` | 오픈 사이즈 중앙값(bb) | 무저항 오픈 | ↑ | `consistency` |

`defend_thresholds` 는 `(tp, tot)` 를 낸다. `aggression` 은 `tp`(3벳 구간),
`looseness` 는 `tot`(참가 구간)에만 걸린다. **둘 다 기록한다.**

### 3.2 포스트플랍 공격 — `decide_aggression` 의 분기부터 본다

**`plan.py:838` `decide_aggression` 이 벳 확률을 정하는 유일한 지점이고,
계획 라벨에 따라 분기가 완전히 갈린다.** 분기를 무시하고 "c-bet 빈도"
하나로 재면 축이 없는 경로까지 분모에 들어간다.

```
giveup / showdown + 이니셔티브   → cbet_freq(...) × max(0.05, 1−0.085·discipline)
trap                             → 0.0
bluff_2street/semibluff/river_bluff
                                 → 0.25 + 0.070·bluff + 0.02·gamble
                                    × fold_equity · board_texture · multiway
                                    · probe(동크 억제) · delayed_cbet
block                            → 0.35 + 0.055·blockbet
pot_control                      → 0.18 + 0.035·aggression   (rel<0.30 이면 0.04)
밸류 계획                         → 0.30 + 0.058·aggression + 0.018·gamble
                                    × (0.55 + 0.09·thin_value_{street})   ← rel<0.85
                                    × value 스타일(xr 0.68 / lead 1.12) × rel 곡선
```

**`cbet_freq` 호출부는 `plan.py:863` 하나뿐이고 그 자리는 `giveup`/`showdown`
분기다.** 즉 `cbet_flop`·`barrel_turn`·`barrel_river` 가 사는 곳은
**이탈 지속벳 자리 하나**이지 c-bet 일반이 아니다. 실제 c-bet 의 대부분은
밸류·블러프 분기에서 나오고 그 경로에 이 세 축은 등장하지 않는다.

`tools/axis_sites.py` 가 `cbet_flop 1건 → plan:cbet_freq` 로 이미 찍어줬는데,
그 1건이 **어느 분기 안인지**를 연결하지 않아 분모를 잘못 잡을 뻔했다.

| 축 | 관측 지표 | 분모 | 기대 | 공동 구동축 |
|---|---|---|---|---|
| `cbet_flop` | 플랍 벳 | 플랍 이니셔티브 **+ 계획 `giveup`/`showdown`** | ↑ | `aggression`·`bluff`·`multiway`·`board_texture`·`discipline` |
| `barrel_turn` | 턴 벳 | 턴에서 같은 조건 | ↑ | 같음 |
| `barrel_river` | 리버 벳 | 리버에서 같은 조건 + `river_fix` 경로 | ↑ | 같음 |
| `discipline` | 위 분모에서의 벳 | 같은 분모 | ↓ | `cbet_freq` 전체 |
| `multiway` | n_opp 1→2→3 감소 **기울기** | 위 분모 + 블러프 분기, n_opp 로 층화 | ⇄ | 같음 |
| `board_texture` | 건조/젖은 보드 **차이** | 같음, 텍스처로 층화 | ⇄ | 같음 |
| `bluff` | 블러프 계획에서의 벳 | 계획이 `bluff_2street`/`semibluff`/`river_bluff` | ↑ | `gamble`·`fold_equity`·`probe`·`delayed_cbet` |
| `blockbet` | 벳 | 계획이 `block` | ↑ | 없음 — 단독 축 |
| `thin_value_turn` | 벳 | **플랍·턴** 밸류 계획 + `rel < 0.85` | ↑ | `aggression`·`gamble`·`value` 스타일 |
| `thin_value_river` | 벳 | 리버 밸류 계획 + `rel < 0.85` | ↑ | 같음 |
| `aggression` | 벳 | 밸류 계획 전체 / `pot_control` 계획 | ↑ | `gamble`·`thin_value_*` |

`street_concept` 이 `('thin_value','flop') → 'thin_value_turn'` 으로 보낸다
(`persona.py`). **`thin_value_turn` 은 턴 전용이 아니라 플랍+턴 전체**이고
배수가 `0.55 + 0.09·sk` 라 축 0→9 에서 2.6배 스윙이다 — 셋 중 표본이 가장 넉넉하다.

`multiway`·`board_texture` 는 절대 빈도가 아니라 **층 간 차이**다.
`f *= (0.80 − 0.30·multiway)^(n_opp−1)` 이므로 축이 커지면 다인원에서
더 많이 줄어야 한다. 빈도 하나로는 안 보인다.

**각 분기의 반환 확률 `f` 를 그 자리에서 같이 기록한다** (4절 (0-b)).
`barrel_river` 는 분모가 토너당 한 자릿수라 실현 행동으로는 영구히 못 잰다.

### 3.3 응답

| 축 | 관측 지표 | 분모 | 기대 | 비고 |
|---|---|---|---|---|
| `reraise` | 포스트플랍 raise | 포스트플랍에서 벳 직면 | ↑ | `decide_response` 전용 5곳 — 비교적 깨끗 |
| `potodds` | fold 율 | 벳 직면 | ↓ | **`station` 과 분리 불가** (`station` 식이 `potodds` 를 −0.30 가중으로 읽는다). ∩ 모양이 나와도 artifact 로 보지 말 것 |
| `bluffcatch_early` | 플랍·턴 call 율 | 플랍·턴 벳 직면 | ↑ | 리버에서 재지 말 것 |
| `bluffcatch_river` | 리버 call 율 | 리버 벳 직면 | ↑ | 계수 비대칭 — 하위 절반만 실질 작동 |
| `stackoff` | 올인/커밋 도달 | 큰 팟 직면 | ↑ | 집계 %가 아니라 **전환 수**로 센다 |

### 3.4 계획 층

| 축 | 관측 지표 | 분모 | 기대 | 비고 |
|---|---|---|---|---|
| `bluff` | — | — | — | **3.2 로 옮겼다.** `giveup` 은 블러프 분기가 아니라 `cbet_freq` 분기다 |
| `semibluff` | `semibluff` 계획 비율 | 드로우 보유 포스트플랍 계획 | ↑ | 드로우 강도(`outs`)를 층화해야 한다 — 확률식이 `0.25 + 0.24×개념` 이라 8아웃과 13아웃이 같이 굴려진다 |
| `potcontrol` | `pot_control` 계획 비율 | 포스트플랍 계획 | ⌐ | **단조 아님.** PS.sk 3.33 아래 0 / 위 평탄. 1–3 vs 4–9 계단으로 본다 |
| `trap`·`checkraise_flop` | 체크레이즈 비율 | 플랍에서 체크 후 벳 직면 | ↑ | `trap_judgment` 공유 |
| `thin_value_turn` | — | — | — | **3.2 로 옮겼다.** `rel < 0.85` 가 코드의 구간이다 (`plan.py:940`). 새로 발명하지 않았다 |

### 3.5 실행 층

| 축 | 관측 지표 | 분모 | 기대 | 비고 |
|---|---|---|---|---|
| `discipline` | deviation 비율 | 계획이 있는 포스트플랍 액션 | ↓ | `intents[].dev` 로 센다. `pot_control` 벳은 이탈이 아니다 (SIZING 0.30) |
| `equity_denial` | 벳 사이즈 | 벳 | ↑ | 두 번 희석 + 100칩 반올림. **중앙값으로는 안 보인다** — 금액이 달라지는 비율로 본다 |
| `overbet` | 발동 **확률** | 리버 벳 (플랍은 `return None`) | ↑ | 실현 빈도로 재지 말 것 |

### 3.6 이번 라운드 보류 (`opp_est` 의존)

`range_read`·`sizing_tell`·`adaptability`·`attention`.

측정한다면 **빈도가 아니라 반응성**이다 — "잘 읽는다"는 행동량이 아니라
정보가 바뀌었을 때 행동이 적절히 바뀌는가다.

```
sizing_tell   상대 벳 소(<0.5팟) vs 대(>0.8팟) 에서의 fold 율 차이
range_read    레인지 우위 보드 vs 열위 보드 에서의 continue 율 차이
```

축이 클수록 **두 층의 차이가 커져야** 한다. 파일럿에서 `opp_est` 가
비어 있는 것으로 확인되면 이번 라운드에서 빼고 ⑤로 넘긴다.

`persona.size_read` 는 2.0팟 이하에서 항등이라 실전 사이즈에서는
한 번도 동작하지 않는다 — 실제 경로는 `see_size → size_gap →
opp_size_norm` 이다 (`TRACE_STELL.md`).

---

## 4. 판정 통계

### (0) 귀속 — 3단 분해 (모든 `concepts` 축에 적용)

```
단변량 Spearman ρ        축 값 그대로 대 관측치
잠재3 통제 편상관          study·aggro·exp 를 회귀로 뺀 잔차끼리
축 고유 분산 1 − R²       그 축에서 잠재요인이 아닌 몫
```

세 번째가 두 번째의 상한을 정한다. 고유 분산이 작으면 편상관이 작게
나오는 것이 정상이며, **그것은 축이 행동을 못 만든다는 뜻이 아니다.**

```
t:aggression   고유 0.107   ← temper['aggression'] = aggro + gauss(0, 0.8)
```

`aggression` 의 편상관이 0 에 가깝게 나오면 결론은 **"`aggression` 이라는
이름의 축이 사실상 잠재요인 `aggro` 를 측정한다"** 이다. 결함이 아니라
현재 생성 모델의 구조적 사실이고, 그대로 기록한다.

`temper` 는 `aggression` 을 빼면 고유 분산 0.88~1.00 이라 단변량으로 족하다.

---

### (0-b) 층 분리 — 판단 확률 `f` 와 실현 행동

축의 효과를 **두 층으로 나눠 싣는다.** `f` 를 실현 행동의 대체값으로
쓰지 않는다.

```
판단층   축 → cbet_freq / barrel 확률 / sizing 확률      (연속값, 고표본)
   ↓
실행층   실제 bet / check / fold / raise                  (베르누이, 저표본)
```

둘이 갈리는 것 자체가 결과다.

| `f` | 실현 행동 | 판정 |
|---|---|---|
| 갈린다 | 갈린다 | 축이 행동까지 도달한다 |
| 갈린다 | 안 갈린다 | **전달은 됐고 실행 표본이 부족하다.** 축이 죽은 게 아니다 |
| 안 갈린다 | — | 축이 판단에 도달하지 못한다 ← 구조 후보 |

`barrel_river` 는 토너 하나에서 기회가 총 2건이라 실현 행동으로는
영구히 잴 수 없다. `f` 층이 없으면 "측정 불가"와 "축이 죽었다"를
구별할 방법이 없다.

나중에 **"aggression 9 인데 실제 벳이 별로 안 많다"** 가 나왔을 때
축 문제인지 판단→실행 희석인지 이 표로 바로 갈린다.

---

### (1) 방향성 — Spearman ρ

플레이어를 점으로, 축 값 대 관측치의 순위상관. 기회 수로 가중한다.
**부호가 기대 방향과 맞는지**를 먼저 본다. 크기는 그 다음이다.

### (2) 분리도 — 축 버킷별 효과크기

버킷은 1–3 / 4–6 / 7–9. 상·하 버킷 간 Cliff's δ 를 낸다
(관측치 분포가 비정규·유계라 Cohen's d 보다 안전하다).

"축을 알면 관측 행동을 얼마나 구별할 수 있는가"에 직접 답하는 것이 이것이다.

### (3) 귀무 — permutation null

축 값을 플레이어에게 **무작위 재배정**하고 (1)(2)를 다시 낸다. 반복해서
ρ 와 δ 의 귀무분포를 만든다. 실측이 이 분포 안에 있으면 방향성이 없다.

위약 축(`tilt_swing`·`tilt_stack` — `plan.py` 가 안 읽는다)을 함께 돌려
**바닥이 실제로 0 근처로 나오는지** 확인한다. 안 나오면 도구가 틀린 것이다.

### (4) 신뢰도 상한 — split-half

**이것이 "수렴했다"와 "표본이 부족하다"를 가르는 유일한 도구다.**

한 플레이어의 핸드를 홀/짝으로 갈라 같은 지표를 두 번 계산하고
두 값의 상관 `r` 을 낸다. 관측 가능한 ρ 의 상한은 대략 √r 이다.

```
ρ 가 작다 + r 이 작다   → 표본 부족. 축이 죽었다고 말할 수 없다
ρ 가 작다 + r 이 크다   → 축이 실제로 행동을 안 가른다 ← 구조 후보
```

지표마다 r 을 같이 싣는다. r 없이 ρ 만 보고하지 않는다.

---

## 5. 측정조건 calibration

**목표는 최대 표본이 아니라 교란이 최소인 측정조건 결정이다.**

두 손잡이가 서로 다른 것을 산다 (파일럿 실측, 시드 1개):

```
hpl     12→40   토너 221→447핸드   플레이어당 핸드 ↑  → split-half 신뢰도 r
entries 24→48   토너 447→451핸드   플레이어 수 ↑      → Spearman ρ 의 점 개수
                테이블핸드 653→1346, 플레이어당은 그대로
```

`start_stack` 은 **고정한다.** 표본량 손잡이가 아니라 스택 깊이라는
전략 환경 자체다.

### 도달률 하나만 보지 않는다

손잡이를 돌릴 때 같이 움직이는 것을 전부 싣는다.

```
필드 구성    field_q, 잠재요인(study/aggro/exp) 평균·sd, 주요 축 평균·sd
스택 깊이    관측 시점 유효 스택(bb) — 포스트플랍 성격을 정하는 값
블라인드     종료 레벨, 관측 핸드의 레벨 분포
생존 시간    플레이어당 관측 핸드
기회율       스트리트별 도달률, 플레이어당 지표 기회 수
```

### `entries` 는 필드 구성을 직접 바꾼다 — 코드 확인

```
field.py:field_quality   q = 0.35 + 0.65 · min(1, log₁₀(max(10,entries))/3) · buyin
persona.py:make_player   study ~ N(2.6 + 4.2q, 2.1)
                         exp   ~ N(3.0 + 3.8q, 2.2)
persona.py:skill_bounds  lo = max(0.5, −0.6 + 4.2q)   hi = min(10, 5.6 + 3.4q)
```

| entries | field_q | study 평균 | exp 평균 | skill 범위 |
|---|---|---|---|---|
| 24 | 0.649 | 5.33 | 5.47 | 2.13~7.81 |
| 48 | 0.714 | 5.60 | 5.71 | 2.40~8.03 |
| 100 | 0.783 | 5.89 | 5.98 | 2.69~8.26 |
| 250 | 0.870 | 6.25 | 6.30 | 3.05~8.56 |

**`entries` 를 올리면 36개 개념의 평균이 전부 같이 올라가고 `skill_bounds`
기각표집이 범위를 좁힌다.** 범위가 좁아지면 상관이 감쇠한다 —
`entries` 는 ρ 의 점 개수를 사는 대신 ρ 자체를 깎을 수 있다.

`hpl` 은 `field_quality` 를 건드리지 않는다. 이 축에서는 깨끗하다.

`fieldsim` 은 `make_player(rng, q, pid)` 를 `aggr_bias`·`loose_bias` 없이
부른다(`fieldsim.py:69`). `tourney` 와 달리 필드 난폭도·헐거움 편향이
없다 — 교란이 하나 적은 대신 필드 다양성도 없다. 기록해 둔다.

### 실험

```
seed 여러 개
   ├─ hpl 변화
   ├─ entries 변화
   └─ start_stack 고정
          ↓
   위 다섯 묶음을 전부 측정
          ↓
   교란이 가장 평평한 조건 선택
```

`tools/cond_calib.py` 가 이것을 돌린다.

---

## 6. 순서

```
① 관측 지표 정의        ← 이 문서
② fieldsim 구조 확인
③ 작은 파일럿  → 플레이어당 핸드 수·지표별 기회 수      (완료)
④ 측정조건 calibration → 교란이 최소인 조건 결정
⑤ 본 측정
⑥ permutation null + split-half
⑦ 방향성·분리도 평가
```
