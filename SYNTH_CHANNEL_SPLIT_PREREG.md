# SYNTH_CHANNEL_SPLIT — 사전등록

기준 커밋: `4c5fd0d` (`claude/read-use-separation`)
브랜치: `claude/synth-channel-split`
작성 시점: 분리 집계 수치를 보기 **전**.

---

## 0. 무엇을 확인하나

`QX_EV_VALIDATION` 의 합성 극단 대조가 null 이었다.

```
CALC_ONLY regret 0.06074   PIPE_ONLY regret 0.06032
차이 (CALC − PIPE) +0.00042   95%CI [−0.00095, +0.00184]
```

`READ_USE_SEPARATION` 이 이 null 의 한 후보를 **기각**했다. 읽기 정확도와
조정 강도를 2×2 로 갈랐더니 두 축이 같은 방향으로 더해졌고
(`g[HI][HI] − g[LO][LO]` = −0.0147 / −0.0176, 둘 다 유의),
R↔U 상쇄는 지지되지 않았다 (`CANCEL_NOT_SUPPORTED`).

남은 후보는 코드에 있다. `tools/qx_ev_validate.py:135`

```python
reg = [... for s in states if s.group == 'READ']
```

**수비(`D`)와 공격(`A`) 상태를 한 평균에 넣는다.** 그런데 같은 작업이
`QX_E` 의 공격 채널 상관을 fit −0.2477 / holdout −0.2403 으로 **부호가
반대**라고 측정했다. 수비에서 벌고 공격에서 잃으면 합이 0 이 된다.

**이번 판의 질문은 하나다 — 그 null 이 채널 간 상쇄인가.**

## 1. 범위

- **집계 분리만 한다.** 새 측정도, 새 상태도, 새 arm 도 만들지 않는다.
  `tools/qx_ev_fixture.py` 와 `tools/tier5_axis_validate.make_arms` 를
  **그대로** 쓴다. 두 파일을 수정하지 않는다.
- production 무수정. `stat_read` 구현 금지. `c5`·V7 tier 경계·baseline 무변경.
- 공격 채널의 **코드를 고치지 않는다.** §4 의 경로 추적은 읽기 전용이다.

## 2. 재현 관문 — 먼저 통과해야 한다

분리 집계의 전제는 "같은 계산을 다르게 묶기만 했다"는 것이다. 그래서

**G1.** 같은 프로필 집합(`base_profiles(940001..940010, entries=400, n=400)[:120]`)
에서 내 도구의 **pooled** 값이 `qx_ev_validate.synth_control` 의 출력과
**부동소수점까지 일치**해야 한다. 두 경로를 같은 실행에서 돌려 직접 비교한다.

**G2.** pooled 값이 `QX_EV_VALIDATION_RESULT.md` 의 기록
(`CALC_ONLY 0.06074`, `PIPE_ONLY 0.06032`, 차이 `+0.00042`)과
소수점 다섯째 자리에서 일치해야 한다.

하나라도 실패하면 판정은 `INCONCLUSIVE` 이고, 분리 결과를 해석하지 않는다.

## 3. 통계량과 판정 규칙

채널 `X ∈ {D, A, pooled}` 에서

```
d_X = mean regret(CALC_ONLY, X) − mean regret(PIPE_ONLY, X)     > 0 이면 PIPE 가 낫다
```

신뢰구간: 프로필 단위 부트스트랩 4000회, 시드 `v7_num_battery.SEED`
(`v7_num_intervention.boot_ci` 와 같은 절차).

**`FLOOR = 0.002`** (팟 대비). `READ_USE_SEPARATION` 과 같은 값, 같은 근거 —
`QX_EV_VALIDATION` 의 `QX_E` 사분위 격차 0.0130 의 약 1/6.

pooled 는 채널별 평균의 단순 평균이 **아니다**. 상태 수가 채널마다 다르므로
가중 평균이다. 가중치(상태 수)를 결과에 같이 적는다.

### 판정 (순서대로)

```
S0  INCONCLUSIVE                   G1 또는 G2 실패
S1  CHANNEL_CANCELLATION_CONFIRMED d_D 와 d_A 의 부호가 반대이고,
                                   둘 다 CI 가 0 을 배제하며,
                                   최소 하나가 |d| >= FLOOR 이고,
                                   |d_pooled| < min(|d_D|, |d_A|)
S2  CHANNEL_CANCELLATION_WEAK      부호 반대 + 둘 다 CI 가 0 배제,
                                   그러나 둘 다 |d| < FLOOR
S3  NO_CHANNEL_CANCELLATION        위 어느 것도 아님 (같은 부호이거나
                                   한쪽 이상이 CI 에 0 을 포함)
```

`S3` 이면 null 의 원인은 아직 미상이고, 그대로 미상이라고 쓴다.
**사후에 새 설명을 만들어 붙이지 않는다.**

## 4. 상쇄가 지지되면 — 공격 채널 경로 추적 (읽기 전용)

`S1` 또는 `S2` 일 때만 진행한다. 목표는 "`decide_aggression` 이 상대 정보를
**실제로 어디서 어떻게** 소비하는가"를 코드에서 확정하는 것이다.

- `plan.decide_aggression` 전수 독해. `opp_est` / `read_opponent` 결과가
  들어가는 지점을 **줄 번호로** 전부 나열한다.
- 각 지점이 어떤 `plan` 라벨에서만 도달 가능한지 분기 조건을 적는다.
  (`QX_EV_VALIDATION` 에서 `giveup`/`showdown` 은 `cbet_freq` 경로로 빠져
  `fold_equity` 블록에 도달하지 못한다는 것이 이미 확인됐다.)
- **계측으로 확인한다.** `PS.sk` / `PS.read_opponent` 를 monkeypatch 해
  합성 arm 두 개가 공격 상태에서 실제로 읽는 축과 호출 횟수를 센다.
  코드 독해만으로 결론내지 않는다 (CLAUDE.md 작업원칙 4).
- 부호가 왜 반대인지에 대한 **가설은 적되, 이번 판에서 검정하지 않는다.**
  검정하려면 공격 채널 fixture 의 타당성부터 다시 세워야 하고, 그건
  별도 사전등록이다.

## 5. 금지

- `stat_read` 구현·설계 금지.
- `qx_ev_fixture.py`·`tier5_axis_validate.py` 수정 금지 (재현이 거기 걸려 있다).
- production/LIVE 변경 금지. baseline/reference 갱신 금지.
- 공격 채널 **수정** 금지. 이번 판은 관찰만 한다.
- 결과를 보고 `FLOOR`·판정 규칙 변경 금지.
- 분리 결과가 `S3` 일 때 새 설명을 지어내 붙이는 것 금지.

## 6. 산출물

- 본 문서 (측정 전 커밋)
- `tools/synth_channel_split.py`
- `SYNTH_CHANNEL_SPLIT_RESULT.md`
- `S1`/`S2` 일 때만: `docs/AGGR_INFO_PATH.png` 와 경로 표
- 마지막에 production 무수정 / regression 지문 일치 / 실험 프로세스 0 /
  worktree clean / local=remote 확인
