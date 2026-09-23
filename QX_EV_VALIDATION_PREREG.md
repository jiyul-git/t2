# QX_EV_VALIDATION — 사전등록

기준: `claude/tier5-axis-design` `00399b4`. 브랜치 `claude/qx-ev-validation`.
선행: `NUMERIC_BUNDLE_V7_RESULT.md` · `TIER5_AXIS_DESIGN_RESULT.md`

작성 시점: **측정 코드 실행 전.**

## 0. 질문과 금지

**질문 하나. "QX 점수가 높은 판단이 같은 공개 상태에서 실제로 더 높은 chip EV /
더 낮은 regret 를 만드는가?"**

`QX_E` 와 `QX_S` 를 **각각 따로** 검증한다. 합쳐 하나의 점수처럼 다루지 않는다.

```
QX_E   해석·적용 쪽 proxy   (기능 4~6단계. ESTIMATE 를 안 탄다)
QX_S   기억·표본·추정 포함  (Book -> perceived_profile 을 탄다)
```

**금지** — `stat_read` 추가 금지 · 새 concept fitting 금지 · `c5` 재조정 금지 ·
tier 분포 맞추기 금지 · baseline 갱신 금지 · V7/Tier5 변경 금지 ·
production / LIVE wiring 금지 · **QX 결과를 본 뒤 battery/oracle 수정 금지.**

battery coverage 결함이 나오면 **결과를 먼저 보지 않고** 수정 사실을
이 문서의 amendment 로 먼저 남긴다.

`consistency` 는 여기서 닫는다. `TIER5_AXIS_DESIGN_RESULT.md` 3-3 대로
"분석을 잘함"이 아니라 "작은 표본을 얼마나 성급하게 믿느냐"이므로 Tier 5
게이트로 재활용하지 않는다.

## 1. 검증 단위 — decision-state

토너 결과를 통째로 비교하지 않는다. 한 번 행동이 갈리면 이후 스택·보드·RNG
경로가 갈라져 장기 EV 가 연쇄 오염된다 (`HIERARCHICAL_READ_V6_RESULT.md` 3-3
에서 223 엔트리 중 220 이 연쇄였던 것과 같은 문제).

**상태 하나에서 고정하는 것**

```
hero hand · public board · pot · tocall · effective stack · SPR · position
공개 상대 이력 -> 합성 Book -> opp_est (공개 추정치)
legal actions
```

**상대의 진짜 정책**(`b_true` 등)은 fixture 를 만들 때 내가 정한 생성 파라미터다.
`opp_est` 는 같은 파라미터에서 표본 `n` 으로 만든 **공개 관측**이다.
봇은 `b_true` 를 못 보고 `opp_est` 만 본다. oracle 만 `b_true` 를 쓴다.
**target 의 hidden profile/concepts 는 쓰지 않는다** — `b_true` 는 합성 표본의
생성 파라미터이지 상대 프로필이 아니다.

## 2. 두 채널 (봇 판단 진입점에 대응)

| 계열 | 상태 | 봇 판단 | 후보 행동 |
|---|---|---|---|
| **D (defend)** | 턴에서 벳에 직면 | `plan.calldown_need` → `need` | fold / call |
| **A (attack)** | 턴에서 무저항 | `plan.decide_aggression` → `p` | check / bet |

D 는 `need_bot` 과 실제 에퀴티로 행동이 정해진다 (`call iff eq_true ≥ need_bot`).
A 는 봇이 확률 `p` 로 섞으므로 **혼합전략의 기대 regret** 을 쓴다
(`regret = p·regret(bet) + (1−p)·regret(check)`).

**범위 한계를 미리 적는다**: raise/3bet 채널은 이번 fixture 에 없다.
`calldown_need` 와 `decide_aggression` 두 진입점만 검증한다.

## 3. 상태 집합 — 일반 계산 vs 상대 해석

| 집합 | 정의 | 무엇을 가르는가 |
|---|---|---|
| **GEN** | `b_true` 를 모집단 기준(`PRIOR['bluff']/10`)에 고정하고 **가격·에퀴티만** 흔든다 | 상대를 안 읽어도 잘 풀 수 있다 |
| **READ** | 가격은 고정하고 `b_true` 를 극단(0.15 ~ 0.75)으로 흔든다. 최적 행동이 `b_true` 에 따라 **뒤집히도록** 잡는다 | 상대 빈도를 읽어야만 풀 수 있다 |

두 집합의 결과를 **분리해서** 보고한다.

## 4. continuation-EV 계산

**단순 showdown equity 를 EV 라고 부르지 않는다.** fold equity · 리버 베팅 ·
스택 이동을 넣는다.

상대의 턴 벳 레인지는 명시적 콤보 두 묶음이다.

```
V (밸류)   ranges.preflop_range 를 보드로 좁힌 상위 묶음
B (블러프) 같은 레인지의 하위 묶음
실제 혼합   P(bluff) = b_true
```

히어로의 쇼다운 승률은 `bot.equity_vs_combos(hero, board, [V]/[B], sims, seed)`
로 **실제 카드 평가**에서 나온다. 손으로 정한 승률 상수를 쓰지 않는다.

**연속 구간 (리버)**

```
call 후   리버 카드 표본 -> 상대가 밸류면 확률 barrel_true, 블러프면 b_river_true 로 벳
          사이즈 sz_true x pot
          히어로는 **모든 arm 에서 동일한 고정 정책**: 리버 팟오즈 이상이면 콜
          쇼다운은 에퀴티로 해소
bet 후    상대는 블러프면 f_bluff, 밸류면 f_value 확률로 폴드 (fold equity)
          콜되면 같은 리버 연속 구간, 팟만 커진 상태
```

히어로의 리버 정책이 arm 마다 같으므로 **arm 사이 차이는 그 한 번의 결정에서만
온다.**

**paired design**: 한 상태의 모든 후보 행동이 **같은 시드 집합 · 같은 상대 정책 ·
같은 hidden-hand 표본**을 공유한다 (common random numbers).

```
EV(fold)  = 0                      (이미 넣은 칩은 매몰)
EV(call)  = −tocall + E[연속 구간]
EV(check) / EV(bet) 도 같은 표본으로
regret    = EV(best) − EV(chosen)     단위는 **팟 대비 비율**
```

## 5. QX ↔ EV 연결

프로필마다 `QX_E` · `QX_S` 를 재고, fixture 전체의 평균 regret 을 잰다.

```
1  r( QX , −regret )                       GEN · READ 분리
2  QX 상위 25% 집단과 하위 25% 집단의 평균 regret 차이
3  overall = mean(sk(c) for c in persona.CALC) 을 통제한 부분상관
4  CALC_ONLY vs PIPE_ONLY 합성 프로필의 평균 regret  (READ 에서)
```

`CALC_ONLY` / `PIPE_ONLY` 정의는 `TIER5_AXIS_DESIGN_PREREG.md` 3-1-3 과 동일하다.

**first-divergence 원칙**: 이번 fixture 는 상태마다 독립이라 연쇄가 없다.
자연 게임으로 확장하지 않는다. 확장한다면 한 핸드에서 **최초로** QX 관련 판단이
갈린 지점만 독립 표본으로 쓰고 이후는 같은 원인으로 묶는다.

## 6. 표본과 시드

```
fit      프로필 시드 940001..940010 (400인 필드) 에서 400명
holdout  프로필 시드 950001..950010 에서 400명       적합하지 않는다
fixture  RNG 시드 20260925 고정. 모든 프로필이 같은 상태·같은 표본을 본다
```

기존 어느 집합과도 겹치지 않는다.

## 7. 판정 기준 (결과 보기 전 고정)

문턱과 이유.

- **`|r| ≥ 0.20`** — 프로필 400명에서 상관의 SE ≈ 1/√400 = 0.05 이므로 0.20 은
  약 4 SE 다. 설명 분산으로는 4% — 작지만 노이즈가 아니다.
- **holdout `|r| ≥ 0.15` 이고 부호 동일** — 재현 요건. 0.15 는 3 SE 다.
- **부분상관 `≥ 0.10`** — 전반 실력(`overall CALC`)을 통제하고도 남는 몫.
  `NUMERIC_BUNDLE_V7_RESULT.md` 에서 `r(num, overall) = 0.938` 이었으므로
  이 통제가 없으면 실력 대리변수와 구분되지 않는다.
- **PIPE_ONLY 평균 regret < CALC_ONLY** (부트스트랩 95% CI 가 0 제외), READ 에서.

판정은 순서대로.

```
0  INCONCLUSIVE : fixture 의 regret sd 가 팟의 1% 미만이거나
                  최적 행동이 모든 상태에서 같으면 (fixture 퇴화)

1  QX_INVALID   : fit 에서 QX_E·QX_S 둘 다 r ≤ 0 (READ)
                  또는 READ 에서 CALC_ONLY 의 평균 regret 이 PIPE_ONLY 이하

2  QX_VALID     : QX_E 또는 QX_S 중 **해당 계열에 맞는 쪽**이
                  fit r ≥ 0.20 AND holdout r ≥ 0.15 (부호 동일)
                  AND 부분상관 ≥ 0.10 AND PIPE_ONLY < CALC_ONLY (READ)

3  QX_PARTIAL   : 부호가 맞고 holdout 이 |r| ≥ 0.10 으로 재현되지만
                  VALID 문턱에 못 미치는 경우, 또는 두 배터리 중 하나만 연결되는 경우

4  INCONCLUSIVE : 그 외
```

**"해당 계열에 맞는 쪽"** — `QX_S` 는 ESTIMATE 까지 덮으므로 표본이 작은
(`n` 작은) 상태에서, `QX_E` 는 표본이 충분한 상태에서 더 맞는 proxy 다.
fixture 를 `n` 작은 것과 큰 것으로 나눠 둘 다 보고한다.

## 8. 결과 이후 (이번 단계에서 실행하지 않음)

- `QX_VALID` 또는 충분한 `QX_PARTIAL` → 그때 `stat_read` 설계 시작.
  **pid 유도 독립 RNG** 안을 우선 검토한다. `LOADING` 순회에 키를 그냥 추가해
  기존 모든 player RNG 를 미는 방식은 **금지 후보**로 취급한다.
- `QX_INVALID` → `stat_read` 를 만들지 않고 quantitative-exploit task 정의부터
  다시 본다.

## 9. 산출물

```
QX_EV_VALIDATION_PREREG.md        이 문서
tools/qx_ev_fixture.py            decision-state fixture + paired continuation-EV
tools/qx_ev_validate.py           프로필별 regret · QX 연결 · fit/holdout
QX_EV_VALIDATION_RESULT.md        결과 (사실 / 판정 / 해석 / 아직 모르는 것)
```

마지막에 production unchanged · regression fingerprint exact ·
실험 프로세스 0 · worktree clean · local = remote 를 실제로 확인한다.
