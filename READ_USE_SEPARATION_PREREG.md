# READ_USE_SEPARATION — 사전등록

기준 커밋: `b0f2d26` (`claude/qx-ev-validation`)
브랜치: `claude/read-use-separation`
작성 시점: 결과 수치를 보기 **전**. 이 문서는 측정 후 수정하지 않는다.

---

## 0. 왜 이 실험인가

`QX_EV_VALIDATION` 판정은 `QX_PARTIAL` 이었다. 수비 채널에서 `QX_E` 는
EV 와 붙었지만(holdout r=+0.277, overall CALC·행동빈도 통제 후 +0.183),
합성 극단 대조 `CALC_ONLY` vs `PIPE_ONLY` 는 null 이었다
(+0.0004, 95%CI [−0.00095, +0.00184]).

`PIPE_ONLY` 는 "더 잘 읽는다" 뿐 아니라 `adaptability → use → w` 를 통해
**조정 폭도 같이 키운다.** 그래서 지금 상태로는

- 정확하게 읽어서 좋아진 것인지
- 그냥 더 세게 조정해서 좋아지거나 나빠진 것인지

를 나눌 수 없다. `stat_read` 를 지금 넣으면 어느 쪽을 올리는 축인지
모른 채 넣는 것이 된다.

**이번 실험의 목적은 하나다 — 수비 READ 상태에서 읽기 정확도와 조정 강도를
인과적으로 분리한다.**

## 1. 범위

- **대상: `READ` × `D`(수비) 상태만.**
  `READ_attack` 은 `QX_EV_VALIDATION` 에서 fit −0.2477 / holdout −0.2403 으로
  EV 와 **부호가 반대**였다. 타당성 검증에 섞지 않는다.
  공격 채널(`decide_aggression` 이 상대 정보에 어떻게 반응하는가)은 별도 문제로
  남긴다 — 이번 판에서 측정도, 수정도 하지 않는다.
- `stat_read` 를 비롯한 **새 concept 을 만들지 않는다.**
- production 무수정. `c5=0.7087277777777778` 무변경, V7 tier 경계 무변경,
  baseline/reference 무갱신, LIVE 배선 없음.
- 개입은 전부 도구 쪽 monkeypatch 다. `plan.py` / `persona.py` / `reads.py` 를
  건드리지 않는다.

## 2. 2×2 설계

같은 decision state, 같은 hidden-hand 표본, 같은 continuation 난수에서
두 축을 독립으로 조작한다. 단위는 **(프로필 × 상태)** 이고, 네 arm 이
같은 프로필·같은 상태를 공유한다(완전 paired).

```
            U = LOW_USE (u=0.40)      U = HIGH_USE (u=1.60)
R = LOW_READ    (a=0.20, u=0.40)          (a=0.20, u=1.60)
R = HIGH_READ   (a=1.00, u=0.40)          (a=1.00, u=1.60)
```

### 2-1. 축 R — 읽기 정확도

공개 장부(`reads.Book`)로 만든 추정치를 **모집단 사전분포 쪽으로 블렌드**한다.

```
est_a[k] = PRIOR[k]·(1 − a) + est[k]·a
```

- `LOW_READ  a = 0.20` — 증거의 20% 만 반영. 사실상 모집단 평균으로 본다.
- `HIGH_READ a = 1.00` — `reads.estimate` 가 공개 증거에서 뽑은 값 그대로.

`a=1.00` 을 상한으로 두는 이유: 그 이상은 증거를 **증폭**하는 것이라 정확도가
아니라 과신이 된다. 그리고 `estimate` 출력을 넘어서는 값은 공개 정보로
정당화되지 않는다.

`a` 를 두 수준만 두는 이유: 이번 질문은 "정확도가 EV 를 바꾸는가" 의 유무이지
용량-반응 곡선이 아니다. 곡선은 U 축에서만 잰다(§2-5).

**블렌드 대상(믿음 채널):**
`vpip pfr cbet barrel ftb ftb_flop ftb_turn ftb_river pf_3bet pf_fold_to_3bet
pf_4bet pf_fold_to_4bet pf_limp rfi_rel sz_mean sz_sd sz_big sz_river
aggr bluff tight`

**블렌드 제외(표본 사실 — 믿음이 아니다):** `n`, `confidence`, `sz_n`, `rfi_n`, `type`

제외가 결정적이다. `persona.read_opponent` 의
`data = min(1,conf)·min(1,n/12)`, `w = clamp(use·data, 0, 0.85)` 는
`n` 과 `confidence` 에서만 나온다. 둘을 건드리지 않으므로
**R 을 바꿔도 `w` 는 비트까지 같다.** §4-1 에서 전수 검증한다.

개입 지점은 `reads.estimate` 의 반환값이다. 그래야 `estimate_concepts` 와
`perceived_profile` 의 나머지가 블렌드된 믿음과 정합한다. `estimate` 의
`jitter`(rng.uniform ×2)와 `estimate_concepts`(LOADING 키당 rng.gauss ×1)는
**값과 무관하게 난수 소비 횟수가 같다.** paired 설계가 유지된다.

### 2-2. 축 U — 익스플로잇 적용 강도

**perceived estimate 는 완전히 고정한다.** `est` 를 먼저 만들고, 그 뒤
적용 지점에서만 배수를 건다.

`calldown_need` 에서 읽기가 `need` 를 움직이는 자리는 정확히 둘이다.

1. `need -= trust · (read − 0.35)`   (`plan.py:678`)
2. `need = PS.blend(need, need·max(0.55, 1−0.35·bluff_gap), _rdz['w'])` (`plan.py:708`)

그래서 U 는

```
read' = 0.35 + u·(read − 0.35)      ← trust *= u 와 대수적으로 동일
w'    = clamp(u·w, 0, 0.85)
```

`read` 는 `calldown_need` 안에서 `trust·(read−0.35)` 로만 쓰인다(전수 확인).
따라서 첫 줄은 `trust` 에 `u` 를 곱하는 것과 **정확히 같다.** 지역 변수
`trust` 를 patch 할 수 없어 호출 인자로 등가 변환한 것이지, 다른 개입이 아니다.

`read'` 에는 추가 클램프를 두지 않는다 — `need` 는 이미 production 의
`need_true·1.75+0.05` / `need_true·0.55` 상·하한에 걸린다. 도구가 경계를
새로 발명하지 않는다.
`w'` 는 `PS.blend` 의 혼합 가중치라 1 을 넘으면 외삽이 되어 "더 센 적용"이
아니라 무의미가 된다. production 자신의 상한 0.85 를 그대로 쓴다.

**`u` 수준:** `u_lo = 0.40`, `u_hi = 1.60`. production 값 1.0 을 중심으로
±0.60 대칭이다. 대칭으로 두는 이유는 한쪽 arm 이 production 과 일치하면
주효과가 "production 으로부터의 거리"와 교락되기 때문이다.

### 2-3. 사이즈 인식 동결 — U 의 누출 차단

`persona.opp_size_norm` 도 `w` 를 읽어 **인식 사이즈**를 바꾼다
(`persona.py:652-665`). 사이즈 정규화는 "얼마나 세게 조정하는가"가 아니라
"무엇으로 보이는가" 쪽이므로 U 가 여기 닿으면 안 된다.

그래서 patch 된 `read_opponent` 는 원래 `w` 를 `_w0` 로 보관하고,
patch 된 `opp_size_norm` 은 `_w0` 를 복원해서 계산한다.
**U 는 `_sz_seen` 을 바꾸지 않는다.** §4-2 에서 검증한다.

R 은 `sz_mean`/`sz_sd`/`sz_big`/`sz_river` 를 블렌드하므로 `_sz_seen` 을
바꾼다 — 이건 읽기 정확도의 일부이므로 그대로 둔다.

### 2-4. 상태 집합

`tools/qx_ev_fixture.py` 의 `State` 와 EV 엔진을 그대로 쓴다(수정 없음).
상태 목록만 새로 만든다.

- 보드 4개: `Kc7d2s5h`, `Jh Th 4c 2d`, `Qd8s3hTc`, `9c6d2hKd` (전부 턴)
- 히어로 12핸드 × 가격 9수준에서 `_flip_point('D', ...)` 를 스캔
- 뒤집힘점 `b*` 의 **밴드별로 균등 추출** — `[0.10,0.20] (0.20,0.30]
  (0.30,0.40] (0.40,0.50] (0.50,0.80]` 각 4셀, (보드,히어로) 쌍당 최대 1셀
- `b_true` 6수준: `0.15 0.27 0.39 0.51 0.63 0.75`
- 표본 `n_obs` 2수준: `6`, `40`

총 **20셀 × 6 × 2 = 240 상태**.

밴드 균등 추출의 이유: 밴드별 대표 `b*` 가 0.15/0.27/0.39/0.51/0.63 이면
셀당 콜-최적 수준이 5/4/3/2/1 개라 전체 평균이 정확히 **0.50** 이 된다.
`QX_EV` Amendment A1 에서 최적 행동이 한쪽으로 2.6:1 쏠린 것이 결과를
"행동 빈도 측정"으로 만들었다. 같은 실수를 반복하지 않는다.

### 2-5. U 사다리 (보조, 서술용)

주 판정은 2×2 로만 한다. 별도로 `u ∈ {0.0, 0.4, 0.7, 1.0, 1.3, 1.6, 2.0}`
× `R ∈ {LOW, HIGH}` 14셀을 **서술 목적으로** 같이 계산한다.
질문 2·3(과조정이 있는가, 잘 읽어도 use 가 크면 손해인가)은 두 점으로는
답이 안 나오기 때문이다. **판정 규칙에는 들어가지 않는다.**

## 3. 통계량

프로필 `p`, 상태 `s`, arm `(R,U)` 에서

```
regret(p,s,R,U) = EV(최적행동, s) − EV(봇이 고른 행동, p,s,R,U)
```

EV 는 `State.ev_actions()` — fold equity · 리버 한 스트리트 · 스택 이동을
넣은 연속구간이고, 한 상태의 모든 후보 행동이 같은 난수 표본을 쓴다.
**단순 showdown equity 가 아니다.** 상태의 EV 는 arm 과 무관하게 한 번만
계산해 네 arm 이 공유한다.

```
ΔR(u) = mean regret(LOW_READ, u) − mean regret(HIGH_READ, u)     > 0 이면 잘 읽는 쪽이 이득
ΔU(a) = mean regret(a, LOW_USE)  − mean regret(a, HIGH_USE)      > 0 이면 세게 쓰는 쪽이 이득
INT   = ΔR(u_hi) − ΔR(u_lo)                                      > 0 이면 use 가 클 때 읽기가 더 값지다
```

신뢰구간: **프로필 단위 클러스터 부트스트랩** 4000회, 시드 `v7_num_battery.SEED`.
상태는 모든 프로필이 공유하므로 프로필이 독립 단위다.

보고 항목:
- `ΔR(u_lo)`, `ΔR(u_hi)`, `ΔU(a_lo)`, `ΔU(a_hi)`, `INT` — 각각 평균 + 95%CI
- 네 arm 의 평균 regret
- `n_obs = 6` / `40` 분리 집계
- SET_A / SET_B 각각

**사전 방향 예측(게이트 아님):** `ΔR` 은 `n=40` 에서 `n=6` 보다 클 것이다.
표본이 6이면 사전분포로 수축하는 것이 실제로 덜 틀릴 수 있기 때문이다.
빗나가도 판정에 영향을 주지 않는다. 사후 해석 재료로만 쓴다.

**효과 크기 하한 `FLOOR = 0.002` (팟 대비).**
근거: `QX_EV_VALIDATION` 에서 `QX_E` 상위25% vs 하위25% 의 `READ_all` regret
차이가 **0.0130 팟**이었다. 그 작업이 실물로 취급한 가장 작은 효과의
약 1/6 이다. 그보다 작으면 이전 작업의 해상도로는 보이지도 않던 크기라
행동 의미가 없다. paired 설계라 MC 노이즈는 arm 간 차분에서 상쇄되므로
이 하한은 노이즈 바닥이 아니라 **의사결정 의미**의 기준이다.

## 4. 타당성 검사 — 결과를 보기 전에 통과해야 한다

아래 검사는 regret 을 **전혀 집계하지 않고** 돌린다(`--check`).
하나라도 실패하면 판정은 `INCONCLUSIVE` 이고, 고친 사실은 결과를 보기 전에
amendment 로 남긴다.

**4-1. R 은 `w` 를 바꾸지 않는다.**
모든 (프로필, 상태) 에서 `read_opponent(prof, est_lo)['w'] == read_opponent(prof, est_hi)['w']`.
불일치 0건이어야 한다.

**4-2. U 는 인식 사이즈를 바꾸지 않는다.**
모든 (프로필, 상태) 에서 `_sz_seen(u_lo) == _sz_seen(u_hi)`. 불일치 0건.

**4-3. R 은 실제로 믿음을 바꾼다 (manipulation check).**
`|line_bluff_prior(est_a) − b_true|` 의 평균이 `HIGH_READ` 에서 `LOW_READ` 보다
작아야 한다. 이건 방향이 아니라 **정확도**의 검사다 — 실패하면 `HIGH_READ` 라는
이름이 거짓이고 실험 전체가 무의미하다.

**4-4. 널 개입 대조 (negative control).**
`a_lo = a_hi = 1.00` 으로 두면 `ΔR ≡ 0` 이, `u_lo = u_hi = 1.00` 으로 두면
`ΔU ≡ 0` 이 **정확히 0.0** 이어야 한다. 0 이 아니면 하네스에 난수 누출이 있다.

**4-5. arm 이 행동을 바꾼다 (discrimination).**
네 arm 중 최소 둘이 서로 다른 행동을 내는 (프로필, 상태) 비율이 **≥ 10%**.
미만이면 개입이 `need` 를 움직여도 콜/폴드 경계를 못 넘은 것이므로
EV 로는 잴 수 없다 → `INCONCLUSIVE`.

**4-6. 상태가 판별력을 가진다.**
20셀 전부에서 `b_true` 에 따라 최적 행동이 뒤집혀야 한다 (20/20).

## 5. 판정 규칙 — 순서대로 적용

`OK(x)` = `x ≥ FLOOR` 이고 95%CI 가 0 을 배제하며 **SET_A·SET_B 둘 다** 충족.

```
R0  INCONCLUSIVE              §4 검사 중 하나라도 실패
R1  READ_ABILITY_JUSTIFIED    OK(ΔR(u_lo)) 그리고 OK(ΔR(u_hi))
R2  READ_ONLY_IN_INTERACTION  OK(ΔR(u_hi)) 이고 OK(ΔR(u_lo)) 는 불충족
R3  USE_DOMINATES             ΔR 이 어느 u 에서도 불충족이고, OK(|ΔU|) 가
                              a_lo·a_hi 중 최소 하나에서 충족
R4  NO_CAUSAL_READ_EFFECT     위 어느 것도 아님
```

`READ_ABILITY_JUSTIFIED` 는 **use 를 고정한 채로** 읽기 정확도만 올렸을 때
regret 이 줄고, 그것이 두 use 수준 모두에서 그리고 두 표본집합 모두에서
재현될 때만 나온다. 이게 사용자가 요구한 조건이다.

`ΔR` 이 유의하게 **음수**(잘 읽는 쪽이 손해)로 나오면 R4 로 가되,
결과 문서 본문에 "역방향"을 명시한다. 새 라벨을 만들지 않는다.

## 6. 질문 4 — 합성 null 의 설명

`PIPE_ONLY` 는 읽기와 use 를 **동시에** 올린 arm 이므로 2×2 의
`(HIGH_READ, HIGH_USE)` 에 대응하고, `CALC_ONLY` 는 `(LOW_READ, LOW_USE)` 에
대응한다. 상쇄 가설은 결과를 보기 전에 이렇게 고정한다.

```
CANCEL_SUPPORTED   OK(ΔR(u_hi)) 이고
                   ΔU(a_hi) ≤ −FLOOR 이며 CI 가 0 을 배제하고 (잘 읽을수록 과조정이 손해)
                   |mean g[HI][HI] − mean g[LO][LO]| < FLOOR 이고 그 차이의 CI 가 0 을 포함
CANCEL_NOT_SUPPORTED   그 외
```

## 7. 금지 사항

- `stat_read` 등 새 concept 구현 금지. 이번 판은 설계도 하지 않는다.
- `c5` 변경 금지. V7 tier 경계 재적합 금지. V7 분포 재측정 금지.
- production/LIVE 변경 금지. baseline/reference 갱신 금지.
- 공격 채널 수정 금지. 공격 채널 측정도 이번 판에는 넣지 않는다.
- hidden target profile/concepts 참조 금지. `h.pf_seed` 참조 금지.
  상대에 대한 입력은 공개 장부에서 나온 `perceived_profile` 뿐이다.
  (`b_true` 는 fixture 가 EV 정답을 계산할 때만 쓴다. 봇에게 가지 않는다.
   단, 히어로 자신의 에쿼티 `eq_true` 는 네 arm 에서 **동일하게** 주어진다 —
   §8 한계 참조.)
- 결과를 보고 arm 수준·FLOOR·판정 규칙을 고치는 것 금지.
  타당성 결함이 나오면 **결과를 보기 전에** amendment 로 남기고 고친다.
- 사후 결합식으로 판정 만들기 금지.

## 8. 알려진 한계 (결과 해석 전에 기록)

1. **히어로는 자기 에쿼티를 정확히 안다.** `eq_true = b_true·eq_blf +
   (1−b_true)·eq_val` 은 네 arm 에서 같다. 즉 이 실험은 상대 모델 채널만
   격리하며, "읽기가 에쿼티 추정을 개선하는" 경로는 재지 않는다.
   `QX_EV_VALIDATION` 도 같은 설정이었고 거기서 READ_D 가 r=+0.28 로
   판별력을 보였으므로 설계가 퇴화하지는 않는다.
2. **`a` 블렌드는 `estimate` 출력 전체에 건다.** 블러프 읽기만이 아니라
   상대 믿음 전부의 정확도다. "읽기 정확도"를 좁게 정의하지 않은 것이며,
   좁히면 `stat_read` 후보 축을 미리 고르는 셈이 되어 순환이 된다.
3. **`u` 는 수비 채널의 두 적용 지점에만 건다.** 공격 채널은 §1 대로 제외다.
4. 상태는 턴 단일 스트리트다. 멀티스트리트 계획 효과는 재지 않는다.

## 9. 산출물

- 본 문서 (측정 전 커밋)
- `tools/read_use_fixture.py` — 상태 집합과 arm 개입
- `tools/read_use_2x2.py` — 측정·통계·판정
- `READ_USE_SEPARATION_RESULT.md` — 결과와 판정
- `docs/READ_USE_SEPARATION.png` — 그림
- 마지막에 production 무수정 / regression 지문 일치 / 실험 프로세스 0 /
  worktree clean / local=remote 확인

---

# Amendment B1 — 상태 집합 구성 (측정 전)

본 amendment 는 **regret 을 한 번도 집계하지 않은 시점**에 기록한다.
지금까지 본 것은 상태 구성 진단뿐이다 — 셀 개수, 최적 행동이 뒤집히는 셀 수,
최적=call 비율. arm 비교도, 프로필 투입도 없었다.

## B1-1. 왜 고쳤나

§2-4 원안(보드 4 · 히어로 12 · 가격 9 · 뒤집힘점 밴드 `[0.10,0.20] …
(0.50,0.80]`)을 그대로 돌리니 세 가지가 깨졌다.

1. **뒤집힘 셀 12/20.** `QF._flip_point` 는 `0.05` 간격 스캔 격자에서
   뒤집힘점을 찾는데 `b_true` 격자(`0.15 0.27 … 0.75`)와 어긋난다.
   `b* = 0.10` 셀은 6수준 전부 call 최적이라 실제로는 안 뒤집힌다.
2. **최적=call 비율 0.760.** §2-4 가 막으려던 바로 그 쏠림이다.
3. **가장 희귀한 밴드가 0셀.** 흔한 밴드가 `(보드,히어로)` 쌍을 먼저
   소비했다.

## B1-2. 무엇을 바꿨나

- **층화 기준 교체.** 뒤집힘점 밴드 대신, **실제로 쓰는 `B_LEVELS` 격자
  위에서 call 이 최적인 수준의 개수 `k`** 로 층화한다. `k ∈ {1,2,3,4,5}`
  각 4셀. 정의상 20/20 이 뒤집히고, call 비율이
  `(1+2+3+4+5)×4 / 120 = 0.500` 으로 **구성상 정확히 균형**이다.
  스캔 격자와 사용 격자의 불일치가 원리적으로 사라진다.
- **후보 확대.** 보드 4 → **6**, 히어로 12 → **16**.
  희귀 층(`k=1,2`)을 `(보드,히어로)` 쌍 중복 없이 채우기 위함이다.
- **가격 상한 1.80.** 원안의 `2.20`·`2.80` 을 뺐다.
  `persona.size_read` 는 2.0 이하에서 항등이고 그 위는 정의역 밖 분기다
  (CLAUDE.md: 아카이브 포스트플랍 `sz` 최대 0.915). 이번 실험의 축은
  사이즈 인식이 아니므로 그 분기를 켜지 않는다.
- **선택 순서.** 후보가 적은 층부터 채우고, 층 안에서는 **보드
  라운드로빈**으로 고른다. 이름순 정렬만 두면 한 층을 보드 하나가
  독식했다(첫 시도에서 20셀이 보드 2개에 몰렸다).

## B1-3. 바뀌지 않은 것

- 상태 수 **240** (20셀 × `b_true` 6 × `n_obs` 2) — 원안과 같다.
- `B_LEVELS`, `N_LEVELS`, arm 수준(`A_LO/A_HI`, `U_LO/U_HI`, U 사다리),
  `FLOOR = 0.002`, 통계량 정의, §5 판정 규칙, §6 상쇄 가설 — **전부 그대로**.
- §4 타당성 검사도 그대로다. §4-6 은 "20셀 전부에서 `b_true` 에 따라 최적
  행동이 뒤집힌다" 인데, 새 층화에서는 구성상 보장된다. 검사는 남긴다 —
  보장이 코드에서 실제로 성립하는지 보는 것이 검사의 일이다.

## B1-4. 확인된 구성 결과

```
cells 20   (k=1..5 각 4셀, 보드 6개 전부 사용, 가격 0.30~1.80)
states 240
뒤집힘 셀 20/20
최적=call 비율 0.500
```
