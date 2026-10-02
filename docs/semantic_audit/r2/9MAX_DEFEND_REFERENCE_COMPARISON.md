# C. 9MAX_DEFEND_REFERENCE_COMPARISON — 기준 자료 대비 현재 디펜스 지식 (R2-B)

기준 `test` `46a2070`. 읽기 전용 감사이며 production 숫자는 바꾸지 않았다.

그림: `defend_vs_reference.png`. 위 줄은 디펜스 총량, 아래 줄은 3벳 비중이다.

## 1. 근거 자료와 신뢰도

| 우선순위 | 자료 | 조건 | 9-max 직접값 | 신뢰도 | 이번 사용 |
|---|---|---|---|---|---|
| 1 | 우리 9-max GTO DB / solver | — | **없음** | — | 저장소에 9-max solver 결과나 실행 가능한 프리플랍 solver 가 없다(검색: `git ls-files`, gto/solver/chart/rank/prior/calib 이름, 데이터 디렉터리) |
| 2 | 조건이 명확한 공개 9-max MTT solver 차트 | — | **확보 못 함** | — | 웹 검색에서 GTOBase, preflopranges.app 등 상용 뷰어만 나왔다(다운로드 가능한 수치 없음) |
| 2' | `emanuelebermani/gto-poker-trainer` `nine.ts` (커밋 `e25022e`) | 9-max | 있음 | **낮음 — 기준으로 쓰지 않음** | 파일 스스로 "6-max 차트를 손으로 좁힌 파생"이라고 밝힌다. solver 출력이 아니다 |
| 3 | `matthiola0/poker-hand-review` `gto-preflop/mtt/8max/charts` (커밋 `9ef33a4`) | 8-max MTT, 4액션(raise/allin/call/fold). solver 이름·안테 크기·오픈 사이즈는 명시되지 않음 | 없음(8-max) | **중하 — 참고만** | 현재 `gto._MTT8_ANTE_*` 와 `persona.GTO_STUDIED` 의 출처와 같다. 위치 이름 EP/MP 의 정의도 없다. 이 감사는 EP→UTG+1, MP→LJ 로 가정했다(`tools/verify_human_model_v2.py` 의 기존 가정과 같음) |
| — | `gto.py` 주석 "공개 자료(9맥스, 3x 오픈 대면 BB): BTN 51%→56% / CO 36%→48% / HJ 28%→40% / UTG 15%→30%" | 9-max, 3x 오픈, 안테 미기재 | 4점 | **출처 미상** | legacy `DEF_A=0.22, DEF_B=0.68` 이 이 4점에 맞춘 값이다. 출처 링크가 없고 오픈 크기(3x)도 T2(2.15x, 1bb BBA)와 다르다 |

**결론: 9-max 디펜스 값을 판정할 수 있는 조건 일치 자료가 지금 없다.** 그래서 이 문서는 두 가지만 한다.
- (a) 8-max 자료로 현재 식의 **형태**(선형식, 좌석 배수, 3벳 비중 고정, 깊이 처리)를 반증할 수 있는지 본다.
- (b) 코드 내부의 층 사이 손실을 측정한다. 이것은 자료와 무관하게 확인된다.

9-max **값**은 전부 `NEEDS_SOLVER_DATA` 로 남긴다.

8-max 값을 위치 이름만 맞춰 9-max 로 옮기지 않았다. 표의 9-max 행은 `REFERENCE_ONLY` 다.

## 2. 비교표 (realized = 1326 콤보 가중으로 실제로 치는 빈도)

생성: `python tools/r2_compare_defend_reference.py docs/semantic_audit/r2/reference_8max_summary.json docs/semantic_audit/r2/defend_reference_comparison.json`

조건:
- max-skill 중립, 콜러 0, raise_level 1
- 오픈 사이즈는 코드의 2.15x(SB 2.75x), 1bb BBA

기준 자료에 25bb, 40bb vs-open 차트는 없다(40bb 는 RFI 만 있음). 그래서 20/30/50bb 로 둘러싼다. 25bb 의 코드 값은 B 표에 있다.

### 2.1 20bb

| 기준 노드 | 코드 좌석 | 기준 defend/3bet/call | 8-max 코드 L0 → realized defend/3bet/call | 9-max 코드 realized defend/3bet/call (REFERENCE_ONLY) |
|---|---|---|---|---|
| BTN-vs-BB | BB vs BTN | 0.87 / 0.20 / 0.68 | 0.87 → **0.55** / 0.18 / 0.37 | **0.34** / 0.14 / 0.20 |
| EP-vs-BB | BB vs UTG+1 | 0.78 / 0.10 / 0.68 | 0.79 → **0.50** / 0.13 / 0.37 | **0.27** / 0.08 / 0.19 |
| MP-vs-BB | BB vs LJ | 0.85 / 0.16 / 0.69 | 0.80 → **0.51** / 0.14 / 0.37 | **0.29** / 0.08 / 0.20 |
| SB-vs-BB | BB vs SB | 0.68 / 0.14 / 0.55 | 0.76 → 0.48 / 0.18 / 0.31 | 0.35 / 0.15 / 0.19 |
| BTN-vs-SB | SB vs BTN | 0.26 / 0.26 / 0.00 | 0.30 → 0.31 / 0.19 / 0.12 | 0.26 / 0.13 / 0.12 |
| EP-vs-BTN | BTN vs UTG+1 | 0.18 / 0.08 / 0.10 | 0.23 → 0.19 / 0.09 / 0.10 | 0.15 / 0.05 / 0.10 |
| EP-vs-MP | LJ vs UTG+1 | 0.14 / 0.08 / 0.06 | (legacy) 0.09 → 0.08 / 0.04 / 0.04 | 0.07 / 0.04 / 0.04 |

### 2.2 30bb

| 기준 노드 | 코드 좌석 | 기준 defend/3bet/call | 8-max 코드 L0 → realized | 9-max 코드 realized (REFERENCE_ONLY) |
|---|---|---|---|---|
| BTN-vs-BB | BB vs BTN | 0.90 / 0.18 / 0.72 | 0.89 → 0.86 / **0.09** / 0.77 | **0.58** / 0.05 / 0.53 |
| EP-vs-BB | BB vs UTG+1 | 0.76 / 0.09 / 0.66 | 0.79 → 0.79 / 0.08 / 0.71 | **0.44** / 0.04 / 0.40 |
| MP-vs-BB | BB vs LJ | 0.83 / 0.14 / 0.70 | 0.81 → 0.80 / 0.08 / 0.72 | **0.47** / 0.05 / 0.43 |
| SB-vs-BB | BB vs SB | 0.74 / 0.12 / 0.63 | 0.76 → 0.77 / 0.08 / 0.69 | 0.56 / 0.05 / 0.51 |
| BTN-vs-SB | SB vs BTN | 0.29 / 0.22 / 0.07 | 0.31 → 0.32 / **0.10** / 0.22 | 0.44 / **0.04** / **0.39** |
| EP-vs-BTN | BTN vs UTG+1 | 0.22 / 0.08 / 0.14 | 0.24 → 0.24 / 0.06 / 0.18 | 0.25 / 0.03 / 0.22 |
| EP-vs-SB | SB vs UTG+1 | 0.24 / 0.11 / 0.14 | 0.28 → 0.28 / 0.09 / 0.19 | 0.31 / 0.03 / 0.28 |
| EP-vs-MP | LJ vs UTG+1 | 0.17 / 0.08 / 0.09 | (legacy) 0.09 → 0.13 / 0.02 / 0.11 | 0.12 / 0.02 / 0.10 |

15/50/100bb 를 포함한 전체 행은 `defend_reference_comparison.json` 에 있다(차이 열 포함).

## 3. 확인된 사실 (자료 조건과 무관한 것부터)

### 3.1 [코드 내부] 짧은 스택 처리가 두 번 들어간다 — 8-max 보정 경로

- 보정된 `_MTT8_ANTE_*` prior 는 스택별 차트에서 역산한 값이다. 20bb 에서 L0 BB vs BTN 은 0.87 로 기준과 같다.
- 그 뒤 `adjust_defend_widths_for_short_stack` 가 `base_feel(bb) < 0.20`(≈26.7bb 미만: base_feel 26bb 0.192, 27bb 0.204)이면 `tot×0.62, tp×1.6` 을 다시 적용한다.
- 결과: 15~25bb 실제 BB 디펜스가 0.50~0.55 다(기준 0.77~0.87). 30bb 에서는 0.86 으로 돌아온다. 26~27bb 에 절벽이 있다(그림 왼쪽 위).
- 같은 깊이 지식이 prior 와 후처리에 이중으로 들어간 것이다. 판정: **WRONG_QUANTITY**(이중 적용). 이 부분은 9-max 자료 없이도 확인된다.

### 3.2 [코드 내부] legacy 경로의 `_saturate` 는 좁은 폭을 넓힌다

- `_saturate(tot) = 0.80·(1 − e^(−tot/0.55))` 의 원점 기울기는 0.80/0.55 = 1.45 다.
- "100% 초과 방지" 라는 주석과 달리, 좁은 디펜스 폭은 최대 1.45배로 넓히고 넓은 폭은 0.80 쪽으로 누른다.
  - 9-max 30bb BTN vs UTG: L0 0.19 → L1 0.23
  - BB vs BTN: L0 0.68 → L1 0.57
- 판정: **WRONG_QUANTITY**. 포화 함수가 prior 를 변형한다.

### 3.3 [코드 내부] 3벳 폭(tp)의 약 절반만 실제 3벳이 된다

- `w_raise = logistic(r, tp) × (0.35 + 0.65·(1 − r/tp)) × (0.55 + 0.085·aggr)` 와 `w_call`/`w_fold` 정규화 때문이다.
- 그래서 tp 폭 안의 핸드도 일부만 3벳한다.
  - 8-max 보정 경로 30bb BB vs BTN: L0 3벳 0.17 → 실제 0.09
  - 9-max: 0.12 → 0.05
- prior 를 "빈도"로 교정해 놓고 정책은 그 값을 "경계"로 해석해 다시 깎는다. 판정: **WRONG_QUANTITY**(prior→정책 변환 미교정).

### 3.4 [형태 반증, 8-max 자료] `DEF_A + DEF_B·rfi` 선형식

기준 BB 디펜스를 오프너 RFI(같은 자료의 RFI 차트)에 대해 최소제곱으로 맞춘 결과:

| 스택 | 기준 점 (rfi → BB defend) | 적합 A, B | legacy A=0.22, B=0.68 이 같은 rfi 에서 내는 값 |
|---|---|---|---|
| 15bb | 0.17→0.76, 0.20→0.78, 0.38→0.77 | 0.76, 0.03 | 0.34, 0.36, 0.48 |
| 20bb | 0.20→0.78, 0.22→0.85, 0.41→0.87 | 0.75, 0.30 | 0.35, 0.37, 0.50 |
| 30bb | 0.21→0.76, 0.25→0.83, 0.49→0.90 | 0.70, 0.41 | 0.37, 0.39, 0.55 |
| 50bb | 0.20→0.74, 0.24→0.80, 0.54→0.88 | 0.69, 0.36 | 0.35, 0.38, 0.59 |
| 100bb | 0.20→0.70, 0.24→0.77, 0.54→0.77 | 0.71, 0.11 | 0.35, 0.38, 0.59 |

- BB 디펜스는 오프너 폭에 **약하게** 의존한다(기울기 0.03~0.41, 절편 0.69~0.76).
- legacy 식(절편 0.22, 기울기 0.68)은 "오프너가 좁으면 BB 도 아주 좁다"는 모양이다. 자료와 반대 방향은 아니지만 크기가 크게 다르다.
- `mdf(2.15)/mdf(3) = 1.23` 보정을 곱해도 legacy L0 는 BB vs BTN 0.62~0.70, vs UTG+1 0.40~0.43 이다.
- 이 차이는 좌석 수(8 vs 9)로 설명하기 어렵다. BB 의 가격(2.15x 오픈, 1bb BBA → 필요 equity ≈ 0.20)은 좌석 수와 무관하기 때문이다. 다만 9-max 기준값이 없으므로 **값은 NEEDS_SOLVER_DATA**, **현재 식은 UNSUPPORTED_PRIOR** 로 판정한다.
- 정정할 점: 위 legacy 주석의 근거 4점(3x 오픈)은 출처가 없다. T2 의 2.15x + BBA 조건과도 다르다.

### 3.5 [형태 반증, 8-max 자료] `DEF_SEAT` 단일 배수

같은 오프너에 대해 디펜더 디펜스 / BB 디펜스 비율:

| 스택 | BTN vs EP | SB vs EP | BTN vs MP | SB vs MP | SB vs BTN |
|---|---|---|---|---|---|
| 15bb | 0.19 | 0.27 | 0.24 | 0.29 | 0.36 |
| 20bb | 0.23 | 0.31 | 0.24 | 0.30 | 0.30 |
| 30bb | 0.29 | 0.32 | 0.30 | 0.34 | 0.32 |
| 50bb | 0.33 | 0.34 | 0.36 | 0.37 | 0.38 |
| 100bb | 0.39 | 0.37 | 0.40 | 0.39 | 0.40 |

- 오프너가 바뀌어도 비율은 비슷하다. 곱셈 구조 자체는 지지된다.
- 비율은 스택에 따라 0.19 → 0.40 으로 변한다.
- 현재 값:
  - legacy `DEF_SEAT` BTN 0.46, SB 0.62 는 모든 스택에서 기준보다 크다.
  - 보정 `_MTT8_ANTE_DEF_SEAT` BTN 0.298, SB 0.350 은 30bb 근처와 맞는다.
- 판정: 구조 **APPROXIMATION_ACCEPTABLE**. legacy 값은 **UNSUPPORTED_PRIOR**. 스택 의존은 **MISSING_KNOWLEDGE**.

### 3.6 [형태 반증, 8-max 자료] `TB_SHARE = 0.18` 전역 고정

기준 3벳 비중(3벳 / 디펜스, 15~100bb):

| 디펜더 | 최소 | 최대 | 경향 |
|---|---|---|---|
| BB | 0.08 | 0.25 | 오프너가 늦을수록, 스택이 짧을수록 높다. 0.18 은 **범위 안**에 있다 |
| SB | 0.28 | **1.00** | 15~20bb vs BTN 은 거의 순수 3벳/폴드(0.98~0.99). 100bb 에서도 0.28~0.51 |
| BTN (vs EP/MP) | 0.29 | 0.76 | 짧을수록 높다 |
| MP (vs EP) | 0.35 | 0.79 | 짧을수록 높다 |

- 0.18 은 BB 에서만 대략 맞는다. SB 와 IP cold 디펜더에는 1.5~5배 작다.
- 그래서 9-max 실제 SB vs BTN 30~100bb 는 플랫이 과다하다(콜 0.39, 3벳 0.04, 기준 콜 0.07~0.16 / 3벳 0.16~0.22).
- 보정 경로의 `_MTT8_ANTE_TB_SHARE` 도 SB 0.65 하나로 고정이라, 15~20bb 의 0.98 과 100bb 의 0.51 을 구분하지 못한다.
- 판정: legacy 는 **UNSUPPORTED_PRIOR**(BB 제외). 스택·오프너 의존은 **MISSING_KNOWLEDGE**.

### 3.7 오픈 사이즈 보정 `mdf(open)/mdf(3)`

- 기준 자료에는 오픈 사이즈 변화가 없다(사이즈 미기재). 방향과 크기를 검증할 수 없다: **NEEDS_SOLVER_DATA**.
- 현재 배수:
  - 2.15x → 1.23
  - 2.36x → 1.16
  - SB 2.75x → 1.05
  - 3벳 크기(6.45~10.95bb)가 들어가는 vs-3bet 경로 → 0.68(표 하한 6bb 에서 고정)
- 개념상 MDF 는 "마지막 디펜더(액션을 닫는 사람)의 레인지 전체"에 대한 하한이다. 뒤에 사람이 남은 cold 디펜더(BTN, CO, SB)에게 같은 비율을 곱하는 것은 질문이 다르다. 판정: **WRONG_QUANTITY 후보**(검증 자료 필요).

### 3.8 스택 깊이

- legacy 경로에서 스택은 두 곳으로만 들어간다. (1) `rfi(opener, bb)` 의 깊이 배수(오프너 폭을 통한 간접 효과), (2) `base_feel < 0.20` 절벽(3.1).
- 기준 BB vs BTN 은 15→20→30→50→100bb 에서 0.77 / 0.87 / 0.90 / 0.88 / 0.77 로 **가운데가 가장 넓은 곡선**이다.
- 코드 9-max 는 0.35 / 0.34 / 0.58 / 0.59 / 0.58 로 **26bb 절벽 + 평탄**이다.
- 3벳 비중의 스택 의존(3.6)은 legacy 에 없다.
- 판정: **MISSING_KNOWLEDGE**(직접적인 스택 의존 디펜스/3벳 지식 없음) + 3.1 의 **WRONG_QUANTITY**.

### 3.9 3벳 이후 (vs-3bet, 4벳+) — 재명시

- 독립 prior 가 없다. 오프너가 HU 3벳을 맞으면 `defend_decision(def_pos=오프너, opener_pos=3벳터, open_bb=3벳 크기, raise_level=2)` 로 간다. 즉 **vs-open 디펜스 prior 를 위치만 바꿔** 쓴다.
  - 3벳터가 BB 면 `rfi(BB)=0` → `DEF_A` 만 남는다.
  - 3벳터가 SB 면 블라인드 대 블라인드용 `DEF_VS_SB` 가 쓰인다.
  - 오프너의 `DEF_SEAT`(예: LJ 0.21)가 곱해진다. 이 값은 cold 디펜더용 배수다.
- 그 뒤 `LEVEL_TIGHTEN[3]=0.34` 를 곱한다(3벳 폭 자료를 축소해 4벳 지식으로 쓰는 구조).
- 측정(`vs3bet_probe.json`, 기준 오픈 레인지 조건부, 30·100bb):

| 노드 | 기준 계속 / 4벳 | 코드 계속 / 4벳 (8-max, 9-max 같음) |
|---|---|---|
| MPopen-vs-IP3bet 30bb | 0.89 / 0.31 | 0.16 / 0.05 |
| EPopen-vs-IP3bet 30bb | 0.81 / 0.25 | 0.16 / 0.05 |
| BTNopen-vs-blind3bet 30bb | 0.55 / 0.13 | 0.08~0.10 / 0.02~0.04 |
| SBopen-vs-BB3bet 30bb | 0.63 / 0.14 | 0.11~0.15 / 0.04~0.07 |
| MPopen-vs-IP3bet 100bb | 0.75 / 0.25 | 0.17 / 0.05 |
| BTNopen-vs-blind3bet 100bb | 0.43 / 0.06 | 0.07~0.09 / 0.02~0.03 |

- 기준의 3벳 크기는 알 수 없다. 그래도 계속률 차이(코드 7~25% vs 기준 43~89%)는 크기 차이로 설명할 수 있는 범위를 넘는다.
- baseline sim(46a2070, 시드 11·12, 1,149핸드)에서 `opener_backaction` 비올인 리레이즈 87회 중 73회(84%)가 폴드다.
- 판정: **MISSING_KNOWLEDGE**.
  - R2-B 에서 3벳 자료를 4벳 지식으로 재사용하지 않는다.
  - vs-3bet, 4벳, cold 4벳은 별도 지식 항목으로 분리한다(D 문서).

## 4. spot 별 판정 요약

| spot 군 | 경로 | 판정 |
|---|---|---|
| BB vs 모든 오픈, 9-max | legacy | 값 **NEEDS_SOLVER_DATA**, 현재 식 **UNSUPPORTED_PRIOR** (자료 대비 −0.2~−0.56, 구조 3.2·3.4) |
| BB/SB/BTN/CO, 8-max 15~25bb | 보정 + 짧은 스택 후처리 | **WRONG_QUANTITY** (3.1 이중 적용) |
| BB/SB/BTN/CO, 8-max 30bb 이상 | 보정 | 디펜스 총량 **PRIOR_SUPPORTED**(±0.08, 출처 신뢰도 중하). 3벳은 **WRONG_QUANTITY**(3.3 실현 손실) |
| SB vs 오픈, 9-max | legacy | 총량 **APPROXIMATION_ACCEPTABLE**(≤25bb) ~ 과다(30bb 이상). 3벳/콜 분할 **UNSUPPORTED_PRIOR**(3.6) |
| BTN/CO cold 디펜스, 9-max | legacy | 총량 **APPROXIMATION_ACCEPTABLE**(±0.06). 3벳 비중 **UNSUPPORTED_PRIOR** |
| UTG+2~HJ cold 디펜스 (8·9-max 모두 legacy) | legacy | **NEEDS_SOLVER_DATA**(자료는 LJ vs EP 한 노드뿐이고 코드가 디펜스·3벳 모두 낮다) |
| BB vs SB (BvB) | `DEF_VS_SB` 0.60 / 보정 0.72 | 9-max **UNSUPPORTED_PRIOR**, 8-max 30bb 이상 **PRIOR_SUPPORTED** |
| 오픈 사이즈 보정 | 공통 | **NEEDS_SOLVER_DATA**, cold 디펜더 적용은 **WRONG_QUANTITY 후보** |
| vs-3bet / 4벳 / cold 4벳 | 위치 바꾼 vs-open prior × LEVEL_TIGHTEN | **MISSING_KNOWLEDGE** |

이 분류는 내부 감사용이다. 플레이 빈도를 맞추기 위한 점수가 아니다.
