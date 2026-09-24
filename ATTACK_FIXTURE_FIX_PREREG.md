# ATTACK_FIXTURE_FIX — 사전등록

기준 커밋: `b9e3387` (`claude/synth-channel-split`, 동결)
브랜치: `claude/attack-fixture-fix`
작성 시점: **측정 수치를 보기 전.** 아래 "구성 확인"은 상태 구성 진단이고
regret·arm 비교는 한 번도 돌리지 않았다.

---

## 0. 질문

`SYNTH_CHANNEL_SPLIT` 이 `PIPE_ONLY` null 의 정체를 밝혔다 —
수비 `+0.00527` 과 공격 `−0.00200` 을 24:48 로 섞어 `+0.00042` 가 된 것이고,
**공격의 음수는 production 판단이 아니라 fixture 배선 오류**였다.

```
qx_ev_fixture.State.book()        ftb = 1 − b_true             r(b_true, ·) = −1.000
qx_ev_fixture.State.ev_actions()  P(fold) = .18 + .60·b_true   r(b_true, ·) = +1.000
```

그래서 남은 질문은 하나다.

> **공격 정보를 정상적으로 배선했을 때도 읽기 정확도가 실제 EV 를 개선하는가?**

## 1. 동결과 범위

- **`tools/qx_ev_fixture.py` 를 수정하지 않는다.** `QX_EV_VALIDATION` 과
  `SYNTH_CHANNEL_SPLIT` 의 재현이 거기 걸려 있다. 새 파일에서 파생만 한다.
- 기존 QX / READ_USE / SYNTH 산출물 **전부 무수정.**
  옛 공격 결과 `−0.00200` 은 **결함 fixture 의 역사적 결과로 동결**한다.
  재현하려 하지 않는다.
- production 무수정. `stat_read` 구현 금지. **새 축 추가 금지.**
- `c5` · V7 tier 경계 · baseline 무변경.

## 2. 무엇을 고쳤나

공격 상태에서 두 파라미터를 **독립**으로 만든다.

| 파라미터 | 뜻 | 장부에 남는 곳 | 오라클에서 쓰이는 곳 |
|---|---|---|---|
| `b_true` | 상대가 **벳할 때** 블러프인 비율 | `cbet`, `barrel`, `sd_weak` | 히어로 에쿼티, 리버 배럴 확률 |
| `ftb_true` | 상대가 **벳을 마주쳤을 때** 접는 빈도 | `fold_to_bet`, `f2b_*` | 내 벳에 접을 확률 |

```python
f_bluff = ftb_true + (1 − b_true)·D
f_value = ftb_true − b_true·D
#   주변 폴드확률 = b·f_bluff + (1−b)·f_value ≡ ftb_true      (항등)
#   그리고 f_value < f_bluff — 약한 손이 더 접는다는 구조는 유지
```

`D = 0.28` 을 **상수**로 둔다. 상태마다 다르면 "손 종류가 주는 정보량"이
`ftb_true` 와 교락된다. 격자에서 `f_bluff` 최대 `0.918`, `f_value` 최소
`0.110` 이라 클램프가 걸리지 않고 항등이 정확히 성립한다.

격자는 **교차(crossed)** 다 — `ftb_true ∈ {0.32, 0.44, 0.56, 0.68}` ×
`b_true ∈ {0.15, 0.35, 0.55, 0.75}` × `n_obs ∈ {6, 40}`.

**수비 상태는 옛 `qx_ev_fixture.State` 를 그대로 쓴다.** 수비 경로
(`calldown_need`)는 `ftb` 를 읽지 않으므로 결함의 영향이 없고, 그래야
옛 수비 결과와 **비트까지 대조**된다. 이것이 §3 게이트 5 다.

### 구성 확인 (regret 은 안 봤다)

```
공격 셀 9  (층 4~6 / 7~9 / 10~12 벳최적 각 3셀, 보드 6개, 핸드당 최대 2셀)
공격 상태 288   수비 상태 24
최적=bet 비율 0.500          (구성상 균형)
ftb 로 최적이 뒤집히는 (셀,b) 32/36
```

`ftb` 가 최적을 2개 미만의 `b` 수준에서만 바꾸는 셀은 후보에서 제외했다 —
공격 채널에서 읽어야 할 것이 `ftb` 이므로 그런 셀로는 읽기 능력을 못 잰다.

## 3. 게이트 — 측정 전에 전부 통과해야 한다

`--check` 로 **regret 집계 없이** 돌린다. 하나라도 실패하면 `INCONCLUSIVE`.

**G1 — `ftb_true` 와 `b_true` 의 독립성.**
공격 상태 전체에서 `|r(ftb_true, b_true)| < 1e-12`. 교차 격자이므로
설계상 0 이고, 코드에서 실제로 0 인지 확인한다.

**G2 — 장부가 `ftb` 를 올바른 방향으로 추적한다.**
잘 읽는 arm 기준 `r(ftb_true, est['ftb']) > 0.5` 이고
`r(ftb_true, fold_gap(turn)) > 0.5`.
추가로 **`r(b_true, est['ftb'])` 의 절대값이 0.2 미만**이어야 한다 —
옛 결함(`−1.000`)이 사라졌다는 직접 확인이다.

**G3 — 오라클이 `ftb` 와 같은 방향이다.**
`r(ftb_true, P(fold)) > 0.99` 이고, 항등 잔차
`max |b·f_bluff + (1−b)·f_value − ftb_true| < 1e-9`.

**G4 — 소비 지점이 arm 별로 갈린다.**
공격 상태에서 `PIPE_ONLY` 는 `plan.py:918` 과 `plan.py:1240` 둘 다
`w > 0` 비율 **100%**, `CALC_ONLY` 는 **0%**.

**G4b — 봇의 행동이 `ftb` 를 따라간다.**
`PIPE_ONLY` 의 벳 확률에 대해 `r(ftb_true, p_bet) > 0.1`,
`CALC_ONLY` 는 `|r| < 0.02`. (읽는 쪽만 반응해야 한다.)

**G5 — 수비 대조는 옛 결과를 그대로 낸다.**
같은 프로필 150 에서 수비 채널이
`CALC_ONLY 0.03323 / PIPE_ONLY 0.02796 / d = +0.00527` 을
**소수점 다섯째 자리까지** 재현.
수비 상태를 옛 `State` 그대로 쓰므로 정확히 나와야 한다.
안 나오면 내가 모르는 곳이 바뀐 것이고, 그러면 공격 결과도 못 믿는다.

**G6 — 판별력.** 최적=bet 비율이 `[0.45, 0.55]` 안, `ftb` 뒤집힘 `≥ 30/36`.

## 4. 통계량과 판정 — 결과를 보기 전에 고정

```
d_X = mean regret(CALC_ONLY, X) − mean regret(PIPE_ONLY, X)     > 0 이면 잘 읽는 쪽이 낫다
```

- 표본: `base_profiles(seeds, entries=400, n=400)[:150]`
  - **SET_A** `940001-940010` — `QX_EV_VALIDATION` · `SYNTH_CHANNEL_SPLIT` 과
    같은 집합. 과거 대조를 위해 주 집합으로 쓴다.
  - **SET_B** `950001-950010` — 재현 집합.
- 신뢰구간: **프로필 단위 클러스터 부트스트랩 4000회**, 시드
  `v7_num_battery.SEED`. (`v7_num_intervention.boot_ci` 와 같은 절차.)
- **`FLOOR = 0.002`** (팟 대비). `READ_USE_SEPARATION`·`SYNTH_CHANNEL_SPLIT`
  과 같은 값·같은 근거 — `QX_EV_VALIDATION` 의 `QX_E` 사분위 격차 0.0130 의
  약 1/6. 묶음 전체에서 문턱을 바꾸지 않는다.

`OK(d)` = `d ≥ FLOOR` 이고 95%CI 가 0 을 배제하며 **SET_A·SET_B 둘 다** 성립.
`OK₋(d)` = 같은 조건을 `d ≤ −FLOOR` 로.

```
V0  INCONCLUSIVE        G1~G6 중 하나라도 실패
V1  ATTACK_READ_HELPS   OK(d_A)
V2  ATTACK_READ_HURTS   OK₋(d_A)
V3  ATTACK_READ_NULL    그 외 (부호가 집합 간에 엇갈리거나, FLOOR 미만이거나,
                        CI 가 0 을 포함)
```

`V3` 은 "효과 없음"이 아니라 **"이 설계로는 문턱 위 효과를 못 보였다"** 로
쓴다. `d_A` 가 유의하지만 FLOOR 미만이면 그 값을 본문에 그대로 적는다 —
`READ_USE_SEPARATION` 에서 `R4` 라벨이 데이터를 잘못 요약한 일을 반복하지
않기 위해, **라벨과 수치를 분리해서 보고한다.**

### 사용자 결정 지점과의 대응

```
A  stat_read 설계 진입 가능     V1 이고 수비 대조 d_D 도 양수 (G5 로 이미 보장)
B  채널별 분리 또는 개념 재검토   V2 또는 V3
```

이 대응은 **결과를 보기 전에** 고정한다. 판단은 사용자가 한다.

## 5. 보고 항목

1. 게이트 G1~G6 전부
2. 공격 채널 단독 `d_A` (SET_A / SET_B, 평균 + 95%CI)
3. 수비 채널 `d_D` (옛 결과와의 대조)
4. 정상 fixture 에서의 합산 — 가중치(상태 수)를 명시한다.
   **옛 24:48 과 새 24:288 은 다르다.** 합산 값은 가중치에 크게 의존하므로
   상태 수 비율을 바꾸면 값이 바뀐다는 점을 본문에 적고, 채널별 값을
   1차 근거로 삼는다.
5. `n_obs` 6 / 40 분리
6. 옛 `−0.00200` 과 **나란히 놓되 비교하지 않는다** — 다른 fixture, 다른 상태다.

## 6. 금지

- `qx_ev_fixture.py` 수정 금지. 기존 산출물 수정 금지.
- 옛 공격 결과 `−0.00200` 재현 시도 금지.
- production/LIVE 변경 금지. baseline 갱신 금지.
- `stat_read` 구현 금지. 새 persona 축 추가 금지.
- 결과를 보고 `FLOOR`·판정 규칙·격자·`D` 변경 금지.
- 게이트 결함이 나오면 **결과를 보기 전에** amendment 로 남기고 고친다.
  이번에는 게이트와 본 측정을 **분리된 실행**으로 돌린다
  (`SYNTH_CHANNEL_SPLIT` Amendment C1-4 의 반성).

## 7. 산출물

- 본 문서 (측정 전 커밋)
- `tools/attack_fixture.py` — 고친 공격 상태 + 옛 수비 상태
- `tools/attack_read_measure.py` — 게이트(`--check`)와 측정
- `ATTACK_FIXTURE_FIX_RESULT.md`
- `docs/ATTACK_FIXTURE_FIX.png`
- production 무수정 / regression 지문 **전 시드 일치** / 실험 프로세스 0 /
  worktree clean / local=remote 확인
