# READ_SAMPLE_CURVE — 사전등록

기준 커밋: `3fd8d01` (`claude/attack-fixture-fix`, 동결)
브랜치: `claude/read-sample-curve`
작성 시점: **측정 수치를 보기 전.** 아래 "구성 확인"은 상태 구성 진단이다.

**이 묶음의 마지막 측정이다.** 끝나면 결과를 동결하고 A5 blockbet →
`revise_plan` context 계약으로 복귀한다.

---

## 0. 남은 질문 하나

`ATTACK_FIXTURE_FIX` 가 공격 배선을 고친 뒤, 깨끗한 대조에서

```
공격  n_obs = 40   ΔR +0.00292 / +0.00255      FLOOR 통과
공격  n_obs = 6    ΔR +0.00009 / +0.00007      사실상 0
```

였다. 두 점뿐이라 **문턱이 어디인지 모른다.** `data = min(1, conf)·min(1, n/12)`
가 `n = 12` 에서 꺾이고 `conf = min(1, n·skill/25)` 는 더 뒤에서 포화하므로
그 사이에 구조가 있을 것이다. 두 채널의 곡선을 같은 축에서 닫는다.

## 1. 범위

- **깨끗한 개입만 쓴다.** `READ_USE_SEPARATION` 의 R 축 —
  실제 필드 프로필의 **믿음만** 모집단 사전분포로 블렌드(`a = 0.20` vs `1.00`),
  `n`·`confidence` 제외로 `w` 는 비트까지 동일, `u` 는 production 값.
- **합성 arm(`make_arms`)을 쓰지 않는다.** `ATTACK_FIXTURE_FIX` Amendment D1
  이 APPLY 개념 다발 교락을 확정했다.
- `tools/read_use_fixture.py` · `tools/attack_fixture.py` · `tools/qx_ev_fixture.py`
  **전부 무수정.** 셀 정의만 빌려 `n_obs` 격자를 갈아끼운다.
- production 무수정. `stat_read` 구현 금지. 새 축 금지.
  `c5` · V7 tier 경계 · baseline 무변경.

## 2. 설계

```
n_obs 격자   8, 10, 12, 16, 24, 40      (두 채널 동일)
수비 셀      read_use_fixture.pick_cells()   20셀 × b 6수준 × n 6 = 720 상태
공격 셀      attack_fixture.pick_cells()      9셀 × ftb 4 × b 4 × n 6 = 864 상태
표본         SET_A 940001-940010, SET_B 950001-950010, 각 [:150]
```

격자에 `12` 를 반드시 넣는다 — `min(1, n/12)` 의 꺾이는 점이다.
`8`·`10` 은 그 아래, `16`·`24`·`40` 은 위다.

### 구성 확인 (regret 은 안 봤다)

```
수비 720 상태   최적=call 0.500
공격 864 상태   최적=bet  0.500
n_obs 격자 두 채널 동일
```

## 3. 게이트

**G-a 조작 점검.** 모든 `n` 에서
`slope(ftb_true → 믿는 ftb)` 와 `sd(믿는 ftb)` 의 `HIGH/LOW` 비율이
`A_HI/A_LO = 5.0` 의 ±20%(4.0~6.0) 안.
**상관은 쓰지 않는다** — 양의 아핀 변환에 불변이라 이 개입을 못 잰다
(`ATTACK_FIXTURE_FIX` Amendment D2).

**G-b 구성 균형.** 두 채널 다 최적 행동 비율이 `[0.45, 0.55]`. → 확인됨(0.500/0.500).

**G-c 게이트 기전.** 측정된 평균 `w` 가 `n` 에 대해 **단조 증가**.
아니면 `data` 식에 대한 내 이해가 틀린 것이고 곡선 해석이 무의미해진다.

하나라도 실패하면 `C0_INCONCLUSIVE`.

## 4. 통계량

```
ΔR(채널, n) = mean regret(LOW_READ) − mean regret(HIGH_READ)     > 0 이면 읽기가 이득
```

프로필 단위 클러스터 부트스트랩 4000회, 시드 `v7_num_battery.SEED`.
**`FLOOR = 0.002`** — 묶음 전체에서 동일한 값, 동일한 근거
(`QX_EV_VALIDATION` 의 `QX_E` 사분위 격차 0.0130 의 약 1/6).

`PASS(n)` = `ΔR ≥ FLOOR` 이고 CI 가 0 을 배제, **SET_A·SET_B 둘 다**.

## 5. 판정 — 결과 전에 고정

```
C0  INCONCLUSIVE        G-a 또는 G-c 실패
C1  THRESHOLD_FOUND     PASS 인 n 집합과 아닌 n 집합이 둘 다 비어 있지 않고,
                        min(PASS) > max(비PASS)   (즉 한 번만 넘는다)
C2  THRESHOLD_UNCLEAR   둘 다 비어 있지 않으나 넘나든다
C3  NO_THRESHOLD        전부 PASS 이거나 전부 비PASS
```

**문턱은 점이 아니라 격자 구간으로 보고한다** — `max(비PASS)` 와 `min(PASS)`
사이라고만 말한다. 격자 사이를 보간해 점추정을 만들지 않는다.

## 6. 부수 보고 (판정에 쓰지 않는다)

- 채널별 `Spearman(n, ΔR)` — 단조 증가 주장의 근거. 양수여야 "증가"라고 쓴다.
- 각 `n` 에서 **수비/공격 비율**. `ATTACK_FIXTURE_FIX` 가 점추정으로
  "수비 > 공격 약 2.3배"라 했던 것을 같은 축에서 다시 본다.
- 각 `n` 의 평균 `w`.

## 7. 금지

- `read_use_fixture.py` · `attack_fixture.py` · `qx_ev_fixture.py` 수정 금지.
- 기존 QX / READ_USE / SYNTH / ATTACK 산출물 수정 금지.
- production/LIVE 변경 금지. baseline 갱신 금지.
- `stat_read` 구현 금지. 새 persona 축 금지.
- 결과를 보고 `FLOOR`·`n` 격자·판정 규칙 변경 금지.
- 격자 사이 보간으로 문턱 점추정 만들기 금지.
- 게이트와 본 측정을 **분리 실행**한다.

## 8. 산출물과 종결

- 본 문서 · `tools/read_sample_curve.py` · `READ_SAMPLE_CURVE_RESULT.md`
  · `docs/READ_SAMPLE_CURVE.png`
- `CLAUDE.md` 에 **근거 지위 기록** — `PIPE_ONLY` 기반 옛 QX/SYNTH 능력 해석은
  교락으로 근거에서 내리고, `READ_USE_SEPARATION` 계열(깨끗한 R 축)을
  주 근거로 유지한다는 것을 남긴다. 기존 결과 문서는 **수정하지 않는다.**
- production 무수정 / regression 지문 전 시드 일치 / 실험 프로세스 0 /
  worktree clean / local=remote 확인
- 그 뒤 이 묶음을 **닫고** A5 로 복귀한다.
